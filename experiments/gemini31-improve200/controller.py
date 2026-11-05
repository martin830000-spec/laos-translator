"""Bounded new200 campaign. Prior campaigns are never executed or modified."""
import json,hashlib,os,time,copy,datetime
from pathlib import Path
ID='GEMINI31_AUTONOMOUS_IMPROVE_200_20261106'
LIMITS={ph:{'total':n,**{p:n for p in ['KF','LF','KB','LB']}}for ph,n in [('A',72),('B',64),('C',56),('FINAL',72)]}
CAP={p:200 for p in ['KF','LF','KB','LB']}
def digest(x):return hashlib.sha256(json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def check(ok):
 if not ok:raise ValueError('IMPROVE200_CONTRACT')
def validate(plan,a):
 check(a['campaign_id']==plan['campaign_id']==ID and a['authorized'] is True and a['execution_enabled'] is True and a['approved_limit']==200 and a['plan_sha256']==digest(plan))
 check(set(plan)=={'campaign_id','phase','tasks','freeze_sha256'})
 ph=plan['phase'];check(ph in LIMITS and ph==a['phase']);ts=plan['tasks'];check(0<len(ts)<=LIMITS[ph]['total'] and a['actual_attempts']+len(ts)<=200)
 counts={p:0 for p in CAP};seen={};
 for t in ts:
  check(set(t) in [{'slot','case_id','path','variant','input'},{'slot','case_id','path','variant','from_slot'}]);check(type(t['slot']) is int and t['slot']not in seen and t['path'] in CAP)
  p=t['path'];v=t['variant'];check(v in (['SERVICE','BASE_FIRST','KO_JSON','KO_KEY','KO_TEXT','LO_KEY','KO_CHAT','KO_DEMO','TURN_DEMO','CONTRAST_DEMO','BALANCED_DEMO'] if p.endswith('F') else ['SERVICE','FROZEN','KO_JSON','KO_KEY','KO_TEXT','LO_KEY','KO_CHAT','KO_DEMO','TURN_DEMO','CONTRAST_DEMO','BALANCED_DEMO']))
  check(v in ['KO_DEMO','TURN_DEMO','CONTRAST_DEMO','BALANCED_DEMO'])
  if 'from_slot' in t:
   dep=seen.get(t['from_slot']);check(p.endswith('B') and dep and dep['path']==p[0]+'F' and dep['case_id']==t['case_id'])
  else:check(isinstance(t['input'],str) and bool(t['input'].strip()))
  if ph=='B':check(p.endswith('B') and 'input'in t)
  seen[t['slot']]=t;counts[p]+=1
 for p,n in counts.items():check(n<=LIMITS[ph][p] and a['actual_by_path'][p]+n<=CAP[p])
 check(sum(a['actual_by_path'].values())==a['actual_attempts'])
 check(a['actual_38']+sum(t['variant']=='SERVICE'for t in ts)<=128)
 return True
def audit(q,t,s):
 expected='gemini-3.8-flash' if t['variant']=='SERVICE' else 'gemini-3.1-flash-lite';check(q['model']==expected)
 g=q['payload']['generationConfig'];check(g['maxOutputTokens']==1024 and g['thinkingConfig']==dict(thinkingLevel='low' if t['variant']=='SERVICE'else'minimal',includeThoughts=False));check('temperature'not in g and 'topP'not in g)
 cs=q['payload']['contents'];
 if t['variant']=='TURN_DEMO':
  check(len(cs)==5 and [z['role']for z in cs]==['user','model','user','model','user']);cs=cs[-1:]
 check(len(cs)==1 and len(cs[0]['parts'])==1 and set(cs[0]['parts'][0])=={'text'});body=cs[0]['parts'][0]['text']
 if t['path'].endswith('B') and t['path']=='KB' and t['variant']=='FROZEN':
  obj=json.loads(body);check(set(obj)=={'segments'} and ''.join(x['text']for x in obj['segments'])==s)
 elif t['variant']=='BASE_FIRST':
  obj=json.loads(body);check(obj['current_message']==s and set(obj)==({'current_message','focus'}if t['variant']=='BASE_FIRST'else{'current_message'}))
 else:check(body==s)
 return {'actual_input_sha256':hashlib.sha256(s.encode()).hexdigest(),'first_only':t['path'].endswith('B'),'original_gold_old_back_injected':False}
def run(plan,a,worker,send,journal,persist):
 validate(plan,a)
 with Path(journal).open('x') as f:f.write(digest(plan)+'\n');f.flush();os.fsync(f.fileno())
 result={'campaign_id':ID,'phase':plan['phase'],'prior_actual':a['actual_attempts'],'attempts':0,'slots':[],'retry':0,'judge':0};by={p:0 for p in CAP};done={};starts={}
 for t in plan['tasks']:
  x=copy.deepcopy(t);result['slots'].append(x)
  if 'from_slot'in t and done[t['from_slot']].get('status')!='SUCCESS':x.update(status='SKIPPED_DEPENDENCY',attempted=False);done[t['slot']]=x;persist(result);continue
  s=done[t['from_slot']]['displayed'] if 'from_slot'in t else t['input'];x['actual_input']=s
  start=time.perf_counter_ns();starts[t['slot']]=start;q=worker.call(dict(mode='build',path=t['path'],variant=t['variant'],text=s));built=time.perf_counter_ns();ar=audit(q,t,s)
  check(a['actual_attempts']+result['attempts']<200 and a['actual_by_path'][t['path']]+by[t['path']]<CAP[t['path']]);result['attempts']+=1;by[t['path']]+=1
  x.update(attempted=True,status='SENT_OR_UNKNOWN',global_attempt=a['actual_attempts']+result['attempts'],request=q,request_sha256=digest(q),request_audit=ar,build_ms=(built-start)/1e6,t0_ns=start,sent_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
  with Path(journal).open('a') as f:f.write(json.dumps({'attempt':x['global_attempt'],'request_sha256':x['request_sha256'],'slot':t['slot']})+'\n');f.flush();os.fsync(f.fileno())
  persist(result);sendstart=time.perf_counter_ns();fatal=False
  try:
   packet=send(q);x.update(raw=packet['raw'],wire=packet['wire']);check(packet['wire']['http_status']==200)
   if packet['raw'].get('modelVersion') and not packet['raw']['modelVersion'].startswith(q['model']):fatal=True;raise ValueError('MODEL_MISMATCH')
   x.update(worker.call(dict(mode='inspect',raw=packet['raw'],path=t['path'],variant=t['variant'],text=s)))
  except Exception as e:x.update(status='FAILED',failure_kind=type(e).__name__,displayed=None)
  finally:
   end=time.perf_counter_ns();x.update(tparse_ns=end,request_to_display_ready_ms=(end-sendstart)/1e6,ready_ms=(end-start)/1e6)
   if 'from_slot'in t:x['pairwall_ms']=(end-starts[t['from_slot']])/1e6
   done[t['slot']]=x;persist(result)
  if result['attempts']%8==0:print(json.dumps({'phase':plan['phase'],'attempts':result['attempts'],'latest_status':x['status'],'retry':0}),flush=True)
  if fatal:raise ValueError('MODEL_MISMATCH_STOP')
 result['actual_by_path_phase']=by;return result
