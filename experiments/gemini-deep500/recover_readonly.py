"""Read existing DEEP500 objects only. No generation, writes to GCS, or API key."""
import concurrent.futures,hashlib,json,os,pathlib,subprocess,tempfile,zipfile
from google.cloud import storage
HERE=pathlib.Path(__file__).resolve().parent
PREFIX='research/gemini-model-native500-20261107/deep500-20261108'
bucket=storage.Client(project='gen-lang-client-0422436907').bucket('lao-translator-src-460077888071')
def read(name): return bucket.blob(PREFIX+'/'+name).download_as_bytes(timeout=60)
objects={}
for model in ('35','36'):
    c=json.loads((HERE/model/'config.json').read_text())
    assert c['enabled'] is False and c['max_new']==0 and c['cumulative_actual']==500
    assert len(c['prior_plans'])==5
    names=[f'{model}/call-budget/{i:04d}.json' for i in range(1,501)]
    for sha in c['prior_plans']:
        name=f'{model}/plans/{sha}.json'; raw=read(name)
        assert hashlib.sha256(raw).hexdigest()==sha
        objects[name]=raw; p=json.loads(raw); base=f'{model}/results/{sha}'
        raw=read(base+'/RUN_FINISHED.json'); objects[base+'/RUN_FINISHED.json']=raw
        done=json.loads(raw); assert done['status']=='DONE' and done['failed']==0 and done['skipped']==0
        assert done['attempted']==len(p['tasks'])
        names += [base+'/RUN_STARTED.json']
        names += [f'{base}/journal/{i:04d}.json' for i in range(1,done['attempted']+1)]
        names += [f'{base}/slots/{i:04d}-{t["slot"]}.json' for i,t in enumerate(p['tasks'],1)]
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        for name,data in zip(names,pool.map(read,names)): objects[name]=data
manifest={n:{'bytes':len(v),'sha256':hashlib.sha256(v).hexdigest()} for n,v in objects.items()}
with tempfile.TemporaryDirectory() as td:
    zp=pathlib.Path(td)/'raw.zip'
    with zipfile.ZipFile(zp,'w',zipfile.ZIP_DEFLATED) as z:
        for n,v in objects.items(): z.writestr(n,v)
        z.writestr('MANIFEST.json',json.dumps(manifest,sort_keys=True))
    out=pathlib.Path(os.environ['RUNNER_TEMP'])/'deep500-recovery.p7m'
    subprocess.run(['openssl','cms','-encrypt','-aes256','-binary','-outform','DER','-in',str(zp),'-out',str(out),str(HERE/'recovery-cert.pem')],check=True,capture_output=True)
    print(json.dumps({'files':len(objects),'generation_calls':0,'raw_zip_sha256':hashlib.sha256(zp.read_bytes()).hexdigest(),'encrypted_sha256':hashlib.sha256(out.read_bytes()).hexdigest()}))
