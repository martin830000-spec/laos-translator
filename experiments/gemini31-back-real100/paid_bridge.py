"""New100 approval, frozen builders; encrypted input/output over existing protected Actions."""
from pathlib import Path
import sys,os,json,hashlib,time,importlib.util,urllib.request,http.client,copy
ROOT=Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT));import controller as c
def module(name,p):
 spec=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
old=module('frozen_bridge',ROOT.parent/'gemini-assets/paid_bridge.py');b=old.b;b.PROTOCOL='gemini31-back-real100-v1'
def guard(plan=None):
 a=b.read(ROOT/'paid-approval.json');f=b.read(ROOT/'paid-config.json');c.require(a['authorized']is True and a['execution_enabled']is True and a['campaign_id']==c.ID and a['approved_limit']==100)
 c.require(a['actual_attempts']==f['prior_actual']and a['plan_sha256']==f['plan_sha256'])
 for name,h in b.read(ROOT/'frozen-files.json').items():c.require(hashlib.sha256((ROOT.parent.parent/name).read_bytes()).hexdigest()==h)
 if plan is not None:c.validate(plan,a);c.require(plan['phase']==f['phase'])
 return a,f
def prepare(state):
 a,f=guard();c.require(not state.exists()and os.environ['GITHUB_RUN_ATTEMPT']=='1')
 issue=b.github('/repos/'+b.REPO+'/issues/'+str(f['issue_number']));c.require(issue['title']==f['title']and issue['state']=='open'and issue['user']['login']==b.OWNER)
 init=json.loads(issue['body']);c.require(init['protocol']==b.PROTOCOL and init['phase']=='init'and len(init['nonce'])==64);b.public_key(init['result_public_key']);state.mkdir(parents=True,mode=0o700)
 h=dict(protocol=b.PROTOCOL,nonce=init['nonce'],run_id=os.environ['GITHUB_RUN_ID'],issue_number=f['issue_number'],commit=os.environ['GITHUB_SHA'],input_public_key=b.keypair(state/'input-private.pem'),result_key_sha256=hashlib.sha256(init['result_public_key'].encode()).hexdigest())
 b.write(state/'init.json',init);b.write(state/'handshake.json',h);print('BACK100 public handshake; generation0',flush=True)
def execute(state):
 a,f=guard();h=b.read(state/'handshake.json');init=b.read(state/'init.json');c.require(os.environ['GITHUB_RUN_ATTEMPT']=='1'and h['commit']==os.environ['GITHUB_SHA']and str(h['run_id'])==os.environ['GITHUB_RUN_ID']);metadata={};worker=None;session=None
 def persist(d):
  dd=copy.deepcopy(d)
  for x in dd.get('slots',[]):
   if x.get('raw'):x.update(old.price(x['raw'],'gemini-3.1-flash-lite'))
  dd.update(phase=f['phase'],model_metadata=metadata,execution={k:h[k]for k in ['run_id','issue_number','commit']},approved_limit=100,per_direction_limit=50,metadata_GET_generation_calls=0,sender_journal_utf8=(state/'once.journal').read_text()if(state/'once.journal').exists()else None)
  b.write(state/'sealed-result.json',b.seal(dd,init['result_public_key'],b.aad_for(h,'result')))
 try:
  until=time.monotonic()+900;plan=None
  while time.monotonic()<until:
   issue=b.github('/repos/'+b.REPO+'/issues/'+str(h['issue_number']));c.require(issue['state']=='open'and issue['title']==f['title']and issue['user']['login']==b.OWNER);body=json.loads(issue['body']);c.require(body['nonce']==init['nonce']and body['result_public_key']==init['result_public_key'])
   if body['phase']=='sealed':plan=b.unseal(body['envelope'],state/'input-private.pem',b.aad_for(h,'input'));break
   c.require(body['phase']=='init');time.sleep(4)
  c.require(plan is not None);guard(plan)
  for tag in f.get('required_tags',[]):b.github('/repos/'+b.REPO+'/git/ref/tags/'+tag)
  b.github('/repos/'+b.REPO+'/git/refs',{'ref':'refs/tags/'+f['tag'],'sha':h['commit']})
  key=os.environ.get('GEMINI_API_KEY');c.require(bool(key));model='gemini-3.1-flash-lite'
  req=urllib.request.Request('https://generativelanguage.googleapis.com/v1beta/models/'+model,headers={'x-goog-api-key':key})
  with urllib.request.build_opener(b.NoRedirect).open(req,timeout=30)as rr:meta=json.loads(rr.read())
  old.validate_metadata(model,'minimal',1024,meta);metadata[model]=meta
  worker=old.Worker();session=old.Session(lambda:http.client.HTTPSConnection('generativelanguage.googleapis.com',timeout=90))
  result=c.run(plan,a,worker,lambda q:session.send(q,{'x-goog-api-key':key,'Content-Type':'application/json'}),state/'once.journal',persist);persist(dict(result,status='PHASE_COMPLETE_REVIEW_REQUIRED'));print(json.dumps(dict(phase=f['phase'],attempts=result['attempts'],status='PHASE_COMPLETE_REVIEW_REQUIRED',retry0=True)),flush=True)
 except Exception as exc:
  if not(state/'sealed-result.json').exists():persist(dict(status='PREFLIGHT_STOP',attempts=0,error_type=type(exc).__name__,slots=[]))
  raise
 finally:
  if session:session.close()
  if worker:worker.close()
if __name__=='__main__':
 try:
  mode=sys.argv[1];state=Path(sys.argv[2]);c.require(mode in ['prepare','execute']);(prepare if mode=='prepare'else execute)(state)
 except Exception as e:print('BACK100 STOP '+type(e).__name__,flush=True);sys.exit(2)
