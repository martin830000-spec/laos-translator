"""R5 paid BASE/REALDB84 four-path runner (public code, never contains private messages).
Sensitive inputs are AES-256-GCM CMS encrypted and decrypted ONLY within WIF-authenticated Github job.
User authorized exactly this R5 campaign: BASE<=48, REALDB84<=48, total<=96, USD2.
No retries, no fallback, create-only GCS ledger, 25 immutable protected pins.
"""
from __future__ import annotations
import collections,datetime,hashlib,io,json,math,os,pathlib,re,subprocess,sys,tempfile,time,unittest,urllib.request,urllib.parse,urllib.error
sys.path.insert(0,str(pathlib.Path(__file__).parent))
import r5_r4_base as r4

CAMPAIGN='GEMINI35_FOURPATH_PAID96_R5_20261121'
PREFIX='sft_fourpath_paid96_r5_20261121/'
BUCKET=r4.BUCKET
KNAME=PREFIX+'_control/INPUT_DECRYPT_RSA_PRIVATE_KEY.pem'
KEY_GENERATION='1795243801474294'
KEY_SHA='f0a7c70498afea03daf7c0e1cf780a2dfb265921fa76553458a0d28223db8812'
DATA_SHA='26f734ee16d68dcd4b7b80308c6059e4e89c62fa030a81bc75c21f9e71e700f2'
ENCRYPTED_SHA='38c83fed53b365dc786e6470d6bd297ef7dfa526a1806660c31682b7aff123ab'
PLAN_SHA=r4.PLAN_SHA
PROVENANCE_SHA=r4.PROVENANCE_SHA
EXPECTED_MODELS={'BASE':'gemini-3.5-flash-lite','REALDB84':'gemini-3.5-flash-lite@default'}
MAX_CALLS=96
PER_MODEL_MAX=48
MAX_COST_USD=2.0
# Conservative upper price for tuned non-global endpoint: input $0.594M/output $4.95M
# Use these or higher for BASE, with x1.25 guard for uncertain billing.
PRICE_IN_PER_MILLION=0.594
PRICE_OUT_PER_MILLION=4.95
PRICE_SAFETY_FACTOR=1.25
MAX_OUTPUT_TOKENS=1024
RUN_ROOT=PREFIX+'actual/'
BOOTSTRAP={'POST':1,'GET':52,'LIST':1,'POST_BYTES':2484} # actual bootstrap key bytes checked in key metadata
# BOOTSTRAP POST_BYTES patched at runtime from real key receipt size, not this placeholder
PUBLIC_FOLDER=pathlib.Path(__file__).parent
r4.PREFIX=PREFIX

class PaidStop(r4.SafetyStop):pass
class PaidUnknown(r4.TransportUnknown):pass

def require(x,code):
 if not x:raise PaidStop(code)
def sha(b:bytes):return hashlib.sha256(b).hexdigest()
def jsonb(x):return (json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False)+'\n').encode()

def exception_kind(e):
 return type(e).__name__

class Budget(r4.Budget):
 LIMITS={'POST':400,'GET':1400,'LIST':20,'POST_BYTES':8*1024*1024}
 def __init__(self,prev=None):
  super().__init__()
  self.cost_usd=0.0
  self.actual_estimate_usd=0.0
  if prev:self.apply_previous(prev)
 def apply_previous(self,p):
  self.post+=int(p.get('POST',0));self.get+=int(p.get('GET',0));self.list+=int(p.get('LIST',0));self.post_bytes+=int(p.get('POST_BYTES',0))
  self.model_attempts+=int(p.get('model_attempts',0));self.per_model.update(p.get('per_model',{}))
  self.cost_usd+=float(p.get('cost_usd',0));self.actual_estimate_usd+=float(p.get('actual_estimate_usd',0))
 def snapshot(self):
  return {'POST':self.post,'GET':self.get,'LIST':self.list,'POST_BYTES':self.post_bytes,'model_attempts':self.model_attempts,'per_model':dict(self.per_model),'cost_usd':self.cost_usd,'actual_estimate_usd':self.actual_estimate_usd}
 def preflight_model(self,model,request_bytes):
  if self.closed or self.halted:raise PaidStop('HALTED_GENERATION_DENIED')
  if model not in ('BASE','REALDB84'):raise PaidStop('MODEL_NOT_PINNED')
  if self.model_attempts>=MAX_CALLS or self.per_model[model]>=PER_MODEL_MAX:raise PaidStop('GENERATIONS_LIMIT')
  # Byte-length upper limit for prompt tokens + 1024 output tokens; including request overhead.
  upper=((request_bytes+1024)*PRICE_IN_PER_MILLION+MAX_OUTPUT_TOKENS*PRICE_OUT_PER_MILLION)/1_000_000*PRICE_SAFETY_FACTOR
  if self.cost_usd+upper>MAX_COST_USD:raise PaidStop('MODEL_COST_GUARD_USD2')
  return upper
 def transmitted(self,model,upper):
  self.model_attempts+=1;self.per_model[model]+=1;self.cost_usd+=upper
 def finish_model(self,upper,usage):
  if not isinstance(usage,dict):return None
  inp=usage.get('promptTokenCount',0);out=usage.get('candidatesTokenCount',0);think=usage.get('thoughtsTokenCount',0)
  total=usage.get('totalTokenCount',0)
  try:
   inp=int(inp or 0);out=int(out or 0);think=int(think or 0);total=int(total or 0)
   if min(inp,out,think,total)<0:raise ValueError
  except (TypeError,ValueError):return None
  # billable output includes thoughts; avoid double-counting via totalCount
  outbill=max(out+think,total-inp,0)
  actual=(inp*PRICE_IN_PER_MILLION+outbill*PRICE_OUT_PER_MILLION)/1_000_000
  guarded=actual*PRICE_SAFETY_FACTOR
  self.cost_usd+=guarded-upper
  self.actual_estimate_usd+=actual
  if self.cost_usd>MAX_COST_USD+1e-9:self.halted=True;self.first.record('COST_GUARD_BREACHED_AFTER_RESPONSE')
  return {'input_tokens':inp,'output_tokens':out,'thinking_tokens':think,'total_tokens':total,'billable_output_tokens_est':outbill,'actual_estimate_usd':actual,'guarded_cost_usd':guarded}

class Network:
 def __init__(self,token,allow_generation=False):
  self.token=token
  self.allow_generation=allow_generation
  self.model_http_requests=0
 def send(self,method,url,data=None,ctype=None):
  u=urllib.parse.urlsplit(url)
  if u.scheme!='https':raise PaidStop('HTTP_SCHEME_DENIED')
  host=u.hostname
  if host=='aiplatform.us.rep.googleapis.com':
   if method=='GET':
    require(u.path in ('/v1/'+r4.TUNED_ENDPOINT,'/v1/'+r4.TUNED_MODEL),'VERTEX_GET_UNEXPECTED_RESOURCE')
   elif method=='POST':
    require(self.allow_generation,'PAID_GENERATION_MODE_OFF')
    expected={'/v1/'+r4.BASE_MODEL+':generateContent','/v1/'+r4.TUNED_ENDPOINT+':generateContent'}
    require(u.path in expected and not u.query,'UNEXPECTED_GENERATION_TARGET')
    require(data is not None and ctype=='application/json','MODEL_POST_CONTENT_TYPE')
    self.model_http_requests+=1
   else:raise PaidStop('VERTEX_METHOD_DENIED')
  elif host=='storage.googleapis.com':
   if method=='POST':
    require(u.path.startswith('/upload/storage/v1/b/'+BUCKET+'/o'),'UNEXPECTED_GCS_TARGET')
    q=urllib.parse.parse_qs(u.query)
    require(q.get('ifGenerationMatch')==['0'] and q.get('uploadType')==['media'],'GCS_CREATE_ONLY_REQUIRED')
    require(q.get('name',[''])[0].startswith(PREFIX),'GCS_PREFIX_NOT_R5')
   elif method=='GET':
    require(u.path.startswith('/storage/v1/b/'+BUCKET+'/o'),'UNEXPECTED_GCS_GET')
   else:raise PaidStop('GCS_MUTATION_FORBIDDEN')
  else:raise PaidStop('NETWORK_HOST_NOT_PINNED')
  hdr={'Authorization':'Bearer '+self.token,'Accept':'application/json','User-Agent':'R5-Paid96/1'}
  if ctype:hdr['Content-Type']=ctype
  r=urllib.request.Request(url,headers=hdr,data=data,method=method)
  try:
   with urllib.request.urlopen(r,timeout=60) as x:return x.status,x.read(1800000)
  except urllib.error.HTTPError as e:return e.code,e.read(1800000)
  except Exception:raise PaidUnknown('TRANSPORT_UNKNOWN_'+method+'_'+host) from None

def read_inputs(store):
 meta,key=store.read_pinned(KNAME,KEY_GENERATION)
 require(sha(key)==KEY_SHA,'RSA_KEY_INTEGRITY')
 f=PUBLIC_FOLDER
 cms_b64=(f/'r5_private_inputs.cms.b64').read_text().strip()
 import base64
 cipher=base64.b64decode(cms_b64,validate=True)
 require(sha(cipher)==ENCRYPTED_SHA,'INPUT_CIPHERTEXT_DRIFT')
 with tempfile.TemporaryDirectory() as temp:
  d=pathlib.Path(temp);pk=d/'key.pem'; inp=d/'input.p7m';out=d/'plain.json'
  pk.write_bytes(key);pk.chmod(0o600);inp.write_bytes(cipher)
  x=subprocess.run(['openssl','cms','-decrypt','-inform','DER','-in',str(inp),'-inkey',str(pk),'-recip',str(f/'r5_input_recipient_public.crt'),'-out',str(out)],capture_output=True,timeout=25)
  require(x.returncode==0,'PRIVATE_INPUT_AUTHENTICATED_DECRYPT_FAILED')
  raw=out.read_bytes();require(sha(raw)==DATA_SHA,'PRIVATE_INPUT_SHA_MISMATCH')
 dset=json.loads(raw)
 require(dset.get('campaign_id')==CAMPAIGN and dset.get('plan_sha256')==PLAN_SHA and dset.get('provenance_sha256')==PROVENANCE_SHA,'DATASET_CAMPAIGN_DRIFT')
 require(len(dset['sources'])==24 and len(dset['prompts'])==4,'PRIVATE_INPUT_CARDINALITY')
 slots=r4.load_plan()
 for slot in slots:
  x=dset['sources'][slot['selection_id']]
  require(x['source_sha256']==slot['source_sha256'] and sha(x['source'].encode())==slot['source_sha256'],'SOURCE_SHA_MISMATCH')
  p=dset['prompts'][slot['prompt_id']]
  require(sha(p.encode())==slot['prompt_sha256'],'PROMPT_SHA_MISMATCH')
 require(len(slots)==96,'SLOT_GRAPH_NOT_96')
 return dset

def get_token():
 return subprocess.check_output(['gcloud','auth','print-access-token'],text=True,stderr=subprocess.DEVNULL,timeout=25).strip()

def verify_model_identity(net):
 info=r4.identity(net)
 return info

def verify_25(store,tag):
 pins=json.loads((PUBLIC_FOLDER/'r5_pins25.json').read_text())
 require(len(pins)==25 and len({x['object'] for x in pins})==25,'PINS_NOT_25')
 out=[]
 for p in pins:
  m,body=store.read_pinned(p['object'],p['generation'])
  require(m['name']==p['object'] and len(body)==p['bytes'] and sha(body)==p['sha256'],'PROTECTED_PIN_MISMATCH')
  x=json.loads(body)
  require(x.get('enabled') is False and x.get('max_new')==0 and x.get('next_new_authorization')==0,'PROTECTED_NOT_CLOSED')
  out.append({'name':p['object'],'generation':m['generation'],'bytes':len(body),'sha256':sha(body)})
 return {'stage':tag,'count':len(out),'pins':out}

def request_for(slot,txt,prompt):
 x=r4.build_future_paid_request(slot,txt,prompt,CAMPAIGN)
 require(x['method']=='POST' and x['model_code']==slot['model_code'] and x['slot_id']==slot['slot_id'],'REQUEST_RESOURCE_DRIFT')
 want='https://aiplatform.us.rep.googleapis.com/v1/'+(r4.BASE_MODEL if slot['model_code']=='BASE' else r4.TUNED_ENDPOINT)+':generateContent'
 require(x['url']==want,'MODEL_ENDPOINT_MIXED')
 body=x['body']
 require(body['contents']==[{'role':'user','parts':[{'text':txt}]}],'MODEL_ACTUAL_INPUT_DRIFT')
 require(body['systemInstruction']['parts'][0]['text']==prompt,'MODEL_PROMPT_DRIFT')
 require(body['generationConfig']=={'maxOutputTokens':1024,'thinkingConfig':{'thinkingLevel':'MINIMAL'}},'GENERATION_CONFIG_DRIFT')
 return x

def parse_response(body,model):
 x=json.loads(body)
 vers=x.get('modelVersion')
 require(isinstance(vers,str) and vers==EXPECTED_MODELS[model],'MODEL_RESPONSE_VERSION_MISMATCH')
 cands=x.get('candidates') or []
 if not isinstance(cands,list):raise PaidStop('MODEL_CANDIDATES_MALFORMED')
 c=cands[0] if cands else {}
 reason=c.get('finishReason','MISSING')
 parts=((c.get('content') or {}).get('parts') or [])
 texts=[v['text'] for v in parts if isinstance(v,dict) and isinstance(v.get('text'),str) and v.get('thought') is not True]
 text=''.join(texts).strip()
 usable=bool(text and reason=='STOP')
 return {'modelVersion':vers,'finishReason':reason,'text':text,'usable':usable,'usageMetadata':x.get('usageMetadata',{}),'promptFeedback':x.get('promptFeedback')}

# Four slots per source, including 2 independent BASE/TUNED FIRST+BACK pairs.
PILOT_IDS={f'SLOT{i:03d}' for i in [1,2,3,4,49,50,51,52]}

def slot_order(stage):
 slots=r4.load_plan()
 return [s for s in slots if (s['slot_id'] in PILOT_IDS)==(stage=='PILOT')]

def expected_prefix_names(stage,session,pilot_results=None):
 names={KNAME}
 if stage=='PILOT':return names
 names.add(PREFIX+session+'/_control/RUN_CLAIM.json')
 names.add(PREFIX+session+'/_control/PILOT_STATE.json')
 for r in pilot_results:
  for part in ('SEND_INTENT.json','RAW_RESPONSE.json','RESULT.json'):
   names.add(PREFIX+session+'/slots/'+r['slot_id']+'/'+part)
 return names

def record_output_artifact(output,cert_path):
 location=os.environ.get('R5_OUTPUT_CMS')
 if not location:return
 path=pathlib.Path(location);path.parent.mkdir(parents=True,exist_ok=True)
 with tempfile.TemporaryDirectory() as tmp:
  plain=pathlib.Path(tmp)/'private_results.json';plain.write_bytes(jsonb(output));plain.chmod(0o600)
  cmd=['openssl','cms','-encrypt','-aes-256-gcm','-binary','-outform','DER','-in',str(plain),'-out',str(path),str(cert_path)]
  p=subprocess.run(cmd,capture_output=True,timeout=25)
  require(p.returncode==0,'OWNER_ENCRYPTED_ARTIFACT_FAILED')
 path.chmod(0o600)

def run(stage):
 require(stage in ('VERIFY','PILOT','CONTINUE'),'UNKNOWN_STAGE')
 want='true' if stage!='VERIFY' else 'false'
 require(os.environ.get('R5_STAGE')==stage and os.environ.get('ENABLE_GENERATION')==want and os.environ.get('ENABLE_TUNING')=='false','STAGE_APPROVAL_ENV_MISMATCH')
 token=get_token();require(len(token)>25,'WIF_TOKEN_MISSING')
 net=Network(token,allow_generation=(stage!='VERIFY'))
 b=Budget()
 session='actual' # deterministic root to disallow new random session and duplicate campaign reruns
 store=r4.Store(net,b,session)
 # r4.Store prefixes ROOT + session + / -> R5/actual/
 require(store.root==RUN_ROOT,'SESSION_ROOT_DRIFT')
 out={'campaign':CAMPAIGN,'stage':stage,'actual':[], 'skipped':[], 'first_failure':None,'secondary_errors':[],'protected_before':None,'protected_after':None,'identity':None,'private_input_checks':None,'cumulative':None,'new_lock':None,'continued_from_pilot':False,'gcs_receipts':{}}
 error=None
 try:
  inv=set(store.inventory(PREFIX))
  if stage in ('VERIFY','PILOT'):
   require(inv=={KNAME},'PRIOR_R5_OBJECT_EXISTS_NO_REUSE')
  elif stage=='CONTINUE':
   require(KNAME in inv and RUN_ROOT+'_control/PILOT_STATE.json' in inv and RUN_ROOT+'_control/RUN_CLAIM.json' in inv,'PILOT_LEDGER_REQUIRED')
  before=verify_25(store,'START');out['protected_before']=before
  out['identity']=verify_model_identity(net)
  inputs=read_inputs(store)
  out['private_input_checks']={'source_count':24,'prompt_count':4,'data_sha256':DATA_SHA,'plan_sha256':PLAN_SHA,'prompts_sha256':PROVENANCE_SHA}
  if stage=='VERIFY':
   for slot in r4.load_plan():
    text=inputs['sources'][slot['selection_id']]['source'] if slot['action']=='FIRST' else 'R5_STATIC_PARENT_PLACEHOLDER'
    request_for(slot,text,inputs['prompts'][slot['prompt_id']])
   # Read-only security gate, no paid or GCS CREATEs. No output artifact needed.
   out['status']='R5_PAID_SENDER_PRIVATE_INPUT_VERIFY_PASS_NO_GENERATIONS'
   out['cumulative']=b.snapshot()
   print('R5_VERIFY_ONLY_PASS '+json.dumps({'protected':25,'model_identity':out['identity'],'frozen_slots':96,'model_calls':0,'gcs':b.snapshot()},sort_keys=True),flush=True)
   return out
  if stage=='PILOT':
   # Conservatively include observed bootstrap usage before sending model calls.
   b.apply_previous({'POST':1,'GET':52,'LIST':1,'POST_BYTES':len(store.read_pinned(KNAME,KEY_GENERATION)[1])})
   # The extra key re-read above was budget-counted already, update limits still conservative.
   initial=store.create('_control/RUN_CLAIM.json',{'campaign':CAMPAIGN,'stage':'PILOT','approved_generateContent_max':96,'BASE_max':48,'REALDB84_max':48,'budget_usd_max':2,'created_from_new_user_approval':True,'source_plan_sha256':PLAN_SHA,'prompt_provenance_sha256':PROVENANCE_SHA,'session':session,'enabled':True,'next_new_authorization':0,'approval_is_only_this_campaign':True})
  else:
   m,pb=store.read('_control/PILOT_STATE.json');pilot_state_generation=m['generation'];pilot=json.loads(pb)
   require(pilot.get('campaign')==CAMPAIGN and pilot.get('stage')=='PILOT_COMPLETED_READY_FOR_REVIEW' and len(pilot.get('results',[]))==8,'PILOT_NOT_COMPLETE_OR_UNSAFE')
   pgot=pilot['results']
   expect=expected_prefix_names('CONTINUE',session,pgot)
   require(inv==expect,'R5_PREFIX_HAS_UNEXPECTED_OBJECTS')
   # load pilot's cumulative attempt, cost, and GCS counters; current pre-read GETs were charged and retained.
   pre=b.snapshot()
   b.apply_previous(pilot['cumulative'])
   # Independent remote verification of all pilot slot RESULT objects before any CONTINUE model send.
   for entry in pgot:
    m,raw=store.read(f"slots/{entry['slot_id']}/RESULT.json")
    require(sha(raw)==entry['result_sha256'] and m['generation']==entry['generation'],'PILOT_RESULT_CHANGED')
    result=json.loads(raw)
    require(result.get('slot_id')==entry['slot_id'] and result.get('model_code')==entry['model_code'],'PILOT_RESULT_MISMATCH')
   require(len(pgot)==8 and len({x['slot_id'] for x in pgot})==8,'PILOT_COVERAGE_BAD')
   store.create('_control/CONTINUE_CLAIM.json',{'campaign':CAMPAIGN,'stage':'CONTINUE','same_session':session,'prior_pilot_state_generation':pilot_state_generation,'previous_model_calls':b.model_attempts,'created_only_once':True})
   out['continued_from_pilot']=True
  seen={}
  # PILOT and CONTINUE use no source text in BACK, only current-run stored FIRST.
  stop_after=False
  for slot in slot_order(stage):
   sid=slot['slot_id'];code=slot['model_code'];sel=slot['selection_id'];kind=slot['action']
   r4.verify_slot_frozen(slot)
   if kind=='FIRST':
    inp=inputs['sources'][sel]['source']
    require(sha(inp.encode())==slot['source_sha256'],'FROZEN_SOURCE_MISMATCH')
   else:
    par=seen.get(slot['parent_first_slot_id'])
    if not par or not par.get('usable'):
     out['skipped'].append({'slot_id':sid,'reason':'PARENT_FIRST_UNUSABLE_NO_BACK_ATTEMPT','model_code':code})
     continue
    require(par['model_code']==code and par['selection_id']==sel and par['action']=='FIRST','BACK_WRONG_PARENT')
    require(f"slots/{par['slot_id']}/RESULT.json" in store.receipts,'BACK_PARENT_NOT_VERIFIED_SAVED')
    inp=par['translation_text']
    require(inp and sha(inp.encode())==par['translation_sha256'],'BACK_PARENT_TEXT_DRIFT')
   prompt=inputs['prompts'][slot['prompt_id']]
   query=request_for(slot,inp,prompt)
   req_body=jsonb(query['body'])
   upper=b.preflight_model(code,len(req_body))
   intent={'schema':'R5_SEND_INTENT','campaign':CAMPAIGN,'slot_id':sid,'model_code':code,'action':kind,'direction':slot['direction'],'selection_id':sel,'parent_first_slot_id':slot['parent_first_slot_id'],'source_sha256':slot['source_sha256'],'prompt_sha256':slot['prompt_sha256'],'model_target':query['url'].split('/v1/',1)[-1],'request_body_sha256':sha(req_body),'actual_input_sha256':sha(inp.encode()),'cost_upper_reservation_usd':upper,'generated_only_after_create_only_intent':True}
   store.create(f'slots/{sid}/SEND_INTENT.json',intent)
   b.transmitted(code,upper)
   start=time.perf_counter();sent_time=datetime.datetime.now(datetime.timezone.utc).isoformat();http=None;raw=b'';is_unknown=False
   try:
    http,raw=net.send('POST',query['url'],req_body,'application/json')
   except PaidUnknown:
    is_unknown=True
   elapsed_ms=(time.perf_counter()-start)*1000
   raw_obj={'schema':'R5_RAW_RESPONSE','slot_id':sid,'model_code':code,'http_status':http,'unknown':is_unknown,'sent_utc':sent_time,'completed_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'latency_ms':round(elapsed_ms,2),'body_sha256':sha(raw),'body_b64':__import__('base64').b64encode(raw).decode()}
   store.create(f'slots/{sid}/RAW_RESPONSE.json',raw_obj)
   detail={'slot_id':sid,'model_code':code,'action':kind,'direction':slot['direction'],'selection_id':sel,'parent_first_slot_id':slot['parent_first_slot_id'],'request':query,'http_status':http,'unknown':is_unknown,'elapsed_ms':round(elapsed_ms,2),'response_raw':raw.decode('utf-8',errors='replace'),'usage':None,'finishReason':None,'modelVersion':None,'translation_text':'','usable':False}
   if is_unknown:
    out['first_failure']='MODEL_HTTP_UNKNOWN'
    stop_after=True
   elif http!=200:
    out['first_failure']='MODEL_HTTP_'+str(http)
    stop_after=True
   else:
    try:
     parsed=parse_response(raw,code)
     detail.update({'usage':parsed['usageMetadata'],'finishReason':parsed['finishReason'],'modelVersion':parsed['modelVersion'],'translation_text':parsed['text'],'usable':parsed['usable']})
     detail['billable_tokens']=b.finish_model(upper,parsed['usageMetadata'])
     if b.halted:
      out['first_failure']='MODEL_COST_GUARD_AFTER_RESPONSE';stop_after=True
    except (ValueError,TypeError,r4.SafetyStop) as e:
     out['first_failure']='MODEL_RESPONSE_INVALID_'+exception_kind(e)
     stop_after=True
   result={'schema':'R5_RESULT','campaign':CAMPAIGN,'slot_id':sid,'model_code':code,'action':kind,'direction':slot['direction'],'selection_id':sel,'source_sha256':slot['source_sha256'],'prompt_sha256':slot['prompt_sha256'],'parent_first_slot_id':slot['parent_first_slot_id'],'actual_input_sha256':sha(inp.encode()),'translation_text':detail['translation_text'],'translation_sha256':sha(detail['translation_text'].encode()),'http_status':http,'unknown':is_unknown,'modelVersion':detail['modelVersion'],'finishReason':detail['finishReason'],'usage':detail['usage'],'latency_ms':detail['elapsed_ms'],'usable':detail['usable'],'raw_response_sha256':sha(raw)}
   receipt=store.create(f'slots/{sid}/RESULT.json',result)
   detail['result_receipt']=receipt
   detail['result_sha256']=receipt['sha256']
   detail['generation']=receipt['generation']
   detail['translation_sha256']=result['translation_sha256']
   out['actual'].append(detail)
   seen[sid]=result
   if stop_after:break
  # Error or transport unknown: do not transmit any further models, and close when GCS remains usable.
  if out['first_failure']:
   out['status']='STOPPED_MODEL_OR_SAFETY_GATE'
  elif stage=='PILOT' and len(out['actual'])==8 and all(r['usable'] for r in out['actual']):
   entries=[{'slot_id':r['slot_id'],'model_code':r['model_code'],'generation':r['generation'],'result_sha256':r['result_sha256']} for r in out['actual']]
   pil={'schema':'R5_PILOT_STATE','campaign':CAMPAIGN,'stage':'PILOT_COMPLETED_READY_FOR_REVIEW','session':session,'results':entries,'cumulative':b.snapshot(),'enabled':False,'next_new_authorization':0,'user_new_approval_applies_to_remaining_calls_only':True}
   # make cumulative budget include pilot-state POST/GET by anticipating 1 POST+2GET+payload length
   pil['cumulative']['POST']+=1;pil['cumulative']['GET']+=2
   # Fixed-point serialization: the stored cumulative POST_BYTES includes its own GCS body.
   base_bytes=pil['cumulative']['POST_BYTES']
   for _ in range(10):
    pil['cumulative']['POST_BYTES']=base_bytes+len(jsonb(pil))
   require(pil['cumulative']['POST_BYTES']==base_bytes+len(jsonb(pil)),'PILOT_CUMULATIVE_SERIALIZATION')
   store.create('_control/PILOT_STATE.json',pil)
   out['status']='PILOT_8_COMPLETE_PAUSE_FOR_QUALITY_REVIEW'
  elif stage=='PILOT':
   out['status']='PILOT_INCOMPLETE_LOCK'
  else:
   out['status']='PAID96_COMPLETE' if len(out['actual'])==88 and not out['skipped'] else 'PARTIAL_COMPLETE_WITH_SKIPS'
  if stage!='PILOT' or out['status']!='PILOT_8_COMPLETE_PAUSE_FOR_QUALITY_REVIEW':
   # Close after post-PILOT hold, final success, or model error; never on GCS unknown.
   after=verify_25(store,'END');out['protected_after']=after
   require(out['protected_before']['pins']==after['pins'],'PROTECTED_CHANGED_DURING_RUN')
   lockval={'schema':'R5_FINAL_STATE','campaign':CAMPAIGN,'status':out['status'],'enabled':False,'max_new':0,'next_new_authorization':0,'this_stage':stage,'generation_attempts':b.model_attempts,'per_model_attempts':dict(b.per_model),'gcs':b.snapshot(),'first_failure':out['first_failure'],'protected25_unchanged':True,'source_plan_sha256':PLAN_SHA,'provenance_sha256':PROVENANCE_SHA,'no_independent_final':True,'service_changed':False}
   out['new_lock']=store.create('_control/FINAL_STATE.json',lockval)
   b.closed=True
  out['cumulative']=b.snapshot()
  out['gcs_receipts']=store.receipts
  return out
 except Exception as e:
  error=e
  if out['first_failure'] is None:out['first_failure']=str(e) if isinstance(e,(PaidStop,r4.SafetyStop)) else 'UNEXPECTED_'+exception_kind(e)
  if b.first.first and not out['first_failure'].startswith('GCS_'):out['secondary_errors'].append(str(b.first.first))
  out['status']='SAFE_STOP_INCOMPLETE'
  out['cumulative']=b.snapshot()
  out['gcs_receipts']=store.receipts
  return out
 finally:
  # Never print exception messages; contain request/response private bytes only in encrypted artifact.
  if stage!='VERIFY':
   try:record_output_artifact(out,PUBLIC_FOLDER/'r5_output_reader_public.crt')
   except Exception:print('R5_ENCRYPTED_ARTIFACT_UNAVAILABLE',flush=True)
  print('R5_REMOTE_PUBLIC_STATUS '+json.dumps({'campaign':CAMPAIGN,'stage':stage,'status':out.get('status'),'actual_attempts_this_stage':len(out['actual']),'cumulative_attempts':out['cumulative'].get('model_attempts',0) if out.get('cumulative') else 0,'per_model':out['cumulative'].get('per_model',{}) if out.get('cumulative') else {},'first_failure':out.get('first_failure'),'gcs':{k:out['cumulative'].get(k) for k in ('POST','GET','LIST','POST_BYTES')} if out.get('cumulative') else {},'owner_cipher_artifact_created':bool(os.environ.get('R5_OUTPUT_CMS') and pathlib.Path(os.environ.get('R5_OUTPUT_CMS')).exists()),'new_lock_created':bool(out.get('new_lock'))},sort_keys=True),flush=True)

class PaidUnitTests(unittest.TestCase):
 def test_01_limits(self):
  b=Budget();self.assertEqual(Budget.LIMITS,{'POST':400,'GET':1400,'LIST':20,'POST_BYTES':8388608});self.assertEqual(MAX_CALLS,96)
 def test_02_model_before_send_cap(self):
  b=Budget();b.model_attempts=96
  with self.assertRaises(PaidStop):b.preflight_model('BASE',1000)
 def test_03_per_model_limit(self):
  b=Budget();b.per_model['BASE']=48
  with self.assertRaises(PaidStop):b.preflight_model('BASE',1000)
 def test_04_model_cost_guard(self):
  b=Budget();b.cost_usd=1.99999
  with self.assertRaises(PaidStop):b.preflight_model('BASE',3000)
 def test_05_no_network_without_paid_env(self):
  t=Network('FAKE',allow_generation=False)
  with self.assertRaises(PaidStop):t.send('POST','https://aiplatform.us.rep.googleapis.com/v1/'+r4.BASE_MODEL+':generateContent',b'{}','application/json')
  self.assertEqual(t.model_http_requests,0)
 def test_06_wrong_region_denied(self):
  t=Network('FAKE',True)
  with self.assertRaises(PaidStop):t.send('POST','https://aiplatform.europe-west1.rep.googleapis.com/v1/'+r4.BASE_MODEL+':generateContent',b'{}','application/json')
  self.assertEqual(t.model_http_requests,0)
 def test_07_fallback_denied(self):
  t=Network('FAKE',True)
  with self.assertRaises(PaidStop):t.send('POST','https://aiplatform.us.rep.googleapis.com/v1/projects/460077888071/locations/us/publishers/google/models/gemini-3.8-flash:generateContent',b'{}','application/json')
 def test_08_r4_storage_inheritance(self):
  b=Budget();s=r4.Store(r4.FakeTransport(),b,'test')
  x=s.create('test.json',{'a':1});self.assertEqual(x['size'],len(jsonb({'a':1})))
 def test_09_wrong_model_first_prohibited(self):
  s=r4.load_plan();self.assertNotEqual(s[0]['model_code'],s[2]['model_code']);self.assertEqual(s[3]['parent_first_slot_id'],'SLOT003')
 def test_10_actual_pilot_both_sides(self):
  x=slot_order('PILOT');self.assertEqual([z['slot_id'] for z in x],['SLOT001','SLOT002','SLOT003','SLOT004','SLOT049','SLOT050','SLOT051','SLOT052'])
 def test_11_actual_pilot_remaining(self):
  x=slot_order('CONTINUE');self.assertEqual(len(x),88);self.assertEqual(len({z['slot_id'] for z in x}),88)
 def test_12_model_usage_parsing(self):
  b=Budget();upper=b.preflight_model('BASE',2000);b.transmitted('BASE',upper)
  u=b.finish_model(upper,{'promptTokenCount':100,'candidatesTokenCount':50,'thoughtsTokenCount':20,'totalTokenCount':170})
  self.assertEqual(u['billable_output_tokens_est'],70);self.assertEqual(b.model_attempts,1)
 def test_13_model_response_parser(self):
  x={'modelVersion':EXPECTED_MODELS['BASE'],'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':'translated'}]}}],'usageMetadata':{'promptTokenCount':3,'candidatesTokenCount':2}}
  p=parse_response(jsonb(x),'BASE');self.assertTrue(p['usable']);self.assertEqual(p['text'],'translated')
 def test_14_max_tokens_not_usable(self):
  x={'modelVersion':EXPECTED_MODELS['BASE'],'candidates':[{'finishReason':'MAX_TOKENS','content':{'parts':[{'text':'partial'}]}}]}
  self.assertFalse(parse_response(jsonb(x),'BASE')['usable'])
 def test_15_tuned_wrong_version_stops(self):
  x={'modelVersion':EXPECTED_MODELS['BASE'],'candidates':[]}
  with self.assertRaises(PaidStop):parse_response(jsonb(x),'REALDB84')
 def test_16_readonly_no_model_send(self):
  self.assertEqual(Budget().model_attempts,0)
 def test_17_r4_30_test_count(self):
  self.assertEqual(unittest.defaultTestLoader.loadTestsFromTestCase(r4.GuardTests).countTestCases(),30)
 def test_18_model_http_no_retry(self):
  self.assertFalse(hasattr(Network,'retry'))
 def test_19_one_canonical_prefix(self):
  self.assertEqual(PREFIX,'sft_fourpath_paid96_r5_20261121/')
 def test_20_no_real_message_in_public(self):
  raw=pathlib.Path(__file__).read_text();self.assertNotIn(chr(0xC544)+chr(0xB0B4),raw);self.assertNotIn(chr(0x0E97)+chr(0x0EB5)+chr(0x0EC8),raw)
 def test_21_first_parent_for_lao(self):
  x=r4.load_plan();self.assertEqual(x[49]['parent_first_slot_id'],x[48]['slot_id'])
 def test_22_send_intent_precedes_actual(self):
  self.assertIn('SEND_INTENT.json',pathlib.Path(__file__).read_text())

def tests():
 suite=unittest.defaultTestLoader.loadTestsFromTestCase(PaidUnitTests)
 v=unittest.TextTestRunner(verbosity=0).run(suite)
 if not v.wasSuccessful():raise SystemExit(1)
 print('R5_PAID_GUARDS_PASS '+json.dumps({'testsRun':v.testsRun,'failures':len(v.failures),'errors':len(v.errors),'optimized':not __debug__,'model_calls':0}),flush=True)

if __name__=='__main__':
 stage=sys.argv[1] if len(sys.argv)>1 else 'test'
 if stage=='test':tests()
 elif stage in ('VERIFY','PILOT','CONTINUE'):
  result=run(stage)
  if result.get('status') not in ('R5_PAID_SENDER_PRIVATE_INPUT_VERIFY_PASS_NO_GENERATIONS','PILOT_8_COMPLETE_PAUSE_FOR_QUALITY_REVIEW','PAID96_COMPLETE','PARTIAL_COMPLETE_WITH_SKIPS'):
   raise SystemExit(10)
 else:raise SystemExit('usage: r5_paid_runner.py test|VERIFY|PILOT|CONTINUE')
