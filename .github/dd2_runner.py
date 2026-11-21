"""Developer Direct2: two single-use Gemini Developer API SSE POSTs, TEST only.
GCS is WIF owner-only create-once, Developer model calls use only existing Actions secret.
Never print/store any part/length/hash of the Gemini API key.
"""
from __future__ import annotations
import base64,collections,datetime,hashlib,json,os,pathlib,subprocess,sys,tempfile,time,urllib.parse,urllib.request,urllib.error,unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent))
import legacy_gcs as gcs
from dd2_sse import SSEAssembler,SafetyStop as SSEError
BASE=pathlib.Path(__file__).resolve().parent
CAMP='GEMINI4_HYDROGEN_DEVELOPER_DIRECT2_20261122'
PREFIX='gemini4_hydrogen_developer_direct2_20261122/'
MODEL='gemini-4-hydrogen'
API='https://generativelanguage.googleapis.com/v1beta/models/gemini-4-hydrogen:streamGenerateContent?alt=sse'
BUCKET='ko-lao-gemini35-tuning-460077888071'
CAP={'POST':50,'GET':350,'LIST':10,'POST_BYTES':4*1024*1024}
MODEL_CAP=2;USD_CAP=1.0;MAX_OUTPUT=6144
PUBLIC_SHA='1772c2fd3704c184470359c39832ec47cabe13528f7860a414b25d7405901792'
PINS_SHA='a0ddc9924ccf7628fb609410726071a8106dccc4e488840ff47f4cb7d8cc5af7'
BASE_BOOT_SHA='e044aa4f2d0b0623e30d02607b9c3d4b26d22ed17255f0c0bcd3e8ed87d29563'
BASE_BOOT_GEN='1795301886852870'
KEY_GEN='1795301886515458'
KEY_SHA='7e36abe6ca0cfc902fffb649d6f30caf22337b94199177ef98ae42248d2c05e6'
PRIVATE_CMS_SHA='eb6faacc596dca340d379354961da8b4c0828ddc7870a31ec31b09cc180b6979'
PRIVATE_SHA='d15738c7538576f646388c098b1363c027df5ad38c9ad212596fb82510cafded'
BOOT_RECEIPT_SHA=None # checked against exact GCS pinned generation and immutable public model discovery receipt
APPROVAL={'max_new_generate_calls':2,'first':1,'back':1,'usd_management_cap':1.0,'other_models':0,'vertex_generation_calls':0}
COST_STANDARD_INPUT=1.50;COST_STANDARD_OUTPUT=7.50
COST_GUARD_INPUT=3.30;COST_GUARD_OUTPUT=16.50  # upper than official Standard, including thinking
sha=lambda b:hashlib.sha256(b).hexdigest()
canon=lambda d:(json.dumps(d,ensure_ascii=False,sort_keys=True,separators=(',',':'))+'\n').encode()
class SafetyStop(gcs.SafetyStop):pass

def need(cond,why):
 if not cond:raise SafetyStop(why)
gcs.PREFIX=PREFIX
class Budget(gcs.Budget):
 LIMITS=CAP
 def __init__(self):
  super().__init__();self.per={'FIRST':0,'BACK':0};self.guarded_usd=0.0;self.cost_usd=0.0;self.valid=0;self.invalid=0
 def snapshot(self):
  return {'POST':self.post,'GET':self.get,'LIST':self.list,'POST_BYTES':self.post_bytes,'model_attempts':self.model_attempts,'actions':self.per.copy(),'valid':self.valid,'invalid':self.invalid,'guarded_usd':round(self.guarded_usd,12),'estimated_cost_usd':round(self.cost_usd,12)}
 def hydrate(self,d):
  for k,v in [('POST','post'),('GET','get'),('LIST','list'),('POST_BYTES','post_bytes')]:setattr(self,v,getattr(self,v)+int(d.get(k,0)))
  self.model_attempts+=int(d.get('model_attempts',0));self.per.update(d.get('actions',{}));self.valid+=int(d.get('valid',0));self.invalid+=int(d.get('invalid',0));self.guarded_usd+=float(d.get('guarded_usd',0));self.cost_usd+=float(d.get('estimated_cost_usd',0));self.check()
 def check(self):
  need(not self.halted and not self.closed,'BUDGET_HALTED');need(all(getattr(self,{'POST':'post','GET':'get','LIST':'list','POST_BYTES':'post_bytes'}[k])<=CAP[k] for k in CAP),'GCS_CAP')
  need(self.model_attempts<=2 and self.per['FIRST']<=1 and self.per['BACK']<=1 and self.guarded_usd<=USD_CAP+1e-9,'MODEL2_OR_USD1_CAP')
 def reserve_model_slot(self,action,wirelen):
  self.check();need(action in ('FIRST','BACK'),'ACTION_BAD')
  need(self.model_attempts<2 and self.per[action]==0,'ALREADY_ATTEMPTED_NO_REPOST')
  need(self.post+5<=50 and self.get+15<=350,'STORAGE_AFTER_MODEL_SEND_INSUFFICIENT')
  val=(wirelen*COST_GUARD_INPUT+MAX_OUTPUT*COST_GUARD_OUTPUT)/1_000_000*1.3
  need(self.guarded_usd+val<=USD_CAP,'USD1_PRE_SEND_RESERVATION')
  return val
 def transmitted(self,action,reserved):
  self.model_attempts+=1;self.per[action]+=1;self.guarded_usd+=reserved;self.check()
 def usage(self,j,reserved):
  try:
   need(isinstance(j,dict) and ('totalTokenCount' in j or 'promptTokenCount' in j),'NO_USAGE')
   p=int(j.get('promptTokenCount') or 0);o=int(j.get('candidatesTokenCount') or 0);t=int(j.get('thoughtsTokenCount') or 0);total=int(j.get('totalTokenCount') or 0);cache=int(j.get('cachedContentTokenCount') or 0)
   need(min(p,o,t,total,cache)>=0 and (p>0 or total>0),'BAD_USAGE')
  except Exception:
   return {'usage_verified':False,'billable':'UNKNOWN_RESERVATION_HELD','reserved_usd':reserved}
  bill=max(o+t,total-p,0);actual=(p*COST_STANDARD_INPUT+bill*COST_STANDARD_OUTPUT)/1e6
  conserv=(p*COST_GUARD_INPUT+bill*COST_GUARD_OUTPUT)/1e6*1.3
  self.cost_usd+=actual;self.guarded_usd+=conserv-reserved;self.check()
  return {'usage_verified':True,'prompt_tokens':p,'output_tokens':o,'thinking_tokens':t,'total_tokens':total,'cache_tokens':cache,'billable_output_est':bill,'estimated_standard_usd':round(actual,12),'conservative_guard_usd':round(conserv,12)}
class Net:
 def __init__(self,gcloud,paid=False):self.gcloud=gcloud;self.paid=paid;self.model_send_count=0
 def send(self,method,url,data=None,ctype=None):
  u=urllib.parse.urlsplit(url)
  need(u.scheme=='https' and u.hostname=='storage.googleapis.com','GCS_ONLY_WIF')
  if method=='POST':
   qs=urllib.parse.parse_qs(u.query)
   need(u.path.startswith('/upload/storage/v1/b/'+BUCKET+'/o') and qs.get('ifGenerationMatch')==['0'] and qs.get('uploadType')==['media'] and qs.get('name',[''])[0].startswith(PREFIX),'GCS_WRITE_PREFIX_OR_GENERATION_DENIED')
  else:need(method=='GET' and u.path.startswith('/storage/v1/b/'+BUCKET+'/o'),'GCS_GET_ONLY_DENIED')
  headers={'Authorization':'Bearer '+self.gcloud,'Content-Type':ctype or 'application/json','Accept':'application/json'}
  req=urllib.request.Request(url,data=data,headers=headers,method=method)
  try:
   with urllib.request.urlopen(req,timeout=55) as r:return r.status,r.read(2_000_000)
  except urllib.error.HTTPError as e:return e.code,e.read(2_000_000)
  except Exception:raise gcs.TransportUnknown('GCS_ACK_UNKNOWN_NO_RETRY') from None
 def stream(self,url,wire):
  need(self.paid,'MODEL_CALL_IN_FREE_MODE_DENIED')
  need(url==API,'MODEL_HOST_URI_OR_QUERY_NOT_APPROVED')
  need(os.getenv('GITHUB_REPOSITORY')=='martin830000-spec/laos-translator' and os.getenv('GITHUB_REF')=='refs/heads/research/gemini35-tuning-test' and os.getenv('GITHUB_RUN_ATTEMPT')=='1','EXACT_TEST_ONLY')
  need('/.github/workflows/gemini35-tuning-test.yml@' in os.getenv('GITHUB_WORKFLOW_REF',''),'WORKFLOW_SOURCE_MISMATCH')
  need(bool(os.environ.get('GEMINI_API_KEY')),'EXISTING_SECRET_MISSING')
  # API key is used ONLY as a header value and is never logged, serialized, printed or hashed.
  request=urllib.request.Request(url,data=wire,method='POST',headers={'Content-Type':'application/json','Accept':'text/event-stream','x-goog-api-key':os.environ['GEMINI_API_KEY']})
  self.model_send_count+=1;start=time.perf_counter();header_ms=None;first_byte_ms=None;raw=bytearray();safe_headers={};parser=None
  try:
   with urllib.request.urlopen(request,timeout=110) as response:
    header_ms=(time.perf_counter()-start)*1000
    safe_headers={k:v for k,v in response.headers.items() if k.lower() in ('content-type','retry-after','x-request-id','x-goog-request-id')}
    parser=SSEAssembler(start=start)
    while True:
     chunk=response.read1(4096)
     if not chunk:break
     if first_byte_ms is None:first_byte_ms=(time.perf_counter()-start)*1000
     raw.extend(chunk);need(len(raw)<=1_000_000,'STREAM_TOO_LONG')
     parser.feed(chunk,time.perf_counter())
    parser.finish(time.perf_counter());finish_ms=(time.perf_counter()-start)*1000
    return {'http':response.status,'headers':safe_headers,'raw':bytes(raw),'header_ms':header_ms,'first_byte_ms':first_byte_ms,'total_ms':finish_ms,'assembled':parser.result(),'unknown':False}
  except urllib.error.HTTPError as e:
   finish_ms=(time.perf_counter()-start)*1000
   safe_headers={k:v for k,v in e.headers.items() if k.lower() in ('content-type','retry-after','x-request-id','x-goog-request-id')}
   return {'http':e.code,'headers':safe_headers,'raw':e.read(200_000),'header_ms':finish_ms,'first_byte_ms':None,'total_ms':finish_ms,'assembled':None,'unknown':False}
  except Exception as e:
   # The HTTP request might have been transmitted; never retry even after timeout/ACK loss.
   return {'http':None,'headers':safe_headers,'raw':bytes(raw),'header_ms':header_ms,'first_byte_ms':first_byte_ms,'total_ms':(time.perf_counter()-start)*1000,'assembled':None,'unknown':True,'unknown_type':type(e).__name__}

def pub():
 raw=(BASE/'dd2_public_freeze.json').read_bytes();need(sha(raw)==PUBLIC_SHA,'PUBLIC_INPUT_SHA_DRIFT');x=json.loads(raw)
 need(x['campaign_id']==CAMP and x['scope']=={'FIRST':1,'BACK':1,'total':2,'usd_max':1},'CAMPAIGN_APPROVAL_DRIFT')
 need(x['sse_api']==API and x['generate_cfg']=={'maxOutputTokens':6144,'thinkingConfig':{'thinkingLevel':'LOW'}},'DEV_API_CONFIG_DRIFT')
 need(sha((BASE/'dd2_pins29.json').read_bytes())==PINS_SHA and len(json.loads((BASE/'dd2_pins29.json').read_bytes()))==29,'PINS29_SHA_DRIFT')
 return x

def protected29(store):
 rows=json.loads((BASE/'dd2_pins29.json').read_bytes());need(len(rows)==len({x['object'] for x in rows})==29,'PIN29_MISSING')
 out=[]
 for x in rows:
  m,body=store.read_pinned(x['object'],x['generation']);need(len(body)==x['bytes'] and sha(body)==x['sha256'],'PROTECTED_OLD_PIN_DRIFT')
  d=json.loads(body);need(d.get('enabled') is False and d.get('max_new')==0 and d.get('next_new_authorization')==0,'OLD_LOCK_OPENED')
  out.append({'object':x['object'],'generation':str(m['generation']),'bytes':len(body),'sha256':sha(body)})
 return out

def bootpub():
 d=json.loads((BASE/'dd2_bootstrap_public.json').read_bytes())
 need(d['status']=='BOOTSTRAP_FREE_READY' and d['secret_present'] and d['discovery']['model_discovered'] and d['old_pins29_pass'] and d['model_generation_calls']==0,'BOOTSTRAP_NOT_PASS')
 need(d['boot_state']['generation']==BASE_BOOT_GEN and d['boot_state']['sha256']==BASE_BOOT_SHA,'BOOT_STATE_RECEIPT_DRIFT')
 need(d['new_key']['generation']==KEY_GEN and d['new_key']['sha256']==KEY_SHA,'INPUT_KEY_RECEIPT_DRIFT')
 need(d['gcs']=={'POST':4,'GET':66,'LIST':1,'POST_BYTES':5711},'BOOTSTRAP_GCS_COUNTS_DRIFT')
 return d

def get_private(store):
 p=pub();meta,key=store.read_pinned(PREFIX+'_control/INPUT_PRIVATE_RSA_3072.pem',KEY_GEN)
 need(sha(key)==KEY_SHA,'NEW_INPUT_KEY_DRIFT')
 enc=base64.b64decode((BASE/'dd2_input.cms.b64').read_text().strip(),validate=True)
 need(sha(enc)==PRIVATE_CMS_SHA,'NEW_CIPHERTEXT_DRIFT')
 with tempfile.TemporaryDirectory() as td:
  root=pathlib.Path(td);(root/'key.pem').write_bytes(key);(root/'source.p7m').write_bytes(enc)
  z=subprocess.run(['openssl','cms','-decrypt','-inform','DER','-in',str(root/'source.p7m'),'-recip',str(BASE/'dd2_input_public.crt'),'-inkey',str(root/'key.pem'),'-out',str(root/'out.json')],capture_output=True,timeout=40)
  need(z.returncode==0,'PRIVATE_FREEZE_DECRYPT_FAILED');raw=(root/'out.json').read_bytes()
 need(sha(raw)==PRIVATE_SHA==p['private_sha256'],'PRIVATE_FREEZE_HASH_CHANGED')
 x=json.loads(raw)
 need(x['campaign_id']==CAMP and x['model']==MODEL and x['thinkingLevel']=='LOW' and x['maxOutputTokens']==6144 and x['source_id']=='newK:0013','FROZEN_MODEL_OR_SOURCE_DRIFT')
 need(sha(x['source_text'].encode())==x['source_sha256']==p['source_sha256'],'FROZEN_SOURCE_DRIFT')
 for key in ('first','back'):
  need(sha(x['prompt_'+key+'_text'].encode())==x['prompt_'+key+'_sha256']==p['prompt_'+key+'_sha256'],'FROZEN_PROMPT_DRIFT')
 return x

def request_body(inp,prompt):
 need(inp and prompt and isinstance(inp,str) and isinstance(prompt,str),'BLANK_REQUEST_FIELDS')
 cfg={'maxOutputTokens':6144,'thinkingConfig':{'thinkingLevel':'LOW'}}
 body={'contents':[{'role':'user','parts':[{'text':inp}]}],'systemInstruction':{'parts':[{'text':prompt}]},'generationConfig':cfg}
 wire=canon(body);j=json.loads(wire)
 need(set(j)=={'contents','systemInstruction','generationConfig'} and set(j['generationConfig'])=={'maxOutputTokens','thinkingConfig'},'WIRE_REQUEST_KEYS_INVALID')
 need(not (set(j['generationConfig'])&{'candidateCount','thinkingBudget','temperature','topP','topK'}),'UNSUPPORTED_GEMINI_PARAMS')
 need(j['generationConfig']==cfg and j['contents'][0]['parts'][0]['text']==inp and j['systemInstruction']['parts'][0]['text']==prompt,'WIRE_REQUEST_MUTATED')
 return API,wire

def crypto_archive(d):
 dest=os.getenv('DD2_OWNER_CMS');need(bool(dest) and os.path.isabs(dest),'OWNER_CMS_DESTINATION_MISSING')
 with tempfile.TemporaryDirectory() as td:
  root=pathlib.Path(td);(root/'plain.json').write_bytes(canon(d))
  z=subprocess.run(['openssl','cms','-encrypt','-aes-256-gcm','-binary','-in',str(root/'plain.json'),'-out',str(root/'encrypted.p7m'),'-outform','DER',str(BASE/'dd2_owner_output_public.crt')],capture_output=True,timeout=40)
  need(z.returncode==0,'OWNER_CMS_ENCRYPTION_FAIL');body=(root/'encrypted.p7m').read_bytes()
  pathlib.Path(dest).write_bytes(body);pathlib.Path(dest).chmod(0o600)
 return {'bytes':len(body),'sha256':sha(body)}

def state_save(store,b,name,state):
 # Include own create-only POST and two generation-pinned GET readbacks in cum counters.
 data={**state,'cumulative':b.snapshot()};data['cumulative']['POST']+=1;data['cumulative']['GET']+=2
 basebytes=data['cumulative']['POST_BYTES']
 for _ in range(16):data['cumulative']['POST_BYTES']=basebytes+len(canon(data))
 need(data['cumulative']['POST_BYTES']==basebytes+len(canon(data)),'STATE_COUNTER_FIXEDPOINT_FAILED')
 receipt=store.create('_control/'+name+'.json',data)
 now=b.snapshot();need(all(now[k]==data['cumulative'][k] for k in ('POST','GET','LIST','POST_BYTES')),'STATE_COUNTER_INCONSISTENT')
 return receipt,data

def run(stage):
 need(stage in ('FREEQA','PILOT'),'UNSUPPORTED_STAGE')
 need(os.getenv('DD2_STAGE')==stage and os.getenv('ENABLE_GENERATION')==('false' if stage=='FREEQA' else 'true') and os.getenv('ENABLE_TUNING')=='false','STAGE_ENV_DENIED')
 need(os.getenv('GITHUB_REPOSITORY')=='martin830000-spec/laos-translator' and os.getenv('GITHUB_REF')=='refs/heads/research/gemini35-tuning-test' and os.getenv('GITHUB_RUN_ATTEMPT')=='1','GITHUB_IDENTITY_DENIED')
 need('/.github/workflows/gemini35-tuning-test.yml@' in os.getenv('GITHUB_WORKFLOW_REF',''),'WORKFLOW_WIF_PATH_DENIED')
 need(bool(os.environ.get('GEMINI_API_KEY')) if stage=='PILOT' else True,'SECRET_MISSING_PRE_SEND')
 boot=bootpub();pubx=pub();b=Budget();token=subprocess.check_output(['gcloud','auth','print-access-token'],stderr=subprocess.DEVNULL,text=True,timeout=35).strip();need(len(token)>30,'WIF_GCS_ABSENT')
 net=Net(token,paid=stage=='PILOT');store=gcs.Store(net,b,'actual')
 out={'schema':'DD2_OWNER_RUN_V1','campaign_id':CAMP,'stage':stage,'status':'STARTED','first_failure':None,'secondary_errors':[],'actual':[],'new_lock':None,'source_private_sha256':PRIVATE_SHA,'runner_sha256':os.getenv('DD2_RUNNER_SHA256',''),'protection29_verified':False,'GITHUB_RUN_ID':os.getenv('GITHUB_RUN_ID'),'model_exclusively_developer_api':True,'api_key_ever_recorded':False,'baseline_source':pubx.get('stream24_zip_sha256'),'budget':None}
 try:
  current=set(store.inventory(PREFIX))
  expected={PREFIX+'_freeqa/SMOKE.json',PREFIX+'_control/INPUT_PRIVATE_RSA_3072.pem',PREFIX+'_control/BOOTSTRAP_STATE.json'}
  if stage=='PILOT':expected|={PREFIX+'actual/_control/FREEQA_STATE.json',PREFIX+'freeqa/SYNTHETIC_FIRST.json',PREFIX+'freeqa/SYNTHETIC_BACK.json'}
  need(current==expected,'NEW_PREFIX_NOT_EXPECTED_OR_RETRY')
  priorname=PREFIX+('_control/BOOTSTRAP_STATE.json' if stage=='FREEQA' else 'actual/_control/FREEQA_STATE.json')
  meta,raw=store.read_pinned(priorname,BASE_BOOT_GEN if stage=='FREEQA' else None)
  if stage=='FREEQA':
   need(sha(raw)==BASE_BOOT_SHA,'BOOT_OBJECT_DRIFT')
   prior=boot['gcs'].copy();prior.update({'model_attempts':0,'actions':{'FIRST':0,'BACK':0},'valid':0,'invalid':0,'guarded_usd':0.,'estimated_cost_usd':0.})
  else:
   prev=json.loads(raw);need(prev['stage']=='FREEQA_PASS' and prev['model_calls']==0 and prev['campaign_id']==CAMP,'FREEQA_NOT_VERIFIED');prior=prev['cumulative']
  b.hydrate(prior)
  x=get_private(store)
  if stage=='FREEQA':
   protected29(store)
   for action,inp,prompt in [('FIRST',x['source_text'],x['prompt_first_text']),('BACK','DD2_SYNTHETIC_FIRST_ONLY',x['prompt_back_text'])]:
    uri,wire=request_body(inp,prompt)
    need(uri==API and len(wire)>100,'SSE_REQUEST_FORMAT_INVALID')
   synth=gcs.Store(net,b,'freeqa');s1=synth.create('SYNTHETIC_FIRST.json',{'synthetic':True,'output':'SYNTHETIC_FIRST','model_calls':0});s2=synth.create('SYNTHETIC_BACK.json',{'synthetic':True,'input_sha256':sha(b'SYNTHETIC_FIRST'),'output':'SYNTHETIC_BACK','model_calls':0})
   rec,locked=state_save(store,b,'FREEQA_STATE',{'schema':'DD2_FREEQA_STATE','campaign_id':CAMP,'stage':'FREEQA_PASS','model_calls':0,'source_sha256':x['source_sha256'],'prompt_first_sha256':x['prompt_first_sha256'],'prompt_back_sha256':x['prompt_back_sha256'],'protected29':True,'synthetic_receipts':[s1,s2],'enabled':False,'max_new':0,'next_new_authorization':0})
   out.update({'status':'FREEQA_PASS_0_PAID','freeqa_receipt':rec,'budget':locked['cumulative'],'protection29_verified':True});return out
  # PILOT starts only after the frozen FREEQA receipt and exact prefix contents are checked.
  claim=store.create('_control/PILOT_CLAIM.json',{'schema':'DD2_SINGLE_USE_CLAIM','campaign_id':CAMP,'max_new_model_calls':2,'source_sha256':x['source_sha256'],'actions':['FIRST','BACK'],'no_retry':True,'developer_api_only':True,'freeqa_stage_receipt_generation':str(meta['generation'])})
  for slotid,action in [('SLOT001','FIRST'),('SLOT002','BACK')]:
   if action=='FIRST':inp=x['source_text'];prompt=x['prompt_first_text'];parent=None
   else:
    parent=out['actual'][0]['result'] if out['actual'] else None
    need(parent and parent['usable'] and parent['action']=='FIRST','PARENT_FIRST_NOT_VALID_OR_PRESENT')
    pmeta,pbody=store.read('slots/SLOT001/RESULT.json');verified=json.loads(pbody)
    need(verified['translation_sha256']==parent['translation_sha256'] and verified['usable'],'READBACK_PARENT_MISMATCH')
    inp=verified['translation_text'];prompt=x['prompt_back_text'];need(sha(inp.encode())==parent['translation_sha256'],'BACK_NOT_EXACT_ACTUAL_FIRST')
   prompt_hash=x['prompt_'+action.lower()+'_sha256']
   need(sha(prompt.encode())==prompt_hash,'STORED_PROMPT_DIFFERS')
   u,wire=request_body(inp,prompt)
   reserved=b.reserve_model_slot(action,len(wire))
   intent={'schema':'DD2_SEND_INTENT','campaign_id':CAMP,'slot_id':slotid,'action':action,'model':MODEL,'developer_api_only':True,'prompt_sha256':prompt_hash,'source_sha256':x['source_sha256'],'input_sha256':sha(inp.encode()),'parent_first_slot_id':None if action=='FIRST' else 'SLOT001','request_sha256':sha(wire),'reserved_usd':reserved,'max_output':MAX_OUTPUT}
   ir=store.create('slots/'+slotid+'/SEND_INTENT.json',intent)
   b.transmitted(action,reserved)
   response=net.stream(u,wire)
   assembled=response['assembled'] or {};ctype=response['headers'].get('Content-Type',response['headers'].get('content-type',''))
   valid=bool(response['http']==200 and 'text/event-stream' in ctype.lower() and not response['unknown'] and assembled.get('finishReason')=='STOP' and assembled.get('text') and assembled.get('modelVersion','').startswith(MODEL) and assembled.get('first_text_ms') is not None)
   raw_doc={'schema':'DD2_RAW_RESPONSE','slot_id':slotid,'http':response['http'],'unknown':response['unknown'],'headers_safe':response['headers'],'request_sha256':sha(wire),'response_sha256':sha(response['raw']),'body_b64':base64.b64encode(response['raw']).decode(),'header_ms':response['header_ms'],'first_byte_ms':response['first_byte_ms'],'total_ms':response['total_ms']}
   raw_receipt=store.create('slots/'+slotid+'/RAW_RESPONSE.json',raw_doc)
   tr=assembled.get('text') if valid else ''
   result={'schema':'DD2_RESULT','slot_id':slotid,'campaign_id':CAMP,'action':action,'source_id':'newK:0013','model':MODEL,'developer_api_only':True,'parent_first_slot_id':intent['parent_first_slot_id'],'source_sha256':x['source_sha256'],'prompt_sha256':prompt_hash,'input_sha256':sha(inp.encode()),'request_sha256':sha(wire),'response_sha256':sha(response['raw']),'http':response['http'],'unknown':response['unknown'],'finishReason':assembled.get('finishReason'),'modelVersion':assembled.get('modelVersion'),'translation_text':tr,'translation_sha256':sha(tr.encode()),'usable':valid,'header_ms':response['header_ms'],'first_byte_ms':response['first_byte_ms'],'first_sse_ms':assembled.get('first_sse_ms'),'first_text_ms':assembled.get('first_text_ms'),'elapsed_ms':response['total_ms'],'sse_events':assembled.get('events') or [],'sse_event_count':assembled.get('events_count'),'thought_parts_skipped':assembled.get('thought_parts_skipped'),'usageMetadata':assembled.get('usageMetadata') or {},'billable':None,'invalid_reason':None if valid else ('TRANSPORT_UNKNOWN' if response['unknown'] else 'HTTP_'+str(response['http']) if response['http']!=200 else 'INCOMPLETE_SSE_OR_MODEL_VERSION')}
   if response['http']==200 and not response['unknown']:result['billable']=b.usage(result['usageMetadata'],reserved)
   else:result['billable']={'usage_verified':False,'billable':'UNKNOWN_RESERVATION_HELD','reserved_usd':reserved}
   if valid:b.valid+=1
   else:b.invalid+=1
   result_receipt=store.create('slots/'+slotid+'/RESULT.json',result)
   out['actual'].append({'result':result,'intent_receipt':ir,'raw_receipt':raw_receipt,'result_receipt':result_receipt,'request_body':json.loads(wire),'raw_sse_b64':base64.b64encode(response['raw']).decode(),'safe_headers':response['headers']})
   if not valid:
    out['first_failure']=result['invalid_reason'];break
  pins=protected29(store);out['protection29_verified']=len(pins)==29
  closed={'schema':'DD2_FINAL_STATE','campaign_id':CAMP,'stage':'PILOT_COMPLETE' if b.valid==2 else 'PILOT_PARTIAL_OR_STOP','terminal':True,'enabled':False,'max_new':0,'next_new_authorization':0,'model_calls':b.model_attempts,'valid':b.valid,'invalid':b.invalid,'unused_locked':2-b.model_attempts,'model_per':{'gemini-4-hydrogen':b.model_attempts},'first_failure':out['first_failure'],'protected29_unchanged':True,'code_sha256':os.getenv('DD2_RUNNER_SHA256','')}
  rec,state=state_save(store,b,'FINAL_STATE',closed)
  out.update({'new_lock':rec,'budget':state['cumulative'],'status':'CLOSED_LOCKED_2_VALID' if b.valid==2 else 'STOPPED_CLOSED_LOCKED'});return out
 except Exception as e:
  if out['first_failure'] is None:out['first_failure']=str(e) if isinstance(e,SafetyStop) else 'UNEXPECTED_'+type(e).__name__
  out.update({'status':'STOPPED_UNVERIFIED_LOCK' if not out.get('new_lock') else 'STOPPED_CLOSED_LOCKED','budget':b.snapshot()});return out
 finally:
  if stage=='PILOT':
   try:out['owner_artifact_receipt']=crypto_archive(out)
   except Exception as e:print('DD2_OWNER_ARTIFACT_CMS_ERROR '+type(e).__name__,flush=True)
  print('DD2_PUBLIC_STAGE_STATUS '+json.dumps({'stage':stage,'status':out.get('status'),'first_failure':out.get('first_failure'),'attempts':b.model_attempts,'valid':b.valid,'invalid':b.invalid,'actions':b.per,'protected29_verified':out.get('protection29_verified'),'new_lock':out.get('new_lock'),'gcs':b.snapshot(),'service_changed':False,'secret_printed':False,'no_retry':True},sort_keys=True),flush=True)

class UnitTests(unittest.TestCase):
 def test_pins(self):self.assertEqual(len(json.loads((BASE/'dd2_pins29.json').read_text())),29)
 def test_public(self):self.assertEqual(pub()['model'],MODEL)
 def test_model_only_dev(self):self.assertEqual(API,'https://generativelanguage.googleapis.com/v1beta/models/gemini-4-hydrogen:streamGenerateContent?alt=sse')
 def test_request_exact(self):
  u,w=request_body('synthetic','synthetic prompt');j=json.loads(w);self.assertEqual(j['generationConfig'],{'maxOutputTokens':6144,'thinkingConfig':{'thinkingLevel':'LOW'}});self.assertEqual(u,API)
 def test_key_not_in_query(self):self.assertEqual(urllib.parse.urlsplit(API).query,'alt=sse')
 def test_free_model_denied(self):
  n=Net('fake',False)
  with self.assertRaises(SafetyStop):n.stream(API,b'{}')
  self.assertEqual(n.model_send_count,0)
 def test_bad_endpoint_denied(self):
  n=Net('fake',True)
  with self.assertRaises(SafetyStop):n.stream('https://aiplatform.us.rep.googleapis.com/v1beta1/models/gemini-4-hydrogen:streamGenerateContent?alt=sse',b'{}')
  self.assertEqual(n.model_send_count,0)
 def test_budget_two_only(self):
  b=Budget();x=b.reserve_model_slot('FIRST',200);b.transmitted('FIRST',x)
  with self.assertRaises(SafetyStop):b.reserve_model_slot('FIRST',200)
  y=b.reserve_model_slot('BACK',200);b.transmitted('BACK',y)
  with self.assertRaises(SafetyStop):b.reserve_model_slot('BACK',200)
 def test_conservative_max_cost(self):
  b=Budget();x=b.reserve_model_slot('FIRST',10000);b.transmitted('FIRST',x);y=b.reserve_model_slot('BACK',10000);b.transmitted('BACK',y);self.assertLess(b.guarded_usd,1)
 def test_usage_thinking(self):
  b=Budget();v=b.reserve_model_slot('FIRST',1000);b.transmitted('FIRST',v);j=b.usage({'promptTokenCount':200,'candidatesTokenCount':80,'thoughtsTokenCount':700,'totalTokenCount':980},v);self.assertEqual(j['billable_output_est'],780)
 def test_unknown_usage_guard_held(self):
  b=Budget();v=b.reserve_model_slot('FIRST',1000);b.transmitted('FIRST',v);j=b.usage({},v);self.assertFalse(j['usage_verified']);self.assertEqual(b.guarded_usd,v)
 def test_old_gcs_fake_create_only(self):
  b=Budget();s=gcs.Store(gcs.FakeTransport(),b,'test');s.create('x.json',{'dummy':True})
  with self.assertRaises(gcs.SafetyStop):s.create('x.json',{'changed':True})
 def test_old_gcs_ack_no_retry(self):
  b=Budget();t=gcs.FakeTransport();s=gcs.Store(t,b,'test');t.inject_unknown=True
  with self.assertRaises(gcs.TransportUnknown):s.create('x.json',{'dummy':True})
  with self.assertRaises(gcs.SafetyStop):s.create('x.json',{'again':True})
  self.assertEqual(t.posts,1)
 def test_no_plaintext_in_public_code(self):
  for name in ('dd2_runner.py','dd2_sse.py','dd2_bootstrap.py'):
   txt=(BASE/name).read_text();self.assertTrue(txt.isascii());self.assertNotIn('BEGIN'+' PRIVATE KEY',txt)
 def test_stage_block_model_retries(self):self.assertNotIn('retry',Net.stream.__code__.co_names)
 def test_safe_schema_composition(self):
  u,w=request_body('orig','prompt');d=json.loads(w);self.assertEqual(len(d['contents']),1);self.assertNotIn('apiKey',str(d))
 def test_output_public_cert(self):self.assertTrue((BASE/'dd2_owner_output_public.crt').read_text().startswith('-----BEGIN CERTIFICATE-----'))
if __name__=='__main__':
 arg=sys.argv[1] if len(sys.argv)>1 else 'TEST'
 if arg=='TEST':
  res=unittest.TextTestRunner(verbosity=0).run(unittest.defaultTestLoader.loadTestsFromTestCase(UnitTests));print('DD2_RUNNER_GUARDS',res.testsRun,'PASS' if res.wasSuccessful() else 'FAIL','optimized',not __debug__,flush=True);raise SystemExit(0 if res.wasSuccessful() else 1)
 if arg not in ('FREEQA','PILOT'):raise SystemExit('usage: TEST|FREEQA|PILOT')
 done=run(arg)
 required={'FREEQA':'FREEQA_PASS_0_PAID','PILOT':'CLOSED_LOCKED_2_VALID'}[arg]
 if done['status']!=required:raise SystemExit(12)
