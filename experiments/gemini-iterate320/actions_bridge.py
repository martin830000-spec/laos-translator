"""Protected phase runner reusing inherited RSA/AES channel, no model retries."""
from pathlib import Path
import importlib.util,sys,json,os,time,hashlib,base64,zlib
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
import campaign as c
def load(n,p):
 s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
b=load('iterate_crypto',ROOT.parent/'s47-realuse16/run.py')
CONFIG=b.read(ROOT/'config.json')
b.TITLE=CONFIG['title'];b.PROTOCOL='gemini-iterate320-private-v1';b.TAG=CONFIG['tag']
def approval_guard():
 a=b.read(ROOT/'approval.json')
 b.check(a['authorized']is True and a['campaign_id']==c.ID and a['whole_campaign_limit']==320)
 b.check(0<a['maximum_new_attempts']<=320 and a['prior_new_attempts']+a['maximum_new_attempts']<=320)
 b.check(a['plan_sha256']==CONFIG['plan_sha256'])
 return a
def pack(m):return {'zlib_plan_b64':base64.b64encode(zlib.compress(b.canonical(m),9)).decode()}
def unpack(v):
 b.check(set(v)=={'zlib_plan_b64'})
 raw=base64.b64decode(v['zlib_plan_b64'],validate=True);b.check(len(raw)<64000)
 z=zlib.decompressobj();plain=z.decompress(raw,600001);b.check(len(plain)<=600000 and z.eof and not z.unused_data)
 return json.loads(plain)
def prepare(state):
 approval_guard();b.check(not state.exists()and os.environ['GITHUB_RUN_ATTEMPT']=='1')
 issue=b.github('/repos/'+b.REPO+'/issues/'+str(CONFIG['issue_number']))
 b.check(issue['title']==b.TITLE and issue['user']['login']==b.OWNER and issue['state']=='open')
 init=json.loads(issue['body']);b.check(init['protocol']==b.PROTOCOL and init['phase']=='init'and len(init['nonce'])==64)
 b.public_key(init['result_public_key']);state.mkdir(parents=True,mode=0o700)
 pem=b.keypair(state/'input-private.pem')
 h=dict(protocol=b.PROTOCOL,nonce=init['nonce'],run_id=os.environ['GITHUB_RUN_ID'],issue_number=CONFIG['issue_number'],commit=os.environ['GITHUB_SHA'],input_public_key=pem,result_key_sha256=hashlib.sha256(init['result_public_key'].encode()).hexdigest())
 b.write(state/'init.json',init);b.write(state/'handshake.json',h)
 print('Public handshake; generation attempts0',flush=True)
def execute(state):
 approval=approval_guard();h=b.read(state/'handshake.json');init=b.read(state/'init.json')
 b.check(os.environ['GITHUB_RUN_ATTEMPT']=='1'and h['commit']==os.environ['GITHUB_SHA']and str(h['run_id'])==os.environ['GITHUB_RUN_ID'])
 persist=lambda d:b.write(state/'sealed-result.json',b.seal(dict(d,execution={k:h[k]for k in ['run_id','issue_number','commit']}),init['result_public_key'],b.aad_for(h,'result')))
 try:
  until=time.monotonic()+900;plan=None
  while time.monotonic()<until:
   issue=b.github('/repos/'+b.REPO+'/issues/'+str(h['issue_number']))
   b.check(issue['title']==b.TITLE and issue['user']['login']==b.OWNER and issue['state']=='open')
   body=json.loads(issue['body']);b.check(body['nonce']==init['nonce']and body['result_public_key']==init['result_public_key'])
   if body['phase']=='sealed':plan=unpack(b.unseal(body['envelope'],state/'input-private.pem',b.aad_for(h,'input')));break
   b.check(body['phase']=='init');time.sleep(5)
  b.check(plan is not None);c.authorize(plan,approval);c.validate(plan)
  for tag in CONFIG.get('required_tags',[]):b.github('/repos/'+b.REPO+'/git/ref/tags/'+tag)
  b.github('/repos/'+b.REPO+'/git/refs',{'ref':'refs/tags/'+b.TAG,'sha':h['commit']})
  b.check(bool(os.environ.get('GEMINI_API_KEY')))
  data=c.run(plan,approval,c.transport(os.environ['GEMINI_API_KEY']),state/'once.journal',persist)
  print(json.dumps({k:data[k]for k in ['campaign_id','status','attempts','automatic_retries']}),flush=True)
 except Exception as exc:
  if not(state/'sealed-result.json').exists():persist(dict(status='PREFLIGHT_STOP',attempts=0,error_type=type(exc).__name__))
  raise
def main():
 mode=sys.argv[1];state=Path(sys.argv[2])
 if mode=='prepare':prepare(state)
 elif mode=='execute':execute(state)
 elif mode=='client-init':b.client_init(state)
 elif mode=='client-seal':
  init=b.read(state/'init.json');h=b.read(sys.argv[3]);plan=b.read(sys.argv[4])
  b.check(h['nonce']==init['nonce']and h['result_key_sha256']==hashlib.sha256(init['result_public_key'].encode()).hexdigest())
  b.check(h['commit']==sys.argv[5]and str(h['run_id'])==sys.argv[6]and str(h['issue_number'])==sys.argv[7])
  c.authorize(plan,b.read(ROOT/'approval.json'));c.validate(plan)
  body=dict(init,phase='sealed',envelope=b.seal(pack(plan),h['input_public_key'],b.aad_for(h,'input')))
  b.check(len(json.dumps(body))<64000);b.write(state/'handshake.json',h);b.write(state/'sealed-issue-body.json',body)
  print('Approved phase sealed; generation attempts0')
 elif mode=='client-decrypt':
  h=b.read(state/'handshake.json');d=b.unseal(b.read(sys.argv[3]),state/'result-private.pem',b.aad_for(h,'result'))
  b.write(state/'decrypted-result-private.json',d);print('Result decrypted locally')
 else:raise ValueError('mode')
if __name__=='__main__':
 try:main()
 except Exception as exc:print('FOLLOWUP320 STOP '+type(exc).__name__,flush=True);sys.exit(2)
