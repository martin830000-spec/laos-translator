"""SOLO320 zero-generation WIF/model-access/transport preflight; create-only new scope."""
import os,json,hashlib,pathlib,tempfile,subprocess,base64,zipfile,concurrent.futures,datetime
from google.cloud import storage
from google.api_core.exceptions import NotFound,PreconditionFailed
import httpx
from locked_objects import verify as verify_old
CAMPAIGN='GPT_LUNA_SOLO100_FOURPATH_MECHANISM320_20261115'
ROOT='research/gemini-model-native500-20261107/'
PREFIX=ROOT+'gpt-luna-solo100-fourpath-mechanism320-20261115/'
INPUT_KEY=ROOT+'fidelity240-20261108/keys/input-key.pem'
HERE=pathlib.Path(__file__).resolve().parent
CAPS={'A':96,'B':32,'C':128,'FINAL':64}
def canon(x):return (json.dumps(x,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode()
def sha(x):return hashlib.sha256(x).hexdigest()
def main():
 assert os.environ['GITHUB_REF']=='refs/heads/research/gemini-model-native500-20261107','WRONG_BRANCH'
 assert os.environ['GITHUB_RUN_ATTEMPT']=='1' and os.environ['GITHUB_ACTOR']=='martin830000-spec','UNAUTHORIZED_OR_REPLAY'
 c=json.loads((HERE/'CONTROL.json').read_bytes())
 assert c['campaign']==CAMPAIGN and c['mode']=='PREFLIGHT' and c['enabled'] is False and c['max_new']==0 and c['approved_total']==320,'PREFLIGHT_CONTROL'
 assert sha((HERE/'preflight.py').read_bytes())==c['preflight_code_sha256'],'PREFLIGHT_CODE_SHA'
 assert sha((HERE/'locked_objects.py').read_bytes())==c['locked_objects_code_sha256'],'LOCK_VERIFIER_CODE_SHA'
 B=storage.Client(project='gen-lang-client-0422436907').bucket('lao-translator-src-460077888071')
 def get(n):
  try:return B.blob(n).download_as_bytes(timeout=30,retry=None)
  except NotFound:return None
 def create(n,b):
  B.blob(PREFIX+n).upload_from_string(b,if_generation_match=0,timeout=30,retry=None)
  assert get(PREFIX+n)==b,'CREATE_READBACK_MISMATCH'
 old_raw=(HERE/'OLD_LOCK_EXPECTATIONS.json').read_bytes();old=verify_old(old_raw,c['old_locks_sha256'],get)
 names=[f'budget/{i:04d}.json' for i in range(1,321)]+['CONTROL.json','LOCK.json','states/CLOSED_LOCKED.json','states/PAUSED_LOCKED.json','preflight/PREFLIGHT.json','controls/CLOSED/CLOSED_LOCKED.json','controls/PAUSED/PAUSED_LOCKED.json','preparation/SOURCES.json','preparation/PROMPTS.json','preparation/FREEZE.json','preparation/OLD_LOCK_EXPECTATIONS.json']
 for ph,cap in CAPS.items():
  names += [f'{kind}/{ph}-{i:03d}.json' for kind in ('results','requests','skips') for i in range(1,cap+1)]
  names += [f'controls/{ph}/{status}.json' for status in ('STAGED_LOCKED','RUNNING','CHECKPOINT_LOCKED','PAUSED_LOCKED')]
  names += [f'plans/{ph}.json',f'gates/{ph}.json',f'locks/{ph}.json',f'locks/{ph}.RELEASED.json',f'states/{ph}-running.json',f'states/{ph}-finished.json',f'selection/{ph}.json']
 with concurrent.futures.ThreadPoolExecutor(max_workers=16) as pool:found=list(pool.map(lambda n:get(PREFIX+n),names))
 assert not any(x is not None for x in found),'EXISTING_CAMPAIGN_STOP_NO_OVERWRITE'
 api_key=os.environ.get('OPENAI_API_KEY');assert api_key,'MISSING_EXISTING_API_SECRET'
 with httpx.Client(transport=httpx.HTTPTransport(retries=0),timeout=20,follow_redirects=False) as client:
  response=client.get('https://api.openai.com/v1/models/gpt-6-luna',headers={'Authorization':'Bearer '+api_key})
  assert response.status_code==200,'MODEL_ACCESS_HTTP_'+str(response.status_code)
  assert response.json().get('id')=='gpt-6-luna','MODEL_ACCESS_ID'
 with tempfile.TemporaryDirectory() as td:
  t=pathlib.Path(td);key=get(INPUT_KEY);assert key is not None,'INPUT_KEY_MISSING'
  (t/'key.pem').write_bytes(key);(t/'key.pem').chmod(0o600);del key
  (t/'probe.p7m').write_bytes(base64.b64decode((HERE/'probe.p7m.b64').read_bytes(),validate=True))
  subprocess.run(['openssl','cms','-decrypt','-binary','-inform','DER','-in',str(t/'probe.p7m'),'-inkey',str(t/'key.pem'),'-out',str(t/'probe.json')],check=True,capture_output=True)
  probe=(t/'probe.json').read_bytes();assert sha(probe)==c['probe_sha256'],'PROBE_SHA';p=json.loads(probe);assert p['campaign']==CAMPAIGN and p['owner_token']==c['owner_token'],'PROBE_IDENTITY'
  lock={'campaign':CAMPAIGN,'owner_token':c['owner_token'],'created_run':os.environ['GITHUB_RUN_ID'],'created_commit':os.environ['GITHUB_SHA'],'enabled':False,'approved_total':320,'single_executor':True};create('LOCK.json',canon(lock))
  create('checks/PREFLIGHT_PROBE.json',probe)
  try:B.blob(PREFIX+'checks/PREFLIGHT_PROBE.json').upload_from_string(probe,if_generation_match=0,timeout=30,retry=None)
  except PreconditionFailed:pass
  else:raise AssertionError('DUPLICATE_CREATE_NOT_REJECTED')
  assert get(PREFIX+'checks/PREFLIGHT_PROBE.json')==probe,'DUPLICATE_CHANGED_BYTES'
  control={'campaign':CAMPAIGN,'owner_token':c['owner_token'],'status':'PREFLIGHT_LOCKED','enabled':False,'max_new':0,'approved_total':320,'reserved_total':0,'actual':0,'success':0,'failed':0,'unknown':0,'unused_locked':320,'generation_calls':0};create('CONTROL.json',canon(control))
  create('preparation/OLD_LOCK_EXPECTATIONS.json',old_raw)
  receipt={'campaign':CAMPAIGN,'owner_token':c['owner_token'],'generation_calls':0,'model_access':{'luna':{'allowed':True,'http_status':200,'id':'gpt-6-luna'}},'fast_access':'DOCUMENTED_AND_PREVIOUS_CAMPAIGN_VERIFIED_NOT_NEW_GENERATION_TESTED','old_locks_sha256':sha(old_raw),'old_locks':old,'known_absent_keys_checked':len(names),'create_only_readback_verified':True,'duplicate_create_rejected':True,'input_decryption_verified':True,'probe_sha256':sha(probe),'run':os.environ['GITHUB_RUN_ID'],'commit':os.environ['GITHUB_SHA'],'timestamp_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()};create('preflight/PREFLIGHT.json',canon(receipt))
  objects={'preflight/PREFLIGHT.json':canon(receipt),'CONTROL.json':canon(control),'LOCK.json':canon(lock),'checks/PREFLIGHT_PROBE.json':probe,'preparation/OLD_LOCK_EXPECTATIONS.json':old_raw};manifest={n:{'bytes':len(b),'sha256':sha(b)} for n,b in objects.items()};raw=t/'preflight.zip'
  with zipfile.ZipFile(raw,'w',zipfile.ZIP_DEFLATED) as z:
   for n,b in objects.items():z.writestr(n,b)
   z.writestr('MANIFEST.json',canon(manifest))
  out=pathlib.Path(os.environ['RUNNER_TEMP'])/'solo320-preflight.p7m'
  subprocess.run(['openssl','cms','-encrypt','-aes256','-binary','-outform','DER','-in',str(raw),'-out',str(out),str(HERE/'export-cert.pem')],check=True,capture_output=True)
  create('exports/PREFLIGHT-'+os.environ['GITHUB_RUN_ID']+'.p7m',out.read_bytes())
  print('PREFLIGHT_RECEIPT='+json.dumps(receipt,sort_keys=True))
  print('EXPORT_RECEIPT='+json.dumps({'generation_calls':0,'plain_sha256':sha(raw.read_bytes()),'cipher_sha256':sha(out.read_bytes()),'objects':len(objects),'file':out.name}))
if __name__=='__main__':
 try:main()
 except Exception as exc:
  code=str(exc) if isinstance(exc,AssertionError) and all(ch in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_' for ch in str(exc)) else type(exc).__name__
  print('PREFLIGHT_STOP='+json.dumps({'generation_calls':0,'code':code}));raise SystemExit(1)
