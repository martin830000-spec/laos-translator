"""VARIANCE320 only. Create-only stage locks and ordinal reservations before HTTP."""
import os,sys,json,pathlib,hashlib,time,datetime,asyncio,concurrent.futures,subprocess,tempfile,zipfile,base64,gzip,threading
from google.cloud import storage
from google.api_core.exceptions import NotFound,PreconditionFailed
from contract import build_payload,assert_back_payload,budget_guard,back_input
from http_sender import make_client,send
HERE=pathlib.Path(__file__).resolve().parent
CAMPAIGN='GPT_LUNA_LF_VARIANCE320_20261110'
PREFIX='research/gemini-model-native500-20261107/gpt-luna-lf-variance320-20261110'
INPUT_KEY='research/gemini-model-native500-20261107/fidelity240-20261108/keys/input-key.pem'
def canon(x):return (json.dumps(x,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode()
def sha(b):return hashlib.sha256(b).hexdigest()
class Store:
 def __init__(self):self.bucket=storage.Client(project='gen-lang-client-0422436907').bucket('lao-translator-src-460077888071')
 def get(self,n,optional=False):
  try:return self.bucket.blob(PREFIX+'/'+n).download_as_bytes(timeout=30,retry=None)
  except NotFound:
   if optional:return None
   raise
 def create(self,n,b):
  self.bucket.blob(PREFIX+'/'+n).upload_from_string(b,if_generation_match=0,timeout=30,retry=None)
  assert self.get(n)==b,'CREATE_READBACK_MISMATCH'
 def control(self,obj):
  assert obj['campaign']==CAMPAIGN
  key='controls/'+obj.get('phase','CLOSED')+'/'+obj['status']+'.json'
  self.put(key,canon(obj));assert self.get(key)==canon(obj)
 def put(self,n,b):
  try:self.create(n,b)
  except PreconditionFailed:assert self.get(n)==b,'IMMUTABLE_OBJECT_MISMATCH'
def reservations(s):
 with concurrent.futures.ThreadPoolExecutor(max_workers=32) as pool:raw=list(pool.map(lambda i:s.get(f'budget/{i:04d}.json',True),range(1,321)))
 rs=[json.loads(x) for x in raw if x is not None]
 assert all(raw[:len(rs)]) and not any(raw[len(rs):]),'NONCONTIGUOUS_BUDGET'
 assert len({r['slot'] for r in rs})==len(rs)
 assert all(r['campaign']==CAMPAIGN and r['ordinal']==i+1 for i,r in enumerate(rs))
 return rs
def load_control():
 assert os.environ['GITHUB_REF']=='refs/heads/research/gemini-model-native500-20261107'
 assert os.environ['GITHUB_RUN_ATTEMPT']=='1' and os.environ['GITHUB_ACTOR']=='martin830000-spec'
 c=json.loads((HERE/'CONTROL.json').read_bytes());assert c['campaign']==CAMPAIGN
 return c
def plan(s,c):
 raw=s.get('plans/'+c['plan_sha256']+'.json');assert sha(raw)==c['plan_sha256']
 p=json.loads(raw);assert p['campaign']==CAMPAIGN and p['phase']==c['phase']
 assert len({t['slot'] for t in p['slots']})==len(p['slots'])
 source_raw=s.get(p.get('source_split_object','preparation/SOURCE_SPLIT.json'));assert sha(source_raw)==p['source_split_sha256'],'SOURCE_FREEZE_CHANGED'
 source=json.loads(source_raw)['selected']
 allowed={x['id']:x for x in source if x['stage']==('FINAL' if c['phase'] in ('D','E1','E2') else 'DEV')}
 for t in p['slots']:
  if 'input' in t:
   assert t['source_id'] in allowed and t['input']==allowed[t['source_id']]['source']
  assert t['variant'] in json.loads((HERE/'prompts.json').read_bytes())
 assert {m:sum(t['model']==m for t in p['slots']) for m in c['model_plan']}==c['model_plan']
 assert sha((HERE/'prompts.json').read_bytes())==c['prompt_file_sha256']
 for name,h in c['code_sha256'].items():assert sha((HERE/name).read_bytes())==h,'CODE_FREEZE_CHANGED'
 return p
def stage(s,c):
 assert not c['enabled'] and c['mode']=='STAGE'
 with tempfile.TemporaryDirectory() as td:
  t=pathlib.Path(td);(t/'key.pem').write_bytes(s.bucket.blob(INPUT_KEY).download_as_bytes(timeout=30,retry=None));(t/'key.pem').chmod(0o600)
  (t/'in.p7m').write_bytes(base64.b64decode((HERE/'input.p7m.b64').read_bytes()))
  subprocess.run(['openssl','cms','-decrypt','-binary','-inform','DER','-in',str(t/'in.p7m'),'-inkey',str(t/'key.pem'),'-out',str(t/'input.gz')],check=True,capture_output=True)
  raw=gzip.decompress((t/'input.gz').read_bytes());assert sha(raw)==c['package_sha256'];package=json.loads(raw)
  assert package['campaign']==CAMPAIGN
  for n,v in package['objects'].items():
   assert n.startswith(('plans/','preparation/')) and '..' not in n and n.endswith('.json')
   s.put(n,canon(v))
  p=plan(s,c);assert len(p['slots'])==c['max_new']
  if c['phase']=='A':assert not reservations(s),'EXISTING_CAMPAIGN_BUDGET'
  s.put('checks/stage-'+c['phase']+'.json',canon({'package_sha256':sha(raw),'objects':list(package['objects']),'generation_calls':0}))
 s.control(dict(campaign=CAMPAIGN,phase=c['phase'],status='STAGED_LOCKED',enabled=False,max_new=0,reserved_total=len(reservations(s)),plan_sha256=c['plan_sha256']))
 print(json.dumps({'phase':c['phase'],'staged':True,'generation_calls':0}))
def totals(s,rs):
 by={m:{'reserved':0,'success':0,'failed':0,'unknown':0} for m in ['gpt-6-luna']}
 with concurrent.futures.ThreadPoolExecutor(max_workers=32) as pool:raws=list(pool.map(lambda r:s.get('results/'+r['slot']+'.json',True),rs))
 for r,raw in zip(rs,raws):
  t=by[r['model']];t['reserved']+=1
  if raw is None:t['unknown']+=1
  else:
   obj=json.loads(raw);t['unknown' if obj.get('unknown') else 'success' if obj['success'] else 'failed']+=1
 return by
async def execute(s,c):
 assert c['enabled'] and c['mode']=='EXECUTE' and c['deadline_epoch']>time.time()
 assert c['backup_verified'] and os.environ.get('OPENAI_API_KEY')
 p=plan(s,c);prompts=json.loads((HERE/'prompts.json').read_bytes());phase=c['phase']
 assert len(p['slots'])==c['max_new']
 rs=reservations(s);assert len(rs)==c['prior_reserved']
 if c['phase']=='A':assert not rs
 else:
  prior_state=json.loads(s.get(c['previous_state_object']))
  assert not prior_state['enabled'] and prior_state['max_new']==0 and prior_state['reserved_total']==len(rs)
  assert s.get('locks/'+c['previous_phase']+'.RELEASED.json') is not None
 assert c['model_plan']=={'gpt-6-luna':len(p['slots'])}
 assert all(v['unknown']==0 for v in totals(s,rs).values()),'UNKNOWN_STOP'
 from contract import CAPS,stage_root
 assert sum(stage_root(r['stage'])==stage_root(phase) for r in rs)+len(p['slots'])<=CAPS[stage_root(phase)],'STAGE_CAP'
 assert s.get('states/CLOSED_LOCKED.json',True) is None,'CLOSED_STOP'
 assert len(rs)+len(p['slots'])<=320
 # Fixed, immutable per-stage lock. Any duplicate or unresolved old lock blocks execution.
 lock={'run':os.environ['GITHUB_RUN_ID'],'commit':os.environ['GITHUB_SHA'],'phase':phase,'plan_sha256':c['plan_sha256']}
 s.create('locks/after-'+str(len(rs))+'.json',canon(lock))
 s.create('locks/'+phase+'.json',canon(lock))
 # Reconcile again under our lock. Never replay an unknown reservation.
 assert reservations(s)==rs
 assert not {t['slot'] for t in p['slots']} & {r['slot'] for r in rs}
 with concurrent.futures.ThreadPoolExecutor(max_workers=32) as pool:existing=list(pool.map(lambda t:s.get('results/'+t['slot']+'.json',True),p['slots']))
 assert not any(x is not None for x in existing),'EXISTING_SLOT_RESULT'
 s.put('states/'+phase+'-running.json',canon(dict(lock,enabled=True,max_new=len(p['slots']),reserved_total=len(rs))))
 remote_control=json.loads(s.get('controls/'+phase+'/STAGED_LOCKED.json'));assert not remote_control['enabled'] and remote_control['max_new']==0
 assert remote_control['campaign']==CAMPAIGN and remote_control.get('plan_sha256')==c['plan_sha256']
 s.control(dict(remote_control,enabled=True,max_new=len(p['slots']),status='RUNNING',reserved_total=len(rs)))
 progress=[time.monotonic()];done=threading.Event()
 def watch():
  while not done.wait(1):
   if time.monotonic()-progress[0]>180:
    print('NO_PROGRESS_180S_STOP_UNKNOWN_RECONCILIATION_REQUIRED',flush=True);os._exit(73)
 threading.Thread(target=watch,daemon=True).start()
 started=time.monotonic();attempted=0;finished=False;disabled={};streak={};skips=[]
 try:
  async with make_client() as client:
   for t in p['slots']:
    assert c['deadline_epoch']>time.time(),'ACTIVATION_EXPIRED'
    if time.monotonic()-started>1080:disabled['ALL']='STAGE_18MIN_BOUND' 
    slot_started=time.monotonic()
    model=t['model'];path=t['path'];slot=t['slot'];parent=None
    if model in disabled or 'ALL' in disabled:
     reason=disabled.get(model,disabled.get('ALL'));skips.append(slot);s.put('skips/'+slot+'.json',canon({'reason':reason,'unattempted':True}));continue
    if t.get('reference_first_id'):
     refs=json.loads(s.get('preparation/HISTORICAL_FIRST.json'));parent=refs[t['reference_first_id']]
     assert parent['source_id']==t['source_id'] and parent['path'][0]==path[0] and path.endswith('B')
     text=back_input(parent);assert text is not None
    elif 'parent_first_id' in t:
     raw=s.get('results/'+t['parent_first_id']+'.json',True);parent=json.loads(raw) if raw else None;text=back_input(parent)
     if text is None:
      skips.append(slot);s.put('skips/'+slot+'.json',canon({'reason':'NO_TECHNICALLY_COMPLETE_FIRST','unattempted':True}));continue
    else:
     text=t['input'];assert sha(text.encode())==t['input_sha256']
    pp=prompts[t['variant']];payload=build_payload(model,t['effort'],path,text,pp)
    if path.endswith('B'):assert_back_payload(payload,text,pp,path)
    condition=sha(canon({'payload':payload,'source_id':t['source_id'],'variant':t['variant']}))
    repeats=sum(r.get('condition_sha256')==condition for r in rs);assert repeats<5,'REPEAT_CAP'
    if 'repeat_index' in t:assert repeats+1==t['repeat_index'],'REPEAT_INDEX'
    rec=budget_guard(rs,slot,model,phase);rec.update(condition_sha256=condition,repeat_index=repeats+1);rec.update(campaign=CAMPAIGN,ordinal=len(rs)+1,path=path,request_sha256=sha(canon(payload)),input_sha256=sha(text.encode()),run=os.environ['GITHUB_RUN_ID'])
    # Never adopt an existing reservation as our own, even if bytes happen to match.
    s.create(f"budget/{rec['ordinal']:04d}.json",canon(rec));rs.append(rec)
    result=await send(client,payload,os.environ['OPENAI_API_KEY']);attempted+=1
    result['unknown']=bool(result.get('exception'));result['repeat_index']=repeats+1;result['condition_sha256']=condition
    result.update(reference_first_id=t.get('reference_first_id'),variant=t['variant'],slot=slot,stage=phase,campaign=CAMPAIGN,model=model,path=path,effort=t['effort'],request=payload,request_sha256=rec['request_sha256'],input_sha256=rec['input_sha256'],source_id=t.get('source_id'),parent_first_id=t.get('parent_first_id'),chain_id=t.get('chain_id'),ordinal=rec['ordinal'])
    if parent:
     result['back_input_equals_displayed_first']=text==parent['display_text']
     result['displayed_first_sha256']=sha(parent['display_text'].encode())
     if parent.get('stage')==phase and not t.get('reference_first_id'):
      result['chain_wall_seconds']=result['t_request_start_monotonic']+result['t_response_done']-parent['t_request_start_monotonic']
      result['first_done_to_back_start_seconds']=result['t_request_start_monotonic']-(parent['t_request_start_monotonic']+parent['t_response_done'])
     else:result['fixed_first_cross_run']=True
    s.create('results/'+slot+'.json',canon(result))
    s.create(f"checkpoints/attempt-{len(rs):04d}.json",canon({'slot':slot,'reserved':len(rs),'result_sha256':sha(canon(result))}))
    progress[0]=time.monotonic()
    if time.monotonic()-slot_started>60:disabled['ALL']='SLOT_WALL_BOTTLENECK_60S'
    if not result['success']:disabled['ALL']='TECHNICAL_FAILURE_STOP_NO_RETRY'
    http=result['http_status'];code=(result.get('http_error') or {}).get('error',{}).get('code')
    if not result['success']:
     sig=str(http)+'/'+str(code)+'/'+str(result.get('exception'));streak.setdefault(model,[]).append(sig)
     if http==401 or code=='insufficient_quota':disabled['ALL']='AUTH_OR_QUOTA'
     elif http in (400,403,404):disabled[model]='REQUEST_OR_ACCESS_ERROR'
     elif len(streak[model])>=2 and streak[model][-1]==streak[model][-2]:disabled[model]='REPEATED_TECHNICAL_ERROR'
    else:streak[model]=[]
    print(json.dumps({'slot':slot,'reserved':len(rs),'success':result['success'],'http':http}),flush=True)
  finished=True
 finally:
  done.set()
  by=totals(s,rs)
  state={'campaign':CAMPAIGN,'enabled':False,'max_new':0,'status':'PAUSED_LOCKED' if any(v['unknown'] or v['failed'] for v in by.values()) or disabled else 'CHECKPOINT_LOCKED','research_complete':False,'phase':phase,'reserved_total':len(rs),'cumulative_actual':len(rs),'success':sum(v['success'] for v in by.values()),'failed':sum(v['failed'] for v in by.values()),'unknown':sum(v['unknown'] for v in by.values()),'unused_locked':320-len(rs),'models':by,'attempted_this_run':attempted,'finished':finished,'skips':skips,'disabled':disabled,'run':os.environ['GITHUB_RUN_ID']}
  s.control(dict(state,plan_sha256=c['plan_sha256']));s.create('states/'+phase+'-finished.json',canon(state));s.create('locks/'+phase+'.RELEASED.json',canon(lock));print('STAGE_STATE='+json.dumps(state))
def close(s,c):
 assert not c['enabled'] and c['max_new']==0 and c['mode']=='CLOSE'
 rs=reservations(s);by=totals(s,rs)
 previous=json.loads(s.get('states/'+c['phase']+'-finished.json'))
 assert previous['reserved_total']==len(rs) and not previous['enabled']
 assert s.get('locks/'+c['phase']+'.RELEASED.json') is not None
 state=dict(campaign=CAMPAIGN,status='CLOSED_LOCKED',enabled=False,max_new=0,models=by,reserved_total=len(rs),success=sum(v['success'] for v in by.values()),failed=sum(v['failed'] for v in by.values()),unknown=sum(v['unknown'] for v in by.values()),unused_locked={m:320-v['reserved'] for m,v in by.items()},run=os.environ['GITHUB_RUN_ID'],generation_calls=0)
 assert state['unknown']==0 and state['failed']==0
 s.control(state);s.create('states/CLOSED_LOCKED.json',canon(state));assert json.loads(s.get('states/CLOSED_LOCKED.json'))==state
 print('CLOSED_STATE='+json.dumps(state))
def export(s,c):
 p=plan(s,c);rs=reservations(s)
 names=['checks/final-publication.json','preparation/FINAL_SCHEDULE.json','preparation/FINAL_EVALUATION.json','CONTROL.json','controls/CLOSED/CLOSED_LOCKED.json','states/CLOSED_LOCKED.json',p.get('source_split_object','preparation/SOURCE_SPLIT.json'),'preparation/SOURCE_SPLIT.json','preparation/HYPOTHESES.json','preparation/HISTORICAL_FIRST.json','plans/'+c['plan_sha256']+'.json','preparation/BASE_COPY.json']
 for ph in c['phases']:
  names += ['preparation/QUALITY_BEFORE_'+ph+'.json']
  names += ['controls/'+ph+'/'+status+'.json' for status in ['STAGED_LOCKED','RUNNING','CHECKPOINT_LOCKED','PAUSED_LOCKED']]
  names += ['checks/stage-'+ph+'.json','states/'+ph+'-running.json','states/'+ph+'-finished.json','locks/'+ph+'.json','locks/'+ph+'.RELEASED.json']
 for r in rs:names += [f"budget/{r['ordinal']:04d}.json",'results/'+r['slot']+'.json',f"checkpoints/attempt-{r['ordinal']:04d}.json"]
 names += ['skips/'+t['slot']+'.json' for t in p['slots']]
 objs={}
 with concurrent.futures.ThreadPoolExecutor(max_workers=32) as pool:
  for n,b in zip(names,pool.map(lambda n:s.get(n,True),names)):
   if b is not None:objs[n]=b
 manifest={n:{'bytes':len(b),'sha256':sha(b)} for n,b in objs.items()}
 out=pathlib.Path(os.environ['RUNNER_TEMP'])/'variance320-export.p7m'
 with tempfile.TemporaryDirectory() as td:
  zpath=pathlib.Path(td)/'raw.zip'
  with zipfile.ZipFile(zpath,'w',zipfile.ZIP_DEFLATED) as z:
   for n,b in objs.items():z.writestr(n,b)
   z.writestr('MANIFEST.json',canon(manifest))
  subprocess.run(['openssl','cms','-encrypt','-aes256','-binary','-outform','DER','-in',str(zpath),'-out',str(out),str(HERE/'export-cert.pem')],check=True,capture_output=True)
  key='exports/'+c['phase']+'-'+os.environ['GITHUB_RUN_ID']+'.p7m';s.create(key,out.read_bytes());out.write_bytes(s.get(key))
  print('EXPORT_RECEIPT='+json.dumps({'key':key,'cipher_sha256':sha(out.read_bytes()),'plain_sha256':sha(zpath.read_bytes()),'objects':len(objs),'generation_calls':0}))
def publish_final(s,c):
 assert not c['enabled'] and c['max_new']==0 and c['mode']=='CLOSE'
 old=s.bucket.blob('research/gemini-model-native500-20261107/gpt-luna-terra-mechanism1000-20261110/states/CLOSED_LOCKED.json').download_as_bytes(timeout=30,retry=None)
 assert sha(old)=='323c3e727c1aee812d23423ea1ed885db50a39dcf4203a4c1bf47810f366290e','OLD_CLOSED_CHANGED'
 with tempfile.TemporaryDirectory() as td:
  t=pathlib.Path(td);(t/'key.pem').write_bytes(s.bucket.blob(INPUT_KEY).download_as_bytes(timeout=30,retry=None));(t/'key.pem').chmod(0o600)
  (t/'in.p7m').write_bytes(base64.b64decode((HERE/'input.p7m.b64').read_bytes()))
  subprocess.run(['openssl','cms','-decrypt','-binary','-inform','DER','-in',str(t/'in.p7m'),'-inkey',str(t/'key.pem'),'-out',str(t/'input.gz')],check=True,capture_output=True)
  raw=gzip.decompress((t/'input.gz').read_bytes());assert sha(raw)==c['package_sha256'];obj=json.loads(raw);assert obj['campaign']==CAMPAIGN
  assert set(obj['objects'])=={'preparation/FINAL_EVALUATION.json'}
  for name,val in obj['objects'].items():s.put(name,canon(val))
 receipt={'old_closed_sha256':sha(old),'old_reserved':776,'final_evaluation_sha256':sha(s.get('preparation/FINAL_EVALUATION.json')),'generation_calls':0,'run':os.environ['GITHUB_RUN_ID']}
 s.create('checks/final-publication.json',canon(receipt));print('FINAL_PUBLICATION='+json.dumps(receipt))

if __name__=='__main__':
 c=load_control();s=Store();mode=sys.argv[1]
 if mode=='STAGE':stage(s,dict(c,enabled=False,mode='STAGE'))
 elif mode=='EXECUTE':asyncio.run(execute(s,c))
 elif mode=='EXPORT':export(s,c)
 elif mode=='CLOSE':close(s,c)
 elif mode=='PUBLISH':publish_final(s,c)
 else:raise ValueError('UNAPPROVED_MODE')
