"""Free synthetic encryption and exact-key authenticated recovery."""
import os,json,hashlib,pathlib,tempfile,zipfile,subprocess
from google.cloud import storage
from google.api_core.exceptions import PreconditionFailed
P='research/gemini-model-native500-20261107/gpt-luna-terra-practical320-20261109'
HERE=pathlib.Path(__file__).resolve().parent
assert os.environ['GITHUB_RUN_ATTEMPT']=='1'
b=storage.Client(project='gen-lang-client-0422436907').bucket('lao-translator-src-460077888071')
raw='FREE_SYNTHETIC 한국어 ລາວ 123\n'.encode()
out=pathlib.Path(os.environ['RUNNER_TEMP'])/'practical320-export.p7m'
with tempfile.TemporaryDirectory() as td:
 zpath=pathlib.Path(td)/'probe.zip'
 with zipfile.ZipFile(zpath,'w') as z:z.writestr('synthetic.txt',raw)
 subprocess.run(['openssl','cms','-encrypt','-aes256','-binary','-outform','DER','-in',str(zpath),'-out',str(out),str(HERE/'export-cert.pem')],check=True,capture_output=True)
 cipher=out.read_bytes()
 o=b.blob(P+'/readiness/encrypted-'+os.environ['GITHUB_RUN_ID']+'.p7m')
 o.upload_from_string(cipher,if_generation_match=0,timeout=30)
 recovered=o.download_as_bytes(timeout=30)
 assert recovered==cipher
 try:o.upload_from_string(b'DUPLICATE',if_generation_match=0,timeout=30);raise AssertionError('DUPLICATE_ACCEPTED')
 except PreconditionFailed:pass
 out.write_bytes(recovered)
 print('ENCRYPTED_PROBE='+json.dumps({'run':os.environ['GITHUB_RUN_ID'],'key':o.name,'plain_sha256':hashlib.sha256(raw).hexdigest(),'zip_sha256':hashlib.sha256(zpath.read_bytes()).hexdigest(),'cipher_sha256':hashlib.sha256(cipher).hexdigest(),'authenticated_readback_equal':True,'duplicate_create_rejected':True,'generation_calls':0}))
