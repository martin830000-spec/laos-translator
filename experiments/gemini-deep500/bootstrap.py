"""Free readiness: provision an input-encryption key in private research GCS only."""
import hashlib,json,os,pathlib,subprocess,tempfile
from google.cloud import storage
PREFIX='research/gemini-model-native500-20261107/deep500-20261108'
b=storage.Client(project='gen-lang-client-0422436907').bucket('lao-translator-src-460077888071')
with tempfile.TemporaryDirectory() as d:
    p=pathlib.Path(d); key=p/'input-key.pem'; cert=p/'input-cert.pem'
    subprocess.run(['openssl','req','-x509','-newkey','rsa:3072','-nodes','-keyout',str(key),'-out',str(cert),'-days','7','-subj','/CN=deep500-private-input'],check=True,capture_output=True)
    os.chmod(key,0o600)
    for f in (key,cert):
        raw=f.read_bytes(); blob=b.blob(PREFIX+'/keys/'+f.name)
        blob.upload_from_string(raw,if_generation_match=0,timeout=30)
        assert blob.download_as_bytes(timeout=30)==raw
    out=pathlib.Path(os.environ['RUNNER_TEMP'])/'deep500-input-cert.pem';out.write_bytes(cert.read_bytes())
    print(json.dumps({'status':'PRIVATE_INPUT_READY','paid_calls':0,'public_certificate_sha256':hashlib.sha256(out.read_bytes()).hexdigest()}))
