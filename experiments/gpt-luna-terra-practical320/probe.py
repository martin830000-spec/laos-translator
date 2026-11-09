"""Free preflight: no OpenAI generation, no modifications to prior campaigns."""
import os,json,hashlib,concurrent.futures,subprocess,tempfile,pathlib
from google.cloud import storage
from google.api_core.exceptions import NotFound,PreconditionFailed
PREFIX='research/gemini-model-native500-20261107/gpt-luna-terra-practical320-20261109'
def main():
 assert os.environ['GITHUB_RUN_ATTEMPT']=='1'
 assert os.environ['GITHUB_REF']=='refs/heads/research/gemini-model-native500-20261107'
 b=storage.Client(project='gen-lang-client-0422436907').bucket('lao-translator-src-460077888071')
 def get(n):
  try:return b.blob(n).download_as_bytes(timeout=30)
  except NotFound:return None
 names=[f'{PREFIX}/budget/{i:04d}.json' for i in range(1,321)]
 names += [PREFIX+'/'+n for n in ['STATE.json','LOCK.json','locks/P1.json','locks/P2.json','locks/FINAL.json','states/CLOSED.json']]
 with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:values=list(pool.map(get,names))
 present=[{'path':n,'sha256':hashlib.sha256(v).hexdigest(),'record':json.loads(v)} for n,v in zip(names,values) if v is not None]
 old=get('research/gemini-model-native500-20261107/gpt-luna-terra-screen160-20261109/states/CLOSED.json')
 assert old is not None
 report={'campaign':'GPT_LUNA_TERRA_PRACTICAL320_20261109','generation_calls':0,'run':os.environ['GITHUB_RUN_ID'],'prior_objects':present,'screen160_closed':json.loads(old),'screen160_closed_sha256':hashlib.sha256(old).hexdigest()}
 if present:
  report['status']='EXISTING_STATE_REQUIRES_RECONCILIATION'
 else:
  report['status']='NO_EXISTING_BUDGET_OR_STAGE_LOCK'
  raw=json.dumps({'kind':'FREE_SYNTHETIC','text':'Test �ѱ��� ??? 123','generation_calls':0},ensure_ascii=False,sort_keys=True).encode()
  o=b.blob(PREFIX+'/readiness/synthetic-'+os.environ['GITHUB_RUN_ID']+'.json')
  o.upload_from_string(raw,if_generation_match=0,timeout=30)
  assert o.download_as_bytes(timeout=30)==raw
  try:
   o.upload_from_string(b'DUPLICATE',if_generation_match=0,timeout=30)
   raise AssertionError('DUPLICATE_NOT_REJECTED')
  except PreconditionFailed:pass
  report['synthetic']={'sha256':hashlib.sha256(raw).hexdigest(),'readback_equal':True,'duplicate_rejected':True}
 with tempfile.TemporaryDirectory() as td:
  key=pathlib.Path(td)/'key.pem'
  key.write_bytes(b.blob('research/gemini-model-native500-20261107/fidelity240-20261108/keys/input-key.pem').download_as_bytes(timeout=30));key.chmod(0o600)
  public=subprocess.run(['openssl','pkey','-in',str(key),'-pubout'],check=True,capture_output=True).stdout.decode()
  report['input_public_key']=public
 out=pathlib.Path(os.environ['RUNNER_TEMP'])/'practical320-preflight.json'
 out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
 print('PRACTICAL320_PREFLIGHT='+json.dumps(report,ensure_ascii=False))
if __name__=='__main__':main()

