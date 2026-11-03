"""Protected one-time RSA/AES-GCM GitHub Actions phase channel for distinct REAL128 campaign."""
from pathlib import Path
import importlib.util,sys,json,os,time,hashlib,base64,zlib
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
import campaign as c

def load(name,path):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
b=load('nx128_crypto',ROOT.parent/'s47-realuse16/run.py')
CONFIG=b.read(ROOT/'config.json')
b.TITLE=CONFIG['title'];b.PROTOCOL='gemini-nextgen-real128-private-v1';b.TAG=CONFIG['tag']
def approval_guard():
 approval=b.read(ROOT/'approval.json')
 c.require(approval['authorized'] is True and approval['execution_enabled'] is True)
 c.require(approval['campaign_id']==c.ID and approval['whole_campaign_limit']==128)
 c.require(approval['plan_sha256']==CONFIG['plan_sha256'])
 c.require(approval['actual_consumed']==CONFIG['prior_actual_attempts'])
 return approval

def audited_transport(api_key):
    """Reuse the existing, completed NUANCE256 transport without new HTTP client code.

    This imports only the prior audited sender. No network request occurs here;
    the callback is invoked by the new approval-bounded campaign only.
    """
    audited_dir = ROOT.parent / 'gemini-nuance256'
    previous_path = list(sys.path)
    try:
        sys.path.insert(0, str(audited_dir))
        old = load('verified_gemini_sender', audited_dir / 'campaign.py')
    finally:
        sys.path[:] = previous_path
    return old.transport(api_key)


def pack(d):return {'zlib_plan_b64':base64.b64encode(zlib.compress(b.canonical(d),9)).decode()}
def unpack(d):
 b.check(set(d)=={'zlib_plan_b64'})
 compressed=base64.b64decode(d['zlib_plan_b64'],validate=True)
 b.check(len(compressed)<64000)
 dec=zlib.decompressobj();plain=dec.decompress(compressed,600001)
 b.check(len(plain)<=600000 and dec.eof and not dec.unused_data)
 return json.loads(plain)

def prepare(state):
 approval_guard()
 b.check(not state.exists() and os.environ['GITHUB_RUN_ATTEMPT']=='1')
 issue=b.github('/repos/'+b.REPO+'/issues/'+str(CONFIG['issue_number']))
 b.check(issue['title']==b.TITLE and issue['user']['login']==b.OWNER and issue['state']=='open')
 init=json.loads(issue['body'])
 b.check(init['protocol']==b.PROTOCOL and init['phase']=='init' and len(init['nonce'])==64)
 b.public_key(init['result_public_key'])
 state.mkdir(parents=True,mode=0o700)
 pem=b.keypair(state/'input-private.pem')
 h={'protocol':b.PROTOCOL,'nonce':init['nonce'],'run_id':os.environ['GITHUB_RUN_ID'],'issue_number':CONFIG['issue_number'],'commit':os.environ['GITHUB_SHA'],'input_public_key':pem,'result_key_sha256':hashlib.sha256(init['result_public_key'].encode()).hexdigest()}
 b.write(state/'init.json',init);b.write(state/'handshake.json',h)
 print('NEXTGEN REAL128 public handshake prepared; paid attempts=0',flush=True)

def execute(state):
 approval=approval_guard();h=b.read(state/'handshake.json');init=b.read(state/'init.json')
 b.check(os.environ['GITHUB_RUN_ATTEMPT']=='1' and h['commit']==os.environ['GITHUB_SHA'] and str(h['run_id'])==os.environ['GITHUB_RUN_ID'])
 persist=lambda d:b.write(state/'sealed-result.json',b.seal(dict(d,execution={k:h[k] for k in ('run_id','issue_number','commit')}),init['result_public_key'],b.aad_for(h,'result')))
 try:
  until=time.monotonic()+900;plan=None
  while time.monotonic()<until:
   issue=b.github('/repos/'+b.REPO+'/issues/'+str(h['issue_number']))
   b.check(issue['title']==b.TITLE and issue['user']['login']==b.OWNER and issue['state']=='open')
   body=json.loads(issue['body'])
   b.check(body['nonce']==init['nonce'] and body['result_public_key']==init['result_public_key'])
   if body['phase']=='sealed':plan=unpack(b.unseal(body['envelope'],state/'input-private.pem',b.aad_for(h,'input')));break
   b.check(body['phase']=='init');time.sleep(5)
  b.check(plan is not None)
  c.authorize(plan,approval,CONFIG);c.validate(plan)
  for tag in CONFIG.get('required_tags',[]):b.github('/repos/'+b.REPO+'/git/ref/tags/'+tag)
  # One-time atomic tag before first send; no rerun may recreate the tag.
  b.github('/repos/'+b.REPO+'/git/refs',{'ref':'refs/tags/'+b.TAG,'sha':h['commit']})
  b.check(bool(os.environ.get('GEMINI_API_KEY')))
  data=c.run(plan,approval,CONFIG,audited_transport(os.environ['GEMINI_API_KEY']),state/'once.journal',persist)
  print(json.dumps({k:data[k] for k in ('campaign_id','phase','status','attempts','automatic_retries')}),flush=True)
 except Exception as exc:
  if not (state/'sealed-result.json').exists():persist({'status':'PREFLIGHT_STOP','attempts':0,'error_type':type(exc).__name__})
  raise

def client_init(state):b.client_init(state)
def client_seal(state,hpath,planpath,commit,runid,issue_number):
 init=b.read(state/'init.json');h=b.read(hpath);plan=b.read(planpath)
 b.check(h['nonce']==init['nonce'] and h['result_key_sha256']==hashlib.sha256(init['result_public_key'].encode()).hexdigest())
 b.check(h['commit']==commit and str(h['run_id'])==str(runid) and int(h['issue_number'])==int(issue_number))
 c.authorize(plan,b.read(ROOT/'approval.json'),CONFIG);c.validate(plan)
 body=dict(init,phase='sealed',envelope=b.seal(pack(plan),h['input_public_key'],b.aad_for(h,'input')))
 b.check(len(json.dumps(body))<64000)
 b.write(state/'handshake.json',h);b.write(state/'sealed-issue-body.json',body)
 print('Private plan sealed, 0 API calls locally')

def client_decrypt(state,encrypted):
 h=b.read(state/'handshake.json')
 v=b.unseal(b.read(encrypted),state/'result-private.pem',b.aad_for(h,'result'))
 b.write(state/'decrypted-result-private.json',v)
 print('Private result decrypted locally, 0 new API calls')

def main():
 mode=sys.argv[1];state=Path(sys.argv[2])
 if mode=='prepare':prepare(state)
 elif mode=='execute':execute(state)
 elif mode=='client-init':client_init(state)
 elif mode=='client-seal':client_seal(state,Path(sys.argv[3]),Path(sys.argv[4]),sys.argv[5],sys.argv[6],sys.argv[7])
 elif mode=='client-decrypt':client_decrypt(state,Path(sys.argv[3]))
 else:raise ValueError('mode')
if __name__=='__main__':
 try:main()
 except Exception as exc:print('GEMINI_NEXTGEN_REAL128 STOP '+type(exc).__name__,flush=True);sys.exit(2)