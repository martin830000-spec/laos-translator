"""Attempt-bounded dependency runner. No network on import/dry-run; no retries."""
from pathlib import Path
import json,hashlib,copy,time,datetime,urllib.request,urllib.error,os
import adapter as a
ID='GEMINI_ITERATE320_20261103'
def require(ok):
 if not ok:raise AssertionError('CONTRACT_REJECTED')
def digest(x):return hashlib.sha256(json.dumps(x,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
def authorize(plan,approval):
 if approval.get('authorized')is not True or approval.get('maximum_new_attempts',0)<=0:raise PermissionError('NEW_PAID_APPROVAL_REQUIRED')
 require(approval['campaign_id']==plan['campaign_id']==ID)
 require(plan.get('data_bound')is True)
 require(approval['plan_sha256']==digest(plan))
 require(len(plan['tasks'])<=approval['maximum_new_attempts'])
 require(approval['prior_new_attempts']==plan['prior_new_attempts'])
 require(approval['prior_new_attempts']+approval['maximum_new_attempts']<=approval['whole_campaign_limit'])
 require(approval['whole_campaign_limit']>0 and plan['recommended_only']is False)
def validate(plan):
 seen=set()
 for t in plan['tasks']:
  require(t['slot']not in seen and t['side']in ('K','L'))
  if t['stage']=='first':require(type(t['input'])is str and t['input'].strip())
  else:
   require(t['stage']=='back')
   require(not(set(t)&{'source','context','history','states','links','answer','grade','original'}))
   if t.get('depends_on')is not None:require(t['depends_on']in seen)
   else:
    f=t['fixed_first'];require(f['status']=='SUCCESS'and f['response_id']and f['text'].strip())
    require(hashlib.sha256(f['text'].encode()).hexdigest()==f['sha256'])
  seen.add(t['slot'])
 return True
def dry_run(plan):
 validate(plan);return dict(network_calls=0,planned_attempts=len(plan['tasks']),manifest_sha256=digest(plan),approval_required=True)
def run(plan,approval,send,journal,persist=lambda r:None):
 authorize(plan,approval);validate(plan)
 result=dict(campaign_id=ID,attempts=0,prior_new_attempts=plan['prior_new_attempts'],slots=[],automatic_retries=0,status='RUNNING')
 by={};journal=Path(journal)
 with journal.open('x',encoding='utf-8')as f:f.write(digest(plan)+'\n')
 for task in plan['tasks']:
  x=copy.deepcopy(task);result['slots'].append(x);by[x['slot']]=x
  if x['stage']=='back'and x.get('depends_on')is not None and by[x['depends_on']]['status']!='SUCCESS':
   x.update(status='SKIPPED_DEPENDENCY',attempted=False);persist(copy.deepcopy(result));continue
  text=x['input']if x['stage']=='first'else by[x['depends_on']]['translation']if x.get('depends_on')is not None else x['fixed_first']['text']
  q=a.build_first(text,x['side'],x['profile'],plan.get('context'))if x['stage']=='first'else a.build_back(text,x['side'],x['profile'])
  require(result['attempts']<approval['maximum_new_attempts'])
  require(plan['prior_new_attempts']+result['attempts']<approval['whole_campaign_limit'])
  result['attempts']+=1;x.update(attempted=True,attempt=result['attempts'],input=text,input_sha256=hashlib.sha256(text.encode()).hexdigest(),request=q,request_sha256=digest(q),sent_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),status='SENT_OR_UNKNOWN')
  with journal.open('a',encoding='utf-8')as f:f.write(json.dumps({'attempt':x['attempt'],'slot':x['slot'],'sha256':x['request_sha256']})+'\n');f.flush();os.fsync(f.fileno())
  persist(copy.deepcopy(result));start=time.perf_counter()
  try:
   response=send(q);raw=response['raw'];wire=response['wire'];x.update(response=raw,wire=wire,http_status=wire['http_status'],api_ms=wire['api_ms'],usage=raw.get('usageMetadata'),response_id=raw.get('responseId'))
   if wire['http_status']in (401,403,404,429):raise PermissionError('AUTH_MODEL_OR_QUOTA_BLOCKED')
   if wire['http_status']!=200:raise ValueError('HTTP_FAILURE')
   if raw.get('modelVersion')and not raw['modelVersion'].startswith(q['model']):raise PermissionError('MODEL_ID_CHANGED')
   x.update(a.inspect(raw,text,x['side'],x['stage'],x['profile']),**a.usage_cost(raw,q['model'],wire))
  except PermissionError:
   x.update(status='FAILED',failure_kind='AUTH_OR_MODEL');result['status']='EXECUTION_BLOCKED';persist(copy.deepcopy(result));raise
  except Exception as exc:x.update(status='FAILED',failure_kind=type(exc).__name__)
  finally:x['ready_ms']=(time.perf_counter()-start)*1000;persist(copy.deepcopy(result))
 result['status']='PHASE_COMPLETE_REVIEW_REQUIRED';persist(copy.deepcopy(result));return result
class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,*args,**kwargs):raise ValueError('redirect forbidden')
def transport(api_key):
 # Construct only AFTER authorize(). No model metadata/auth probe.
 def send(q):
  url='https://generativelanguage.googleapis.com/v1beta/models/'+q['model']+':generateContent'
  body=json.dumps(q['payload'],ensure_ascii=False).encode();req=urllib.request.Request(url,data=body,headers={'Content-Type':'application/json','x-goog-api-key':api_key});st=time.perf_counter()
  try:
   with urllib.request.build_opener(NoRedirect).open(req,timeout=90)as r:txt=r.read().decode();status=r.status;headers={k:r.headers.get(k)for k in ['date','content-type','x-request-id','x-gemini-service-tier']}
  except urllib.error.HTTPError as e:txt=e.read().decode(errors='replace');status=e.code;headers={}
  try:raw=json.loads(txt)
  except ValueError:raw={}
  return {'raw':raw,'wire':dict(endpoint=url,http_status=status,request_body_utf8=body.decode(),response_body_utf8=txt,response_headers=headers,api_ms=(time.perf_counter()-st)*1000)}
 return send
