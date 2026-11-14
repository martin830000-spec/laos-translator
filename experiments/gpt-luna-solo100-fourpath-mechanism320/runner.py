"""SOLO100_FOURPATH_MECHANISM320 private GCS runner. Exactly one POST per immutable reservation."""
import asyncio,base64,concurrent.futures,datetime,gzip,json,os,pathlib,subprocess,tempfile,time,zipfile
from contract import APPROVED_TOTAL,BRANCH,CAMPAIGN,HARD_CAPS,MODEL,PHASES,back_input,budget_guard,build_payload,canon,require,sha,validate_plan,validate_prompts,validate_result_metadata,validate_sources,validate_fixed_first,validate_configuration_change
from locked_objects import verify as verify_old
from http_sender import make_client,send
HERE=pathlib.Path(__file__).resolve().parent
ROOT='research/gemini-model-native500-20261107/'
PREFIX=ROOT+'gpt-luna-solo100-fourpath-mechanism320-20261115'
INPUT_KEY=ROOT+'fidelity240-20261108/keys/input-key.pem'
CODE_FILES={'runner.py','contract.py','http_sender.py','locked_objects.py'}
def safe_code(exc):
 value=str(exc) if isinstance(exc,AssertionError) else ''
 return value if value and all(c in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_' for c in value) else type(exc).__name__
def log(label,value):print(label+'='+json.dumps(value,sort_keys=True),flush=True)
def spool(name,data):
 require(not name.startswith('/') and '..' not in pathlib.PurePosixPath(name).parts,'SPOOL_PATH')
 p=pathlib.Path(os.environ['RUNNER_TEMP'])/'solo320-spool'/name;p.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
 if p.exists():require(p.read_bytes()==data,'SPOOL_IMMUTABILITY');return
 with os.fdopen(os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'wb') as f:f.write(data);f.flush();os.fsync(f.fileno())
class RemoteStore:
 def __init__(self):
  from google.cloud import storage
  from google.api_core.exceptions import NotFound,PreconditionFailed
  self.NotFound=NotFound;self.PreconditionFailed=PreconditionFailed
  self.bucket=storage.Client(project='gen-lang-client-0422436907').bucket('lao-translator-src-460077888071')
 def get(self,name,optional=False):
  try:return self.bucket.blob(PREFIX+'/'+name).download_as_bytes(timeout=30,retry=None)
  except self.NotFound:
   if optional:return None
   raise
 def create(self,name,data):
  spool(name,data);self.bucket.blob(PREFIX+'/'+name).upload_from_string(data,if_generation_match=0,timeout=30,retry=None)
  require(self.get(name)==data,'CREATE_READBACK_MISMATCH')
 def same(self,name,data):
  try:self.create(name,data)
  except self.PreconditionFailed:require(self.get(name)==data,'IMMUTABLE_OBJECT_MISMATCH')
 def input_key(self):return self.bucket.blob(INPUT_KEY).download_as_bytes(timeout=30,retry=None)
def read(store,name):return json.loads(store.get(name))
def runtime_control():
 require(os.environ.get('GITHUB_REF')==BRANCH and os.environ.get('GITHUB_RUN_ATTEMPT')=='1' and os.environ.get('GITHUB_ACTOR')=='martin830000-spec','RUNTIME_BRANCH_ACTOR_ATTEMPT')
 c=json.loads((HERE/'CONTROL.json').read_bytes());require(c['campaign']==CAMPAIGN and c['approved_total']==APPROVED_TOTAL,'CONTROL_CAMPAIGN')
 require(set(c['code_sha256'])==CODE_FILES,'CODE_FREEZE_SET')
 for n,digest in c['code_sha256'].items():require(sha((HERE/n).read_bytes())==digest,'CODE_SHA')
 return c
def verify_lease(store,c):
 for name in ('CONTROL.json','LOCK.json'):
  d=read(store,name);require(d['campaign']==CAMPAIGN and d['owner_token']==c['owner_token'] and d['approved_total']==APPROVED_TOTAL and d['enabled'] is False,'CAMPAIGN_LEASE')
 raw=store.get('preflight/PREFLIGHT.json');require(sha(raw)==c['preflight_sha256'],'PREFLIGHT_SHA');p=json.loads(raw)
 require(p['campaign']==CAMPAIGN and p['owner_token']==c['owner_token'] and p['generation_calls']==0,'PREFLIGHT_IDENTITY')
 require(p['model_access']['luna']['allowed'] is True and p['model_access']['luna']['http_status']==200 and p['input_decryption_verified'] and p['create_only_readback_verified'] and p['duplicate_create_rejected'],'PREFLIGHT_NOT_VERIFIED')
 # Check all 11 authoritative states and 10 companions on every phase.
 old_raw=store.get('preparation/OLD_LOCK_EXPECTATIONS.json');require(sha(old_raw)==c['old_locks_sha256']==p['old_locks_sha256'],'OLD_EXPECTATIONS_SHA')
 verify_old(old_raw,c['old_locks_sha256'],lambda n:store.bucket.blob(n).download_as_bytes(timeout=30,retry=None))
 return p
def require_open(store):
 for name in ('states/CLOSED_LOCKED.json','controls/CLOSED/CLOSED_LOCKED.json','states/PAUSED_LOCKED.json','controls/PAUSED/PAUSED_LOCKED.json'):
  require(store.get(name,True) is None,'TERMINAL_CAMPAIGN_LOCK')
def unpack(store,c):
 with tempfile.TemporaryDirectory() as td:
  t=pathlib.Path(td);(t/'key.pem').write_bytes(store.input_key());(t/'key.pem').chmod(0o600)
  (t/'input.p7m').write_bytes(base64.b64decode((HERE/'input.p7m.b64').read_bytes(),validate=True))
  subprocess.run(['openssl','cms','-decrypt','-binary','-inform','DER','-in',str(t/'input.p7m'),'-inkey',str(t/'key.pem'),'-out',str(t/'package.bin')],check=True,capture_output=True)
  raw=(t/'package.bin').read_bytes();raw=gzip.decompress(raw) if raw.startswith(b'\x1f\x8b') else raw
  require(sha(raw)==c['package_sha256'],'PACKAGE_SHA');p=json.loads(raw)
 require(p['campaign']==CAMPAIGN and set(p)<= {'campaign','objects','objects_b64'},'PACKAGE_SCHEMA')
 objects={n:canon(v) for n,v in p.get('objects',{}).items()}
 for n,v in p.get('objects_b64',{}).items():require(n not in objects,'DUPLICATE_PACKAGE_OBJECT');objects[n]=base64.b64decode(v,validate=True)
 require(bool(objects),'EMPTY_PACKAGE')
 for n in objects:require(n.startswith(('preparation/','plans/','gates/','evaluation/','selection/')) and '..' not in n and n.endswith('.json'),'PACKAGE_PATH')
 return objects
def ingest(store,c):
 objects=unpack(store,c)
 for n,b in objects.items():store.same(n,b)
 store.same('checks/packages/'+c['package_sha256']+'.json',canon({'campaign':CAMPAIGN,'objects':{n:{'sha256':sha(b),'bytes':len(b)} for n,b in objects.items()}}))
 return objects
def load_design(store,c):
 raw_s=store.get('preparation/SOURCES.json');raw_p=store.get('preparation/PROMPTS.json');raw_f=store.get('preparation/FREEZE.json')
 require(sha(raw_s)==c['sources_sha256'] and sha(raw_p)==c['prompts_sha256'] and sha(raw_f)==c['freeze_sha256'],'DESIGN_FILE_SHA')
 document=json.loads(raw_s);prompts=json.loads(raw_p);freeze=json.loads(raw_f)
 require(freeze['campaign']==CAMPAIGN and freeze['sources_sha256']==sha(raw_s) and freeze['prompts_sha256']==sha(raw_p),'FREEZE_POINTERS')
 sources=validate_sources(document);validate_prompts(prompts,freeze)
 require(freeze.get('code_sha256')==c['code_sha256'],'FROZEN_CODE_CHANGED')
 for s in document.get('fixed_first_inputs',[]):
  n=s['origin_result_object'];require(n.startswith('preparation/') and '..' not in n,'FIXED_ORIGIN_PATH')
  raw=store.get(n);require(sha(raw)==s['origin_result_sha256'],'FIXED_ORIGIN_SHA');parent=json.loads(raw)
  validate_fixed_first(s,parent)
  s['_origin_result']=parent;sources[s['input_id']]=s
 return sources,prompts,freeze
def reconcile(store):
 names=[f'budget/{i:04d}.json' for i in range(1,APPROVED_TOTAL+1)]
 with concurrent.futures.ThreadPoolExecutor(max_workers=16) as p:raws=list(p.map(lambda n:store.get(n,True),names))
 records=[json.loads(b) for b in raws if b is not None]
 require(all(b is not None for b in raws[:len(records)]) and all(b is None for b in raws[len(records):]),'LEDGER_GAP')
 require(len({r['slot'] for r in records})==len(records),'DUPLICATE_LEDGER_SLOT')
 with concurrent.futures.ThreadPoolExecutor(max_workers=16) as p:out=list(p.map(lambda r:store.get('results/'+r['slot']+'.json',True),records))
 counts={ph:{'reserved':0,'success':0,'failed':0,'unknown':0,'transmitted_recorded':0} for ph in PHASES};results={}
 for ordinal,(r,raw) in enumerate(zip(records,out),1):
  require(r['campaign']==CAMPAIGN and r['model']==MODEL and r['ordinal']==ordinal and r['stage'] in PHASES,'LEDGER_IDENTITY')
  row=counts[r['stage']];row['reserved']+=1
  if raw is None:row['unknown']+=1;continue
  d=json.loads(raw)
  require(all(d.get(k)==r[k] for k in ('campaign','model','ordinal','slot','stage','request_sha256','input_sha256')),'RESULT_LEDGER_IDENTITY')
  require(sha(canon(d['request']))==r['request_sha256'] and sha(d['request']['input'].encode())==r['input_sha256'],'RESULT_REQUEST_SHA')
  require(d.get('send_invoked') is True and d.get('http_attempts')==1,'RESULT_SEND_CONTRACT')
  row['transmitted_recorded']+=1;row['unknown' if d.get('unknown') else 'success' if d.get('success') else 'failed']+=1;results[r['slot']]=d
 for phase,row in counts.items():require(row['reserved']<=HARD_CAPS[phase],'EXISTING_STAGE_CAP_EXCEEDED')
 totals={k:sum(v[k] for v in counts.values()) for k in ('reserved','success','failed','unknown','transmitted_recorded')}
 return records,results,counts,totals

def verify_gate(store,c,phase,count):
 raw=store.get('gates/'+phase+'.json');require(sha(raw)==c['backup_receipt_sha256'],'BACKUP_GATE_SHA');gate=json.loads(raw)
 require(gate['campaign']==CAMPAIGN and gate['phase']==phase and gate['prior_reserved']==count,'BACKUP_GATE_IDENTITY')
 for key in ('verified','drive_readback_verified','owner_only','sha256_verified','zip_crc_verified','manifest_verified'):require(gate.get(key) is True,'BACKUP_INCOMPLETE')
 previous=c.get('previous_phase');require(gate.get('previous_phase')==previous,'BACKUP_PREVIOUS_PHASE')
 if previous is None:require(phase in ('A','CLOSE') and count==0,'INITIAL_STAGE_ONLY')
 else:
  require(previous in PHASES and (phase=='CLOSE' or PHASES.index(previous)+1==PHASES.index(phase)),'PHASE_ORDER')
  state_raw=store.get('states/'+previous+'-finished.json');require(sha(state_raw)==gate['previous_state_sha256'],'PREVIOUS_STATE_SHA')
  state=json.loads(state_raw);require(state['enabled'] is False and state['max_new']==0 and state['reserved_total']==count and state['ledger_resolved'] is True,'PREVIOUS_STAGE_UNSAFE')
  require(store.get('locks/'+previous+'.RELEASED.json',True) is not None,'PREVIOUS_STAGE_NOT_RELEASED')
 return gate

def load_plan(store,c,sources,prompts,results):
 phase=c['phase'];raw=store.get('plans/'+phase+'.json');require(sha(raw)==c['plan_sha256'],'PLAN_SHA');plan=json.loads(raw)
 require(plan['phase']==phase and len(plan['slots'])==c['max_new'],'PLAN_CONTROL_CAP');validate_plan(plan,sources,prompts)
 # Freeze allows stage plans to be selected later; sources/prompts are immutable.
 freeze=read(store,'preparation/FREEZE.json')
 expected_plan=freeze.get('plan_sha256_by_phase',{}).get(phase)
 if expected_plan is not None:require(expected_plan==sha(raw),'FROZEN_PLAN_SHA')
 if phase in ('C','FINAL'):
  decision=read(store,'selection/'+phase+'.json')
  require(decision['campaign']==CAMPAIGN and decision['review_complete'] is True and decision['generation_api_judge_calls']==0,'DECISION_UNREVIEWED')
  prior_phases=('A','B') if phase=='C' else ('C',)
  expected={slot:sha(canon(r)) for slot,r in results.items() if r['stage'] in prior_phases}
  require(decision['prior_result_sha256']==expected,'DECISION_RESULT_SET')
  require(decision.get('selected_configuration')==plan.get('selected_configuration'),'SELECTED_CONFIGURATION_MISMATCH')
  if plan['slots']:
   require(decision.get('promising_mechanism_observed' if phase=='C' else 'meaningful_improvement_confirmed') is True,'NO_REVIEWED_CANDIDATE')
   if phase=='FINAL':
    previous=read(store,'plans/C.json');validate_configuration_change(previous['selected_configuration'],plan['selected_configuration'],decision)
  else:require(bool(decision.get('omitted_reason')),'EMPTY_PHASE_REASON')
 return plan

def resolve_input(task,sources,results):
 if task['slot'].split('-')[0]=='B':
  fixed=sources[task['input_id']];return fixed['display_text'],fixed['_origin_result']
 source=sources[task['source_id']]
 if task['path'] in ('KF','LF'):return source['source'],None
 parent=results.get(task['parent_first_id']);return back_input(parent),parent

def stage(store,c):
 verify_lease(store,c);require_open(store);ingest(store,c);sources,prompts,freeze=load_design(store,c)
 records,results,counts,totals=reconcile(store);require(totals['reserved']==c['prior_reserved'],'STAGE_COUNT')
 plan=load_plan(store,c,sources,prompts,results);verify_gate(store,c,c['phase'],len(records))
 state={'campaign':CAMPAIGN,'phase':c['phase'],'status':'STAGED_LOCKED','enabled':False,'max_new':0,'owner_token':c['owner_token'],'reserved_total':len(records),'plan_sha256':c['plan_sha256']}
 store.same('controls/'+c['phase']+'/STAGED_LOCKED.json',canon(state));log('STAGED',{'phase':c['phase'],'slots':len(plan['slots']),'generation_calls':0})

def pause(store,state):
 for n in ('states/PAUSED_LOCKED.json','controls/PAUSED/PAUSED_LOCKED.json'):
  b=store.get(n,True)
  if b is None:store.create(n,canon(state))
  else:require(json.loads(b)['campaign']==CAMPAIGN,'FOREIGN_PAUSE')

async def execute(store,c,sender=send,client_factory=make_client):
 require(c['mode']=='EXECUTE' and c['enabled'] is True and c['deadline_epoch']>time.time(),'EXECUTION_DISABLED_EXPIRED')
 require(bool(os.environ.get('OPENAI_API_KEY')),'NO_EXISTING_SECRET');verify_lease(store,c);require_open(store)
 sources,prompts,freeze=load_design(store,c);records,results,counts,totals=reconcile(store)
 require(totals['reserved']==c['prior_reserved'] and totals['unknown']==0,'PRIOR_LEDGER_UNSAFE')
 phase=c['phase'];require(counts[phase]['reserved']==0,'PHASE_ALREADY_ATTEMPTED')
 plan=load_plan(store,c,sources,prompts,results);require(len(records)+len(plan['slots'])<=APPROVED_TOTAL,'CAMPAIGN_CAP')
 verify_gate(store,c,phase,len(records));staged=read(store,'controls/'+phase+'/STAGED_LOCKED.json')
 require(staged['plan_sha256']==c['plan_sha256'] and staged['reserved_total']==len(records),'STAGED_MISMATCH')
 lock={'campaign':CAMPAIGN,'owner_token':c['owner_token'],'phase':phase,'run':os.environ['GITHUB_RUN_ID'],'commit':os.environ['GITHUB_SHA'],'plan_sha256':c['plan_sha256']}
 store.create('locks/'+phase+'.json',canon(lock));attempted=0;skips=[];stop=None;finished=False
 try:
  if plan['slots']:store.create('locks/after-'+str(len(records))+'.json',canon(lock))
  require(reservations_equal(store,records),'LEDGER_CHANGED_AFTER_LOCK')
  for task in plan['slots']:
   require(store.get('requests/'+task['slot']+'.json',True) is None and store.get('results/'+task['slot']+'.json',True) is None,'SLOT_EXISTS')
  store.create('states/'+phase+'-running.json',canon(dict(lock,status='RUNNING',enabled=True,max_new=len(plan['slots']))))
  async with client_factory() as client:
   for task in plan['slots']:
    require(c['deadline_epoch']>time.time(),'ACTIVATION_EXPIRED');require_open(store)
    text,parent=resolve_input(task,sources,results)
    if text is None:
     skips.append(task['slot']);store.create('skips/'+task['slot']+'.json',canon({'campaign':CAMPAIGN,'slot':task['slot'],'reason':'FIRST_TECHNICAL_FAILURE','unattempted':True}));continue
    payload=build_payload(task['path'],text,prompts[task['prompt_id']][task['path']],task['tier'])
    if parent:require(payload['input']==parent['display_text'] and set(payload)=={'model','reasoning','instructions','input','stream','store','max_output_tokens','service_tier'},'BACK_LEAKAGE')
    record=budget_guard(records,task);key=task.get('input_id',task.get('source_id'));source=sources[key]
    record.update(source_id=key,candidate=task['candidate'],prompt_id=task['prompt_id'],path=task['path'],tier=task['tier'],repeat_index=task.get('repeat_index',0),raw_record_number=source.get('raw_record_number'),source_kind='FIXED_ACTUAL_FIRST' if phase=='B' else 'ORIGINAL_SOURCE',source_sha256=source['sha256'],prompt_sha256=sha(payload['instructions'].encode()),input_sha256=sha(text.encode()),request_sha256=sha(canon(payload)),run=os.environ['GITHUB_RUN_ID'],commit=os.environ['GITHUB_SHA'])
    store.create('requests/'+task['slot']+'.json',canon({'campaign':CAMPAIGN,'slot':task['slot'],'request':payload,'request_sha256':record['request_sha256']}))
    store.create(f"budget/{record['ordinal']:04d}.json",canon(record));records.append(record);attempted+=1
    result=await sender(client,payload,os.environ['OPENAI_API_KEY'])
    try:result=validate_result_metadata(result,task['tier'])
    except Exception as exc:
     result.update(success=False,unknown=True,display_text=None,metadata_validation_exception=safe_code(exc))
    result.update({k:v for k,v in record.items() if k!='state'});result.update(request=payload,send_invoked=True,parent_first_id=task.get('parent_first_id'),back_parent_kind='HISTORICAL_FIXED_FIRST' if phase=='B' else 'NEW_CAMPAIGN_FIRST' if parent else None)
    if parent:result.update(back_input_equals_displayed_first=text==parent['display_text'],displayed_first_sha256=sha(parent['display_text'].encode()))
    if phase=='B':result['external_first']={k:source[k] for k in ('origin_result_sha256','origin_result_object')}
    raw=canon(result);require(os.environ['OPENAI_API_KEY'].encode() not in raw,'SECRET_IN_RESULT')
    store.create('results/'+task['slot']+'.json',raw);results[task['slot']]=result
    log('ATTEMPT',{'slot':task['slot'],'ordinal':record['ordinal'],'success':result['success'],'unknown':result['unknown'],'actual_tier':result.get('actual_service_tier'),'http_status':result.get('http_status')})
    if result['unknown']:stop='UNKNOWN_STOP_NO_RETRY';break
    fatal=(bool(result.get('metadata_errors')) and result.get('provider_parse_success')) or result.get('http_status') in (400,401,403,429)
    fatal=fatal or (result.get('actual_model') is not None and result['actual_model']!=MODEL) or (result.get('actual_service_tier') is not None and not result.get('tier_verified')) or (result.get('actual_reasoning_effort') not in (None,'none'))
    if fatal:stop='ENVIRONMENT_OR_METADATA_FAILURE_NO_RETRY';break
  finished=stop is None
 except Exception as exc:stop=safe_code(exc)
 finally:
  try:
   records,results,counts,totals=reconcile(store)
   state={'ledger_resolved':True,'reserved_total':totals['reserved'],'actual_api_attempts_recorded':totals['transmitted_recorded'],'success':totals['success'],'failed':totals['failed'],'unknown':totals['unknown'],'unused_locked':APPROVED_TOTAL-totals['reserved'],'stage_counts':counts}
  except Exception as exc:state={'ledger_resolved':False,'reserved_total':None,'reconciliation_error':safe_code(exc)};stop=stop or 'RECONCILIATION_FAILED'
  state.update(campaign=CAMPAIGN,phase=phase,status='PAUSED_LOCKED' if stop else 'CHECKPOINT_LOCKED',enabled=False,max_new=0,finished=finished,reason=stop,attempted_this_run=attempted,skips=skips,plan_sha256=c['plan_sha256'],run=os.environ['GITHUB_RUN_ID'],owner_token=c['owner_token'],research_complete=False)
  if stop:pause(store,state)
  store.create('states/'+phase+'-finished.json',canon(state));store.create('controls/'+phase+'/'+state['status']+'.json',canon(state));store.create('locks/'+phase+'.RELEASED.json',canon(lock));log('STAGE_STATE',state)
 return state

def reservations_equal(store,records):return reconcile(store)[0]==records

def close(store,c):
 require(c['mode']=='CLOSE' and c['enabled'] is False and c['max_new']==0,'CLOSE_DISABLED_REQUIRED');verify_lease(store,c)
 require(store.get('states/CLOSED_LOCKED.json',True) is None,'ALREADY_CLOSED');ingest(store,c)
 records,results,counts,totals=reconcile(store);require(totals['reserved']==c['prior_reserved'],'CLOSE_COUNT');verify_gate(store,c,'CLOSE',len(records))
 complete=c.get('research_complete') is True
 if complete:
  require(totals['unknown']==0,'UNRESOLVED_CANNOT_COMPLETE')
  for phase in PHASES:
   state=read(store,'states/'+phase+'-finished.json');require(state.get('finished') is True and state['status']=='CHECKPOINT_LOCKED','PHASE_NOT_FINISHED')
 else:require(bool(c.get('closure_reason')),'CLOSE_REASON')
 state=dict(campaign=CAMPAIGN,status='CLOSED_LOCKED',enabled=False,max_new=0,approved_total=APPROVED_TOTAL,reserved_total=totals['reserved'],actual_api_attempts_recorded=totals['transmitted_recorded'],success=totals['success'],failed=totals['failed'],unknown=totals['unknown'],unused_locked=APPROVED_TOTAL-totals['reserved'],stage_counts=counts,hard_stage_caps=HARD_CAPS,owner_token=c['owner_token'],research_complete=complete,closure_reason=c.get('closure_reason'),next_new_authorization=0,generation_calls=0,closed_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),run=os.environ['GITHUB_RUN_ID'],commit=os.environ['GITHUB_SHA'])
 store.create('states/CLOSED_LOCKED.json',canon(state));store.create('controls/CLOSED/CLOSED_LOCKED.json',canon(state));log('CLOSED_STATE',state);return state

def export(store,c):
 verify_lease(store,c)
 names={'CONTROL.json','LOCK.json','preflight/PREFLIGHT.json','checks/PREFLIGHT_PROBE.json','preparation/SOURCES.json','preparation/PROMPTS.json','preparation/FREEZE.json','states/CLOSED_LOCKED.json','states/PAUSED_LOCKED.json','controls/CLOSED/CLOSED_LOCKED.json','controls/PAUSED/PAUSED_LOCKED.json','gates/CLOSE.json','selection/C.json','selection/FINAL.json','preparation/OLD_LOCK_EXPECTATIONS.json'}
 for phase,cap in HARD_CAPS.items():
  names.update({'plans/'+phase+'.json','gates/'+phase+'.json','states/'+phase+'-running.json','states/'+phase+'-finished.json','locks/'+phase+'.json','locks/'+phase+'.RELEASED.json'})
  names.update('controls/'+phase+'/'+status+'.json' for status in ('STAGED_LOCKED','CHECKPOINT_LOCKED','PAUSED_LOCKED'))
  for i in range(1,cap+1):names.update(f'{kind}/{phase}-{i:03d}.json' for kind in ('requests','results','skips'))
 for i in range(1,APPROVED_TOTAL+1):names.update({f'budget/{i:04d}.json','locks/after-'+str(i-1)+'.json'})
 source=store.get('preparation/SOURCES.json',True)
 if source:
  names.update(s['origin_result_object'] for s in json.loads(source).get('fixed_first_inputs',[]))
 freeze=store.get('preparation/FREEZE.json',True)
 if freeze:
  for n in json.loads(freeze).get('additional_export_objects',[]):require(n.startswith(('preparation/','evaluation/')) and '..' not in n,'EXPORT_PATH');names.add(n)
 if c.get('package_sha256'):names.add('checks/packages/'+c['package_sha256']+'.json')
 for n in c.get('additional_export_objects',[]):require(n.startswith('evaluation/') and '..' not in n,'EXPORT_PATH');names.add(n)
 ordered=sorted(names)
 with concurrent.futures.ThreadPoolExecutor(max_workers=16) as p:raws=list(p.map(lambda n:store.get(n,True),ordered))
 objects={n:b for n,b in zip(ordered,raws) if b is not None};unmatched=[];root=pathlib.Path(os.environ['RUNNER_TEMP'])/'solo320-spool'
 if root.exists():
  for p in root.rglob('*'):
   if p.is_file():
    n=str(p.relative_to(root));b=p.read_bytes()
    if objects.get(n)!=b:objects['local_spool_unconfirmed_remote/'+n]=b;unmatched.append(n)
 for n in CODE_FILES|{'CONTROL.json'}:objects['execution_code/'+n]=(HERE/n).read_bytes()
 objects['LOCAL_SPOOL_AUDIT.json']=canon({'campaign':CAMPAIGN,'unmatched_local_objects':unmatched})
 manifest={n:{'bytes':len(b),'sha256':sha(b)} for n,b in objects.items()};out=pathlib.Path(os.environ['RUNNER_TEMP'])/'solo320-export.p7m'
 with tempfile.TemporaryDirectory() as td:
  p=pathlib.Path(td)/'raw.zip'
  with zipfile.ZipFile(p,'w',zipfile.ZIP_DEFLATED) as z:
   for n,b in objects.items():z.writestr(n,b)
   z.writestr('MANIFEST.json',canon(manifest))
  subprocess.run(['openssl','cms','-encrypt','-aes256','-binary','-outform','DER','-in',str(p),'-out',str(out),str(HERE/'export-cert.pem')],check=True,capture_output=True)
  store.create('exports/'+c['mode']+'-'+os.environ['GITHUB_RUN_ID']+'.p7m',out.read_bytes())
  log('EXPORT_RECEIPT',{'file':out.name,'objects':len(objects),'plain_sha256':sha(p.read_bytes()),'cipher_sha256':sha(out.read_bytes()),'generation_calls_during_export':0})

def main():
 c=runtime_control();store=RemoteStore();mode=c['mode'];state=None
 try:
  if mode in ('STAGE','EXECUTE'):stage(store,c)
  if mode=='EXECUTE':state=asyncio.run(execute(store,c))
  elif mode=='CLOSE':state=close(store,c)
  elif mode=='PUBLISH':
   require(c['enabled'] is False and c['max_new']==0,'PUBLISH_DISABLED_REQUIRED');verify_lease(store,c)
   objects=unpack(store,c);require(all(n.startswith('evaluation/') for n in objects),'PUBLISH_EVALUATION_ONLY')
   for n,b in objects.items():store.same(n,b)
  else:require(mode in ('STAGE','EXPORT'),'UNAPPROVED_MODE')
 finally:export(store,c)
 if state and state.get('status')=='PAUSED_LOCKED':raise SystemExit(2)
if __name__=='__main__':
 try:main()
 except Exception as exc:log('STOP',{'code':safe_code(exc),'no_retry':True});raise SystemExit(1)
