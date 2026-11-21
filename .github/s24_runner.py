"""STREAM24 TEST ONLY. Existing WIF path and R4 create-only GCS store reused.

No SERVICE actions. No prior campaign generation. Original chat and prompts are CMS-encrypted
at rest in temporary public GitHub source. All model RAW SSE bodies stay owner-only GCS
and owner-CMS GitHub artifacts. POST attempts count before transmission, no retries.
"""
from __future__ import annotations
import base64,codecs,collections,datetime,hashlib,json,os,pathlib,subprocess,sys,tempfile,time,unittest,urllib.parse,urllib.request,urllib.error,io
sys.path.insert(0,str(pathlib.Path(__file__).parent))
import s24_gcs_base as gcs
CAMP='GEMINI4_HYDROGEN_STREAM24_20261121'
PREFIX='gemini4_hydrogen_stream24_20261121/'
PROJECT='460077888071';BUCKET='ko-lao-gemini35-tuning-460077888071'
ROOT=f'https://aiplatform.us.rep.googleapis.com/v1beta1/projects/{PROJECT}/locations/us/publishers/google/models/'
MODEL={'A':'gemini-3.8-flash','B':'gemini-4-hydrogen','D':'gemini-4-hydrogen'}
COST={'A':(0.825,4.125),'B':(1.65,8.25),'D':(1.65,8.25)}
CAP={'POST':180,'GET':900,'LIST':16,'POST_BYTES':8*1024*1024}
MAX_TOKEN=6144;MAX_COST=2.0;MODEL_LIMIT={'A':8,'H':16}
BASE=pathlib.Path(__file__).parent
PUBLIC_SHA='64e1bec21b9f78e1d2194a32455cb1b54f72898f38ff76069421efc9296a8057'
PRIVATE_SHA='3cc11f81a92bc06bd0e98e5936bbc80ce36fe8ea25419fef9c38ec1afb0a512b'
PINS_SHA='f1be1ba589f2aaf2649750ccaea23a3ba14b73441de47767a007f82527e56f01'
CIPHER_SHA=os.environ.get('S24_EXPECTED_CIPHER_SHA','')
BOOT_G=os.environ.get('S24_EXPECTED_BOOT_GENERATION','')
BOOT_SHA=os.environ.get('S24_EXPECTED_BOOT_SHA','')
KEY_G=os.environ.get('S24_EXPECTED_KEY_GENERATION','')
KEY_SHA=os.environ.get('S24_EXPECTED_KEY_SHA','')
sha=lambda b:hashlib.sha256(b).hexdigest()
canon=lambda x:(json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':'))+'\n').encode('utf-8')
class SafetyStop(Exception):pass
class NetworkUnknown(SafetyStop):pass
def need(x,code):
 if not x:raise SafetyStop(code)
gcs.PREFIX=PREFIX

class Budget(gcs.Budget):
 LIMITS=CAP
 def __init__(self):
  super().__init__();self.models={'A':0,'H':0};self.arm=collections.Counter();self.guarded_usd=0.0;self.estimate_usd=0.0
 def snap(self):
  return {'POST':self.post,'GET':self.get,'LIST':self.list,'POST_BYTES':self.post_bytes,'model_attempts':self.model_attempts,'models':self.models.copy(),'arms':dict(self.arm),'guarded_usd':round(self.guarded_usd,12),'estimated_cost_usd':round(self.estimate_usd,12)}
 def hydrate(self,old):
  for key,att in [('POST','post'),('GET','get'),('LIST','list'),('POST_BYTES','post_bytes')]:setattr(self,att,getattr(self,att)+int(old.get(key,0)))
  self.model_attempts+=int(old.get('model_attempts',0))
  for k in self.models:self.models[k]+=int(old.get('models',{}).get(k,0))
  self.arm.update(old.get('arms',{}));self.guarded_usd+=float(old.get('guarded_usd',0));self.estimate_usd+=float(old.get('estimated_cost_usd',0))
  self.check()
 def check(self):
  need(not self.halted and not self.closed,'HALTED_OR_CLOSED');need(self.post<=180 and self.get<=900 and self.list<=16 and self.post_bytes<=8*1024*1024,'GCS_CAP');need(self.model_attempts<=24 and self.models['A']<=8 and self.models['H']<=16 and self.guarded_usd<=MAX_COST+1e-9,'MODEL_CAP_OR_USD2')
 def reserve_slot(self,arm,nbytes):
  self.check();k='A' if arm=='A' else 'H'
  need(self.model_attempts<24 and self.models[k]<MODEL_LIMIT[k],'MODEL_SLOTS_EXHAUSTED')
  # Need remaining budget for 3 complete slot triplets + stage final lock and readback.
  need(self.post+5<=180 and self.get+16<=900 and self.list<=16,'GCS_FUTURE_CAP_NO_SEND')
  price=COST[arm];reserve=(nbytes*price[0]+MAX_TOKEN*price[1])/1_000_000*1.30
  need(self.guarded_usd+reserve<=MAX_COST,'USD2_PRE_SEND_RESERVATION_DENIED')
  return reserve
 def transmitted(self,arm,reserve):
  k='A' if arm=='A' else 'H';self.model_attempts+=1;self.models[k]+=1;self.arm[arm]+=1;self.guarded_usd+=reserve;self.check()
 def usage(self,arm,meta,reserve):
  try:
   need(isinstance(meta,dict) and ('promptTokenCount' in meta or 'totalTokenCount' in meta),'USAGE_ABSENT')
   p=int(meta.get('promptTokenCount') or 0);c=int(meta.get('candidatesTokenCount') or 0);t=int(meta.get('thoughtsTokenCount') or 0);total=int(meta.get('totalTokenCount') or 0);cache=int(meta.get('cachedContentTokenCount') or 0)
   need(min(p,c,t,total,cache)>=0 and (p>0 or total>0),'USAGE_INVALID')
  except Exception:
   return {'billable':'UNKNOWN_RESERVATION_HELD','reserved_usd':reserve}
  out=max(c+t,total-p,0);rate=COST[arm];cost=(p*rate[0]+out*rate[1])/1_000_000
  guard=cost*1.3
  self.guarded_usd+=guard-reserve;self.estimate_usd+=cost
  self.check()
  return {'prompt_tokens':p,'output_tokens':c,'thinking_tokens':t,'total_tokens':total,'cached_tokens':cache,'estimated_billable_output_tokens':out,'estimated_cost_usd':cost,'post_usage_guarded_usd':guard,'original_reserved_usd':reserve}

class Network:
 def __init__(self,token,paid=False):self.token=token;self.paid=paid;self.gen_posts=0
 def _safe(self,method,url,data):
  u=urllib.parse.urlsplit(url);need(u.scheme=='https','URL_NOT_HTTPS')
  if u.hostname!='storage.googleapis.com':raise SafetyStop('MODEL_STREAM_ENDPOINT_ONLY')
  if method=='POST':
   q=urllib.parse.parse_qs(u.query)
   need(u.path.startswith('/upload/storage/v1/b/'+BUCKET+'/o') and q.get('ifGenerationMatch')==['0'] and q.get('uploadType')==['media'] and q.get('name',[''])[0].startswith(PREFIX),'GCS_CREATE_ONLY_DENIED')
  else:need(method=='GET' and u.path.startswith('/storage/v1/b/'+BUCKET+'/o'),'GCS_READ_ONLY_DENIED')
 def send(self,method,url,data=None,ctype=None):
  self._safe(method,url,data)
  headers={'Authorization':'Bearer '+self.token,'Accept':'application/json','User-Agent':'STREAM24/1'}
  if ctype:headers['Content-Type']=ctype
  req=urllib.request.Request(url,headers=headers,data=data,method=method)
  try:
   with urllib.request.urlopen(req,timeout=50) as r:return r.status,r.read(3_000_000)
  except urllib.error.HTTPError as e:return e.code,e.read(3_000_000)
  except Exception as e:raise gcs.TransportUnknown('GCS_ACK_UNKNOWN_'+type(e).__name__) from None
 def stream(self,url,wire):
  need(self.paid,'FREE_MODE_STREAM_POST_DENIED')
  u=urllib.parse.urlsplit(url);need(u.scheme=='https' and u.hostname=='aiplatform.us.rep.googleapis.com' and u.query=='alt=sse','MODEL_STREAM_URL_DENIED')
  allow={ROOT+m+':streamGenerateContent?alt=sse' for m in MODEL.values()}
  need(url in allow,'MODEL_OTHER_RESOURCE_DENIED')
  req=urllib.request.Request(url,data=wire,headers={'Authorization':'Bearer '+self.token,'Content-Type':'application/json','Accept':'text/event-stream','User-Agent':'STREAM24/1'},method='POST')
  t0=time.perf_counter();self.gen_posts+=1
  raw=bytearray();parser=None;header_ms=None;first_byte_ms=None;headers={}
  try:
   with urllib.request.urlopen(req,timeout=110) as r:
    header_ms=(time.perf_counter()-t0)*1000;headers={k:v for k,v in r.headers.items() if k.lower() in ('content-type','retry-after','x-request-id','x-goog-request-id','x-guploader-uploadid')}
    parser=SSEAssembler(start=t0)
    while True:
     chunk=r.read1(4096)
     if not chunk:break
     if first_byte_ms is None:first_byte_ms=(time.perf_counter()-t0)*1000
     raw.extend(chunk)
     need(len(raw)<=2_000_000,'STREAM_RAW_OVER_2MB')
     parser.feed(chunk,time.perf_counter())
    parser.finish(time.perf_counter());total_ms=(time.perf_counter()-t0)*1000
    return {'http':r.status,'headers':headers,'wire':bytes(raw),'header_ms':header_ms,'first_byte_ms':first_byte_ms,'total_ms':total_ms,'assembled':parser.result(),'transport_unknown':False}
  except urllib.error.HTTPError as e:
   total_ms=(time.perf_counter()-t0)*1000;body=e.read(200000);headers={k:v for k,v in e.headers.items() if k.lower() in ('content-type','retry-after','x-request-id','x-goog-request-id')}
   return {'http':e.code,'headers':headers,'wire':body,'header_ms':total_ms,'first_byte_ms':None,'total_ms':total_ms,'assembled':None,'transport_unknown':False}
  except Exception as e:
   # HTTP may have transmitted. No retry; preserve original failure. Nothing is reported as usable.
   return {'http':None,'headers':headers,'wire':bytes(raw),'header_ms':header_ms,'first_byte_ms':first_byte_ms,'total_ms':(time.perf_counter()-t0)*1000,'assembled':parser.result() if parser is not None else None,'transport_unknown':True,'unknown_type':type(e).__name__}

class SSEAssembler:
 def __init__(self,start=0.0):
  self.start=start;self.utf8=codecs.getincrementaldecoder('utf-8')('strict');self.line='';self.data=[];self.event_type='message';self.first_event_ms=None;self.first_text_ms=None;self.events=[];self.parts=[];self.text='';self.model_version=None;self.reason=None;self.usage={};self.done=False;self.cum_prefix_events=0;self.empty_events=0;self.thought_parts=0;self.raw_event_count=0
 def feed(self,raw,now):
  txt=self.utf8.decode(raw)
  self._lines(txt,now)
 def _lines(self,txt,now):
  self.line+=txt
  while '\n' in self.line:
   line,self.line=self.line.split('\n',1);line=line.rstrip('\r')
   if not line:self._event(now)
   elif line.startswith(':'):pass
   elif line.startswith('data:'):self.data.append(line[5:].lstrip(' '))
   elif line.startswith('event:'):self.event_type=line[6:].lstrip(' ')
   elif line.startswith('id:'):pass
 def _event(self,now):
  if not self.data:
   self.event_type='message';return
  stamp=(now-self.start)*1000;payload='\n'.join(self.data);etype=self.event_type;self.data=[];self.event_type='message'
  self.raw_event_count+=1
  if self.first_event_ms is None:self.first_event_ms=stamp
  if payload.strip()=='[DONE]':self.done=True;self.events.append({'ms':round(stamp,3),'kind':'done','text_chars':0});return
  try:o=json.loads(payload)
  except Exception:raise SafetyStop('SSE_EVENT_JSON_INVALID') from None
  if not isinstance(o,dict):raise SafetyStop('SSE_EVENT_NOT_OBJECT')
  if 'error' in o:raise SafetyStop('SSE_EVENT_ERROR')
  v=o.get('modelVersion')
  if v:
   need(isinstance(v,str),'SSE_MODEL_VERSION_BAD')
   if self.model_version is not None:need(v==self.model_version,'SSE_MODEL_VERSION_DRIFT')
   self.model_version=v
  cs=o.get('candidates') or []
  need(isinstance(cs,list),'SSE_CANDIDATES_BAD')
  text_segs=[];r=None
  if cs:
   candidate=cs[0];need(isinstance(candidate,dict),'SSE_CANDIDATE_BAD')
   r=candidate.get('finishReason')
   if r is not None:self.reason=r
   content=candidate.get('content') or {}
   for p in content.get('parts') or []:
    if not isinstance(p,dict):continue
    if p.get('thought') is True:self.thought_parts+=1;continue
    if isinstance(p.get('text'),str):text_segs.append(p['text'])
  seg=''.join(text_segs);newseg=seg
  if seg and self.text and seg.startswith(self.text) and len(seg)>len(self.text):
   newseg=seg[len(self.text):];self.cum_prefix_events+=1
  elif seg and self.text and seg==self.text and len(seg)>=12:
   # Ambiguous full-prefix retransmission: ignore duplicate, record for audit.
   newseg='';self.cum_prefix_events+=1
  if newseg.strip() and self.first_text_ms is None:self.first_text_ms=stamp
  self.text+=newseg
  usage=o.get('usageMetadata')
  if isinstance(usage,dict) and usage:self.usage=usage
  if not seg and not r:self.empty_events+=1
  self.events.append({'ms':round(stamp,3),'type':etype,'text_chars':len(seg),'added_chars':len(newseg),'finish':r,'has_usage':bool(usage),'had_thought':self.thought_parts>0})
 def finish(self,now):
  self._lines(self.utf8.decode(b'',final=True),now)
  if self.line:
   line=self.line.rstrip('\r');self.line=''
   if line.startswith('data:'):self.data.append(line[5:].lstrip(' '))
   elif line.startswith('event:'):self.event_type=line[6:].lstrip(' ')
  if self.data:self._event(now)
 def result(self):
  return {'text':self.text.strip(),'finishReason':self.reason,'modelVersion':self.model_version,'usageMetadata':self.usage,'first_sse_ms':self.first_event_ms,'first_text_ms':self.first_text_ms,'events':self.events,'events_count':self.raw_event_count,'empty_events':self.empty_events,'thought_parts_skipped':self.thought_parts,'cumulative_prefix_dedup':self.cum_prefix_events,'seen_done':self.done}


def public_freeze():
 raw=(BASE/'PUBLIC_FREEZE.json').read_bytes();need(sha(raw)==PUBLIC_SHA,'PUBLIC_SHA_DRIFT')
 x=json.loads(raw);need(x['campaign_id']==CAMP and len(x['slots'])==24 and len(x['samples'])==4,'PUBLIC_NOT_24')
 return x

def validate_freeze():
 p=public_freeze();need(sha((BASE/'PINS28.json').read_bytes())==PINS_SHA,'PINS28_SHA_DRIFT')
 pins=json.loads((BASE/'PINS28.json').read_text());need(len(pins)==28 and len({x['object'] for x in pins})==28,'PINS_NOT_28')
 ss={r['id']:r for r in p['samples']};need(len(ss)==4,'SAMPLES_DUPLICATE')
 seen={}
 for i,s in enumerate(p['slots']):
  need(s['slot_id']==f'SLOT{i+1:03d}' and s['arm'] in MODEL and s['thinking']=='LOW','SLOT_ARM_OR_ORDER')
  need(s['source_sha256']==ss[s['sample_id']]['sha256'] and s['prompt_sha256']==p['prompts_sha256'][s['arm']][s['path']],'SOURCE_PROMPT_PIN_DRIFT')
  if s['action']=='FIRST':need(s['parent_first_slot_id'] is None and s['path'] in ('KF','LF'),'FIRST_GRAPH_BAD')
  else:
   parent=seen.get(s['parent_first_slot_id']);need(parent and parent['action']=='FIRST' and parent['arm']==s['arm'] and parent['sample_id']==s['sample_id'],'BACK_GRAPH_BAD')
   need(s['path']=={'KF':'KB','LF':'LB'}[parent['path']],'BACK_DIRECTION_BAD')
  seen[s['slot_id']]=s
 need(collections.Counter(x['arm'] for x in p['slots'])=={'A':8,'B':8,'D':8},'SLOT_MODEL_DISTRIBUTION')
 need([x['slot_id'] for x in p['slots'][:4]]==['SLOT001','SLOT002','SLOT003','SLOT004'],'PILOT_ORDER')
 return p

def verify_pins(store):
 out=[]
 for row in json.loads((BASE/'PINS28.json').read_text()):
  meta,body=store.read_pinned(row['object'],row['generation'])
  need(len(body)==row['bytes'] and sha(body)==row['sha256'],'PROTECTED_LOCK_CHANGED')
  j=json.loads(body);need(j.get('enabled') is False and j.get('max_new')==0 and j.get('next_new_authorization')==0,'PROTECTED_NOT_CLOSED')
  out.append([row['object'],str(meta['generation']),sha(body)])
 return out

def private_freeze(store):
 need(all([CIPHER_SHA,BOOT_G,BOOT_SHA,KEY_G,KEY_SHA]),'CERT_OR_CIPHER_PIN_UNSET')
 meta,key=store.read_pinned(PREFIX+'_control/INPUT_PRIVATE_RSA_3072.pem',KEY_G)
 need(sha(key)==KEY_SHA,'INPUT_RSA_KEY_DRIFT')
 raw=base64.b64decode((BASE/'PRIVATE_FREEZE.cms.b64').read_text().strip(),validate=True)
 need(sha(raw)==CIPHER_SHA,'CMS_CIPHERTEXT_DRIFT')
 with tempfile.TemporaryDirectory() as td:
  root=pathlib.Path(td);(root/'key.pem').write_bytes(key);(root/'cipher.p7m').write_bytes(raw)
  x=subprocess.run(['openssl','cms','-decrypt','-inform','DER','-in',str(root/'cipher.p7m'),'-recip',str(BASE/'INPUT_PUBLIC.crt'),'-inkey',str(root/'key.pem'),'-out',str(root/'plain.json')],capture_output=True,timeout=35)
  need(x.returncode==0,'CMS_PRIVATE_DECRYPT_FAIL')
  plain=(root/'plain.json').read_bytes()
 need(sha(plain)==PRIVATE_SHA,'PRIVATE_FREEZE_SHA_DRIFT')
 p=json.loads(plain);pub=validate_freeze();need(p['campaign_id']==CAMP and p['maxOutputTokens']==6144 and len(p['slots'])==24,'PRIVATE_PLAN_BAD')
 need(p['baseline_kind']=='SERVICE_EQUIVALENT_PROXY_NOT_LIVE_DEPLOYED_BYTES','BASELINE_IDENTITY_BAD')
 for a in ('A','B','D'):
  for d in ('KF','KB','LF','LB'):
   v=p['prompts'][a][d];need(sha(v['text'].encode())==pub['prompts_sha256'][a][d]==v['sha256'],'PRIVATE_PROMPT_HASH_BAD')
 for s in p['samples']:
  need(sha(s['source'].encode())==s['sha256'] and pub['samples'][[r['id'] for r in pub['samples']].index(s['id'])]['sha256']==s['sha256'],'PRIVATE_ORIGINAL_HASH_BAD')
 return p

def build(arm,input_text,prompt):
 need(arm in MODEL and isinstance(input_text,str) and input_text.strip() and isinstance(prompt,str) and prompt.strip(),'EMPTY_OR_UNKNOWN_ARM')
 body={'contents':[{'role':'user','parts':[{'text':input_text}]}],'systemInstruction':{'parts':[{'text':prompt}]},'generationConfig':{'maxOutputTokens':MAX_TOKEN,'thinkingConfig':{'thinkingLevel':'LOW'}}}
 need(set(body['generationConfig'])=={'maxOutputTokens','thinkingConfig'},'GEN_CONFIG_FIELDS_DRIFT')
 need(set(body['generationConfig']['thinkingConfig'])=={'thinkingLevel'},'THINK_CONFIG_FIELDS_DRIFT')
 url=ROOT+MODEL[arm]+':streamGenerateContent?alt=sse'
 need(url in {ROOT+m+':streamGenerateContent?alt=sse' for m in MODEL.values()},'ENDPOINT_DRIFT')
 wire=canon(body);x=json.loads(wire)
 need(x==body and x['generationConfig']==body['generationConfig'],'SERIALIZED_BODY_DRIFT')
 need(not any(k in x['generationConfig'] for k in ('candidateCount','temperature','topP','topK','thinkingBudget')),'UNSUPPORTED_WIRE_PARAMETER')
 return url,wire

def archive(out):
 dest=os.environ.get('S24_OUTPUT_CMS')
 if not dest:return None
 with tempfile.TemporaryDirectory() as td:
  d=pathlib.Path(td);(d/'plain.json').write_bytes(canon(out))
  z=subprocess.run(['openssl','cms','-encrypt','-aes-256-gcm','-binary','-in',str(d/'plain.json'),'-out',str(d/'enc.p7m'),'-outform','DER',str(BASE/'OUTPUT_OWNER_PUBLIC.crt')],capture_output=True,timeout=40)
  need(z.returncode==0,'CMS_OWNER_ARTIFACT_ENCRYPT_FAIL')
  dat=(d/'enc.p7m').read_bytes();pathlib.Path(dest).write_bytes(dat);pathlib.Path(dest).chmod(0o600)
 return {'bytes':len(dat),'sha256':sha(dat)}

def save_stage(store,b,kind,obj):
 # fixed point cumulative counters for create-only POST + metadata/body GET readback.
 data={**obj,'cumulative':b.snap()};data['cumulative']['POST']+=1;data['cumulative']['GET']+=2
 pbytes=b.post_bytes
 for _ in range(16):data['cumulative']['POST_BYTES']=pbytes+len(canon(data))
 need(data['cumulative']['POST_BYTES']==pbytes+len(canon(data)),'CUMULATIVE_BYTES_UNSTABLE')
 receipt=store.create('_control/'+kind+'.json',data)
 need(all(b.snap()[k]==data['cumulative'][k] for k in ('POST','GET','LIST','POST_BYTES')),'SELF_COUNTER_DRIFT')
 return receipt,data

def run(stage):
 need(stage in ('FREEQA','PILOT','MAIN'),'STAGE_UNKNOWN')
 need(os.environ.get('S24_STAGE')==stage and os.environ.get('ENABLE_GENERATION')==('false' if stage=='FREEQA' else 'true') and os.environ.get('ENABLE_TUNING')=='false','STAGE_ENV_FORBIDDEN')
 b=Budget();net=Network(subprocess.check_output(['gcloud','auth','print-access-token'],text=True,stderr=subprocess.DEVNULL,timeout=25).strip(),paid=stage!='FREEQA');need(len(net.token)>30,'WIF_TOKEN_MISSING')
 store=gcs.Store(net,b,'actual')
 out={'campaign_id':CAMP,'stage':stage,'status':'STARTED','actual':[],'skipped':[],'first_failure':None,'secondary_failures':[],'protected_before':None,'protected_after':None,'new_lock':None,'stage_receipt':None,'cumulative':None,'model_raw_count':0,'model_generation_requests':0,'new_authorization':{'A':8,'H':16,'USD2':2},'no_service_changes':True}
 origfirst=None
 try:
  inventory=set(store.inventory(PREFIX));pub=validate_freeze()
  prev_name={'FREEQA':PREFIX+'_control/BOOTSTRAP_STATE.json','PILOT':PREFIX+'actual/_control/FREEQA_STATE.json','MAIN':PREFIX+'actual/_control/PILOT_STATE.json'}[stage]
  meta,prevbytes=store.read_pinned(prev_name,BOOT_G if stage=='FREEQA' else None)
  if stage=='FREEQA':need(sha(prevbytes)==BOOT_SHA,'BOOT_STATE_DRIFT')
  prev=json.loads(prevbytes);need(prev['campaign_id']==CAMP,'PARENT_STATE_CAMPAIGN_DRIFT')
  prior=prev.get('completed_slot_ids',[])
  base={PREFIX+'_control/INPUT_PRIVATE_RSA_3072.pem',PREFIX+'_control/BOOTSTRAP_STATE.json',PREFIX+'_freeqa/SMOKE.json'}
  if stage in ('PILOT','MAIN'):base|={PREFIX+'actual/_control/FREEQA_STATE.json',PREFIX+'freeqa/stream24_synthetic_first.json',PREFIX+'freeqa/stream24_synthetic_back.json'}
  if stage=='MAIN':base|={PREFIX+'actual/_control/PILOT_CLAIM.json',PREFIX+'actual/_control/PILOT_STATE.json'}
  for id in prior:
   for n in ('SEND_INTENT.json','RAW_RESPONSE.json','RESULT.json'):base.add(PREFIX+'actual/slots/'+id+'/'+n)
  need(inventory==base,'PREFIX_EXACT_INVENTORY_BAD')
  b.hydrate(prev.get('gcs') if stage=='FREEQA' else prev['cumulative'])
  # reserve enough GETs for final lock and pre/post pins
  need(b.get+28*2*2+30<=900,'GCS_BUDGET_AFTER_PROTECTED_PRECHECK')
  before=verify_pins(store);out['protected_before']=len(before)
  data=private_freeze(store);samples={v['id']:v for v in data['samples']}
  if stage=='FREEQA':
   # Examine 24 actual request envelopes (two-way fake FIRST for BACK, no model call)
   for slot in data['slots']:
    inp=samples[slot['sample_id']]['source'] if slot['action']=='FIRST' else 'S24_SYNTHETIC_PARENT_FIRST_TEXT'
    prompt=data['prompts'][slot['arm']][slot['path']]['text']
    need(sha(prompt.encode())==slot['prompt_sha256'],'PROMPT_CHANGED')
    url,wire=build(slot['arm'],inp,prompt)
    need(len(wire)>50 and url.endswith('?alt=sse'),'STREAM_BUILD_BAD')
   # Synthetic first/back have separate GCS identity and no user input text.
   synth=gcs.Store(net,b,'freeqa')
   first='synthetic_first_sample_no_user_text';synthetic_first=synth.create('stream24_synthetic_first.json',{'synthetic':True,'text':first,'model_calls':0});synthetic_back=synth.create('stream24_synthetic_back.json',{'synthetic':True,'input_sha256':sha(first.encode()),'text':'synthetic_back','model_calls':0})
   after=verify_pins(store);need(after==before,'PROTECTED_CHANGED');out['protected_after']=28
   rec,st=save_stage(store,b,'FREEQA_STATE',{'schema':'S24_STAGE_STATE','campaign_id':CAMP,'stage':'FREEQA_PASS','synthetic_first_sha':synthetic_first['sha256'],'synthetic_back_sha':synthetic_back['sha256'],'completed_slot_ids':[],'enabled':False,'max_new':0,'next_new_authorization':0,'model_calls':0,'protected28_unchanged':True})
   out.update({'status':'FREEQA_PASS_NO_MODEL_POST','stage_receipt':rec,'cumulative':st['cumulative']});return out
  need((stage=='PILOT' and b.model_attempts==0 and not prior) or (stage=='MAIN' and b.model_attempts==4 and len(prior)==4),'PREVIOUS_MODEL_COUNT_BAD')
  need(len(data['slots'])==24,'FREEZE_24_DRIFT')
  selection=data['slots'][:4] if stage=='PILOT' else data['slots'][4:]
  store.create('_control/'+stage+'_CLAIM.json',{'schema':'S24_CREATE_ONLY_CLAIM','campaign_id':CAMP,'stage':stage,'model_attempts_previous':b.model_attempts,'no_retry':True,'frozen_private_sha256':PRIVATE_SHA,'paid_calls_allowed':24})
  seen={}
  for slot in selection:
   sid=slot['slot_id'];arm=slot['arm'];action=slot['action'];sample=samples[slot['sample_id']]
   if action=='FIRST':inp=sample['source'];need(sha(inp.encode())==slot['source_sha256'],'SOURCE_SHA_CHANGED')
   else:
    parent=seen.get(slot['parent_first_slot_id'])
    need(parent and parent['usable'] and parent['action']=='FIRST' and parent['arm']==arm and parent['sample_id']==slot['sample_id'],'PARENT_FIRST_NOT_VERIFIED')
    _,stored=store.read('slots/'+slot['parent_first_slot_id']+'/RESULT.json');pv=json.loads(stored)
    need(pv['translation_sha256']==parent['translation_sha256'] and pv['usable'],'PARENT_RESULT_DRIFT')
    inp=pv['translation_text'];need(sha(inp.encode())==pv['translation_sha256'],'PARENT_TEXT_HASH_DRIFT')
   prompt=data['prompts'][arm][slot['path']]['text'];need(sha(prompt.encode())==slot['prompt_sha256'],'PROMPT_SHA_DRIFT')
   url,body=build(arm,inp,prompt)
   reserved=b.reserve_slot(arm,len(body))
   intent={'schema':'S24_SEND_INTENT','campaign_id':CAMP,'slot_id':sid,'arm':arm,'model':MODEL[arm],'action':action,'sample_id':slot['sample_id'],'source_sha256':slot['source_sha256'],'prompt_sha256':slot['prompt_sha256'],'input_sha256':sha(inp.encode()),'request_sha256':sha(body),'parent_first_slot_id':slot['parent_first_slot_id'],'target':url.split('/v1beta1/',1)[-1],'reserved_usd':reserved,'phase':stage}
   store.create('slots/'+sid+'/SEND_INTENT.json',intent)
   b.transmitted(arm,reserved) # if send fails or UNKNOWN it is consumed
   response=net.stream(url,body);out['model_raw_count']+=1
   raw_obj={'schema':'S24_RAW_RESPONSE','campaign_id':CAMP,'slot_id':sid,'request_sha256':sha(body),'http':response['http'],'transport_unknown':response['transport_unknown'],'response_sha256':sha(response['wire']),'raw_sse_b64':base64.b64encode(response['wire']).decode('ascii'),'headers':response['headers'],'header_ms':response['header_ms'],'first_byte_ms':response['first_byte_ms'],'total_ms':response['total_ms'],'assembled':response['assembled']}
   store.create('slots/'+sid+'/RAW_RESPONSE.json',raw_obj)
   x=response['assembled'] or {};ctype=next((v for k,v in response['headers'].items() if k.lower()=='content-type'),'');valid=('text/event-stream' in ctype.lower() and response['http']==200 and not response['transport_unknown'] and x.get('finishReason')=='STOP' and bool(x.get('text')) and bool(x.get('modelVersion')) and x.get('modelVersion','').startswith(MODEL[arm]) and x.get('first_text_ms') is not None)
   text=x.get('text') or '';result={'schema':'S24_RESULT','campaign_id':CAMP,'slot_id':sid,'arm':arm,'model':MODEL[arm],'action':action,'sample_id':slot['sample_id'],'source_sha256':slot['source_sha256'],'prompt_sha256':slot['prompt_sha256'],'input_sha256':sha(inp.encode()),'request_sha256':sha(body),'parent_first_slot_id':slot['parent_first_slot_id'],'http':response['http'],'transport_unknown':response['transport_unknown'],'finishReason':x.get('finishReason'),'modelVersion':x.get('modelVersion'),'translation_text':text if valid else '', 'translation_sha256':sha(text.encode()) if valid else sha(b''),'usable':bool(valid),'header_ms':response['header_ms'],'first_byte_ms':response['first_byte_ms'],'first_sse_ms':x.get('first_sse_ms'),'first_text_ms':x.get('first_text_ms'),'elapsed_ms':response['total_ms'],'sse_event_count':x.get('events_count',0),'sse_empty_count':x.get('empty_events',0),'thought_parts_skipped':x.get('thought_parts_skipped',0),'prefix_dedup_count':x.get('cumulative_prefix_dedup',0),'usageMetadata':x.get('usageMetadata') or {},'billable':None,'invalid_reason':None if valid else ('UNKNOWN' if response['transport_unknown'] else 'HTTP_'+str(response['http']) if response['http']!=200 else 'MISSING_STOP_TEXT_VERSION_OR_SSE_CONTENT_TYPE'),'phase':stage,'response_content_type':ctype}
   if response['http']==200 and not response['transport_unknown']:result['billable']=b.usage(arm,x.get('usageMetadata'),reserved)
   else:result['billable']={'billable':'UNKNOWN_RESERVATION_HELD','reserved_usd':reserved}
   receipt=store.create('slots/'+sid+'/RESULT.json',result)
   out['actual'].append({'result':result,'result_receipt':receipt,'sse_events':x.get('events',[]),'raw_response_sha256':sha(response['wire'])})
   seen[sid]=result
   if not valid:
    out['first_failure']=result['invalid_reason'];break
  after=verify_pins(store);need(after==before,'PROTECTED28_MUTATED');out['protected_after']=28
  completed=prior+[x['result']['slot_id'] for x in out['actual']]
  status='PILOT_COMPLETE' if stage=='PILOT' and len(out['actual'])==4 and not out['first_failure'] else 'MAIN_COMPLETE' if stage=='MAIN' and len(out['actual'])==20 and not out['first_failure'] else 'STOPPED_PARTIAL'
  state={'schema':'S24_STAGE_STATE','campaign_id':CAMP,'stage':status,'completed_slot_ids':completed,'model_calls':b.model_attempts,'model_per':b.models,'failure':out['first_failure'],'protected28_unchanged':True,'enabled':False,'max_new':0,'next_new_authorization':0}
  if stage=='MAIN' or out['first_failure']:
   state['terminal']=True;state['unused_locked']=24-b.model_attempts
   lock,st=save_stage(store,b,'FINAL_STATE',state);out['new_lock']=lock;out.update({'stage_receipt':lock,'cumulative':st['cumulative'],'status':'CLOSED_LOCKED' if not out['first_failure'] else 'STOPPED_CLOSED_LOCKED'})
  else:
   rec,st=save_stage(store,b,'PILOT_STATE',state);out.update({'stage_receipt':rec,'cumulative':st['cumulative'],'status':'PILOT_COMPLETE_PAUSED'})
  return out
 except Exception as e:
  if not out.get('first_failure'):out['first_failure']=str(e) if isinstance(e,SafetyStop) else type(e).__name__
  out['status']='STOPPED_UNVERIFIED_LOCK' if not out.get('new_lock') else 'STOPPED_CLOSED_LOCKED'
  out['cumulative']=b.snap();return out
 finally:
  out['model_generation_requests']=b.model_attempts
  if stage!='FREEQA':
   try:out['owner_artifact']=archive(out)
   except Exception as e:print('S24_OWNER_ARCHIVE_FAILED '+type(e).__name__,flush=True)
  public={'status':out['status'],'stage':stage,'model_calls_cumulative':b.model_attempts,'models':b.models,'arms':dict(b.arm),'successful_this_stage':sum(a['result']['usable'] for a in out['actual']),'attempts_this_stage':len(out['actual']),'first_failure':out.get('first_failure'),'protected_before':out.get('protected_before'),'protected_after':out.get('protected_after'),'new_lock':out.get('new_lock'),'gcs':b.snap(),'no_retry':True,'service_unchanged':True}
  print('S24_PUBLIC_STAGE_STATUS '+json.dumps(public,sort_keys=True,ensure_ascii=False),flush=True)

class Tests(unittest.TestCase):
 def test_freeze_24(self):self.assertEqual(len(validate_freeze()['slots']),24)
 def test_pin28(self):self.assertEqual(len(json.loads((BASE/'PINS28.json').read_text())),28)
 def test_stream_url(self):
  for a in MODEL:
   url,wire=build(a,'synthetic','prompt');self.assertIn(':streamGenerateContent?alt=sse',url);self.assertEqual(json.loads(wire)['generationConfig'],{'maxOutputTokens':6144,'thinkingConfig':{'thinkingLevel':'LOW'}})
 def test_free_network_deny(self):
  with self.assertRaises(SafetyStop):Network('token',False).stream(ROOT+'gemini-4-hydrogen:streamGenerateContent?alt=sse',b'{}')
 def test_wrong_model_deny(self):
  with self.assertRaises(SafetyStop):Network('token',True).stream(ROOT+'gemini-3.5-flash:streamGenerateContent?alt=sse',b'{}')
 def test_budget_limit_per_model(self):
  b=Budget();b.models['H']=16
  with self.assertRaises(SafetyStop):b.reserve_slot('D',1000)
 def test_budget_total(self):
  b=Budget();b.model_attempts=24
  with self.assertRaises(SafetyStop):b.reserve_slot('A',1000)
 def test_budget_full_schedule(self):
  b=Budget()
  for row in validate_freeze()['slots']:
   v=b.reserve_slot(row['arm'],10000);b.transmitted(row['arm'],v)
  self.assertEqual(b.models,{'A':8,'H':16});self.assertLessEqual(b.guarded_usd,2.0)
 def test_usage_guard(self):
  b=Budget();v=b.reserve_slot('B',2000);b.transmitted('B',v);r=b.usage('B',{'promptTokenCount':120,'candidatesTokenCount':60,'thoughtsTokenCount':140,'totalTokenCount':320},v);self.assertEqual(r['estimated_billable_output_tokens'],200)
 def test_unknown_no_release(self):
  b=Budget();v=b.reserve_slot('A',1000);b.transmitted('A',v);r=b.usage('A',{},v);self.assertIn('UNKNOWN',r['billable']);self.assertEqual(b.guarded_usd,v)
 def test_sse_utf8_split_multi(self):
  t=1;p=SSEAssembler(start=0)
  s=('data: {"modelVersion":"gemini-4-hydrogen","candidates":[{"content":{"parts":[{"text":"\uc548\ub155\ud558\uc138\uc694"}]}}]}\n\n'+
      'data: {"candidates":[{"content":{"parts":[{"text":" \uc5ec\ubcf4"}]},"finishReason":"STOP"}],"usageMetadata":{"totalTokenCount":45}}\n\n').encode()
  for i,c in enumerate(s):p.feed(bytes([c]),i/1000)
  p.finish(0.3);x=p.result();self.assertEqual(x['text'],'\uc548\ub155\ud558\uc138\uc694 \uc5ec\ubcf4');self.assertEqual(x['finishReason'],'STOP');self.assertEqual(x['events_count'],2);self.assertIsNotNone(x['first_text_ms'])
 def test_sse_metadata_before_text(self):
  p=SSEAssembler(0);p.feed(b'data: {"modelVersion":"gemini-4-hydrogen","usageMetadata":{"promptTokenCount":10}}\n\n',.05);p.feed(b'data: {"candidates":[{"content":{"parts":[{"text":"hello"}]},"finishReason":"STOP"}]}\n\n',.15)
  self.assertLess(p.result()['first_sse_ms'],p.result()['first_text_ms'])
 def test_sse_thought_excluded(self):
  p=SSEAssembler(0);p.feed(b'data: {"modelVersion":"gemini-4-hydrogen","candidates":[{"content":{"parts":[{"thought":true,"text":"secret"},{"text":"actual"}]},"finishReason":"STOP"}]}\n\n',1);self.assertEqual(p.result()['text'],'actual');self.assertEqual(p.result()['thought_parts_skipped'],1)
 def test_sse_cumulative_prefix(self):
  p=SSEAssembler(0);p.feed(b'data: {"candidates":[{"content":{"parts":[{"text":"hello"}]}}]}\n\n',1);p.feed(b'data: {"candidates":[{"content":{"parts":[{"text":"hello world"}]},"finishReason":"STOP"}]}\n\n',2);self.assertEqual(p.result()['text'],'hello world');self.assertEqual(p.result()['cumulative_prefix_dedup'],1)
 def test_sse_incomplete(self):
  p=SSEAssembler(0);p.feed(b'data: {"candidates":[{"content":{"parts":[{"text":"partial"}]}}]}\n\n',1);self.assertNotEqual(p.result()['finishReason'],'STOP')
 def test_sse_bad_json(self):
  p=SSEAssembler(0)
  with self.assertRaises(SafetyStop):p.feed(b'data: {broken}\n\n',1)
 def test_sse_multiline_data(self):
  p=SSEAssembler(0);p.feed(b'data: {"candidates":\ndata: [{"content":{"parts":[{"text":"ok"}]},"finishReason":"STOP"}]}\n\n',1);self.assertEqual(p.result()['text'],'ok')
 def test_sse_empty_event_ignored(self):
  p=SSEAssembler(0);p.feed(b': heartbeat\n\ndata: {"candidates":[]}\n\n',1);self.assertEqual(p.result()['events_count'],1)
 def test_gcs_create_only(self):
  b=Budget();s=gcs.Store(gcs.FakeTransport(),b,'test');s.create('x',{'a':1})
  with self.assertRaises(gcs.SafetyStop):s.create('x',{'b':2})
 def test_gcs_unknown_no_repost(self):
  b=Budget();t=gcs.FakeTransport();s=gcs.Store(t,b,'test');t.inject_unknown=True
  with self.assertRaises(gcs.TransportUnknown):s.create('x',{})
  with self.assertRaises(gcs.SafetyStop):s.create('x',{'retry':True})
  self.assertEqual(t.posts,1)
 def test_optimizations_security(self):
  b=Budget();b.closed=True
  with self.assertRaises(SafetyStop):b.reserve_slot('A',1000)
 def test_no_plaintext_in_code(self):
  s=pathlib.Path(__file__).read_text();self.assertFalse(any(0x0E80<=ord(x)<=0x0EFF for x in s));self.assertNotIn('BEGIN '+'PRIVATE KEY',s)
 def test_pilot_exact_first_four(self):
  r=validate_freeze()['slots'];self.assertEqual([(x['arm'],x['sample_id'],x['action']) for x in r[:4]],[('B','LA-MED-01','FIRST'),('B','LA-MED-01','BACK'),('D','newK:0013','FIRST'),('D','newK:0013','BACK')])
 def test_no_retry_path(self):self.assertNotIn('retry',Network.stream.__code__.co_names)


 def test_full_24_fake_gcs_flow(self):
  b=Budget();s=gcs.Store(gcs.FakeTransport(),b,'mock');p=validate_freeze();seen={}
  for slot in p['slots']:
   id=slot['slot_id'];parent=seen.get(slot['parent_first_slot_id']);input_text='synthetic_source' if slot['action']=='FIRST' else parent['translation_text']
   self.assertTrue(input_text);s.create('slots/'+id+'/SEND_INTENT.json',{'slot':id,'input_sha':sha(input_text.encode())})
   text='SYNTH_'+id;s.create('slots/'+id+'/RAW_RESPONSE.json',{'slot':id,'output':text})
   s.create('slots/'+id+'/RESULT.json',{'slot':id,'text':text})
   seen[id]={'translation_text':text}
  self.assertEqual(len(seen),24);self.assertEqual(b.post,72);self.assertEqual(b.get,144);self.assertEqual(b.model_attempts,0)
 def test_sse_event_explicit_error(self):
  x=SSEAssembler(0)
  with self.assertRaises(SafetyStop):x.feed(b'data: {"error":{"code":429,"message":"quota"}}\n\n',1)
 def test_sse_empty_then_done_invalid_without_stop(self):
  x=SSEAssembler(0);x.feed(b'data: {"candidates":[]}\n\ndata: [DONE]\n\n',1)
  self.assertTrue(x.result()['seen_done']);self.assertIsNone(x.result()['finishReason'])

def tests():
 suite=unittest.defaultTestLoader.loadTestsFromTestCase(Tests);r=unittest.TextTestRunner(verbosity=1).run(suite)
 print('S24_UNIT_GUARDS',r.testsRun,'PASS' if r.wasSuccessful() else 'FAIL','optimized',not __debug__)
 if not r.wasSuccessful():raise SystemExit(1)
if __name__=='__main__':
 cmd=sys.argv[1] if len(sys.argv)>1 else 'TEST'
 if cmd=='TEST':tests()
 elif cmd in ('FREEQA','PILOT','MAIN'):
  result=run(cmd)
  valid={'FREEQA':('FREEQA_PASS_NO_MODEL_POST',),'PILOT':('PILOT_COMPLETE_PAUSED',),'MAIN':('CLOSED_LOCKED',)}[cmd]
  if result['status'] not in valid:raise SystemExit(12)
 else:raise SystemExit('Usage: s24_runner.py TEST|FREEQA|PILOT|MAIN')
