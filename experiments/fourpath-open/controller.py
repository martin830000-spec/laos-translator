"""New scope-authorized research controller. No numeric campaign cap; finite plan and one-time journal.
Reserve + fsync before one send; never retry or repair. BACK depends on displayed FIRST.
"""
import json,hashlib,time,copy,os,datetime
from pathlib import Path
ID='GEMINI_FOURPATH_OPEN_20261104'
def digest(x):return hashlib.sha256(json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def validate(plan):
 seen={}
 for t in plan['tasks']:
  if not isinstance(t.get('slot'),int)or t['slot']in seen or t.get('path')not in ['KF','KB','LF','LB']:raise ValueError('TASK')
  if 'displayed_seed'in t:
   if plan.get('phase')not in ['BACK_PROBE','LATENCY']or not t['path'].endswith('F')or set(t)!={'slot','case_id','path','displayed_seed','seed_response_id','seed_sha256'}:raise ValueError('SEED_BOUNDARY')
   if not t['displayed_seed'].strip()or hashlib.sha256(t['displayed_seed'].encode()).hexdigest()!=t['seed_sha256']or not t['seed_response_id']:raise ValueError('SEED_HASH')
   seen[t['slot']]=t;continue
  allowed={'slot','case_id','path','model','variant','input'}if t['path'].endswith('F')else{'slot','case_id','path','model','variant','depends_on'}
  if set(t)!=allowed:raise ValueError('NO_HIDDEN_CONTEXT')
  if t['path'].endswith('F'):
   if not isinstance(t['input'],str)or not t['input'].strip():raise ValueError('SOURCE')
  else:
   dep=seen.get(t['depends_on'])
   if not dep or dep['path']!=t['path'][0]+'F'or dep['case_id']!=t['case_id']:raise ValueError('FIRST_DEPENDENCY')
  seen[t['slot']]=t
 if not seen:raise ValueError('EMPTY_PLAN')
 return True
def run(plan,approval,build,inspect,send,journal,persist):
 validate(plan)
 if approval.get('campaign_id')!=ID or plan.get('campaign_id')!=ID:raise ValueError('NEW_CAMPAIGN_ONLY')
 n=None;prior=approval.get('actual_attempts')
 if approval.get('authorization_mode')!='unbounded-within-scope'or approval.get('approved_limit')is not None or type(prior)is not int or prior<0 or approval.get('planned_task_count')!=len(plan['tasks']):raise ValueError('SCOPE_OR_PHASE_PLAN')
 if approval.get('authorized')is not True or approval.get('execution_enabled')is not True or approval.get('plan_sha256')!=digest(plan):raise ValueError('LOCKED_OR_UNBOUND')
 if plan.get('phase')=='FINAL':
  freeze=plan.get('final_freeze',{});code=hashlib.sha256((Path(__file__).parent/'contracts.cjs').read_bytes()).hexdigest()
  cases={t['case_id']:hashlib.sha256(t['input'].encode()).hexdigest()for t in plan['tasks']if t['path'].endswith('F')}
  if freeze.get('state')!='FROZEN_BEFORE_OPEN'or freeze.get('contracts_sha256')!=code or freeze.get('case_hash_manifest')!=cases or not freeze.get('rubric_sha256'):raise ValueError('FINAL_FREEZE_REQUIRED')
 # Exclusive journal also makes a repeated invocation of a consumed plan fail closed.
 with Path(journal).open('x',encoding='utf8')as f:f.write(digest(plan)+'\n');f.flush();os.fsync(f.fileno())
 result={'campaign_id':ID,'attempts':0,'prior':prior,'slots':[],'automatic_retries':0,'judge_calls':0};by={}
 for t in plan['tasks']:
  x=copy.deepcopy(t);by[t['slot']]=x;result['slots'].append(x)
  if 'displayed_seed'in t:
   x.update(status='SUCCESS',attempted=False,displayed=t['displayed_seed'],is_prior_displayed_FIRST=True);persist(copy.deepcopy(result));continue
  if t['path'].endswith('B'):
   dep=by[t['depends_on']]
   if dep.get('status')!='SUCCESS':x.update(status='SKIPPED_DEPENDENCY',attempted=False);persist(copy.deepcopy(result));continue
   s=dep['displayed']
  else:s=t['input']
  prepare_start=time.perf_counter_ns();q=build(t['path'],t['model'],t['variant'],s);build_end=time.perf_counter_ns()
  if q['model']not in ['gemini-3.1-flash-lite','gemini-3.5-flash-lite','gemini-3.8-flash']:raise ValueError('GEMINI_ONLY')
  if result['attempts']>=len(plan['tasks']):raise ValueError('PLAN_BOUNDARY')
  result['attempts']+=1;x.update(attempted=True,input=s,input_sha256=hashlib.sha256(s.encode()).hexdigest(),request=q,request_sha256=digest(q),global_attempt=prior+result['attempts'],status='SENT_OR_UNKNOWN',build_ms=(build_end-prepare_start)/1e6,prepare_begin_ns=prepare_start,sent_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
  with Path(journal).open('a',encoding='utf8')as f:f.write(json.dumps({'attempt':x['global_attempt'],'request_sha256':x['request_sha256']})+'\n');f.flush();os.fsync(f.fileno())
  persist(copy.deepcopy(result));start=time.perf_counter_ns()
  try:
   packet=send(q);x.update(raw=packet['raw'],wire=packet['wire'])
   if packet['wire'].get('http_status')!=200:raise ValueError('HTTP_FAILURE')
   if packet['raw'].get('modelVersion')and not packet['raw']['modelVersion'].startswith(q['model']):raise ValueError('MODEL_CHANGED')
   x.update(inspect(packet['raw'],t['path'],s))
  except Exception as e:x.update(status='FAILED',failure_kind=type(e).__name__,usage=None,estimated_usd=None,displayed=None)
  finally:
   end=time.perf_counter_ns();x['request_to_display_ready_ms']=(end-start)/1e6;x['first_or_back_ready_ms']=(end-prepare_start)/1e6;x['display_ready_ns']=end;persist(copy.deepcopy(result))
 return result
def close(approval,actual):
 if type(actual)is not int or actual<0:raise ValueError('ACTUAL')
 return dict(approval,actual_attempts=actual,authorized=False,execution_enabled=False,planned_task_count=0,state='SESSION_CLOSED',remaining_numeric_limit=None)
