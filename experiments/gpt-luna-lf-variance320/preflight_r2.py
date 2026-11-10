import concurrent.futures,json,hashlib,pathlib,os
from google.cloud import storage
from google.api_core.exceptions import NotFound,Forbidden
import google.auth
from google.auth.transport.requests import AuthorizedSession
P='research/gemini-model-native500-20261107/gpt-luna-lf-variance320-20261110/'
CAMPAIGN='GPT_LUNA_LF_VARIANCE320_20261110'
assert os.environ['GITHUB_REF']=='refs/heads/research/gemini-model-native500-20261107' and os.environ['GITHUB_ACTOR']=='martin830000-spec' and os.environ['GITHUB_RUN_ATTEMPT']=='1'
B=storage.Client(project='gen-lang-client-0422436907').bucket('lao-translator-src-460077888071')
def get(n):
 try:return B.blob(n).download_as_bytes(timeout=30,retry=None)
 except NotFound:return None
names=[f'budget/{i:04d}.json' for i in range(1,321)]+['states/CLOSED_LOCKED.json','states/PAUSED_LOCKED.json','CONTROL.json','LOCK.json']
for stage,cap in {'A':48,'B':96,'C':72,'C2':48,'D':48,'E1':28,'E2':28}.items():
 names += [f'locks/{stage}.json',f'locks/{stage}.RELEASED.json',f'states/{stage}-running.json',f'states/{stage}-finished.json']+[f'results/{stage}-{i:03d}.json' for i in range(1,cap+1)]
with concurrent.futures.ThreadPoolExecutor(max_workers=32) as pool:raw=list(pool.map(lambda n:get(P+n),names))
existing={n:json.loads(b) for n,b in zip(names,raw) if b is not None};rs=[existing[n] for n in names[:320] if n in existing]
assert all(f'budget/{i:04d}.json' in existing for i in range(1,len(rs)+1))
assert all(x['campaign']==CAMPAIGN and x['model']=='gpt-6-luna' for x in rs)
listing=[];list_status='not_attempted'
try:
 listing=[x.name for x in B.client.list_blobs(B,prefix=P,timeout=30,retry=None)];list_status='success'
except Forbidden:list_status='403_listing_not_permitted'
old='research/gemini-model-native500-20261107/gpt-luna-terra-mechanism1000-20261110/states/CLOSED_LOCKED.json';b=get(old);s=json.loads(b);assert s['reserved_total']==776 and s['success']==776 and s['failed']==s['unknown']==0 and not s['enabled'] and s['max_new']==0
provider={'status':'not_attempted'}
try:
 cred,_=google.auth.default(scopes=['https://www.googleapis.com/auth/cloud-platform']);resp=AuthorizedSession(cred).get('https://iam.googleapis.com/v1/projects/460077888071/locations/global/workloadIdentityPools/lao-github-deploy/providers/gemini-research',timeout=20);provider={'http_status':resp.status_code}
 if resp.status_code==200:
  j=resp.json();provider.update(attributeCondition=j.get('attributeCondition'),attributeMapping=j.get('attributeMapping'))
except Exception as e:provider={'read_error_class':type(e).__name__}
control=existing.get('CONTROL.json');
if control is None:
 control={'campaign':CAMPAIGN,'status':'PREFLIGHT_LOCKED','enabled':False,'max_new':0,'approved_total':320,'reserved_total':len(rs)};data=json.dumps(control,sort_keys=True).encode();B.blob(P+'CONTROL.json').upload_from_string(data,if_generation_match=0,timeout=30,retry=None);assert get(P+'CONTROL.json')==data
else:assert control['campaign']==CAMPAIGN and not control['enabled'] and control['max_new']==0
receipt={'campaign':CAMPAIGN,'reserved':len(rs),'existing_keys':list(existing),'known_objects_checked':len(names),'listing_status':list_status,'listed_names':listing,'old_closed_sha256':hashlib.sha256(b).hexdigest(),'old_reserved':776,'control':control,'provider':provider,'run':os.environ['GITHUB_RUN_ID'],'generation_calls':0,'commit':os.environ['GITHUB_SHA']}
payload=json.dumps(receipt,sort_keys=True).encode();key=P+'preflight/'+os.environ['GITHUB_RUN_ID']+'.json';B.blob(key).upload_from_string(payload,if_generation_match=0,timeout=30,retry=None);assert get(key)==payload
print(json.dumps(receipt));pathlib.Path(os.environ['RUNNER_TEMP'],'variance320-preflight.json').write_bytes(payload)
