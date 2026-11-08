"""V2 private GCS transfer. No generation API or API key access."""
import pathlib,json,os,hashlib,subprocess,tempfile,zipfile,base64,concurrent.futures,sys
from google.cloud import storage
from google.api_core.exceptions import PreconditionFailed
HERE=pathlib.Path(__file__).resolve().parent
PREFIX='research/gemini-model-native500-20261107/focus320-20261108'
BUCKET='lao-translator-src-460077888071'
def digest(b):return hashlib.sha256(b).hexdigest()
def canon(x):return (json.dumps(x,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode()
def main():
 assert os.environ['GITHUB_REF']=='refs/heads/research/gemini-model-native500-20261107'
 assert os.environ['GITHUB_RUN_ATTEMPT']=='1'
 b=storage.Client(project='gen-lang-client-0422436907').bucket(BUCKET)
 cfg=json.loads((HERE/'READINESS.json').read_text())
 if len(sys.argv)>1:
  m=sys.argv[1];assert m in ('35',);a=json.loads((HERE/m/'config.json').read_text());cfg={'mode':'EXPORT','export_cert':'export-cert.pem','plans':[[m,a['plan_sha256']]]}
 def read(n):return b.blob(PREFIX+'/'+n).download_as_bytes(timeout=60)
 def write(n,v):
  try:b.blob(PREFIX+'/'+n).upload_from_string(v,if_generation_match=0,timeout=30)
  except PreconditionFailed:pass
  assert read(n)==v
 objs={};mode=cfg['mode']
 if mode=='PROBE_WRITE':
  for m in ('35',):
   c=json.loads((HERE/m/'config.json').read_text());assert not c['enabled'] and c['max_new']==0 and c['cumulative_actual']==0
  raw=canon({'type':'FOCUS320_FREE_SYNTHETIC_ROUNDTRIP','content':'Synthetic non-sensitive message. 12345. 한국어 ພາສາລາວ','generation_calls':0})
  write('readiness/synthetic.json',raw)
  with tempfile.TemporaryDirectory() as td:
   p=pathlib.Path(td);key=p/'input-key.pem';cert=p/'input-cert.pem'
   subprocess.run(['openssl','req','-x509','-newkey','rsa:3072','-nodes','-keyout',str(key),'-out',str(cert),'-days','7','-subj','/CN=V2-private-plan-input'],check=True,capture_output=True)
   write('keys/input-key.pem',key.read_bytes());write('keys/input-cert.pem',cert.read_bytes())
 if mode in ('PROBE_WRITE','PROBE_READ'):
  objs['synthetic.json']=read('readiness/synthetic.json')
 elif mode=='STAGE':
  with tempfile.TemporaryDirectory() as td:
   p=pathlib.Path(td);(p/'key.pem').write_bytes(read('keys/input-key.pem'));(p/'key.pem').chmod(0o600);(p/'in.p7m').write_bytes(base64.b64decode((HERE/'input.p7m.b64').read_text()))
   subprocess.run(['openssl','cms','-decrypt','-binary','-inform','DER','-in',str(p/'in.p7m'),'-inkey',str(p/'key.pem'),'-out',str(p/'input.json')],check=True,capture_output=True)
   raw=(p/'input.json').read_bytes();assert digest(raw)==cfg['input_sha256'];package=json.loads(raw)
   for m,plan in package['plans'].items():
    assert m in ('35',) and plan['campaign']==f'GEMINI{m}_FOCUS320_20261108'
    import runner
    runner.validate_tasks(plan['tasks'],m,{'max_new':len(plan['tasks']),'prior_plans':[],'frozen_sources':cfg.get('frozen_sources',[])})
    proc=subprocess.Popen(['node',str(HERE/'worker.cjs'),m],stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True)
    try:
     for task in plan['tasks']:
      source=task.get('input','SYNTHETIC_FIRST_FOR_FREE_BUILD_ONLY')
      built=runner.worker_call(proc,{'mode':'build','path':task['path'],'variant':task['variant'],'input':source})
      assert built['payload']['contents']==[{'role':'user','parts':[{'text':source}]}]
    finally:proc.terminate()
    payload=canon(plan);sha=digest(payload);assert sha==cfg['plans'][m];write(f'{m}/plans/{sha}.json',payload);objs[f'{m}/plans/{sha}.json']=read(f'{m}/plans/{sha}.json')
 elif mode=='EXPORT':
  for m,sha in cfg['plans']:
   name=f'{m}/plans/{sha}.json';raw=read(name);assert digest(raw)==sha;objs[name]=raw;plan=json.loads(raw);base=f'{m}/results/{sha}'
   done_raw=read(base+'/RUN_FINISHED.json');done=json.loads(done_raw);objs[base+'/RUN_FINISHED.json']=done_raw
   names=[base+'/RUN_STARTED.json']+[f'{base}/journal/{i:04d}.json' for i in range(1,done['attempted']+1)]
   count=len(plan['tasks'])-done['remaining_in_reserved_plan']
   names += [f'{base}/slots/{i:04d}-{t["slot"]}.json' for i,t in enumerate(plan['tasks'][:count],1)]
   names += [f'{m}/call-budget/{i:04d}.json' for i in range(plan['prior_actual']+1,plan['prior_actual']+done['attempted']+1)]
   with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
    for n,v in zip(names,pool.map(read,names)):objs[n]=v
 else:
  if mode not in ('PROBE_WRITE','PROBE_READ'):raise ValueError('MODE')
 manifest={n:{'bytes':len(v),'sha256':digest(v)} for n,v in objs.items()}
 out=pathlib.Path(os.environ['RUNNER_TEMP']);(out/'focus320-input-cert.pem').write_bytes(read('keys/input-cert.pem'))
 with tempfile.TemporaryDirectory() as td:
  zp=pathlib.Path(td)/'objects.zip'
  with zipfile.ZipFile(zp,'w',zipfile.ZIP_DEFLATED) as z:
   for n,v in objs.items():z.writestr(n,v)
   z.writestr('MANIFEST.json',canon(manifest))
  subprocess.run(['openssl','cms','-encrypt','-aes256','-binary','-outform','DER','-in',str(zp),'-out',str(out/'focus320-transfer.p7m'),str(HERE/cfg['export_cert'])],check=True,capture_output=True)
 print(json.dumps({'mode':mode,'files':len(objs),'generation_calls':0,'encrypted_sha256':digest((out/'focus320-transfer.p7m').read_bytes())}))
if __name__=='__main__':main()
