"""New approved300 controller; injected Gemini-only sender; no retries/judge."""
from pathlib import Path
import json,hashlib,subprocess,time,datetime,copy,os
ID='GEMINI_FULL_AUTONOMOUS300_20261104'
ROOT=Path(__file__).resolve().parent
CAPS={'DISCOVERY':80,'REFINEMENT':64,'BACK_COMPARE':48,'REGRESSION':48,'FINAL':80}
def require(ok):
 if not ok:raise ValueError('CONTRACT_REJECTED')
def digest(x):return hashlib.sha256(json.dumps(x,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
def js(x):
 r=subprocess.run(['node',str(ROOT/'node_cli.cjs')],input=json.dumps(x,ensure_ascii=False),encoding='utf-8',capture_output=True,check=True,timeout=15)
 return json.loads(r.stdout)
def authorize(plan,approval,config):
 require(approval.get('authorized')is True and approval.get('execution_enabled')is True)
 require(approval['campaign_id']==plan['campaign_id']==ID)
 require(approval['user_approved_limit']==approval['whole_campaign_limit']==300)
 require(config['stage']==plan['phase'] and config['phase_cap']==CAPS[plan['phase']])
 prior=config['prior_actual_attempts'];require(prior==approval['actual_consumed']==plan['prior_actual_attempts'])
 require(type(prior)is int and 0<=prior<=300)
 require(len(plan['tasks'])<=config['phase_cap'] and len(plan['tasks'])<=approval['maximum_new_attempts'])
 require(prior+len(plan['tasks'])<=300 and plan.get('data_bound')is True)
 require(approval['plan_sha256']==config['plan_sha256']==digest(plan))
 require(config['source_manifest_sha256']==plan['source_manifest_sha256'])
 return True
def validate(plan):
 seen={}
 for t in plan['tasks']:
  require(type(t['slot'])is int and t['slot']not in seen and t['side']in('K','L'))
  if t['stage']=='first':require(type(t['input'])is str and t['input'].strip() and t['profile']in('SERVICE_FIRST','BASE31_MIN','BASE31_LOW','SCOPE31_MIN','SCOPE31_LOW','SCOPE35_MIN','SCOPE35_LOW','SCOPE38_LOW','REL31_LOW','REL35_MIN','KO31_MIN'))
  else:
   require(t['stage']=='back' and t['profile']in('SERVICE_BACK','BACK31_MIN','BACK31_LOW','BACK35_MIN','BACK38_LOW'))
   require(set(t).isdisjoint({'input','original','source','context','answer','grade','history'}))
   d=seen.get(t['depends_on']);require(d is not None and d['stage']=='first'and d['case_id']==t['case_id']and d['side']==t['side'])
  seen[t['slot']]=t
 require(0<len(seen)<=CAPS[plan['phase']]);return True
def cost(raw,model):
 u=raw.get('usageMetadata',{});p=u.get('promptTokenCount');v=u.get('candidatesTokenCount');t=u.get('thoughtsTokenCount');total=u.get('totalTokenCount');cache=u.get('cachedContentTokenCount')
 out={'estimated_usd':None,'invoice_verified':False,'reported_thinking_tokens':t,'derived_thinking_tokens':None,'reported_cached_tokens':cache}
 if type(p)is not int or type(v)is not int:return out
 if type(t)is not int:
  if type(total)is not int or total<p+v:return out
  t=total-p-v;out['derived_thinking_tokens']=t
 ip,op,cp={'gemini-3.1-flash-lite':(.25,1.5,.025),'gemini-3.5-flash-lite':(.30,2.5,.03),'gemini-3.8-flash':(.75,3.75,.075)}[model]
 out.update(billed_output_including_thinking=v+t,estimated_usd=((p-cache)*ip+cache*cp+(v+t)*op)/1e6 if type(cache)is int else(p*ip+(v+t)*op)/1e6,pricing_basis='Standard USD per1M tokens 2026-11-03; missing cache=no assumed discount; no tools')
 return out
def run(plan,approval,config,send,journal,persist):
 authorize(plan,approval,config);validate(plan)
 out={'campaign_id':ID,'phase':plan['phase'],'prior_actual_attempts':plan['prior_actual_attempts'],'attempts':0,'automatic_retries':0,'judge_calls':0,'slots':[],'status':'RUNNING'};by={}
 with Path(journal).open('x',encoding='utf-8')as f:f.write(digest(plan)+'\n')
 for task in plan['tasks']:
  x=copy.deepcopy(task);out['slots'].append(x);by[x['slot']]=x
  if x['stage']=='back':
   dep=by[x['depends_on']]
   if dep.get('status')!='SUCCESS':x.update(status='SKIPPED_DEPENDENCY',attempted=False);persist(copy.deepcopy(out));continue
   text=dep['translation']
  else:text=x['input']
  q=js(dict(mode='build',text=text,side=x['side'],profile=x['profile']))
  require(q['model']in('gemini-3.1-flash-lite','gemini-3.5-flash-lite','gemini-3.8-flash'))
  require(out['attempts']<config['phase_cap'] and out['prior_actual_attempts']+out['attempts']<300)
  out['attempts']+=1
  x.update(input=text,input_sha256=hashlib.sha256(text.encode()).hexdigest(),request=q,request_sha256=digest(q),attempted=True,attempt=out['attempts'],sent_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),status='SENT_OR_UNKNOWN')
  with Path(journal).open('a',encoding='utf-8')as f:f.write(json.dumps({'attempt':x['attempt'],'request_sha256':x['request_sha256']})+'\n');f.flush();os.fsync(f.fileno())
  persist(copy.deepcopy(out));st=time.perf_counter()
  try:
   response=send(q);raw=response['raw'];wire=response['wire']
   x.update(response=raw,wire=wire,http_status=wire['http_status'],api_ms=wire['api_ms'],usage=raw.get('usageMetadata'),response_id=raw.get('responseId'))
   if wire['http_status']in(401,403,404,429):raise PermissionError('AUTH_MODEL_QUOTA')
   if wire['http_status']!=200:raise ValueError('HTTP_FAILURE')
   if raw.get('modelVersion')and not raw['modelVersion'].startswith(q['model']):raise PermissionError('MODEL_CHANGED')
   x.update(js(dict(mode='inspect',raw=raw)),**cost(raw,q['model']))
  except PermissionError:
   x.update(status='FAILED',failure_kind='AUTH_MODEL_QUOTA');out['status']='BLOCKED';persist(copy.deepcopy(out));raise
  except Exception as exc:x.update(status='FAILED',failure_kind=type(exc).__name__)
  finally:x['display_ready_ms']=(time.perf_counter()-st)*1000;persist(copy.deepcopy(out))
 out['status']='PHASE_COMPLETE_REVIEW_REQUIRED';persist(copy.deepcopy(out));return out
