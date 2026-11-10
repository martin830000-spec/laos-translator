import concurrent.futures,json,hashlib,pathlib,os
from google.cloud import storage
from google.api_core.exceptions import NotFound,Forbidden
import google.auth
from google.auth.transport.requests import AuthorizedSession
P='research/gemini-model-native500-20261107/gpt-source-vs-prompt-factorial320-20261111/'
CAMPAIGN='GPT_SOURCE_VS_PROMPT_FACTORIAL320_20261111'
assert os.environ['GITHUB_REF']=='refs/heads/research/gemini-model-native500-20261107' and os.environ['GITHUB_ACTOR']=='martin830000-spec' and os.environ['GITHUB_RUN_ATTEMPT']=='1'
B=storage.Client(project='gen-lang-client-0422436907').bucket('lao-translator-src-460077888071')
def get(n):
 try:return B.blob(n).download_as_bytes(timeout=30,retry=None)
 except NotFound:return None
names=[f'budget/{i:04d}.json' for i in range(1,321)]+['states/CLOSED_LOCKED.json','states/PAUSED_LOCKED.json','CONTROL.json','LOCK.json']
for stage,cap in {'A1':50,'A2':50,'A3':50,'A4':50,'B1':24,'B2':16,'C':40}.items():
 names += [f'locks/{stage}.json',f'locks/{stage}.RELEASED.json',f'states/{stage}-running.json',f'states/{stage}-finished.json']+[f'results/{stage}-{i:03d}.json' for i in range(1,cap+1)]
with concurrent.futures.ThreadPoolExecutor(max_workers=32) as pool:raw=list(pool.map(lambda n:get(P+n),names))
existing={n:json.loads(b) for n,b in zip(names,raw) if b is not None};rs=[existing[n] for n in names[:320] if n in existing]
assert all(f'budget/{i:04d}.json' in existing for i in range(1,len(rs)+1))
assert all(x['campaign']==CAMPAIGN and x['model'] in ('gpt-6-luna','gemini-3.8-flash') for x in rs)
listing=[];list_status='not_attempted'
try:
 listing=[x.name for x in B.client.list_blobs(B,prefix=P,timeout=30,retry=None)];list_status='success'
except Forbidden:list_status='403_listing_not_permitted'
old='research/gemini-model-native500-20261107/gpt-luna-source-variant320-20261110/states/CLOSED_LOCKED.json';b=get(old);s=json.loads(b);assert s['reserved_total']==290 and s['success']==290 and s['failed']==s['unknown']==0 and not s['enabled'] and s['max_new']==0
assert hashlib.sha256(b).hexdigest()=='99bf3ffcf49186ef932b62c2089105b7bd0e3747accadc8bc53dc061e7b1068a','OLD_CLOSED_BYTES_CHANGED'
old_authority=get('research/gemini-model-native500-20261107/gpt-luna-source-variant320-20261110/controls/CLOSED/CLOSED_LOCKED.json');assert old_authority==b
with concurrent.futures.ThreadPoolExecutor(max_workers=32) as pool:old_budget=list(pool.map(lambda i:get('research/gemini-model-native500-20261107/gpt-luna-source-variant320-20261110/budget/'+f'{i:04d}.json'),range(1,321)))
assert all(old_budget[:290]) and not any(old_budget[290:])
old_res=[json.loads(x) for x in old_budget[:290]]
with concurrent.futures.ThreadPoolExecutor(max_workers=32) as pool:old_results=list(pool.map(lambda x:get('research/gemini-model-native500-20261107/gpt-luna-source-variant320-20261110/results/'+x['slot']+'.json'),old_res))
assert all(x and json.loads(x)['success'] and not json.loads(x).get('unknown') for x in old_results)
provider={'status':'not_attempted'}
try:
 cred,_=google.auth.default(scopes=['https://www.googleapis.com/auth/cloud-platform']);resp=AuthorizedSession(cred).get('https://iam.googleapis.com/v1/projects/460077888071/locations/global/workloadIdentityPools/lao-github-deploy/providers/gemini-research',timeout=20);provider={'http_status':resp.status_code}
 if resp.status_code==200:
  j=resp.json();provider.update(attributeCondition=j.get('attributeCondition'),attributeMapping=j.get('attributeMapping'))
except Exception as e:provider={'read_error_class':type(e).__name__}
assert not rs and not any(n.startswith(('results/','locks/','states/')) for n in existing),'EXISTING_NEW_CAMPAIGN_REQUIRES_RECONCILIATION'
control=existing.get('CONTROL.json');
if control is None:
 control={'campaign':CAMPAIGN,'status':'PREFLIGHT_LOCKED','enabled':False,'max_new':0,'approved_total':320,'reserved_total':len(rs)};data=json.dumps(control,sort_keys=True).encode();B.blob(P+'CONTROL.json').upload_from_string(data,if_generation_match=0,timeout=30,retry=None);assert get(P+'CONTROL.json')==data
else:assert control['campaign']==CAMPAIGN and not control['enabled'] and control['max_new']==0
import httpx
model_access={}
with httpx.Client(transport=httpx.HTTPTransport(retries=0),timeout=20,follow_redirects=False) as client:
 for name,url,env,header in [('luna','https://api.openai.com/v1/models/gpt-6-luna','OPENAI_API_KEY','Authorization'),('gemini','https://generativelanguage.googleapis.com/v1beta/models/gemini-3.8-flash','GEMINI_API_KEY','x-goog-api-key')]:
  key=os.environ.get(env);entry={'present':bool(key),'allowed':False}
  if key:
   try:
    resp=client.get(url,headers={header:('Bearer '+key if name=='luna' else key)});entry.update(http_status=resp.status_code,allowed=resp.status_code==200)
   except Exception as ex:entry['error_class']=type(ex).__name__
  model_access[name]=entry
receipt={'model_access':model_access,'campaign' :CAMPAIGN,'reserved':len(rs),'existing_keys':list(existing),'known_objects_checked':len(names),'listing_status':list_status,'listed_names':listing,'old_closed_sha256':hashlib.sha256(b).hexdigest(),'old_reserved':290,'control':control,'provider':provider,'run':os.environ['GITHUB_RUN_ID'],'generation_calls':0,'commit':os.environ['GITHUB_SHA']}
payload=json.dumps(receipt,sort_keys=True).encode();key=P+'preflight/'+os.environ['GITHUB_RUN_ID']+'.json';B.blob(key).upload_from_string(payload,if_generation_match=0,timeout=30,retry=None);assert get(key)==payload
print(json.dumps(receipt));pathlib.Path(os.environ['RUNNER_TEMP'],'factorial320-preflight.json').write_bytes(payload)
