"""Transport-free REAL128 stage accounting: injected trusted sender only.

No network client, no API key access, and no raw private data in repository.
Actual requests are only possible when a separate audited private runner
provides an explicit send callback AFTER approval and phase validation.
"""
from pathlib import Path
import datetime,hashlib,json,copy,time,os
import engine
ID=engine.ID
PHASES={'DISCOVERY_A':48,'REFINEMENT_B':32,'INDEPENDENT_FINAL':48}
def require(ok):
 if not ok:raise AssertionError('CONTRACT_REJECTED')
def digest(x):return hashlib.sha256(json.dumps(x,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
def authorize(plan,approval,config):
 if approval.get('authorized') is not True or approval.get('execution_enabled') is not True:raise PermissionError('NEW_PAID_APPROVAL_REQUIRED')
 require(approval.get('campaign_id')==plan.get('campaign_id')==ID)
 phase=config['stage'];require(phase in PHASES and plan.get('phase')==phase)
 require(config['phase_cap']==PHASES[phase] and len(plan['tasks'])<=config['phase_cap'])
 prior=config['prior_actual_attempts'];require(prior==approval['actual_consumed']==plan['prior_actual_attempts'])
 require(approval['maximum_new_attempts']>=len(plan['tasks']))
 require(prior+len(plan['tasks'])<=128)
 require(approval['whole_campaign_limit']==128 and approval['user_approved_limit']==128)
 require(plan.get('recommended_only') is False and plan.get('data_bound') is True)
 require(approval['plan_sha256']==config['plan_sha256']==digest(plan))
 require(plan['source_manifest_sha256']==config['source_manifest_sha256'])
 return True

def validate(plan):
 slots=set();by={};groups={}
 for t in plan['tasks']:
  require(type(t['slot']) is int and t['slot'] not in slots);slots.add(t['slot'])
  require(t['side'] in ('K','L') and t['case_id'] and t['arm'] in ('SERVICE','BOUND','FEWSHOT'))
  if t['stage']=='first':
   require(type(t.get('input')) is str and t['input'].strip())
   require(t['profile'] in engine.FIRST_PROFILES[t['side']])
   require(set(t).isdisjoint({'depends_on','fixed_first','original','answer','grade'}))
  else:
   require(t['stage']=='back' and t['profile']==engine.BACK_PROFILE)
   require(t['depends_on'] in by and by[t['depends_on']]['stage']=='first')
   require(t['side']==by[t['depends_on']]['side'] and t['case_id']==by[t['depends_on']]['case_id'] and t['arm']==by[t['depends_on']]['arm'])
   require(set(t).isdisjoint({'input','source','context','history','original','answer','grade','fixed_first'}))
  by[t['slot']]=t
 require(len(slots)>0 and len(slots)<=PHASES[plan['phase']])
 return True

def run(plan,approval,config,send,journal,persist=lambda d:None):
 authorize(plan,approval,config);validate(plan)
 out={'campaign_id':ID,'phase':plan['phase'],'prior_actual_attempts':plan['prior_actual_attempts'],
      'attempts':0,'slots':[],'status':'RUNNING','automatic_retries':0,'reviewer_calls':0,'started_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}
 records={};journal=Path(journal)
 with journal.open('x',encoding='utf-8') as f:f.write(digest(plan)+'\n')
 for task in plan['tasks']:
  x=copy.deepcopy(task);out['slots'].append(x);records[x['slot']]=x
  if x['stage']=='back':
   dep=records[x['depends_on']]
   if dep.get('status')!='SUCCESS':x.update(status='SKIPPED_DEPENDENCY',attempted=False);persist(copy.deepcopy(out));continue
   source=dep['translation']
  else:source=x['input']
  q=engine.build_first(source,x['side'],x['profile']) if x['stage']=='first' else engine.build_back(source,x['side'])
  require(out['attempts']<config['phase_cap'] and out['prior_actual_attempts']+out['attempts']<128)
  out['attempts']+=1
  x.update(attempted=True,attempt=out['attempts'],input=source,input_sha256=hashlib.sha256(source.encode()).hexdigest(),request=q,request_sha256=digest(q),sent_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),status='SENT_OR_UNKNOWN')
  with journal.open('a',encoding='utf-8') as f:
   f.write(json.dumps({'attempt':x['attempt'],'slot':x['slot'],'sha256':x['request_sha256']})+'\n');f.flush();os.fsync(f.fileno())
  persist(copy.deepcopy(out))
  start=time.perf_counter()
  try:
   response=send(q);raw=response['raw'];wire=response['wire']
   x.update(response=raw,wire=wire,http_status=wire['http_status'],api_ms=wire['api_ms'],usage=raw.get('usageMetadata'),response_id=raw.get('responseId'),response_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
   if wire['http_status'] in (401,403,404,429):raise PermissionError('AUTH_QUOTA_OR_MODEL_BLOCKED')
   if wire['http_status']!=200:raise ValueError('HTTP_NON_200')
   if raw.get('modelVersion') and not raw['modelVersion'].startswith(q['model']):raise PermissionError('MODEL_VERSION_MISMATCH')
   x.update(engine.inspect(raw,source,x['side'],x['stage'],x['profile']),**engine.usage_cost(raw,q['model'],wire))
  except PermissionError:
   x.update(status='FAILED',failure_kind='AUTH_QUOTA_OR_MODEL');out['status']='EXECUTION_BLOCKED';persist(copy.deepcopy(out));raise
  except Exception as exc:x.update(status='FAILED',failure_kind=type(exc).__name__)
  finally:x['display_ready_ms']=(time.perf_counter()-start)*1000;persist(copy.deepcopy(out))
 out['status']='PHASE_COMPLETE_REVIEW_REQUIRED';out['completed_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat();persist(copy.deepcopy(out));return out