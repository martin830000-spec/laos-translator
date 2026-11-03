"""New40 one-time encrypted channel. Reuses existing audited crypto primitives only."""
from pathlib import Path
import importlib.util,sys,os,json,time,hashlib
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT));import campaign as c
def module(name,path):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
b=module('audited_private_channel',ROOT.parent/'s47-realuse16/run.py')
b.PROTOCOL='gemini-full-autonomous300-v1'
def cfg():return b.read(ROOT/'config.json')
def guard():
 a=b.read(ROOT/'approval.json');conf=cfg()
 b.check(a['campaign_id']==c.ID and a['authorized']is True and a['execution_enabled']is True and a['user_approved_limit']==300)
 b.check(conf['stage']in c.CAPS and a['actual_consumed']==conf['prior_actual_attempts'])
 return a,conf
def prepare(state):
 a,conf=guard();b.check(not state.exists()and os.environ['GITHUB_RUN_ATTEMPT']=='1')
 issue=b.github('/repos/'+b.REPO+'/issues/'+str(conf['issue_number']))
 b.check(issue['title']==conf['title']and issue['user']['login']==b.OWNER and issue['state']=='open')
 init=json.loads(issue['body']);b.check(init['protocol']==b.PROTOCOL and init['phase']=='init'and len(init['nonce'])==64);b.public_key(init['result_public_key'])
 state.mkdir(parents=True,mode=0o700);pem=b.keypair(state/'input-private.pem')
 h=dict(protocol=b.PROTOCOL,nonce=init['nonce'],run_id=os.environ['GITHUB_RUN_ID'],issue_number=conf['issue_number'],commit=os.environ['GITHUB_SHA'],input_public_key=pem,result_key_sha256=hashlib.sha256(init['result_public_key'].encode()).hexdigest())
 b.write(state/'init.json',init);b.write(state/'handshake.json',h);print('AUTONOMOUS300 public handshake; generated=0',flush=True)
def execute(state):
 approval,conf=guard();h=b.read(state/'handshake.json');init=b.read(state/'init.json')
 b.check(os.environ['GITHUB_RUN_ATTEMPT']=='1'and h['commit']==os.environ['GITHUB_SHA']and str(h['run_id'])==os.environ['GITHUB_RUN_ID'])
 persist=lambda d:b.write(state/'sealed-result.json',b.seal(dict(d,execution={k:h[k]for k in('run_id','issue_number','commit')}),init['result_public_key'],b.aad_for(h,'result')))
 try:
  until=time.monotonic()+900;plan=None
  while time.monotonic()<until:
   issue=b.github('/repos/'+b.REPO+'/issues/'+str(h['issue_number']));b.check(issue['title']==conf['title']and issue['user']['login']==b.OWNER and issue['state']=='open')
   body=json.loads(issue['body']);b.check(body['nonce']==init['nonce']and body['result_public_key']==init['result_public_key'])
   if body['phase']=='sealed':plan=b.unseal(body['envelope'],state/'input-private.pem',b.aad_for(h,'input'));break
   b.check(body['phase']=='init');time.sleep(5)
  b.check(plan is not None);c.authorize(plan,approval,conf);c.validate(plan)
  for tag in conf.get('required_tags',[]):b.github('/repos/'+b.REPO+'/git/ref/tags/'+tag)
  b.github('/repos/'+b.REPO+'/git/refs',{'ref':'refs/tags/'+conf['tag'],'sha':h['commit']})
  b.check(bool(os.environ.get('GEMINI_API_KEY')))
  sender=module('audited_gemini_sender',ROOT/'audited_gemini_transport.py').transport(os.environ['GEMINI_API_KEY'])
  result=c.run(plan,approval,conf,sender,state/'once.journal',persist)
  print(json.dumps({k:result[k]for k in('campaign_id','phase','attempts','automatic_retries','status')}),flush=True)
 except Exception as exc:
  if not(state/'sealed-result.json').exists():persist({'status':'PREFLIGHT_STOP','attempts':0,'error_type':type(exc).__name__})
  raise
def main():
 mode=sys.argv[1];state=Path(sys.argv[2])
 if mode=='prepare':prepare(state)
 elif mode=='execute':execute(state)
 elif mode=='client-init':b.client_init(state)
 elif mode=='client-seal':
  h=b.read(sys.argv[3]);plan=b.read(sys.argv[4]);init=b.read(state/'init.json')
  b.check(h['nonce']==init['nonce']and h['result_key_sha256']==hashlib.sha256(init['result_public_key'].encode()).hexdigest())
  b.check(h['commit']==sys.argv[5]and str(h['run_id'])==sys.argv[6]and str(h['issue_number'])==sys.argv[7]);c.authorize(plan,*guard());c.validate(plan)
  b.write(state/'handshake.json',h);b.write(state/'sealed-issue-body.json',dict(init,phase='sealed',envelope=b.seal(plan,h['input_public_key'],b.aad_for(h,'input'))));print('sealed autonomous300 plan, local generation0')
 elif mode=='client-decrypt':
  h=b.read(state/'handshake.json');b.write(state/'decrypted-result.json',b.unseal(b.read(sys.argv[3]),state/'result-private.pem',b.aad_for(h,'result')));print('decrypted, new generation0')
 else:raise ValueError('MODE')
if __name__=='__main__':
 try:main()
 except Exception as exc:print('AUTONOMOUS300 STOP '+type(exc).__name__,flush=True);sys.exit(2)
