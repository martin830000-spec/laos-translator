"""M1_HEADTOHEAD80: zero-generation AUTH/GCS/transport check. Existing objects read only."""
import os,json,hashlib,pathlib,tempfile,subprocess,base64,zipfile,concurrent.futures,datetime
from google.cloud import storage
from google.api_core.exceptions import NotFound,PreconditionFailed
import httpx

CAMPAIGN='GPT_LUNA_M1_GD_HEADTOHEAD80_20261112'
ROOT='research/gemini-model-native500-20261107/'
PREFIX=ROOT+'gpt-luna-m1-gd-headtohead80-20261112/'
INPUT_KEY=ROOT+'fidelity240-20261108/keys/input-key.pem'
HERE=pathlib.Path(__file__).resolve().parent
CAPS={'A':24,'B':24,'C':32}
def canon(x):return (json.dumps(x,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode()
def sha(x):return hashlib.sha256(x).hexdigest()

def main():
 assert os.environ['GITHUB_REF']=='refs/heads/research/gemini-model-native500-20261107','WRONG_BRANCH'
 assert os.environ['GITHUB_RUN_ATTEMPT']=='1' and os.environ['GITHUB_ACTOR']=='martin830000-spec','UNAUTHORIZED_OR_REPLAY'
 c=json.loads((HERE/'CONTROL.json').read_bytes())
 assert c['campaign']==CAMPAIGN and c['mode']=='PREFLIGHT' and not c['enabled'] and c['max_new']==0 and c['approved_total']==80
 assert sha((HERE/'preflight.py').read_bytes())==c['preflight_code_sha256'],'PREFLIGHT_CODE_MISMATCH'
 B=storage.Client(project='gen-lang-client-0422436907').bucket('lao-translator-src-460077888071')
 def get(n):
  try:return B.blob(n).download_as_bytes(timeout=30,retry=None)
  except NotFound:return None
 def create(n,b):
  B.blob(PREFIX+n).upload_from_string(b,if_generation_match=0,timeout=30,retry=None)
  assert get(PREFIX+n)==b,'READBACK_MISMATCH'
 old={}
 for name,count in [('gpt-luna-p168a-transfer320-20261111',288),('gpt-luna-source-variant320-20261110',290),('gpt-source-vs-prompt-factorial320-20261111',264),('gpt-luna-lf-variance320-20261110',264),('gpt-luna-terra-mechanism1000-20261110',776)]:
  raw=get(ROOT+name+'/states/CLOSED_LOCKED.json');assert raw is not None,'MISSING_OLD_AUTHORITY';d=json.loads(raw)
  assert d['status']=='CLOSED_LOCKED' and not d['enabled'] and d['max_new']==0 and d['reserved_total']==count,'OLD_AUTHORITY_CHANGED'
  if name!='gpt-luna-terra-mechanism1000-20261110':assert get(ROOT+name+'/controls/CLOSED/CLOSED_LOCKED.json')==raw,'OLD_AUTHORITY_MISMATCH'
  old[name]={'sha256':sha(raw),'reserved_total':count,'status':d['status'],'enabled':False,'max_new':0}
 old_prefix=ROOT+'gpt-luna-gd-scope-screen80-20261112/'
 screen=get(old_prefix+'states/PAUSED_LOCKED.json')
 assert screen is not None and sha(screen)=='8434a8e50989a3ffcc1854fb4ce12fe7289696fa208c17e853a3fc0adac048d1','SCREEN80_LOCK_CHANGED'
 assert get(old_prefix+'controls/PAUSED/PAUSED_LOCKED.json')==screen,'SCREEN80_AUTHORITY_MISMATCH'
 sd=json.loads(screen);assert sd['campaign']=='GPT_LUNA_GD_SCOPE_SCREEN80_20261112' and sd['actual']==sd['reserved_total']==0 and sd['unused_locked']==80 and not sd['enabled'] and sd['max_new']==0
 realchat_prefix=ROOT+'gpt-luna-gd-realchat80-20261112/'
 realchat=get(realchat_prefix+'states/CLOSED_LOCKED.json')
 assert realchat is not None and sha(realchat)=='d8b41bda835e084a965ff035f4a1e412ccb337c2a57629d325cdfad4c42b50a2','REALCHAT80_LOCK_CHANGED'
 assert get(realchat_prefix+'controls/CLOSED/CLOSED_LOCKED.json')==realchat,'REALCHAT80_AUTHORITY_MISMATCH'
 rd=json.loads(realchat);assert rd['campaign']=='GPT_LUNA_GD_REALCHAT80_20261112' and rd['status']=='CLOSED_LOCKED' and rd['reserved_total']==rd['success']==68 and rd['failed']==rd['unknown']==0 and rd['unused_locked']==12 and not rd['enabled'] and rd['max_new']==0
 names=[f'budget/{i:04d}.json' for i in range(1,81)]+['CONTROL.json','LOCK.json','states/CLOSED_LOCKED.json','states/PAUSED_LOCKED.json','preflight/PREFLIGHT.json']
 for ph,cap in CAPS.items():
  names += [f'results/{ph}-{i:03d}.json' for i in range(1,cap+1)]
  names += [f'locks/{ph}.json',f'locks/{ph}.RELEASED.json',f'states/{ph}-running.json',f'states/{ph}-finished.json']
 with concurrent.futures.ThreadPoolExecutor(max_workers=16) as pool:found=list(pool.map(lambda n:get(PREFIX+n),names))
 assert not any(x is not None for x in found),'EXISTING_CAMPAIGN_STOP_NO_OVERWRITE'
 api_key=os.environ.get('OPENAI_API_KEY');assert api_key,'MISSING_EXISTING_API_SECRET'
 with httpx.Client(transport=httpx.HTTPTransport(retries=0),timeout=20,follow_redirects=False) as client:
  response=client.get('https://api.openai.com/v1/models/gpt-6-luna',headers={'Authorization':'Bearer '+api_key})
  assert response.status_code==200,'MODEL_ACCESS_HTTP_'+str(response.status_code)
  model_info=response.json();assert model_info.get('id')=='gpt-6-luna','MODEL_ACCESS_ID_MISMATCH'
 with tempfile.TemporaryDirectory() as td:
  t=pathlib.Path(td);key=get(INPUT_KEY);assert key is not None,'EXISTING_INPUT_KEY_MISSING'
  (t/'key.pem').write_bytes(key);(t/'key.pem').chmod(0o600);del key
  (t/'probe.p7m').write_bytes(base64.b64decode((HERE/'probe.p7m.b64').read_bytes(),validate=True))
  subprocess.run(['openssl','cms','-decrypt','-binary','-inform','DER','-in',str(t/'probe.p7m'),'-inkey',str(t/'key.pem'),'-out',str(t/'probe.json')],check=True,capture_output=True)
  probe=(t/'probe.json').read_bytes();assert sha(probe)==c['probe_sha256'],'INPUT_DECRYPT_ROUNDTRIP_FAILED'
  probe_data=json.loads(probe);assert probe_data['campaign']==CAMPAIGN and probe_data['owner_token']==c['owner_token']
  lock={'campaign':CAMPAIGN,'owner_token':c['owner_token'],'created_run':os.environ['GITHUB_RUN_ID'],'created_commit':os.environ['GITHUB_SHA'],'enabled':False,'approved_total':80,'single_executor':True}
  create('LOCK.json',canon(lock))
  create('checks/PREFLIGHT_PROBE.json',probe)
  try:B.blob(PREFIX+'checks/PREFLIGHT_PROBE.json').upload_from_string(probe,if_generation_match=0,timeout=30,retry=None)
  except PreconditionFailed:pass
  else:raise AssertionError('DUPLICATE_CREATE_NOT_REJECTED')
  assert get(PREFIX+'checks/PREFLIGHT_PROBE.json')==probe,'DUPLICATE_CHECK_CHANGED_BYTES'
  control={'campaign':CAMPAIGN,'owner_token':c['owner_token'],'status':'PREFLIGHT_LOCKED','enabled':False,'max_new':0,'approved_total':80,'reserved_total':0,'actual':0,'success':0,'failed':0,'unknown':0,'unused_locked':80,'generation_calls':0}
  create('CONTROL.json',canon(control))
  receipt={'campaign':CAMPAIGN,'owner_token':c['owner_token'],'generation_calls':0,'model_access':{'luna':{'present':True,'allowed':True,'http_status':200,'id':'gpt-6-luna'}},'old_realchat_sha256':sha(realchat),'old_realchat_actual':68,'old_realchat_unused_locked':12,'old_screen_sha256':sha(screen),'old_screen_actual':0,'old_screen_unused_locked':80,'old_closed':old,'known_absent_keys_checked':len(names),'create_only_readback_verified':True,'duplicate_create_rejected':True,'input_decryption_verified':True,'probe_sha256':sha(probe),'run':os.environ['GITHUB_RUN_ID'],'commit':os.environ['GITHUB_SHA'],'timestamp_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}
  create('preflight/PREFLIGHT.json',canon(receipt))
  objects={'preflight/PREFLIGHT.json':canon(receipt),'CONTROL.json':canon(control),'LOCK.json':canon(lock),'checks/PREFLIGHT_PROBE.json':probe}
  manifest={n:{'bytes':len(b),'sha256':sha(b)} for n,b in objects.items()}
  raw=t/'preflight.zip'
  with zipfile.ZipFile(raw,'w',zipfile.ZIP_DEFLATED) as z:
   for n,b in objects.items():z.writestr(n,b)
   z.writestr('MANIFEST.json',canon(manifest))
  out=pathlib.Path(os.environ['RUNNER_TEMP'])/'m1-headtohead80-preflight.p7m'
  subprocess.run(['openssl','cms','-encrypt','-aes256','-binary','-outform','DER','-in',str(raw),'-out',str(out),str(HERE/'export-cert.pem')],check=True,capture_output=True)
  create('exports/PREFLIGHT-'+os.environ['GITHUB_RUN_ID']+'.p7m',out.read_bytes())
  print('PREFLIGHT_RECEIPT='+json.dumps(receipt,sort_keys=True))
  print('EXPORT_RECEIPT='+json.dumps({'generation_calls':0,'plain_sha256':sha(raw.read_bytes()),'cipher_sha256':sha(out.read_bytes()),'objects':len(objects),'file':'m1-headtohead80-preflight.p7m'}))

if __name__=='__main__':
 try:main()
 except Exception as e:
  print('PREFLIGHT_STOP='+json.dumps({'generation_calls':0,'error_class':type(e).__name__,'code':str(e) if isinstance(e,AssertionError) else 'DETAILS_OMITTED_FOR_PRIVACY'}))
  raise SystemExit(1)
