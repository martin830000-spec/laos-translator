"""New conditional HY2 stage1: ten frozen S1 BACKs of historical LA1 displays."""
from pathlib import Path
import copy,hashlib,json,importlib.util,time
ROOT=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('hy2q_frozen',ROOT.parent/'claude-real20-120/adapters.py');a=importlib.util.module_from_spec(s);s.loader.exec_module(a)
PLAN='CLAUDE_HY2_QUALITY_STAGE1_BACK10_20261101'
SOURCE_PLAN_SHA='18ad1bb3619298cac144899302bbe6c1843a3f8c8608a21884ef29c9ff2cbfcb'
MANIFEST='69b56a02fa5dedb6fc3c12a1fe89235561a6f340dd6036932c50aa6450a52905'
class SafetyStop(Exception):pass
def digest(x):return a.core.digest(x)
def authorize(x):
 if x!={'authorized':True,'plan_id':PLAN,'maximum_new_attempts':10,'manifest_sha256':MANIFEST,'source_plan_sha256':SOURCE_PLAN_SHA}:raise PermissionError('Exact new HY2 stage1 ten-call approval required')
def build_request(text):return a.build(text,'K','back','S')
def validate(m):
 if digest(m)!=MANIFEST or m['id']!=PLAN or hashlib.sha256(m['source_plan_utf8'].encode()).hexdigest()!=SOURCE_PLAN_SHA:raise SafetyStop('Frozen manifest changed')
 for f,sha in m['frozen_file_sha256'].items():
  if hashlib.sha256((ROOT.parent/f).read_bytes()).hexdigest()!=sha:raise SafetyStop('Frozen adapter changed')
 p=json.loads(m['source_plan_utf8'])
 if (p['maximum_new_calls'],p['new_FIRST'],p['new_Haiku'],p['new_Sonnet_BACK'],p['new_Opus'],p['new_Gemini'],p['retry'],p['judge'])!=(10,0,0,10,0,0,0,0):raise SafetyStop('Scope changed')
 if [x['id'] for x in p['cases']]!=[32,37,66,68,88,90,103,104,126,19]:raise SafetyStop('Frozen order changed')
 for i,x in enumerate(p['cases']):
  if (x['slot'],x['side'],x['stage'],x['engine'])!=(i+1,'K','back','S'):raise SafetyStop('Route changed')
  if hashlib.sha256(x['input'].encode()).hexdigest()!=x['input_sha256'] or build_request(x['input'])!=x['frozen_payload']:raise SafetyStop('Display or request changed')
 return p
def run_approved(manifest,approval,transport,journal,persist=lambda d:None):
 authorize(approval);plan=validate(manifest)
 with Path(journal).open('x') as f:f.write(json.dumps({'plan_id':PLAN,'attempts':0}))
 state={'plan_id':PLAN,'manifest_sha256':MANIFEST,'source_plan_sha256':SOURCE_PLAN_SHA,'status':'RUNNING','attempts':0,'retries':0,'new_FIRST_calls':0,'per_engine':{'S':0,'H':0,'O':0,'G':0},'slots':[]}
 seen=set();persist(copy.deepcopy(state))
 try:
  for case in plan['cases']:
   q=build_request(case['input'])
   if case['id'] in seen or state['attempts']>=10:raise SafetyStop('Duplicate or cap')
   if q['model']!='claude-sonnet-5-5' or q['max_tokens']!=2048 or q['thinking']!={'type':'between_tools'} or q['output_config']!={'effort':'low'}:raise SafetyStop('S1 changed')
   seen.add(case['id']);state['attempts']+=1;state['per_engine']['S']+=1
   x={k:v for k,v in case.items() if k!='frozen_payload'};x.update(attempt=state['attempts'],attempted=True,status='SENT_OR_UNKNOWN',payload=q,payload_sha256=digest(q));state['slots'].append(x)
   with Path(journal).open('a') as f:f.write('\n'+json.dumps({'slot':x['slot'],'attempt':x['attempt'],'payload_sha256':x['payload_sha256']}))
   persist(copy.deepcopy(state));started=time.perf_counter();raw={}
   try:
    raw=transport(q);x['api_ms']=(time.perf_counter()-started)*1000
    x.update(response=raw,response_id=raw.get('id'),response_sha256=digest(raw),usage=raw.get('usage',{}),http_status=raw.get('http_status',200 if raw.get('type')=='message' else None),stop_reason=raw.get('stop_reason'));x['estimated_usd']=a.cost(x['usage'],'S')
    if x['http_status'] in [401,403]:raise SafetyStop('Global authentication failure')
    if raw.get('type')=='message' and raw.get('model')!=q['model']:raise SafetyStop('Model mismatch')
    x.update(a.inspect(raw,case['input'],'K','back','S'))
   except SafetyStop as exc:x.update(status='FAILED',reason=str(exc));raise
   except Exception as exc:x.update(status='FAILED',reason=type(exc).__name__,raw_visible_text=''.join(b.get('text','') for b in raw.get('content',[]) if b.get('type')=='text'))
   finally:
    x.setdefault('api_ms',(time.perf_counter()-started)*1000);x.setdefault('estimated_usd',None);persist(copy.deepcopy(state))
  state['status']='STAGE1_COMPLETE_REQUIRES_LOCAL_QUALITY_GATE_NO_STAGE2_CALLS'
 except Exception:state['status']='GLOBAL_SAFETY_OR_JOURNAL_STOP';raise
 finally:persist(copy.deepcopy(state))
 return state
