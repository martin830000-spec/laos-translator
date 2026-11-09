"""Free exact-key reconciliation. No listing, no generation, no secret access."""
import os,json,hashlib,concurrent.futures
from google.cloud import storage
from google.api_core.exceptions import NotFound
P='research/gemini-model-native500-20261107/gpt-luna-terra-practical320-20261109'
assert os.environ['GITHUB_RUN_ATTEMPT']=='1'
b=storage.Client(project='gen-lang-client-0422436907').bucket('lao-translator-src-460077888071')
names=['STATE.json','LOCK.json','states/CLOSED.json','readiness/synthetic-42568425386.json']
names += [f'budget/{i:04d}.json' for i in range(1,321)]
names += [f'{kind}/S{i:03d}.json' for i in range(1,321) for kind in ['results','requests','skips']]
names += [f'checkpoints/attempt-{i:04d}.json' for i in range(1,321)]
names += [f'{folder}/{ph}{suffix}.json' for ph in ['P1','P2','FINAL'] for folder,suffix in [('locks',''),('locks','.RELEASED'),('states','-running'),('states','-finished')]]
def get(n):
 try:
  raw=b.blob(P+'/'+n).download_as_bytes(timeout=30)
  return {'key':n,'sha256':hashlib.sha256(raw).hexdigest(),'record':json.loads(raw)}
 except NotFound:return None
with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool: found=[r for r in pool.map(get,names) if r is not None]
closed=next(r for r in found if r['key']=='states/CLOSED.json')
assert closed['sha256']=='73e28408d45c5bf17cf1fc0375e98456aefdf3792a0bcdfbea6603dd2f048f5f'
assert all(r['key'] in ['states/CLOSED.json','readiness/synthetic-42568425386.json'] for r in found)
old=b.blob('research/gemini-model-native500-20261107/gpt-luna-terra-screen160-20261109/states/CLOSED.json').download_as_bytes(timeout=30)
assert hashlib.sha256(old).hexdigest()=='74ee3bb742ddf675ef5050763b231f1e561c39f6c8cae3eebf44a24e38b7e4fc'
print('EXACT_KEY_AUDIT='+json.dumps({'run':os.environ['GITHUB_RUN_ID'],'commit':os.environ['GITHUB_SHA'],'checked_keys':len(names),'found':found,'paid_calls':0,'reserved':0,'unused_locked':320,'screen160_unchanged':True,'inventory_scope':'All deployed PRACTICAL320 writer paths from commit history plus defensive SCREEN160 slot mapping; no assertion about arbitrary external objects'},sort_keys=True))
