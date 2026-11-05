"""Protected Actions envelope protocol. No private plaintext in logs/artifacts."""
from pathlib import Path
import sys,os,json,hashlib,time,importlib.util,subprocess,urllib.request,http.client,copy
ROOT=Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT));import controller as c
spec=importlib.util.spec_from_file_location('crypto_only',ROOT.parent/'s47-realuse16/run.py');b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b);b.PROTOCOL='gemini31-quality240-v1'
spec=importlib.util.spec_from_file_location('metadata_only',ROOT.parent/'gemini-assets/preflight.py');meta=importlib.util.module_from_spec(spec);spec.loader.exec_module(meta)
def guard(plan=None):
 a=b.read(ROOT/'approval.json');f=b.read(ROOT/'config.json');c.check(a['campaign_id']==c.ID and a['approved_limit']==240 and a['authorized']is True and a['execution_enabled']is True and a['actual_attempts']==f['prior_actual'] and a['plan_sha256']==f['plan_sha256'])
 for p,h in b.read(ROOT/'frozen-files.json').items():c.check(hashlib.sha256((ROOT.parent.parent/p).read_bytes()).hexdigest()==h)
 if plan is not None:c.validate(plan,a);c.check(plan['phase']==f['phase'])
 return a,f
def prepare(state):
 a,f=guard();c.check(not state.exists() and os.environ['GITHUB_RUN_ATTEMPT']=='1');i=b.github('/repos/'+b.REPO+'/issues/'+str(f['issue_number']));c.check(i['title']==f['title'] and i['state']=='open'and i['user']['login']==b.OWNER);init=json.loads(i['body']);c.check(init['protocol']==b.PROTOCOL and init['phase']=='init' and len(init['nonce'])==64);b.public_key(init['result_public_key']);state.mkdir(parents=True,mode=0o700)
 h=dict(protocol=b.PROTOCOL,nonce=init['nonce'],run_id=os.environ['GITHUB_RUN_ID'],issue_number=f['issue_number'],commit=os.environ['GITHUB_SHA'],input_public_key=b.keypair(state/'input-private.pem'),result_key_sha256=hashlib.sha256(init['result_public_key'].encode()).hexdigest());b.write(state/'init.json',init);b.write(state/'handshake.json',h);print('QUALITY240 public handshake generation0',flush=True)
class Worker:
 def __init__(self):self.p=subprocess.Popen(['node',str(ROOT/'worker.cjs')],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True,encoding='utf8')
 def call(self,q):
  self.p.stdin.write(json.dumps(q,ensure_ascii=False)+'\n');self.p.stdin.flush();r=json.loads(self.p.stdout.readline());c.check(r['ok']);return r['value']
 def close(self):self.p.terminate();self.p.wait(timeout=10)
class Session:
 def __init__(self):self.conn=None
 def close(self):
  if self.conn:self.conn.close();self.conn=None
 def send(self,q,key):
  reuse=self.conn is not None
  if self.conn is None:self.conn=http.client.HTTPSConnection('generativelanguage.googleapis.com',timeout=90)
  data=json.dumps(q['payload'],ensure_ascii=False,separators=(',',':')).encode();ts=time.perf_counter_ns()
  try:
   self.conn.request('POST','/v1beta/models/'+q['model']+':generateContent',body=data,headers={'x-goog-api-key':key,'Content-Type':'application/json'});sent=time.perf_counter_ns();r=self.conn.getresponse();th=time.perf_counter_ns();wire=r.read();tb=time.perf_counter_ns();status=r.status
   if r.will_close:self.close()
   try:raw=json.loads(wire)
   except ValueError:raw={'invalid_json':True}
   return dict(raw=raw,wire=dict(request_body_utf8=data.decode(),response_body_utf8=wire.decode(),http_status=status,tsend_ns=ts,send_done_ns=sent,theaders_ns=th,tbody_ns=tb,api_ms=(tb-ts)/1e6,header_ms=(th-ts)/1e6,read_body_ms=(tb-th)/1e6,connection_reuse_attempted=reuse))
  except Exception:self.close();raise

def price(raw,model):
 u=raw.get('usageMetadata')or{};p=u.get('promptTokenCount');v=u.get('candidatesTokenCount');t=u.get('thoughtsTokenCount');total=u.get('totalTokenCount');cache=u.get('cachedContentTokenCount');z={'usage':u,'reported_thinking':t,'derived_thinking':None,'reported_cache':cache,'estimated_usd':None,'invoice_verified':False}
 if type(p)is int and type(v)is int:
  if type(t)is not int and type(total)is int and total>=p+v:t=total-p-v;z['derived_thinking']=t
  if type(t)is int:
   ip,op,cp=(.25,1.5,.025) if model=='gemini-3.1-flash-lite'else(.75,3.75,.075);z['estimated_usd']=((p-cache)*ip+cache*cp+(v+t)*op)/1e6 if type(cache)is int else(p*ip+(v+t)*op)/1e6
 return z

def execute(state):
 a,f=guard();h=b.read(state/'handshake.json');init=b.read(state/'init.json');c.check(os.environ['GITHUB_RUN_ATTEMPT']=='1'and h['commit']==os.environ['GITHUB_SHA']and str(h['run_id'])==os.environ['GITHUB_RUN_ID']);metadata={};w=None;session=None
 def persist(d):
  dd=copy.deepcopy(d)
  for x in dd.get('slots',[]):
   if x.get('raw'):x.update(price(x['raw'],x['request']['model']))
  dd.update(model_metadata=metadata,execution={k:h[k]for k in ['run_id','issue_number','commit']},approved_limit=240,sender_journal_utf8=(state/'once.journal').read_text()if(state/'once.journal').exists()else None);b.write(state/'sealed-result.json',b.seal(dd,init['result_public_key'],b.aad_for(h,'result')))
 try:
  until=time.monotonic()+900;plan=None
  while time.monotonic()<until:
   i=b.github('/repos/'+b.REPO+'/issues/'+str(h['issue_number']));c.check(i['state']=='open'and i['title']==f['title']and i['user']['login']==b.OWNER);body=json.loads(i['body']);c.check(body['nonce']==init['nonce']and body['result_public_key']==init['result_public_key'])
   if body['phase']=='sealed':plan=b.unseal(body['envelope'],state/'input-private.pem',b.aad_for(h,'input'));break
   c.check(body['phase']=='init');time.sleep(4)
  c.check(plan is not None);guard(plan)
  for tag in f['required_tags']:b.github('/repos/'+b.REPO+'/git/ref/tags/'+tag)
  b.github('/repos/'+b.REPO+'/git/refs',{'ref':'refs/tags/'+f['tag'],'sha':h['commit']})
  key=os.environ.get('GEMINI_API_KEY');c.check(bool(key))
  for model,thinking in [('gemini-3.1-flash-lite','minimal'),('gemini-3.8-flash','low')]:
   req=urllib.request.Request('https://generativelanguage.googleapis.com/v1beta/models/'+model,headers={'x-goog-api-key':key})
   with urllib.request.build_opener(b.NoRedirect).open(req,timeout=30)as rr:md=json.loads(rr.read())
   meta.validate_metadata(model,thinking,1536 if model=='gemini-3.1-flash-lite'else 1024,md);metadata[model]=md
  w=Worker();session=Session();r=c.run(plan,a,w,lambda q:session.send(q,key),state/'once.journal',persist);persist(dict(r,status='PHASE_COMPLETE_REVIEW_REQUIRED'));print(json.dumps({'phase':f['phase'],'attempts':r['attempts'],'retry':0}),flush=True)
 except Exception as e:
  if not(state/'sealed-result.json').exists():persist(dict(status='PREFLIGHT_STOP',attempts=0,slots=[],error_type=type(e).__name__))
  raise
 finally:
  if session:session.close()
  if w:w.close()
if __name__=='__main__':
 try:
  mode=sys.argv[1];state=Path(sys.argv[2]);c.check(mode in ['prepare','execute']);(prepare if mode=='prepare'else execute)(state)
 except Exception as e:print('QUALITY240 STOP '+type(e).__name__,flush=True);sys.exit(2)
