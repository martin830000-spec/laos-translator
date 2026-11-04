"""Only frozen stored-FIRST BACK calls. Reserve before send, never retry."""
import json,hashlib,time,os,copy,datetime
from pathlib import Path
ID='GEMINI31_BACK_REAL100_20261104'
def digest(x):return hashlib.sha256(json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def require(ok):
 if not ok:raise ValueError('BOUNDED_CONTRACT')
def validate(plan,a):
 require(a['campaign_id']==plan['campaign_id']==ID and a['approved_limit']==100 and a['authorized']is True and a['execution_enabled']is True)
 phase=plan['phase'];require(phase in ['PILOT20','REST80'])
 expected=20 if phase=='PILOT20'else 80;prior=0 if phase=='PILOT20'else 20
 require(len(plan['tasks'])==expected and a['actual_attempts']==prior and a['actual_by_path']==dict(KB=prior//2,LB=prior//2) and a['plan_sha256']==digest(plan))
 require(set(plan)=={'campaign_id','phase','selection_sha256','tasks'})
 counts=dict(KB=0,LB=0);ids=set();slots=set()
 freeze=json.loads((Path(__file__).parent/'sample-freeze.json').read_text());refs={r['id']:r for r in freeze['rows']}
 require(plan['selection_sha256']==freeze['selection_sha256'])
 for t in plan['tasks']:
  require(set(t)=={'slot','case_id','path','model','variant','input','first_sha256'})
  require(t['case_id']not in ids and t['slot']not in slots and type(t['slot'])is int)
  ids.add(t['case_id']);slots.add(t['slot']);p=t['path'];require(p in counts and t['model']=='M31'and t['variant']=={'KB':'ALIGNED_NEUTRAL','LB':'LEGACY31U'}[p])
  require(isinstance(t['input'],str)and bool(t['input'].strip())and hashlib.sha256(t['input'].encode()).hexdigest()==t['first_sha256'])
  r=refs[t['case_id']];require(r['first_sha256']==t['first_sha256']and r['path']==p and r['phase']==phase);counts[p]+=1
 require(counts==dict(KB=expected//2,LB=expected//2))
 return True
def audit_request(q,t):
 require(q['model']=='gemini-3.1-flash-lite');payload=q['payload'];g=payload['generationConfig']
 require(g['maxOutputTokens']==1024 and g['thinkingConfig']==dict(thinkingLevel='minimal',includeThoughts=False))
 require('temperature'not in g and 'topP'not in g)
 contents=payload['contents'];require(len(contents)==1)
 content=contents[0];parts=content['parts'];require(len(parts)==1 and set(parts[0])=={'text'})
 user=parts[0]['text']
 if t['path']=='KB':
  o=json.loads(user);require(set(o)=={'segments'}and ''.join(x['text']for x in o['segments'])==t['input'])
 else:require(user==t['input'])
 return dict(only_actual_stored_FIRST=True,original_or_old_BACK_or_gold_injected=False,first_sha256=t['first_sha256'])
def run(plan,a,worker,send,journal,persist):
 validate(plan,a)
 with Path(journal).open('x',encoding='utf8')as f:f.write(digest(plan)+'\n');f.flush();os.fsync(f.fileno())
 result=dict(campaign_id=ID,attempts=0,prior=a['actual_attempts'],slots=[],automatic_retries=0,judge_calls=0,first_calls=0,new_service_back_calls=0)
 for t in plan['tasks']:
  x=copy.deepcopy(t);result['slots'].append(x);start=time.perf_counter_ns();q=worker.build(t['path'],'M31',t['variant'],t['input']);built=time.perf_counter_ns();audit=audit_request(q,t)
  require(a['actual_attempts']+result['attempts']<100)
  prior_count=a['actual_by_path'][t['path']];phase_count=sum(y.get('attempted',False)and y['path']==t['path']for y in result['slots']);require(prior_count+phase_count<50)
  result['attempts']+=1;x.update(attempted=True,status='SENT_OR_UNKNOWN',request=q,request_sha256=digest(q),request_audit=audit,global_attempt=a['actual_attempts']+result['attempts'],build_ms=(built-start)/1e6,sent_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
  with Path(journal).open('a',encoding='utf8')as f:f.write(json.dumps(dict(attempt=x['global_attempt'],path=t['path'],request_sha256=x['request_sha256']))+'\n');f.flush();os.fsync(f.fileno())
  persist(copy.deepcopy(result));sent=time.perf_counter_ns()
  try:
   packet=send(q);x.update(raw=packet['raw'],wire=packet['wire'])
   require(packet['wire']['http_status']==200)
   require(not packet['raw'].get('modelVersion')or packet['raw']['modelVersion'].startswith(q['model']))
   x.update(worker.inspect(packet['raw'],t['path'],t['input'],t['variant']))
  except Exception as e:x.update(status='FAILED',failure_kind=type(e).__name__,displayed=None)
  finally:
   end=time.perf_counter_ns();x['request_to_display_ready_ms']=(end-sent)/1e6;x['back_ready_including_build_ms']=(end-start)/1e6;persist(copy.deepcopy(result))
 return result
