"""SCREEN160 only. Every generation goes through durable reserve then send()."""
import os,sys,json,pathlib,hashlib,time,datetime,asyncio,concurrent.futures,subprocess,tempfile,zipfile,base64,gzip,platform,importlib.metadata
from google.cloud import storage
from google.api_core.exceptions import NotFound,PreconditionFailed
from contract import build_payload,assert_back_payload,budget_guard
from http_sender import make_client,send
HERE=pathlib.Path(__file__).resolve().parent
CAMPAIGN='GPT_LUNA_TERRA_SCREEN160_20261109'
PREFIX='research/gemini-model-native500-20261107/gpt-luna-terra-screen160-20261109'
INPUT_KEY='research/gemini-model-native500-20261107/fidelity240-20261108/keys/input-key.pem'
def canon(x):return (json.dumps(x,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode()
def sha(b):return hashlib.sha256(b).hexdigest()
class Store:
 def __init__(self):self.bucket=storage.Client(project='gen-lang-client-0422436907').bucket('lao-translator-src-460077888071')
 def get(self,n,optional=False):
  try:return self.bucket.blob(PREFIX+'/'+n).download_as_bytes(timeout=30)
  except NotFound:
   if optional:return None
   raise
 def put(self,n,b):
  o=self.bucket.blob(PREFIX+'/'+n)
  try:o.upload_from_string(b,if_generation_match=0,timeout=30)
  except PreconditionFailed:pass
  assert self.get(n)==b,'IMMUTABLE_OBJECT_MISMATCH'
 def acquire(self,phase):
  if phase=='C':assert self.get('locks/AB.RELEASED.json') is not None
  o=self.bucket.blob(PREFIX+'/locks/'+phase+'.json');o.upload_from_string(canon({'run':os.environ['GITHUB_RUN_ID'],'sha':os.environ['GITHUB_SHA']}),if_generation_match=0,timeout=30);o.reload(timeout=30);return {'phase':phase,'generation':o.generation,'run':os.environ['GITHUB_RUN_ID']}
 def release(self,lock):self.put('locks/'+lock['phase']+'.RELEASED.json',canon(lock))
def config():
 assert os.environ['GITHUB_REF']=='refs/heads/research/gemini-model-native500-20261107'
 assert os.environ['GITHUB_RUN_ATTEMPT']=='1' and os.environ['GITHUB_ACTOR']=='martin830000-spec'
 return json.loads((HERE/'CONTROL.json').read_bytes())
def reservations(s):
 with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:a=list(pool.map(lambda i:s.get(f'budget/{i:04d}.json',True),range(1,161)))
 r=[json.loads(x) for x in a if x is not None];assert all(x is not None for x in a[:len(r)]) and not any(x is not None for x in a[len(r):]);assert len({x['slot'] for x in r})==len(r);return r
def totals(s,rs):
 by={m:{'attempted':0,'success':0,'failed':0,'unknown':0,'unused_locked':80} for m in ['gpt-6-luna','gpt-6.1-terra']}
 for x in rs:
  d=by[x['model']];d['attempted']+=1;d['unused_locked']-=1;b=s.get('results/'+x['slot']+'.json',True)
  if b is None:d['unknown']+=1
  else:
   r=json.loads(b);d['success' if r.get('success') else 'failed']+=1
 return by
def stage(s,c):
 assert not json.loads((HERE/'config.json').read_bytes())['enabled']
 with tempfile.TemporaryDirectory() as td:
  p=pathlib.Path(td);(p/'key.pem').write_bytes(s.bucket.blob(INPUT_KEY).download_as_bytes(timeout=30));(p/'key.pem').chmod(0o600);(p/'in.p7m').write_bytes(base64.b64decode((HERE/'input.p7m.b64').read_bytes()))
  subprocess.run(['openssl','cms','-decrypt','-binary','-inform','DER','-in',str(p/'in.p7m'),'-inkey',str(p/'key.pem'),'-out',str(p/'input.gz')],check=True,capture_output=True)
  raw=gzip.decompress((p/'input.gz').read_bytes());assert sha(raw)==c['package_sha256'];package=json.loads(raw)
  assert package['campaign']==CAMPAIGN
  prompts=json.loads((HERE/'prompts.json').read_bytes());freeze=json.loads((HERE/'PROMPT_FREEZE.json').read_bytes())
  assert {k:sha(v.encode()) for k,v in prompts.items()}==freeze['sha256_by_path']
  for name,plan in package['objects'].items():
   if name.startswith('plans/'):
    assert sha(canon(plan))==name.removeprefix('plans/').removesuffix('.json')
    assert len({t['slot'] for t in plan['slots']})==len(plan['slots'])
    for t in plan['slots']:
     text=t.get('input','FREE_SYNTHETIC_FIRST ລາວ')
     payload=build_payload(t['model'],t['effort'],t['path'],text,prompts)
     if t['path'].endswith('B'):assert_back_payload(payload,text,prompts,t['path'])
  for n,v in package['objects'].items():
   assert n.startswith(('plans/','checkpoints/')) and '..' not in n and n.endswith('.json')
   s.put(n,canon(v))
  s.put('checks/stage-'+c['phase']+'.json',canon({'phase':c['phase'],'package_sha256':sha(raw),'generation_calls':0,'objects':list(package['objects'])}))
 # Exercise a separate synthetic create-only guard, never a paid reservation.
 obj=s.bucket.blob(PREFIX+'/readiness/atomic-guard-'+c['phase']+'.json');obj.upload_from_string(b'SYNTHETIC',if_generation_match=0,timeout=30);obj.reload(timeout=30)
 try:
  obj.upload_from_string(b'DUPLICATE',if_generation_match=0,timeout=30)
  raise AssertionError('GCS_DUPLICATE_GUARD_FAILED')
 except PreconditionFailed:pass
 assert obj.download_as_bytes(timeout=30)==b'SYNTHETIC'
 s.put('checks/atomic-'+c['phase']+'.json',canon({'duplicate_create_rejected':True,'generation_calls':0}))
 print(json.dumps({'stage':c['phase'],'objects':len(package['objects']),'generation_calls':0}))
async def execute(s,c):
 cfg=json.loads((HERE/'config.json').read_bytes());assert cfg['enabled'] and cfg['max_new']==c['max_new'] and cfg['campaign']==CAMPAIGN and c['deadline_epoch']>time.time()
 assert c['phase'] in ('AB','C') and bool(os.environ.get('OPENAI_API_KEY'))
 prompts=json.loads((HERE/'prompts.json').read_bytes());planraw=s.get('plans/'+c['plan_sha256']+'.json');assert sha(planraw)==c['plan_sha256'];plan=json.loads(planraw)
 assert plan['campaign']==CAMPAIGN and len(plan['slots'])==c['max_new'];assert len({x['slot'] for x in plan['slots']})==len(plan['slots'])
 key=os.environ['OPENAI_API_KEY'];lock=s.acquire(c['phase']);rs=reservations(s);prior=len(rs);assert prior==c['prior_actual'];assert len(rs)+c['max_new']<=160
 state=json.loads(s.get(c.get('previous_state_object','STATE.json')));assert state['cumulative_actual']==prior
 assert s.get('recovery/legacy-lock-abandoned-zero.json') is not None
 state=cfg.copy();state['status']='RUNNING';state['phase']=c['phase'];s.put('states/'+c['phase']+'-running.json',canon(state))
 meta={'phase':c['phase'],'run':os.environ['GITHUB_RUN_ID'],'sha':os.environ['GITHUB_SHA'],'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'python':platform.python_version(),'httpx':importlib.metadata.version('httpx'),'concurrency':1,'connection_reuse':True,'http_retries':0,'sdk':'No OpenAI SDK; official Responses HTTP via httpx','runner':os.environ.get('RUNNER_OS'),'runner_region':'Read GitHub hosted runner job header; not assumed'}
 s.put('runs/'+c['phase']+'/START.json',canon(meta));disabled={};streak={};attempted_now=0;all_done=False
 try:
  async with make_client() as client:
   for task in plan['slots']:
    slot=task['slot'];model=task['model'];effort=task['effort'];path=task['path'];pair=model+'|'+effort
    assert model in ['gpt-6-luna','gpt-6.1-terra'] and effort in ('none','low') and path in prompts
    if any(x['slot']==slot for x in rs):continue
    if s.get('skips/'+slot+'.json',True) is not None:continue
    if pair in disabled or model in disabled or 'ALL' in disabled:
     s.put('skips/'+slot+'.json',canon({'slot':slot,'state':'UNATTEMPTED_LOCKED','reason':disabled.get(pair,disabled.get(model,disabled.get('ALL')))}));continue
    parent=None
    if c['phase']=='AB' and task['phase']=='FIRST':text=task['input']
    elif c['phase']=='AB':
     pb=s.get('results/'+task['parent_first_id']+'.json',True)
     if pb is None or not json.loads(pb).get('success'):
      s.put('skips/'+slot+'.json',canon({'slot':slot,'state':'DEPENDENT_SKIPPED','reason':'NO_COMPLETED_FIRST'}));continue
     parent=json.loads(pb);text=parent['display_text']
    else:
     text=task['input'];assert sha(text.encode())==task['displayed_first_sha256']
    payload=build_payload(model,effort,path,text,prompts)
    if path.endswith('B'):assert_back_payload(payload,text,prompts,path)
    record=budget_guard(rs,slot,model);record.update(campaign=CAMPAIGN,phase=c['phase'],path=path,effort=effort,request_sha256=sha(canon(payload)),input_sha256=sha(text.encode()),parent_first_id=task.get('parent_first_id'),ordinal=len(rs)+1,request_reserved_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
    s.put(f'budget/{len(rs)+1:04d}.json',canon(record));rs.append(record)
    # From this point any process death is consumed/unknown and must never be replayed.
    r=await send(client,payload,key);attempted_now+=1
    r.update(slot=slot,campaign=CAMPAIGN,phase=c['phase'],path=path,model=model,effort=effort,request=payload,request_sha256=record['request_sha256'],input_sha256=record['input_sha256'],parent_first_id=task.get('parent_first_id'),chain_id=task.get('chain_id'),source_id=task.get('source_id'),ordinal=record['ordinal'])
    if parent:
     r['chain_wall_seconds']=r['t_request_start_monotonic']+r['t_response_done']-parent['t_request_start_monotonic']
     r['first_done_to_back_start_seconds']=r['t_request_start_monotonic']-(parent['t_request_start_monotonic']+parent['t_response_done'])
     r['back_input_equals_displayed_first']=payload['input']==parent['display_text']
    s.put('results/'+slot+'.json',canon(r))
    # Persist a compact durable checkpoint immediately after each full raw response.
    s.put(f'checkpoints/attempt-{len(rs):04d}.json',canon({'reserved_count':len(rs),'slot':slot,'success':r['success'],'model':model,'effort':effort,'raw_sha256':sha(canon(r))}))
    error=(r.get('http_error') or {}).get('error',{});code=error.get('code');http=r.get('http_status')
    if not r['success']:
     signature=str(http)+'/'+str(code)+'/'+str(r.get('exception'))+'/'+str(r.get('terminal'));streak[pair]=streak.get(pair,[])+[signature]
     if code=='model_not_found':disabled[model]='model_not_found'
     elif http==400:disabled[pair]='HTTP400_PARAMETER_OR_REQUEST_ERROR'
     elif http==401 or code=='insufficient_quota':disabled['ALL']='AUTH_OR_QUOTA'
     elif http==403:disabled[model]='HTTP403_ACCESS'
     elif len(streak[pair])>=2 and streak[pair][-1]==streak[pair][-2]:disabled[pair]='REPEATED_TECHNICAL_ERROR'
    else:streak[pair]=[]
    print(json.dumps({'slot':slot,'attempted':len(rs),'success':r['success'],'http_status':http}),flush=True)
  all_done=True
 finally:
  by=totals(s,rs);end={'phase':c['phase'],'prior_actual':prior,'attempted_new':attempted_now,'reserved_total':len(rs),'models':by,'disabled':disabled,'finished':all_done,'run':os.environ['GITHUB_RUN_ID']}
  s.put('runs/'+c['phase']+'/FINISH.json',canon(end))
  state.update(enabled=False,max_new=0,status='CHECKPOINT_LOCKED',cumulative_actual=len(rs),unused_locked=160-len(rs),models_ledger=by)
  s.put('states/'+c['phase']+'-finished.json',canon(state));s.release(lock)
def export(s,c):
 rs=reservations(s);names=['STATE.json','readiness/synthetic.json']+[f'budget/{i:04d}.json' for i in range(1,len(rs)+1)]
 for ph in ['AB','C']:
  names += ['runs/'+ph+'/START.json','runs/'+ph+'/FINISH.json','checks/stage-'+ph+'.json','states/'+ph+'-running.json','states/'+ph+'-finished.json','locks/'+ph+'.json','locks/'+ph+'.RELEASED.json']
 names += ['LOCK.json','recovery/legacy-lock-abandoned-zero.json','checks/append-only.json']
 for i in range(1,161):names += [f'results/S{i:03d}.json',f'skips/S{i:03d}.json',f'checkpoints/attempt-{i:04d}.json']
 names+=c.get('export_objects',[])
 objs={}
 with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
  for n,b in zip(names,pool.map(lambda n:s.get(n,True),names)):
   if b is not None:objs[n]=b
 manifest={n:{'bytes':len(b),'sha256':sha(b)} for n,b in objs.items()}
 out=pathlib.Path(os.environ['RUNNER_TEMP'])/'screen160-export.p7m'
 with tempfile.TemporaryDirectory() as td:
  zp=pathlib.Path(td)/'raw.zip'
  with zipfile.ZipFile(zp,'w',zipfile.ZIP_DEFLATED) as z:
   for n,b in objs.items():z.writestr(n,b)
   z.writestr('MANIFEST.json',canon(manifest))
  subprocess.run(['openssl','cms','-encrypt','-aes256','-binary','-outform','DER','-in',str(zp),'-out',str(out),str(HERE/'export-cert.pem')],check=True,capture_output=True)
 print(json.dumps({'exported_objects':len(objs),'ciphertext_sha256':sha(out.read_bytes()),'generation_calls':0}))
if __name__=='__main__':
 c=config();s=Store();mode=sys.argv[1] if len(sys.argv)>1 else c['mode']
 if mode=='STAGE':stage(s,c)
 elif mode=='EXECUTE':asyncio.run(execute(s,c))
 elif mode=='EXPORT':export(s,c)
 elif mode=='CHECK_APPEND_ONLY':
  assert not json.loads((HERE/'config.json').read_bytes())['enabled']
  rs=reservations(s);assert not rs
  old=json.loads(s.get('LOCK.json'));assert old['run']=='42512297440' and old['sha']=='5258cbccde82a2381438267719ec0b291083af1a'
  assert s.get('locks/AB.json',True) is None
  s.put('recovery/legacy-lock-abandoned-zero.json',canon({'old_lock':old,'reservations':0,'reason':'Prior finished Actions failed before any budget reservation; append-only recovery, no deletion or replay','confirmed_failed_run':42512297440}))
  s.put('checks/append-only.json',canon({'only_create_and_get':True,'generation_calls':0,'state_no_overwrite':True,'legacy_lock_preserved':True}))
  print(json.dumps({'append_only_readiness':'PASS','generation_calls':0}))
 else:raise ValueError('MODE_NOT_ALLOWED')
