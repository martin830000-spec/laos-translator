"""Read exact private objects; standard CMS encrypted analysis copy only. No API."""
import sys, concurrent.futures, hashlib, json, os, pathlib, subprocess, tempfile, zipfile
from google.cloud import storage
HERE=pathlib.Path(__file__).resolve().parent
PREFIX='research/gemini-model-native500-20261107'
BUCKET='lao-translator-src-460077888071'
cfg=json.loads((HERE/'review_export.json').read_text())
if len(sys.argv)==2:
    model=sys.argv[1]; assert model in ('35','36')
    active=json.loads((HERE.parent/f'gemini{model}-native500'/'config.json').read_text())
    cfg={'plans':[[model,active['plan_sha256']]],'samples':{}}
b=storage.Client(project='gen-lang-client-0422436907').bucket(BUCKET)
def read(name):
    return b.blob(PREFIX+'/'+name).download_as_bytes(timeout=30)
with tempfile.TemporaryDirectory() as d:
    root=pathlib.Path(d); objects={}
    for name,sha in cfg.get('samples',{}).items():
        raw=read('samples/20261107_R2/'+name)
        assert hashlib.sha256(raw).hexdigest()==sha
        objects['samples/'+name]=raw
    for model,sha in cfg['plans']:
        name=f'{model}/plans/{sha}.json'; raw=read(name)
        assert hashlib.sha256(raw).hexdigest()==sha
        objects[name]=raw; plan=json.loads(raw)
        base=f'{model}/results/{sha}'
        finish=read(base+'/RUN_FINISHED.json'); done=json.loads(finish); objects[base+'/RUN_FINISHED.json']=finish
        count=len(plan['tasks'])-done['remaining_in_reserved_plan']
        names=[base+'/RUN_STARTED.json']
        names += [f'{base}/journal/{i:04d}.json' for i in range(1,done['attempted']+1)]
        names += [f'{base}/slots/{i:04d}-{t["slot"]}.json' for i,t in enumerate(plan['tasks'][:count],1)]
        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
            for name,data in zip(names,pool.map(read,names)): objects[name]=data
    manifest={n:{'bytes':len(v),'sha256':hashlib.sha256(v).hexdigest()} for n,v in objects.items()}
    with zipfile.ZipFile(root/'private.zip','w',zipfile.ZIP_DEFLATED) as z:
        for n,v in objects.items(): z.writestr(n,v)
        z.writestr('MANIFEST.json',json.dumps(manifest,sort_keys=True))
    out=pathlib.Path(os.environ['RUNNER_TEMP'])/'native500-review.p7m'
    subprocess.run(['openssl','cms','-encrypt','-aes256','-binary','-outform','DER','-in',str(root/'private.zip'),'-out',str(out),str(HERE/'export-cert.pem')],check=True,capture_output=True)
    print(json.dumps({'encrypted_bytes':out.stat().st_size,'files':len(objects),'paid_calls':0,'sha256':hashlib.sha256(out.read_bytes()).hexdigest()}))
