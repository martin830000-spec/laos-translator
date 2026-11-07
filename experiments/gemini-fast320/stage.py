"""Decrypt standard CMS input in private runner memory/disk; stage immutable private plans."""
import base64,hashlib,json,pathlib,subprocess,tempfile
from google.cloud import storage
from google.api_core.exceptions import PreconditionFailed
HERE=pathlib.Path(__file__).resolve().parent
PREFIX='research/gemini-model-native500-20261107/fast-replacement320-20261108'
b=storage.Client(project='gen-lang-client-0422436907').bucket('lao-translator-src-460077888071')
cfg=json.loads((HERE/'stage.json').read_text())
with tempfile.TemporaryDirectory()as d:
 p=pathlib.Path(d);key=p/'key.pem';key.write_bytes(b.blob(PREFIX+'/keys/input-key.pem').download_as_bytes(timeout=30));key.chmod(0o600)
 enc=p/'input.p7m';enc.write_bytes(base64.b64decode((HERE/'input.p7m.b64').read_text()));out=p/'input.json'
 subprocess.run(['openssl','cms','-decrypt','-binary','-inform','DER','-in',str(enc),'-inkey',str(key),'-out',str(out)],check=True,capture_output=True)
 raw=out.read_bytes();assert hashlib.sha256(raw).hexdigest()==cfg['input_sha256'];package=json.loads(raw)
 for m,plan in package['plans'].items():
  assert m in ('35','36') and plan['campaign']==f'GEMINI{m}_FAST_REPLACEMENT320_20261108'
  payload=(json.dumps(plan,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode();sha=hashlib.sha256(payload).hexdigest();assert sha==cfg['plans'][m]
  blob=b.blob(f'{PREFIX}/{m}/plans/{sha}.json')
  try:blob.upload_from_string(payload,if_generation_match=0,timeout=30)
  except PreconditionFailed:pass
  assert blob.download_as_bytes(timeout=30)==payload
  print(json.dumps({'model':m,'plan_sha256':sha,'slots':len(plan['tasks']),'paid_calls':0}))
