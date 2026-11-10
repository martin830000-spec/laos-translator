import concurrent.futures,json,hashlib,pathlib,os
from google.cloud import storage
from google.api_core.exceptions import NotFound
B=storage.Client(project='gen-lang-client-0422436907').bucket('lao-translator-src-460077888071')
P='research/gemini-model-native500-20261107/gpt-luna-lf-variance320-20261110/'
def get(n):
 try:return B.blob(n).download_as_bytes(timeout=30,retry=None)
 except NotFound:return None
names=[f'budget/{i:04d}.json' for i in range(1,321)]+['states/CLOSED_LOCKED.json','states/PAUSED_LOCKED.json','CONTROL.json','LOCK.json']
for stage,cap in {'A':48,'B':96,'C':72,'D':48,'E':56}.items():
 names += [f'locks/{stage}.json',f'states/{stage}-running.json',f'states/{stage}-finished.json']+[f'results/{stage}-{i:03d}.json' for i in range(1,cap+1)]
with concurrent.futures.ThreadPoolExecutor(max_workers=32) as pool:raw=list(pool.map(lambda n:get(P+n),names))
existing=[n for n,b in zip(names,raw) if b is not None]
assert not existing,'EXISTING_CAMPAIGN_STATE_STOP'
old='research/gemini-model-native500-20261107/gpt-luna-terra-mechanism1000-20261110/states/CLOSED_LOCKED.json';b=get(old);s=json.loads(b);assert s['reserved_total']==776 and s['success']==776 and s['failed']==s['unknown']==0 and not s['enabled'] and s['max_new']==0
receipt={'campaign':'GPT_LUNA_LF_VARIANCE320_20261110','reserved':0,'known_objects_checked':len(names),'known_namespace_empty':True,'github_namespace_absent_verified_before_run':True,'old_closed_sha256':hashlib.sha256(b).hexdigest(),'old_reserved':776,'run':os.environ['GITHUB_RUN_ID'],'generation_calls':0,'limitation':'No bucket listing permission; checked complete budget/stage schema plus GitHub path/run history, not arbitrary unknown object names.'}
payload=json.dumps(receipt,sort_keys=True).encode();key=P+'preflight/'+os.environ['GITHUB_RUN_ID']+'.json';B.blob(key).upload_from_string(payload,if_generation_match=0,timeout=30,retry=None);assert get(key)==payload
print(json.dumps(receipt));pathlib.Path(os.environ['RUNNER_TEMP'],'variance320-preflight.json').write_bytes(payload)
