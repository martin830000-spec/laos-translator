"""Gemini4 Hydrogen SCREEN64: TEST-only bounded no-retry runner; public code, no chat text."""
from __future__ import annotations
import base64, collections, datetime, hashlib, json, os, pathlib, subprocess, sys, tempfile, time, urllib.parse, urllib.request, urllib.error, unittest
sys.path.insert(0,str(pathlib.Path(__file__).parent))
import r5_r4_base as r4
import hydrogen_r2_free_contract_preflight as contract
CAMPAIGN='GEMINI4_HYDROGEN_SCREEN64_R2_20261121'
PREFIX='gemini4_hydrogen_screen64_r2_20261121/'
BUCKET='ko-lao-gemini35-tuning-460077888071'
PROJECT='460077888071'
BASE_MODEL=f'projects/{PROJECT}/locations/us/publishers/google/models/gemini-3.8-flash'
HYD_MODEL=f'projects/{PROJECT}/locations/us/publishers/google/models/gemini-4-hydrogen'
ROOT='https://aiplatform.us.rep.googleapis.com/v1beta1/'
KEY=PREFIX+'_control/INPUT_PRIVATE_RSA_3072.pem'
KEY_GENERATION='1795250145694066'
KEY_SHA='d06c898b8e746b6ceb0783b9a05b8ccd1068028e720682c62ab93dfcc781acab'
BOOTSTATE=PREFIX+'_control/BOOTSTRAP_STATE.json'
BOOTGEN='1795250145977592'
BOOT_SHA='637fd03887e70fd9c79d732c9d3dddba98f1121a927c608505d60f3dfa051ae4'
PRIVATE_SHA='4c37eb85cce4e813477b8dd343164483886647180f91db106a11c011ac7b6ac8'
PINS_SHA='80afd411fad6c798146a75131b25a41fa2152451bca485de8b4eb18ecc8a6b22'
LIMIT_CALLS=64
MODEL_MAX={'A':20,'H':44}
GCS_CAP={'POST':350,'GET':1500,'LIST':20,'POST_BYTES':16*1024*1024}
PRICE={'A':(0.825,4.125),'H':(1.65,8.25)}
MAX_OUTPUT=6144
COST_MAX=5.0
DIR=pathlib.Path(__file__).parent
r4.PREFIX=PREFIX
sha=lambda b:hashlib.sha256(b).hexdigest()
def jsonb(x):return (json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':'))+'\n').encode()
def require(v,code):
 if not v:raise SafetyStop(code)
class SafetyStop(r4.SafetyStop):pass
class Unknown(r4.TransportUnknown):pass
class Budget(r4.Budget):
 LIMITS=GCS_CAP
 def __init__(self):
  super().__init__();self.model_per={'A':0,'H':0};self.arms=collections.Counter();self.guarded_usd=0.0;self.actual_estimate_usd=0.0
 def add_previous(self,p):
  for k,attr in (('POST','post'),('GET','get'),('LIST','list'),('POST_BYTES','post_bytes')):setattr(self,attr,getattr(self,attr)+int(p.get(k,0)))
  self.model_attempts+=int(p.get('model_attempts',0));self.guarded_usd+=float(p.get('guarded_usd',0));self.actual_estimate_usd+=float(p.get('actual_estimate_usd',0))
  for k in ('A','H'):self.model_per[k]+=int(p.get('models',{}).get(k,0))
  self.arms.update(p.get('arms',{}))
  self.check()
 def check(self):
  require(not self.halted and not self.closed,'BUDGET_HALTED');require(self.post<=350 and self.get<=1500 and self.list<=20 and self.post_bytes<=16*1024*1024,'GCS_LIMIT');require(self.model_attempts<=64 and self.model_per['A']<=20 and self.model_per['H']<=44 and self.guarded_usd<=5.0,'MODEL_LIMIT')
 def snapshot(self):return {'POST':self.post,'GET':self.get,'LIST':self.list,'POST_BYTES':self.post_bytes,'model_attempts':self.model_attempts,'models':dict(self.model_per),'arms':dict(self.arms),'guarded_usd':round(self.guarded_usd,10),'actual_estimate_usd':round(self.actual_estimate_usd,10)}
 def model_preflight(self,arm,bytes_request):
  self.check();m='A' if arm=='A' else 'H';require(self.model_attempts<64 and self.model_per[m]<MODEL_MAX[m],'MAX_GENERATIONS')
  # one UTF-8 byte is conservatively budgeted as one input token; 4096 thinking + output tokens
  p=PRICE[m];reserved=(bytes_request*p[0]+MAX_OUTPUT*p[1])/1_000_000*1.3
  require(self.guarded_usd+reserved<=COST_MAX,'USD5_GUARD')
  return reserved
 def model_transmitted(self,arm,upper):
  m='A' if arm=='A' else 'H';self.model_attempts+=1;self.model_per[m]+=1;self.arms[arm]+=1;self.guarded_usd+=upper;self.check()
 def model_actual(self,arm,usage,reserved):
   if not isinstance(usage,dict) or not any(k in usage for k in ('promptTokenCount','totalTokenCount','candidatesTokenCount','thoughtsTokenCount')):
    return {'billable':'UNKNOWN_NO_RELEASE','reservation_held_usd':reserved}
   try:
    inp=int(usage.get('promptTokenCount') or 0);out=int(usage.get('candidatesTokenCount') or 0);think=int(usage.get('thoughtsTokenCount') or 0);total=int(usage.get('totalTokenCount') or 0);cache=int(usage.get('cachedContentTokenCount') or 0)
    if min(inp,out,think,total,cache)<0 or (inp==0 and total==0):raise ValueError
   except (TypeError,ValueError):return {'billable':'UNKNOWN_INVALID_USAGE_NO_RELEASE','reservation_held_usd':reserved}
   outbill=max(out+think,total-inp,0);p=PRICE['A' if arm=='A' else 'H'];cost=(inp*p[0]+outbill*p[1])/1_000_000
   guarded=cost*1.30
   # Only release a verified unused *non-UNKNOWN* reservation after valid usage metadata.
   # Preserve the reservation if model usage unexpectedly exceeds it (halt before next post).
   if guarded<=reserved:
    self.guarded_usd-=reserved-guarded
   else:
    self.guarded_usd+=guarded-reserved
   self.actual_estimate_usd+=cost;self.check()
   return {'input_tokens':inp,'output_tokens':out,'thinking_tokens':think,'cache_tokens':cache,'total_tokens':total,'billable_output_est':outbill,'model_cost_est_usd':cost,'guarded_cost_usd':guarded,'reservation_reconciled':guarded<=reserved}

class Network:
 def __init__(self,token,permit_generation=False):self.token=token;self.permit_generation=permit_generation;self.model_post_count=0
 def send(self,m,url,data=None,ctype=None):
  u=urllib.parse.urlsplit(url);require(u.scheme=='https','HTTP_ONLY_TLS')
  if u.hostname=='aiplatform.us.rep.googleapis.com':
   if m=='POST':
    require(self.permit_generation,'MODEL_POST_IN_FREE_DENIED')
    require(not u.query and u.path in ('/v1beta1/'+BASE_MODEL+':generateContent','/v1beta1/'+HYD_MODEL+':generateContent') and ctype=='application/json','UNEXPECTED_MODEL_POST')
    self.model_post_count+=1
   else:require(m=='GET' and u.path in ('/v1beta1/'+BASE_MODEL,'/v1beta1/'+HYD_MODEL),'VERTEX_GET_ONLY')
  elif u.hostname=='storage.googleapis.com':
   if m=='POST':
    q=urllib.parse.parse_qs(u.query);require(u.path.startswith('/upload/storage/v1/b/'+BUCKET+'/o') and q.get('uploadType')==['media'] and q.get('ifGenerationMatch')==['0'] and q.get('name',[''])[0].startswith(PREFIX),'GCS_CREATE_ONLY')
   else:require(m=='GET' and u.path.startswith('/storage/v1/b/'+BUCKET+'/o'),'GCS_READ_ONLY')
  else:raise SafetyStop('UNAPPROVED_HOST')
  h={'Authorization':'Bearer '+self.token,'Accept':'application/json','User-Agent':'SCREEN64-Hydrogen-R2/1'}
  if ctype:h['Content-Type']=ctype
  req=urllib.request.Request(url,data=data,headers=h,method=m)
  try:
   with urllib.request.urlopen(req,timeout=90) as r:return r.status,r.read(2000000)
  except urllib.error.HTTPError as e:return e.code,e.read(2000000)
  except Exception:raise Unknown('NETWORK_UNKNOWN_'+m+'_NO_RETRY') from None

def config_for(arm):
 require(arm in ('A','B','C','D'),'UNKNOWN_ARM')
 cfg=contract.config_for(arm,max_output_tokens=MAX_OUTPUT)
 require(cfg['thinkingConfig']['thinkingLevel']==('MEDIUM' if arm=='C' else 'LOW'),'MODEL_LEVEL_DRIFT')
 require(set(cfg)=={'maxOutputTokens','thinkingConfig'} and not (set(cfg)&contract.FORBIDDEN_GENERATION),'MODEL_CONFIG_FORBIDDEN_FIELDS')
 return cfg
def parsed(body,arm):
 x=json.loads(body);version=x.get('modelVersion')
 require(isinstance(version,str) and version.startswith('gemini-3.8-flash' if arm=='A' else 'gemini-4-hydrogen'),'MODEL_VERSION_MISMATCH')
 cs=x.get('candidates') or []
 require(isinstance(cs,list),'CANDIDATES_NOT_LIST')
 c=cs[0] if cs else {};reason=c.get('finishReason','MISSING');parts=(c.get('content') or {}).get('parts') or []
 text=''.join(a['text'] for a in parts if isinstance(a,dict) and isinstance(a.get('text'),str) and a.get('thought') is not True).strip()
 return {'modelVersion':version,'finishReason':reason,'text':text,'usable':bool(text and reason=='STOP'),'usageMetadata':x.get('usageMetadata') or {},'promptFeedback':x.get('promptFeedback')}
def slots_for(data,stage,choice=None):
 rows=data['slots']
 if stage=='PILOT':
   selected=[s for s in rows if s['partition']=='DEV' and s['sample_id'] in ('newK:0013','LA-MED-01')]
   priority=[('B','LA-MED-01'),('B','newK:0013'),('A','LA-MED-01'),('A','newK:0013'),('C','LA-MED-01'),('C','newK:0013'),('D','LA-MED-01'),('D','newK:0013')]
   rank={(a,id):(i) for i,(a,id) in enumerate(priority)}
   return sorted(selected,key=lambda s:(rank[(s['arm'],s['sample_id'])],0 if s['action']=='FIRST' else 1))
 if stage=='DEV':return [s for s in rows if s['partition']=='DEV' and s['sample_id'] not in ('newK:0013','LA-MED-01')]
 if stage=='FINAL':return [s for s in rows if s['partition']=='HOLDOUT']
 return []
def target(arm):return ROOT+(BASE_MODEL if arm=='A' else HYD_MODEL)+':generateContent'
def actual_arm(slot,choice):return choice if slot['arm']=='SELECTED_HYDROGEN' else slot['arm']
def build_req(text,prompt,arm):
  require(arm in ('A','B','C','D') and isinstance(text,str) and text.strip() and isinstance(prompt,str) and prompt.strip(),'REQUEST_MISSING')
  cfg=config_for(arm)
  body={'contents':[{'role':'user','parts':[{'text':text}]}], 'systemInstruction':{'parts':[{'text':prompt}]},'generationConfig':cfg}
  uri=target(arm)
  contract.validate_request(uri,body,arm,project=PROJECT,location='us')
  require(cfg['maxOutputTokens']==MAX_OUTPUT,'MAX_OUTPUT_FROZEN_DRIFT')
  wire=jsonb(body)
  # Security guard runs against actual serialized bytes, not merely config_for's returned dict.
  decoded=json.loads(wire)
  contract.validate_request(uri,decoded,arm,project=PROJECT,location='us')
  require(jsonb(decoded)==wire,'WIRE_REQUEST_CANONICAL_DRIFT')
  return uri,wire

def get_data(store):
 keymeta,key=store.read_pinned(KEY,KEY_GENERATION);require(sha(key)==KEY_SHA,'PRIVATE_KEY_SHA_DRIFT')
 cipher_b64=(DIR/'r2_private_inputs.cms.b64').read_text().strip();body=base64.b64decode(cipher_b64,validate=True)
 require(sha(body)=='5c30e66144ce3af8aaa3c94029dd1edb98957d04185bf3a061791ec415586fab','CIPHER_SHA_DRIFT')
 with tempfile.TemporaryDirectory() as td:
  d=pathlib.Path(td);(d/'pk.pem').write_bytes(key);(d/'cipher.p7m').write_bytes(body)
  q=subprocess.run(['openssl','cms','-decrypt','-inform','DER','-in',str(d/'cipher.p7m'),'-recip',str(DIR/'r2_input_recipient.crt'),'-inkey',str(d/'pk.pem'),'-out',str(d/'plain.json')],capture_output=True,timeout=30)
  require(q.returncode==0,'PRIVATE_CMS_DECRYPT_FAIL');raw=(d/'plain.json').read_bytes()
 require(sha(raw)==PRIVATE_SHA,'PRIVATE_INPUT_SHA_DRIFT')
 dataset=json.loads(raw);require(dataset['campaign_id']==CAMPAIGN and len(dataset['samples'])==10 and len(dataset['slots'])==64 and dataset.get('maxOutputTokens')==MAX_OUTPUT and dataset.get('region')=='us' and dataset.get('base_thinking')=='LOW','PRIVATE_FREEZE_INCONSISTENT')
 public=json.loads((DIR/'public_freeze_R2.json').read_text());require(public['campaign_id']==CAMPAIGN and len(public['slots_64'])==64 and public['private_sha256']==PRIVATE_SHA and public['maxOutputTokens']==MAX_OUTPUT,'PUBLIC_FREEZE_INCONSISTENT')
 ids={r['id']:r for r in dataset['samples']};require(len(ids)==10 and len({x['sha256'] for x in ids.values()})==10,'SAMPLE_DUPLICATE')
 for sid,r in ids.items():require(sha(r['source'].encode())==r['sha256'] and sid in public['sample_sha256'] and public['sample_sha256'][sid]==r['sha256'],'SOURCE_DRIFT')
 for arm,ps in dataset['prompts'].items():
  for path,v in ps.items():require(sha(v['text'].encode())==v['sha256'] and public['prompts_sha256'][arm][path]==v['sha256'],'PROMPT_DRIFT')
 require(dataset['baseline_kind']=='SERVICE_EQUIVALENT_PROXY_NOT_LIVE_DEPLOYED_BYTES','BASELINE_KIND_DRIFT')
 return dataset,ids

def protected27(store):
 pins_raw=(DIR/'pins27.json').read_bytes();require(sha(pins_raw)==PINS_SHA,'PIN_LIST_DRIFT');pins=json.loads(pins_raw);require(len(pins)==27,'PIN27_COUNT')
 rec=[]
 for p in pins:
  m,b=store.read_pinned(p['object'],p['generation']);require(len(b)==p['bytes'] and sha(b)==p['sha256'],'PIN_PROTECTED_CHANGED')
  j=json.loads(b);require(j.get('enabled') is False and j.get('max_new')==0 and j.get('next_new_authorization')==0,'PIN_REOPENED')
  rec.append([p['object'],m['generation'],sha(b)])
 return rec

def expected_inventory(stage,previous_actual):
 r={KEY,BOOTSTATE,PREFIX+'_freeqa/SMOKE.json'}
 if stage in ('PILOT','DEV','FINAL'):
  r|={PREFIX+'freeqa/h64_synth_first.json',PREFIX+'freeqa/h64_synth_back.json',PREFIX+'actual/_control/FREEQA_STATE.json'}
 if stage in ('DEV','FINAL'):
  r|={PREFIX+'actual/_control/PILOT_CLAIM.json',PREFIX+'actual/_control/PILOT_STATE.json'}
 if stage=='FINAL':r|={PREFIX+'actual/_control/DEV_CLAIM.json',PREFIX+'actual/_control/DEV_STATE.json'}
 for s in previous_actual:
  for suffix in ('SEND_INTENT.json','RAW_RESPONSE.json','RESULT.json'):
   r.add(PREFIX+'actual/slots/'+s+'/'+suffix)
 return r

def artifact(obj):
 file=os.environ.get('R2_OUTPUT_CMS');require(bool(file),'OWNER_CMS_OUTPUT_PATH_MISSING')
 with tempfile.TemporaryDirectory() as td:
  d=pathlib.Path(td);(d/'plain.json').write_bytes(jsonb(obj));o=d/'cipher.p7m'
  q=subprocess.run(['openssl','cms','-encrypt','-aes-256-gcm','-binary','-in',str(d/'plain.json'),'-out',str(o),'-outform','DER',str(DIR/'r2_owner_output_public.crt')],capture_output=True,timeout=30)
  require(q.returncode==0,'OWNER_CMS_ENCRYPT_FAIL');pathlib.Path(file).write_bytes(o.read_bytes())
  pathlib.Path(file).chmod(0o600)

def record_state(store,b,name,state):
 # Anticipate own create-only POST plus two readbacks, including serialized counter footprint.
 nxt={**state,'cumulative':b.snapshot()};nxt['cumulative']['POST']+=1;nxt['cumulative']['GET']+=2
 base=nxt['cumulative']['POST_BYTES']
 for _ in range(14):nxt['cumulative']['POST_BYTES']=base+len(jsonb(nxt))
 require(nxt['cumulative']['POST_BYTES']==base+len(jsonb(nxt)),'STATE_SELF_BYTES_UNSTABLE')
 receipt=store.create('_control/'+name+'.json',nxt);require(b.snapshot()['POST']==nxt['cumulative']['POST'] and b.snapshot()['GET']==nxt['cumulative']['GET'] and b.snapshot()['POST_BYTES']==nxt['cumulative']['POST_BYTES'],'STAGE_CUMULATIVE_MISMATCH')
 return receipt,nxt

def run(stage):
 require(stage in ('FREEQA','PILOT','DEV','FINAL'),'STAGE_UNKNOWN')
 expected='false' if stage=='FREEQA' else 'true'
 require(os.environ.get('R2_STAGE')==stage and os.environ.get('ENABLE_GENERATION')==expected and os.environ.get('ENABLE_TUNING')=='false','STAGE_ENV_REJECTED')
 choice=os.environ.get('R2_FINAL_CHOICE','')
 if stage=='FINAL':require(choice in ('B','C','D'),'FINAL_CHOICE_MISSING')
 else:require(not choice,'CHOICE_EARLY_NOT_ALLOWED')
 token=subprocess.check_output(['gcloud','auth','print-access-token'],text=True,stderr=subprocess.DEVNULL,timeout=25).strip();require(len(token)>30,'WIF_TOKEN_ABSENT')
 net=Network(token,stage!='FREEQA');b=Budget();store=r4.Store(net,b,'actual')
 out={'campaign_id':CAMPAIGN,'stage':stage,'chosen_hydrogen':choice or None,'actual':[],'skipped':[],'first_failure':None,'secondaries':[],'protected_before':None,'protected_after':None,'new_lock':None,'stage_receipt':None,'cumulative':None,'original_inputs_sha256':PRIVATE_SHA,'run_source_sha256':os.environ.get('R2_RUNNER_SHA256',''),'previous_actual':[]}
 current_id=[]
 try:
  inv=set(store.inventory(PREFIX))
  prevstage={'FREEQA':'BOOT','PILOT':'FREEQA','DEV':'PILOT','FINAL':'DEV'}[stage]
  if stage=='FREEQA':
   m,body=store.read_pinned(BOOTSTATE,BOOTGEN);require(sha(body)==BOOT_SHA,'BOOTSTRAP_INTEGRITY_DRIFT');prev=json.loads(body)
  else:
   m,body=store.read('_control/'+prevstage+'_STATE.json');prev=json.loads(body)
  require(prev.get('campaign_id')==CAMPAIGN and prev.get('cumulative' if stage!='FREEQA' else 'gcs'),'PRIOR_STATE_INVALID')
  prior_entries=prev.get('completed_slot_ids',[]) if stage!='FREEQA' else []
  require(inv==expected_inventory(stage,prior_entries),'PREFIX_INVENTORY_NOT_EXACT')
  b.add_previous(prev['gcs'] if stage=='FREEQA' else prev['cumulative'])
  if stage=='FINAL':
   recovery=json.loads((DIR/'r2_dev_recovery_public.json').read_text())
   require(recovery.get('schema')=='R2_READONLY_DEV_RECOVERY_RECEIPT' and recovery.get('status')=='PASS' and recovery.get('run_id')=='44887185650' and recovery.get('model_calls')==0 and recovery.get('prior_dev_model_attempts')==48 and recovery.get('slots')==32,'DEV_READONLY_AUDIT_RECEIPT_INVALID')
   require(recovery.get('gcs_extra')=={'GET':250,'LIST':1,'POST':0},'DEV_READONLY_EXTRA_BUDGET_DRIFT')
   b.add_previous({'GET':250,'LIST':1})
  require(b.snapshot()['POST']<=350 and b.snapshot()['GET']<=1500,'GCS_ALREADY_OVER_BUDGET')
  before=protected27(store);out['protected_before']={'count':len(before),'pins':before}
  dataset,ids=get_data(store)
  if stage=='FREEQA':
   for s in dataset['slots']:
    arm='B' if s['arm']=='SELECTED_HYDROGEN' else s['arm'];txt=ids[s['sample_id']]['source'] if s['action']=='FIRST' else 'FROZEN_FIRST_TEXT_PLACEHOLDER'
    prompt=dataset['prompts'][arm][s['path']]['text'];uri,raw=build_req(txt,prompt,arm)
    require(uri in (ROOT+BASE_MODEL+':generateContent',ROOT+HYD_MODEL+':generateContent'),'MODEL_RESOURCE_INCORRECT')
    require(len(raw)>100,'REQ_TOO_SHORT')
   synth=r4.Store(net,b,'freeqa');a=synth.create('h64_synth_first.json',{'synthetic':True,'text':'FIRST_FAKE','model_calls':0});bb=synth.create('h64_synth_back.json',{'synthetic':True,'parent_sha':sha(b'FIRST_FAKE'),'model_calls':0})
   require(len(a['sha256'])==64 and len(bb['sha256'])==64,'FREEQA_SHA');require(b.model_attempts==0,'FREEQA_MODEL_BREACH')
   out['protected_after']={'count':27,'pins':protected27(store)}
   receipt,st=record_state(store,b,'FREEQA_STATE',{'schema':'R2_STAGE_STATE','campaign_id':CAMPAIGN,'stage':'FREEQA_PASS','completed_slot_ids':[],'protected27_unchanged':before==out['protected_after']['pins'],'enabled':False,'max_new':0,'next_new_authorization':0,'model_calls':0,'synthetic_only':True})
   out.update({'stage_receipt':receipt,'cumulative':st['cumulative'],'status':'FREEQA_PASS_NO_MODEL_POST'});return out
  want={'PILOT':16,'DEV':32,'FINAL':16}[stage]
  require((stage=='PILOT' and b.model_attempts==0) or (stage=='DEV' and b.model_attempts<=16) or (stage=='FINAL' and b.model_attempts<=48),'PRIOR_MODEL_COUNT_BAD')
  # All remote stages are single-use and preserve original sessions and previous results.
  if stage in ('DEV','FINAL'):
   pre_expected={'DEV':16,'FINAL':48}[stage]
   require(len(prior_entries)==pre_expected,'PRIOR_COVERAGE_BAD')
  store.create('_control/'+stage+'_CLAIM.json',{'schema':'R2_ONCE_CLAIM','campaign_id':CAMPAIGN,'stage':stage,'previous_model_attempts':b.model_attempts,'choice':choice or None,'user_approval_total64':True,'no_retries':True})
  local={}
  for slot in slots_for(dataset,stage,choice):
   sid=slot['slot_id'];arm=actual_arm(slot,choice);action=slot['action'];sample=ids[slot['sample_id']]
   if action=='FIRST':inp=sample['source'];require(sha(inp.encode())==slot['source_sha256'],'FROZEN_ORIGINAL_SHA_BAD')
   else:
    p=local.get(slot['parent_first_slot_id'])
    if not p or not p.get('usable'):
     out['skipped'].append({'slot_id':sid,'parent':slot['parent_first_slot_id'],'cause':'PARENT_FIRST_UNUSABLE_NO_BACK'});continue
    require(p['model_code']==('A' if arm=='A' else 'H') and p['source_id']==slot['sample_id'] and p['action']=='FIRST','CROSS_MODEL_PARENT_DENIED')
    mg,previous=store.read('slots/'+p['slot_id']+'/RESULT.json');prior=json.loads(previous)
    require(prior['source_id']==sample['id'] and prior['translation_sha256']==p['translation_sha256'] and prior['usable'],'PARENT_GCS_DRIFT')
    inp=prior['translation_text'];require(inp and sha(inp.encode())==p['translation_sha256'],'PARENT_FIRST_INPUT_DRIFT')
   prompt=dataset['prompts'][arm]['%s'%slot['path']]['text']
   require(sha(prompt.encode())==dataset['prompts'][arm][slot['path']]['sha256'],'PROMPT_SHA_CHANGED')
   uri,reqbody=build_req(inp,prompt,arm)
   upper=b.model_preflight(arm,len(reqbody))
   intent={'schema':'R2_SEND_INTENT','campaign_id':CAMPAIGN,'slot_id':sid,'arm':arm,'action':action,'path':slot['path'],'source_id':slot['sample_id'],'source_sha256':sample['sha256'],'parent_first_slot_id':slot['parent_first_slot_id'],'input_sha256':sha(inp.encode()),'prompt_sha256':sha(prompt.encode()),'request_sha256':sha(reqbody),'target':uri.split('/v1beta1/',1)[-1],'cost_reserve_usd':upper,'stage':stage}
   store.create('slots/'+sid+'/SEND_INTENT.json',intent)
   b.model_transmitted(arm,upper)
   t0=time.perf_counter();utc0=datetime.datetime.now(datetime.timezone.utc).isoformat();raw=b'';http=None;unknown=False
   try:http,raw=net.send('POST',uri,reqbody,'application/json')
   except Unknown:unknown=True
   ms=round((time.perf_counter()-t0)*1000,2)
   raw_obj={'schema':'R2_RAW_RESPONSE','slot_id':sid,'http':http,'unknown':unknown,'request_sha256':sha(reqbody),'response_sha256':sha(raw),'body_b64':base64.b64encode(raw).decode(),'sent_utc':utc0,'duration_ms':ms}
   store.create('slots/'+sid+'/RAW_RESPONSE.json',raw_obj)
   result={'schema':'R2_RESULT','slot_id':sid,'arm':arm,'model_code':'A' if arm=='A' else 'H','source_id':slot['sample_id'],'partition':slot['partition'],'action':action,'path':slot['path'],'source_sha256':sample['sha256'],'input_sha256':sha(inp.encode()),'parent_first_slot_id':slot['parent_first_slot_id'],'prompt_sha256':sha(prompt.encode()),'model_target':uri,'http':http,'unknown':unknown,'response_sha256':sha(raw),'modelVersion':None,'finishReason':None,'translation_text':'','translation_sha256':sha(b''),'usageMetadata':{},'billable':None,'elapsed_ms':ms,'usable':False}
   if unknown:out['first_failure']='GENERATION_TRANSPORT_UNKNOWN'
   elif http!=200:out['first_failure']='GENERATION_HTTP_'+str(http)
   else:
    try:
     pr=parsed(raw,arm);result.update({'modelVersion':pr['modelVersion'],'finishReason':pr['finishReason'],'translation_text':pr['text'],'translation_sha256':sha(pr['text'].encode()),'usageMetadata':pr['usageMetadata'],'billable':b.model_actual(arm,pr['usageMetadata'],upper),'usable':pr['usable']})
    except Exception as e:out['first_failure']='GENERATION_MODEL_VERSION_OR_PARSE_'+type(e).__name__
   receipt=store.create('slots/'+sid+'/RESULT.json',result)
   detail={**result,'result_receipt':receipt,'response_raw_text':raw.decode('utf-8',errors='replace'),'request':json.loads(reqbody)}
   out['actual'].append(detail);local[sid]=result;current_id.append(sid)
   if out['first_failure']:break
  out['protected_after']={'count':27,'pins':protected27(store)}
  require(out['protected_after']['pins']==before,'PROTECTED27_CHANGED')
  completed=prior_entries+current_id
  state={'schema':'R2_STAGE_STATE','campaign_id':CAMPAIGN,'stage':stage+'_COMPLETE' if len(current_id)==want and not out['first_failure'] else stage+'_PARTIAL_OR_STOP','completed_slot_ids':completed,'stage_attempts':len(current_id),'stage_skipped':out['skipped'],'stage_first_failure':out['first_failure'],'choice':choice or None,'protected27_unchanged':True,'model_calls':b.model_attempts,'model_per':b.model_per,'service_changed':False,'enabled':False,'max_new':0,'next_new_authorization':0}
  if stage=='FINAL' or out['first_failure'] or (stage=='PILOT' and len(current_id)!=16):
   state['unused_locked']=64-b.model_attempts
   state['terminal']=True
   lock,locked_state=record_state(store,b,'FINAL_STATE',state)
   out.update({'new_lock':lock,'stage_receipt':lock,'cumulative':locked_state['cumulative'],'status':'CLOSED_LOCKED' if not out['first_failure'] else 'STOPPED_CLOSED_LOCKED'})
  else:
   marker={'PILOT':'PILOT_STATE','DEV':'DEV_STATE'}[stage]
   receipt,newst=record_state(store,b,marker,state);out.update({'stage_receipt':receipt,'cumulative':newst['cumulative'],'status':stage+'_COMPLETE_PAUSED_FOR_REVIEW' if len(current_id)==want else stage+'_PARTIAL_PAUSED'})
  return out
 except Exception as e:
  if out['first_failure'] is None:out['first_failure']=str(e) if isinstance(e,SafetyStop) else 'UNEXPECTED_'+type(e).__name__
  out['status']='STOPPED_UNVERIFIED_LOCK' if not out.get('new_lock') else 'STOPPED_CLOSED_LOCKED'
  out['cumulative']=b.snapshot()
  return out
 finally:
  if stage!='FREEQA':
   try:artifact(out)
   except Exception:print('R2_OWNER_ARTIFACT_ENCRYPT_FAILED',flush=True)
  print('R2_PUBLIC_STAGE_STATUS '+json.dumps({'stage':stage,'status':out.get('status'),'stage_actual_count':len(out['actual']),'model_attempts_cumulative':out['cumulative']['model_attempts'] if out.get('cumulative') else b.model_attempts,'model_per':out['cumulative']['models'] if out.get('cumulative') else b.model_per,'first_failure':out.get('first_failure'),'skipped':len(out['skipped']),'protected_before':out['protected_before']['count'] if out.get('protected_before') else None,'protected_after':out['protected_after']['count'] if out.get('protected_after') else None,'new_lock':bool(out.get('new_lock')),'gcs':{k:(out['cumulative'] or b.snapshot())[k] for k in GCS_CAP}},sort_keys=True),flush=True)

class UnitTests(unittest.TestCase):
 def test_caps(self):self.assertEqual(Budget.LIMITS,GCS_CAP)
 def test_free_no_post(self):
  n=Network('fake',False)
  with self.assertRaises(SafetyStop):n.send('POST',ROOT+HYD_MODEL+':generateContent',b'{}','application/json')
  self.assertEqual(n.model_post_count,0)
 def test_model_limit(self):
  b=Budget();b.model_attempts=64
  with self.assertRaises(SafetyStop):b.model_preflight('A',2000)
 def test_a_limit(self):
  b=Budget();b.model_per['A']=20
  with self.assertRaises(SafetyStop):b.model_preflight('A',2000)
 def test_h_limit(self):
  b=Budget();b.model_per['H']=44
  with self.assertRaises(SafetyStop):b.model_preflight('B',2000)
 def test_cost_limit(self):
  b=Budget();b.guarded_usd=4.999
  with self.assertRaises(SafetyStop):b.model_preflight('C',2000)
 def test_6144(self):
  for a in 'ABCD':self.assertEqual(config_for(a)['maxOutputTokens'],6144)
 def test_minimal_all_denied(self):self.assertEqual([config_for(x)['thinkingConfig']['thinkingLevel'] for x in 'ABCD'],['LOW','LOW','MEDIUM','LOW'])
 def test_3_8_resource(self):self.assertIn('gemini-3.8-flash',target('A'))
 def test_h_resource(self):self.assertIn('gemini-4-hydrogen',target('B'))
 def test_d_same_h_resource(self):self.assertEqual(target('B'),target('D'))
 def test_parse_valid(self):
  x={'modelVersion':'gemini-4-hydrogen','candidates':[{'finishReason':'STOP','content':{'parts':[{'text':'hello'}]}}]}
  self.assertEqual(parsed(jsonb(x),'D')['text'],'hello')
 def test_max_tokens_invalid(self):
  x={'modelVersion':'gemini-4-hydrogen','candidates':[{'finishReason':'MAX_TOKENS','content':{'parts':[{'text':'partial'}]}}]}
  self.assertFalse(parsed(jsonb(x),'C')['usable'])
 def test_no_text_invalid(self):
  x={'modelVersion':'gemini-3.8-flash','candidates':[{'finishReason':'STOP','content':{'parts':[{'thought':True,'text':'hidden'}]}}]}
  self.assertFalse(parsed(jsonb(x),'A')['usable'])
 def test_wrong_version_denied(self):
  x={'modelVersion':'gemini-3.8-flash','candidates':[]}
  with self.assertRaises(SafetyStop):parsed(jsonb(x),'B')
 def test_cross_region_denied(self):
  n=Network('fake',True)
  with self.assertRaises(SafetyStop):n.send('POST','https://aiplatform.global.rep.googleapis.com/v1beta1/'+HYD_MODEL+':generateContent',b'{}','application/json')
 def test_no_fallback(self):
  n=Network('fake',True)
  with self.assertRaises(SafetyStop):n.send('POST',ROOT+f'projects/{PROJECT}/locations/us/publishers/google/models/gemini-3.5-flash-lite:generateContent',b'{}','application/json')
 def test_no_secret_in_public(self):self.assertFalse(any(0x0E80<=ord(ch)<=0x0EFF for ch in pathlib.Path(__file__).read_text()))
 def test_legacy_r4(self):self.assertEqual(unittest.defaultTestLoader.loadTestsFromTestCase(r4.GuardTests).countTestCases(),30)
 def test_gcs_simulated(self):
  b=Budget();r4.PREFIX=PREFIX;store=r4.Store(r4.FakeTransport(),b,'test')
  x=store.create('synth.json',{'yes':1});self.assertEqual(x['size'],len(jsonb({'yes':1})))
 def test_gcs_duplicate(self):
  b=Budget();store=r4.Store(r4.FakeTransport(),b,'test')
  a=store.create('x',{'v':1});self.assertEqual(store.create('x',{'v':2},expect_412=True)['status'],412)
 def test_gcs_unknown_no_retry(self):
  b=Budget();t=r4.FakeTransport();s=r4.Store(t,b,'test');t.inject_unknown=True
  with self.assertRaises(r4.TransportUnknown):s.create('x',{'v':1})
  with self.assertRaises(r4.SafetyStop):s.create('x',{'v':2})
  self.assertEqual(t.posts,1)
 def test_request_no_ignored_params(self):
  u,b=build_req('test','prompt','B');v=json.loads(b);self.assertNotIn('temperature',v['generationConfig']);self.assertNotIn('topP',v['generationConfig'])
 def test_schedule_pilot(self):
   p=json.loads((DIR/'public_freeze_R2.json').read_text()); z=slots_for({'slots':p['slots_64']},'PILOT');self.assertEqual(len(z),16)
   self.assertEqual([(q['arm'],q['sample_id'],q['action']) for q in z[:4]],[('B','LA-MED-01','FIRST'),('B','LA-MED-01','BACK'),('B','newK:0013','FIRST'),('B','newK:0013','BACK')])
 def test_schedule_dev(self):
   p=json.loads((DIR/'public_freeze_R2.json').read_text());self.assertEqual(len(slots_for({'slots':p['slots_64']},'DEV')),32)
 def test_schedule_final(self):
   p=json.loads((DIR/'public_freeze_R2.json').read_text());self.assertEqual(len(slots_for({'slots':p['slots_64']},'FINAL')),16)
 def test_27pins(self):self.assertEqual(len(json.loads((DIR/'pins27.json').read_text())),27)
 def test_no_model_in_legacy(self):
  with self.assertRaises(r4.SafetyStop):r4.Budget().reserve_model('BASE')
 def test_no_model_after_lock(self):
  b=Budget();b.closed=True
  with self.assertRaises(SafetyStop):b.model_preflight('B',1000)
 def test_budget_cumulative(self):
  b=Budget();b.add_previous({'POST':4,'GET':62,'LIST':1,'POST_BYTES':5848,'model_attempts':0,'models':{'A':0,'H':0}})
  self.assertEqual((b.post,b.get,b.list), (4,62,1))


 def test_r2_final_includes_independent_readonly_recovery(self):
  recovery=json.loads((DIR/'r2_dev_recovery_public.json').read_text());self.assertEqual(recovery['gcs_extra'],{'GET':250,'LIST':1,'POST':0})
  b=Budget();b.add_previous({'POST':155,'GET':748,'LIST':4,'POST_BYTES':528340,'model_attempts':48,'models':{'A':12,'H':36},'guarded_usd':0.5716736025,'actual_estimate_usd':0.439748925})
  b.add_previous({'GET':250,'LIST':1});self.assertEqual((b.get,b.list,b.model_attempts),(998,5,48))
 def test_r2_final_record_immutable_development(self):
  self.assertEqual(sha((DIR/'r2_dev_recovery_public.json').read_bytes()),'671314bc392af7920271b12030b8a061aa29fe47c508ebf5db208ca325de20f9')
 def test_r2_full_wire_negative_minimal(self):
   for arm in 'ABCD':
    uri,w=build_req('synthetic input','synthetic prompt',arm);x=json.loads(w);x['generationConfig']['thinkingConfig']['thinkingLevel']='MINIMAL'
    with self.assertRaises(contract.ContractError):contract.validate_request(uri,json.loads(jsonb(x)),arm)
 def test_r2_full_wire_negative_candidatecount(self):
   for arm in 'ABCD':
    uri,w=build_req('synthetic input','synthetic prompt',arm);x=json.loads(w);x['generationConfig']['candidateCount']=1
    with self.assertRaises(contract.ContractError):contract.validate_request(uri,json.loads(jsonb(x)),arm)
 def test_r2_full_wire_negative_wrong_model(self):
   uri,w=build_req('synthetic input','synthetic prompt','A')
   with self.assertRaises(contract.ContractError):contract.validate_request(uri.replace('3.8-flash','4-hydrogen'),json.loads(w),'A')
 def test_r2_actual_arm_unknown(self):
   with self.assertRaises(SafetyStop):config_for('AB')
 def test_r2_budget_worst_all_64(self):
   p=json.loads((DIR/'public_freeze_R2.json').read_text())
   b=Budget()
   for row in p['slots_64']:
    arm='B' if row['arm']=='SELECTED_HYDROGEN' else row['arm'];upper=b.model_preflight(arm,8000);b.model_transmitted(arm,upper)
   self.assertEqual(b.model_attempts,64);self.assertLess(b.guarded_usd,5.0)
 def test_r2_usage_releases_verified_only(self):
   b=Budget();upper=b.model_preflight('B',1000);b.model_transmitted('B',upper)
   r=b.model_actual('B',{'promptTokenCount':300,'candidatesTokenCount':200,'thoughtsTokenCount':300,'totalTokenCount':800},upper)
   self.assertTrue(r['reservation_reconciled']);self.assertEqual(r['billable_output_est'],500);self.assertLess(b.guarded_usd,upper)
 def test_r2_unknown_usage_no_refund(self):
   b=Budget();upper=b.model_preflight('B',1000);b.model_transmitted('B',upper)
   r=b.model_actual('B',{},upper);self.assertEqual(b.guarded_usd,upper);self.assertIn('UNKNOWN',r['billable'])
 def test_r2_campaign_not_reuse(self):
   self.assertNotEqual(CAMPAIGN,'GEMINI4_HYDROGEN_SCREEN64_20261121');self.assertTrue(PREFIX.startswith('gemini4_hydrogen_screen64_r2_'))

def tests():
 suite=unittest.defaultTestLoader.loadTestsFromTestCase(UnitTests);r=unittest.TextTestRunner(verbosity=0).run(suite)
 if not r.wasSuccessful():raise SystemExit(1)
 print('R2_LOCAL_UNIT_PASS '+json.dumps({'tests':r.testsRun,'errors':len(r.errors),'failures':len(r.failures),'optimized':not __debug__,'generations':0}),flush=True)
if __name__=='__main__':
 stage=sys.argv[1] if len(sys.argv)>1 else 'TEST'
 if stage=='TEST':tests()
 elif stage in ('FREEQA','PILOT','DEV','FINAL'):
  result=run(stage)
  accepted={'FREEQA':['FREEQA_PASS_NO_MODEL_POST'],'PILOT':['PILOT_COMPLETE_PAUSED_FOR_REVIEW'],'DEV':['DEV_COMPLETE_PAUSED_FOR_REVIEW'],'FINAL':['CLOSED_LOCKED']}
  if result.get('status') not in accepted[stage]:raise SystemExit(12)
 else:raise SystemExit('usage: h64_paid_runner.py TEST|FREEQA|PILOT|DEV|FINAL')
