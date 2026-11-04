"""New scope-approved encrypted one-time phase. Existing crypto only; no old sender calls."""
from pathlib import Path
import importlib.util,sys,os,json,time,hashlib,subprocess,urllib.request,urllib.error,http.client,copy
ROOT=Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT))
import controller as c
from preflight import validate_metadata
from transport import Session
def module(name,path):
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
b=module('crypto_only',ROOT.parent/'s47-realuse16/run.py');b.PROTOCOL='gemini-assets-open-v1'
def cfg():return b.read(ROOT/'paid-config.json')
def guard(plan=None):
 a=b.read(ROOT/'paid-approval.json');f=cfg();b.check(a['campaign_id']==c.ID and a['authorization_mode']=='unbounded-within-scope'and a['approved_limit']is None and a['authorized']is True and a['execution_enabled']is True)
 b.check(type(a['actual_attempts'])is int and a['actual_attempts']==f['prior_actual']and 0<=a['actual_attempts'])
 if plan is not None:
  c.validate(plan);b.check(plan['phase']==f['phase']and len(plan['tasks'])==f['planned_task_count']==a['planned_task_count'])
  b.check(c.digest(plan)==a['plan_sha256']==f['plan_sha256'])
 return a,f
def prepare(state):
 a,f=guard();b.check(not state.exists()and os.environ['GITHUB_RUN_ATTEMPT']=='1')
 issue=b.github('/repos/'+b.REPO+'/issues/'+str(f['issue_number']));b.check(issue['title']==f['title']and issue['state']=='open'and issue['user']['login']==b.OWNER)
 init=json.loads(issue['body']);b.check(init['protocol']==b.PROTOCOL and init['phase']=='init'and len(init['nonce'])==64);b.public_key(init['result_public_key']);state.mkdir(parents=True,mode=0o700)
 h=dict(protocol=b.PROTOCOL,nonce=init['nonce'],run_id=os.environ['GITHUB_RUN_ID'],issue_number=f['issue_number'],commit=os.environ['GITHUB_SHA'],input_public_key=b.keypair(state/'input-private.pem'),result_key_sha256=hashlib.sha256(init['result_public_key'].encode()).hexdigest())
 b.write(state/'init.json',init);b.write(state/'handshake.json',h);print('GEMINI_ASSETS public handshake; generated0',flush=True)
class Worker:
 def __init__(self):self.p=subprocess.Popen(['node',str(ROOT/'worker.cjs')],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True,encoding='utf8')
 def call(self,x):
  self.p.stdin.write(json.dumps(x,ensure_ascii=False)+'\n');self.p.stdin.flush();r=json.loads(self.p.stdout.readline());b.check(r['ok']);return r['value']
 def build(self,p,m,v,s):return self.call(dict(mode='build',path=p,model=m,variant=v,text=s))
 def inspect(self,r,p,s,v):return self.call(dict(mode='inspect',raw=r,path=p,text=s,variant=v))
 def close(self):self.p.terminate();self.p.wait(timeout=10)
def price(raw,model):
 u=raw.get('usageMetadata')or{};p=u.get('promptTokenCount');v=u.get('candidatesTokenCount');t=u.get('thoughtsTokenCount');total=u.get('totalTokenCount');cache=u.get('cachedContentTokenCount');out=dict(usage=u,reported_thinking=t,derived_thinking=None,reported_cache=cache,estimated_usd=None,invoice_verified=False)
 if type(p)is not int or type(v)is not int:return out
 if type(t)is not int:
  if type(total)is not int or total<p+v:return out
  t=total-p-v;out['derived_thinking']=t
 ip,op,cp={'gemini-3.1-flash-lite':(.25,1.5,.025),'gemini-3.5-flash-lite':(.30,2.5,.03),'gemini-3.8-flash':(.75,3.75,.075)}[model]
 out.update(billed_output_including_thinking=v+t,estimated_usd=((p-cache)*ip+cache*cp+(v+t)*op)/1e6 if type(cache)is int else(p*ip+(v+t)*op)/1e6,pricing='standard20261104 USD/1M, missingcache no discount assumed');return out
def execute(state):
 a,f=guard();h=b.read(state/'handshake.json');init=b.read(state/'init.json');b.check(os.environ['GITHUB_RUN_ATTEMPT']=='1'and h['commit']==os.environ['GITHUB_SHA']and str(h['run_id'])==os.environ['GITHUB_RUN_ID']);metadata={};last_slot={};worker=None;session=None
 def persist(d):
  if d.get('slots'):last_slot.update(slot=d['slots'][-1]['slot'])
  # Usage is derived from observed raw response; missing usage stays unknown.
  dd=copy.deepcopy(d)
  for x in dd.get('slots',[]):
   if x.get('raw'):x.update(price(x['raw'],x['request']['model']))
  dd['sender_journal_utf8']=(state/'once.journal').read_text()if(state/'once.journal').exists()else None
  dd.update(phase=f['phase'],model_metadata=metadata,execution={k:h[k]for k in ['run_id','issue_number','commit']},approval_mode='unbounded-within-scope',approval_numeric_limit=None,metadata_GET_generation_calls=0)
  b.write(state/'sealed-result.json',b.seal(dd,init['result_public_key'],b.aad_for(h,'result')))
 try:
  until=time.monotonic()+900;plan=None
  while time.monotonic()<until:
   issue=b.github('/repos/'+b.REPO+'/issues/'+str(h['issue_number']));b.check(issue['state']=='open'and issue['title']==f['title']and issue['user']['login']==b.OWNER);body=json.loads(issue['body']);b.check(body['nonce']==init['nonce']and body['result_public_key']==init['result_public_key'])
   if body['phase']=='sealed':plan=b.unseal(body['envelope'],state/'input-private.pem',b.aad_for(h,'input'));break
   b.check(body['phase']=='init');time.sleep(4)
  b.check(plan is not None);guard(plan)
  for tag in f.get('required_tags',[]):b.github('/repos/'+b.REPO+'/git/ref/tags/'+tag)
  # Atomic remote phase reservation before any model request; reruns cannot reuse it.
  b.github('/repos/'+b.REPO+'/git/refs',{'ref':'refs/tags/'+f['tag'],'sha':h['commit']})
  key=os.environ.get('GEMINI_API_KEY');b.check(bool(key))
  for model,think in [('gemini-3.1-flash-lite','minimal'),('gemini-3.5-flash-lite','minimal'),('gemini-3.8-flash','low')]:
   req=urllib.request.Request('https://generativelanguage.googleapis.com/v1beta/models/'+model,headers={'x-goog-api-key':key})
   with urllib.request.build_opener(b.NoRedirect).open(req,timeout=30)as rr:meta=json.loads(rr.read())
   validate_metadata(model,think,2048,meta);metadata[model]=meta
  worker=Worker();worker.build('KF','M31','DIRECT','warmup build only');session=Session(lambda:http.client.HTTPSConnection('generativelanguage.googleapis.com',timeout=90))
  def send(q):
   if plan.get('transport_modes',{}).get(str(last_slot['slot']))=='cold':session.close()
   return session.send(q,{'x-goog-api-key':key,'Content-Type':'application/json'})
  result=c.run(plan,a,worker.build,worker.inspect,send,state/'once.journal',persist);persist(dict(result,status='PHASE_COMPLETE_REVIEW_REQUIRED'));print(json.dumps(dict(phase=f['phase'],attempts=result['attempts'],status='PHASE_COMPLETE_REVIEW_REQUIRED',retry0=True)),flush=True)
 except Exception as exc:
  if not(state/'sealed-result.json').exists():persist(dict(status='PREFLIGHT_STOP',attempts=0,error_type=type(exc).__name__,slots=[]))
  raise
 finally:
  if session:session.close()
  if worker:worker.close()
def main():
 mode=sys.argv[1];s=Path(sys.argv[2])
 if mode=='prepare':prepare(s)
 elif mode=='execute':execute(s)
 elif mode=='client-init':b.client_init(s)
 elif mode=='client-seal':
  h=b.read(sys.argv[3]);plan=b.read(sys.argv[4]);init=b.read(s/'init.json');b.check(h['nonce']==init['nonce']and h['result_key_sha256']==hashlib.sha256(init['result_public_key'].encode()).hexdigest());b.check(h['commit']==sys.argv[5]and str(h['run_id'])==sys.argv[6]and str(h['issue_number'])==sys.argv[7]);guard(plan);b.write(s/'handshake.json',h);b.write(s/'sealed-issue-body.json',dict(init,phase='sealed',envelope=b.seal(plan,h['input_public_key'],b.aad_for(h,'input'))));print('Sealed scope-open phase, localgeneration0')
 elif mode=='client-decrypt':
  h=b.read(s/'handshake.json');b.write(s/'decrypted-result.json',b.unseal(b.read(sys.argv[3]),s/'result-private.pem',b.aad_for(h,'result')));print('Decrypted, newgeneration0')
 else:raise ValueError('MODE')
if __name__=='__main__':
 try:main()
 except Exception as exc:print('GEMINI_ASSETS STOP '+type(exc).__name__,flush=True);sys.exit(2)
