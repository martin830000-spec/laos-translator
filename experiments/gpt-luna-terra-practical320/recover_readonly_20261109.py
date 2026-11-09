"""Read-only known-key recovery. No generation client, credentials or GCS writes."""
import os,json,hashlib,pathlib,concurrent.futures,zipfile,subprocess,tempfile
from google.cloud import storage
from google.api_core.exceptions import NotFound
PREFIX='research/gemini-model-native500-20261107/gpt-luna-terra-practical320-20261109/'
bucket=storage.Client(project='gen-lang-client-0422436907').bucket('lao-translator-src-460077888071')
def get(n):
 try:return bucket.blob(PREFIX+n).download_as_bytes(timeout=30)
 except NotFound:return None
def sha(b):return hashlib.sha256(b).hexdigest()
def canon(x):return (json.dumps(x,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode()
assert not os.environ.get('OPENAI_API_KEY')
names=[f'budget/{i:04d}.json' for i in range(1,321)]
objs={};missing=[]
def collect(names):
 with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
  for n,b in zip(names,pool.map(get,names)):
   if b is None:missing.append(n)
   else:objs[n]=b
collect(names)
rs=[json.loads(objs[n]) for n in names if n in objs]
assert [r['ordinal'] for r in rs]==list(range(1,len(rs)+1))
assert len(set(r['slot'] for r in rs))==len(rs)
names=['states/CLOSED.json','preparation/SOURCE_SPLIT.json','preparation/FREEZE.json','preparation/BASE_COPY.json','plans/a2ceeb5585f46939d2c184cf80d57aa1bb0302947a2b51f4b71ca19c50b51129.json']
for ph in ['P1','P2','FINAL']:
 names += ['checks/stage-'+ph+'.json','states/'+ph+'-running.json','states/'+ph+'-finished.json','locks/'+ph+'.json','locks/'+ph+'.RELEASED.json']
for r in rs:names += ['results/'+r['slot']+'.json',f"checkpoints/attempt-{r['ordinal']:04d}.json"]
collect(names)
for ph in ['P1','P2','FINAL']:
 n='locks/'+ph+'.json'
 if n in objs:
  h=json.loads(objs[n]).get('plan_sha256')
  if h and 'plans/'+h+'.json' not in objs:collect(['plans/'+h+'.json'])
results=[json.loads(objs['results/'+r['slot']+'.json']) for r in rs if 'results/'+r['slot']+'.json' in objs]
summary={'generation_calls':0,'gcs_writes':0,'reserved':len(rs),'success':sum(bool(x['success']) for x in results),'failed':sum(not x['success'] for x in results),'unknown':len(rs)-len(results),'models':{m:sum(x['model']==m for x in results) for m in set(x['model'] for x in results)},'missing_keys':missing,'run':os.environ['GITHUB_RUN_ID']}
for r in rs:
 n='results/'+r['slot']+'.json';cp=f"checkpoints/attempt-{r['ordinal']:04d}.json"
 if n in objs and cp in objs:assert json.loads(objs[cp])['result_sha256']==sha(objs[n])
objs['RECOVERY_AUDIT.json']=canon(summary)
manifest={n:{'bytes':len(b),'sha256':sha(b)} for n,b in objs.items()}
out=pathlib.Path(os.environ['RUNNER_TEMP'])/'practical320-recovered.p7m'
with tempfile.TemporaryDirectory() as td:
 p=pathlib.Path(td)/'raw.zip'
 with zipfile.ZipFile(p,'w',zipfile.ZIP_DEFLATED) as z:
  for n,b in objs.items():z.writestr(n,b)
  z.writestr('MANIFEST.json',canon(manifest))
 subprocess.run(['openssl','cms','-encrypt','-aes256','-binary','-outform','DER','-in',str(p),'-out',str(out),str(pathlib.Path(__file__).with_name('recovery-cert.pem'))],check=True,capture_output=True)
 print('RECOVERY_RECEIPT='+json.dumps({k:v for k,v in summary.items() if k!='missing_keys'}|{'objects':len(objs),'plain_sha256':sha(p.read_bytes()),'cipher_sha256':sha(out.read_bytes())}))
 for ph in ['P1','P2','FINAL']:
  n='states/'+ph+'-finished.json'
  if n in objs:print('VERIFIED_STATE='+objs[n].decode())
