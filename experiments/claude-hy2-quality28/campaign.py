"""HY2 stage2 max28 new calls only after a frozen local stage1 quality gate."""
from pathlib import Path
import copy,hashlib,json,importlib.util,time
ROOT=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('hy2q28_frozen',ROOT.parent/'claude-real20-120/adapters.py');a=importlib.util.module_from_spec(s);s.loader.exec_module(a)
PLAN='CLAUDE_HY2_QUALITY_STAGE2_NORMAL8_28_20261101'
SOURCE_PLAN_SHA='db678c8370d2e5bc04fa9ad699a347645567651f9e5f362de912064ae61a7465'
MANIFEST='c33bb07455c0ac9c99c551c771d4d10c3e7b580483a85b251dbaa85b3e26f8cb'
GATE='b84b451af51c3b9d77b5efdad28a78fd71bb3166723cfc2dd83004291a2f29a4'
class SafetyStop(Exception):pass
def digest(x):return a.core.digest(x)
def authorize(x):
 if x!={'authorized':True,'plan_id':PLAN,'maximum_new_attempts':28,'manifest_sha256':MANIFEST,'source_plan_sha256':SOURCE_PLAN_SHA,'stage1_gate_sha256':GATE}:raise PermissionError('Exact conditional HY2 stage2 approval required')
def validate(m):
 if digest(m)!=MANIFEST or m['id']!=PLAN or hashlib.sha256(m['source_plan_utf8'].encode()).hexdigest()!=SOURCE_PLAN_SHA:raise SafetyStop('Frozen manifest changed')
 for f,h in m['frozen_file_sha256'].items():
  if hashlib.sha256((ROOT.parent/f).read_bytes()).hexdigest()!=h:raise SafetyStop('Frozen adapter changed')
 p=json.loads(m['source_plan_utf8']);g=p['stage1_gate']
 if p['stage1_gate_sha256']!=GATE or g['decision']!='PROCEED_STAGE2_CONDITIONAL_VALIDATION' or g['new_confirmed_important_P0']!=0 or not g['meaningful_quality_benefit_observed']:raise SafetyStop('Stage1 quality gate closed')
 if (p['maximum_new_calls'],p['whole_task_maximum'],p['stage1_attempts'],p['new_Haiku'],p['new_Sonnet'],p['new_Opus'],p['new_Gemini'],p['retry'],p['judge'])!=(28,38,10,16,12,0,0,0,0):raise SafetyStop('Scope changed')
 if [(x['id'],x['side']) for x in p['sources']]!=[(152,'K'),(154,'L'),(106,'K'),(178,'L'),(79,'K'),(86,'L'),(237,'K'),(191,'L')]:raise SafetyStop('Sources changed')
 by={x['id']:x for x in p['sources']}
 for src in by.values():
  if hashlib.sha256(src['source'].encode()).hexdigest()!=src['source_sha256']:raise SafetyStop('Source bytes changed')
 if len(p['schedule'])!=28:raise SafetyStop('Schedule changed')
 for i,x in enumerate(p['schedule']):
  if x['slot']!=i+1 or x['engine'] not in ['H','S'] or x['stage'] not in ['first','back'] or x['side']!=by[x['id']]['side']:raise SafetyStop('Route changed')
  if x['stage']=='first':
   if x['depends_on'] is not None or x['frozen_first_payload']!=a.build(by[x['id']]['source'],x['side'],'first',x['engine']):raise SafetyStop('FIRST changed')
  else:
   f=p['schedule'][x['depends_on']-1]
   if f['stage']!='first' or f['slot']>=x['slot'] or f['id']!=x['id'] or f['side']!=x['side'] or f['engine']!=('H' if x['side']=='K' else x['engine']):raise SafetyStop('BACK dependency changed')
 return p
def run_approved(manifest,approval,transport,journal,persist=lambda d:None):
 authorize(approval);p=validate(manifest);srcs={x['id']:x for x in p['sources']}
 with Path(journal).open('x') as f:f.write(json.dumps({'plan_id':PLAN,'attempts':0}))
 state={'plan_id':PLAN,'manifest_sha256':MANIFEST,'source_plan_sha256':SOURCE_PLAN_SHA,'stage1_gate_sha256':GATE,'status':'RUNNING','attempts':0,'retries':0,'stage1_attempts':10,'whole_task_maximum':38,'per_engine':{'H':0,'S':0,'O':0,'G':0},'slots':[]};by={};persist(copy.deepcopy(state))
 try:
  for case in p['schedule']:
   x={k:v for k,v in case.items() if k!='frozen_first_payload'};x.update(attempted=False);state['slots'].append(x);by[x['slot']]=x
   if x['stage']=='back' and by[x['depends_on']]['status']!='SUCCESS':
    x.update(status='SKIPPED_DEPENDENCY',reason='FIRST failed; no retry or replacement');persist(copy.deepcopy(state));continue
   text=srcs[x['id']]['source'] if x['stage']=='first' else by[x['depends_on']]['translation'];q=a.build(text,x['side'],x['stage'],x['engine'])
   if state['attempts']>=28 or state['attempts']+10>=38 or state['per_engine'][x['engine']]>={'H':16,'S':12}[x['engine']]:raise SafetyStop('Call cap')
   state['attempts']+=1;state['per_engine'][x['engine']]+=1;x.update(attempt=state['attempts'],attempted=True,status='SENT_OR_UNKNOWN',input=text,input_sha256=hashlib.sha256(text.encode()).hexdigest(),payload=q,payload_sha256=digest(q))
   with Path(journal).open('a') as f:f.write('\n'+json.dumps({'slot':x['slot'],'attempt':x['attempt'],'payload_sha256':x['payload_sha256']}))
   persist(copy.deepcopy(state));start=time.perf_counter();raw={}
   try:
    raw=transport(q);x['api_ms']=(time.perf_counter()-start)*1000
    x.update(response=raw,response_id=raw.get('id'),response_sha256=digest(raw),usage=raw.get('usage',{}),http_status=raw.get('http_status',200 if raw.get('type')=='message' else None),stop_reason=raw.get('stop_reason'));x['estimated_usd']=a.cost(x['usage'],x['engine'])
    if x['http_status'] in [401,403]:raise SafetyStop('Global authentication failure')
    if raw.get('type')=='message' and raw.get('model')!=q['model']:raise SafetyStop('Model mismatch')
    x.update(a.inspect(raw,text,x['side'],x['stage'],x['engine']))
   except SafetyStop as exc:x.update(status='FAILED',reason=str(exc));raise
   except Exception as exc:x.update(status='FAILED',reason=type(exc).__name__,raw_visible_text=''.join(b.get('text','') for b in raw.get('content',[]) if b.get('type')=='text'))
   finally:
    x.setdefault('api_ms',(time.perf_counter()-start)*1000);x.setdefault('estimated_usd',None);persist(copy.deepcopy(state))
  state['status']='PROCEDURE_COMPLETE_QUALITY_REVIEW_REQUIRED'
 except Exception:state['status']='GLOBAL_SAFETY_OR_JOURNAL_STOP';raise
 finally:persist(copy.deepcopy(state))
 return state
