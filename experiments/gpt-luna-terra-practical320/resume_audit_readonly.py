"""Read-only resume audit: no generation, no GCS writes, no secret access."""
import os,json,hashlib,concurrent.futures
from google.cloud import storage
from google.api_core.exceptions import NotFound
P='research/gemini-model-native500-20261107/gpt-luna-terra-practical320-20261109'
assert os.environ['GITHUB_RUN_ATTEMPT']=='1'
b=storage.Client(project='gen-lang-client-0422436907').bucket('lao-translator-src-460077888071')
def get(n):
 try:
  v=b.blob(n).download_as_bytes(timeout=30)
  return {'path':n,'sha256':hashlib.sha256(v).hexdigest(),'record':json.loads(v)}
 except NotFound:return None
names=[P+'/budget/%04d.json'%i for i in range(1,321)]
names += [P+'/'+s for s in ['STATE.json','LOCK.json','locks/P1.json','locks/P2.json','locks/FINAL.json','states/CLOSED.json']]
with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool: found=[v for v in pool.map(get,names) if v is not None]
# Listing is read-only; fail closed if the existing identity cannot enumerate unknown outputs.
objects=[{'name':v.name,'size':v.size,'generation':v.generation} for v in b.list_blobs(prefix=P+'/')]
old=get('research/gemini-model-native500-20261107/gpt-luna-terra-screen160-20261109/states/CLOSED.json')
print('RESUME_AUDIT='+json.dumps({'run':os.environ['GITHUB_RUN_ID'],'generation_calls':0,'found':found,'objects':objects,'screen160':old},sort_keys=True))
