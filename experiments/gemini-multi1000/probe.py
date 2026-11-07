import datetime, http.client, json, os, time
from pathlib import Path
MODELS=['gemini-3.1-flash-lite','gemini-3.5-flash-lite','gemini-3.6-flash','gemini-3.8-flash']
result={'campaign':'GEMINI_MULTI1000_20261107','purpose':'access and returned version preflight, synthetic input only','limit':1000,'phase_limit':4,'attempts':0,'records':[]}
output=Path('probe-result.json')
def save():output.write_text(json.dumps(result,ensure_ascii=False,indent=2))
assert os.environ['GITHUB_RUN_ATTEMPT']=='1'
key=os.environ['GEMINI_API_KEY']
for model in MODELS:
 record={'model':model,'metadata':None,'attempted':False}
 result['records'].append(record)
 connection=http.client.HTTPSConnection('generativelanguage.googleapis.com',timeout=40)
 try:
  connection.request('GET','/v1beta/models/'+model,headers={'x-goog-api-key':key})
  response=connection.getresponse();raw=response.read().decode();record['metadata_http']=response.status
  record['metadata']=json.loads(raw.replace(key,'REDACTED'))
  if response.status!=200:
   save();continue
  payload={'contents':[{'role':'user','parts':[{'text':'Translate this Korean sentence into Lao. Return only the translation: 오늘 저녁에 전화할게.'}]}],'generationConfig':{'maxOutputTokens':256,'thinkingConfig':{'thinkingLevel':'minimal' if 'lite' in model else 'low'}}}
  record['request']=payload;record['sent_at']=datetime.datetime.now(datetime.timezone.utc).isoformat()
  result['attempts']+=1;record['attempted']=True;save()
  start=time.perf_counter();connection.request('POST','/v1beta/models/'+model+':generateContent',body=json.dumps(payload).encode(),headers={'x-goog-api-key':key,'Content-Type':'application/json'})
  response=connection.getresponse();headers_at=time.perf_counter();raw=response.read().decode();end=time.perf_counter()
  record.update(http_status=response.status,ttfb_ms=(headers_at-start)*1000,total_ms=(end-start)*1000,raw=json.loads(raw.replace(key,'REDACTED')))
  version=record['raw'].get('modelVersion');record['returned_model_version']=version
  record['version_matches']=bool(version and version.startswith(model))
  if response.status in [401,403,429] or response.status>=500:
   result['stop']='PROVIDER_ACCESS_OR_LIMIT';save();break
 except Exception as error:
  record['error_type']=type(error).__name__;result['stop']='TRANSPORT_OR_PROTOCOL';save();break
 finally:
  connection.close();save()
print(json.dumps({'attempts':result['attempts'],'stop':result.get('stop')}))
