"""Future research controller. Zero authorized calls now. No built-in credentials/sender.
Reserve + fsync before one send; never retry or repair. BACK depends on displayed FIRST.
"""
import json,hashlib,time,copy,os
from pathlib import Path
ID='GEMINI_FOURPATH_NEXT_20261104'
def digest(x):return hashlib.sha256(json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def validate(plan):
 seen={}
 for t in plan['tasks']:
  if not isinstance(t.get('slot'),int)or t['slot']in seen or t.get('path')not in ['KF','KB','LF','LB']:raise ValueError('TASK')
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
 n=approval.get('approved_new');prior=approval.get('actual_attempts')
 if type(n)is not int or type(prior)is not int or n<=0 or prior<0 or prior+len(plan['tasks'])>n:raise ValueError('NO_NEW_APPROVAL_OR_BUDGET')
 if approval.get('authorized')is not True or approval.get('execution_enabled')is not True or approval.get('plan_sha256')!=digest(plan):raise ValueError('LOCKED_OR_UNBOUND')
 # Exclusive journal also makes a repeated invocation of a consumed plan fail closed.
 with Path(journal).open('x',encoding='utf8')as f:f.write(digest(plan)+'\n');f.flush();os.fsync(f.fileno())
 result={'campaign_id':ID,'attempts':0,'prior':prior,'slots':[],'automatic_retries':0,'judge_calls':0};by={}
 for t in plan['tasks']:
  x=copy.deepcopy(t);by[t['slot']]=x;result['slots'].append(x)
  if t['path'].endswith('B'):
   dep=by[t['depends_on']]
   if dep.get('status')!='SUCCESS':x.update(status='SKIPPED_DEPENDENCY',attempted=False);persist(copy.deepcopy(result));continue
   s=dep['displayed']
  else:s=t['input']
  q=build(t['path'],t['model'],t['variant'],s)
  if q['model']not in ['gemini-3.1-flash-lite','gemini-3.5-flash-lite','gemini-3.8-flash']:raise ValueError('GEMINI_ONLY')
  if prior+result['attempts']>=n:raise ValueError('BUDGET')
  result['attempts']+=1;x.update(attempted=True,input=s,input_sha256=hashlib.sha256(s.encode()).hexdigest(),request=q,request_sha256=digest(q),global_attempt=prior+result['attempts'],status='SENT_OR_UNKNOWN')
  with Path(journal).open('a',encoding='utf8')as f:f.write(json.dumps({'attempt':x['global_attempt'],'request_sha256':x['request_sha256']})+'\n');f.flush();os.fsync(f.fileno())
  persist(copy.deepcopy(result));start=time.perf_counter_ns()
  try:
   packet=send(q);x.update(raw=packet['raw'],wire=packet['wire'])
   if packet['wire'].get('http_status')!=200:raise ValueError('HTTP_FAILURE')
   if packet['raw'].get('modelVersion')and not packet['raw']['modelVersion'].startswith(q['model']):raise ValueError('MODEL_CHANGED')
   x.update(inspect(packet['raw']))
  except Exception as e:x.update(status='FAILED',failure_kind=type(e).__name__,usage=None,estimated_usd=None,displayed=None)
  finally:x['request_to_display_ready_ms']=(time.perf_counter_ns()-start)/1e6;persist(copy.deepcopy(result))
 return result
def close(approval,actual):
 if type(actual)is not int or actual<0 or actual>approval['approved_new']:raise ValueError('ACTUAL')
 return dict(approval,actual_attempts=actual,authorized=False,execution_enabled=False,maximum_new_attempts=0,unused=approval['approved_new']-actual,state='LOCKED')
