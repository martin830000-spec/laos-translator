"""Bounded SA2 validation using the original frozen SA2/SA1 adapters."""
from pathlib import Path
import copy,hashlib,json,importlib.util,time
ROOT=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('existing_sa2_frozen',ROOT.parent/'sonnet-sa2-medium/adapter.py');a=importlib.util.module_from_spec(s);s.loader.exec_module(a)
PLAN='SONNET_SA2_STAGE2_NORMAL6_AB24_20261101'
SOURCE_PLAN_SHA='598975ffd6a484176739c8aec72a7459b79495c9c072942890f3c4f524a91ffe'
MANIFEST='c3eeca56ad41d506fae3792abd89c0cdbf4a58df6569b5a1183e504d87d28517'
CAP=24;PRIOR=12;PHASE=2
class SafetyStop(Exception):pass
def digest(x):return a.prior.core.digest(x)
def build(text,side,stage,variant):
 if variant=='SA2':return a.build_request(text,side,stage)
 if variant=='SA1':return a.prior.build_request(text,side,stage)
 raise SafetyStop('Unknown variant')
def cost(u):
 if not all(type(u.get(k)) is int for k in ['input_tokens','output_tokens']):return None
 cc=u.get('cache_creation_input_tokens',0);hour=u.get('cache_creation',{}).get('ephemeral_1h_input_tokens',0)
 return round((u['input_tokens']*2+u['output_tokens']*10+max(0,cc-hour)*2*1.25+hour*4+u.get('cache_read_input_tokens',0)*.1)/1e6,9)
def authorize(x):
 if x!={'authorized':True,'plan_id':PLAN,'maximum_new_attempts':CAP,'manifest_sha256':MANIFEST,'source_plan_sha256':SOURCE_PLAN_SHA}:raise PermissionError('Exact new SA2 phase approval required')
def validate(m):
 if digest(m)!=MANIFEST or m['id']!=PLAN or hashlib.sha256(m['source_plan_utf8'].encode()).hexdigest()!=SOURCE_PLAN_SHA:raise SafetyStop('Frozen manifest changed')
 for f,h in m['frozen_file_sha256'].items():
  if hashlib.sha256((ROOT.parent/f).read_bytes()).hexdigest()!=h:raise SafetyStop('Frozen adapter changed')
 p=json.loads(m['source_plan_utf8']);srcs={x['id']:x for x in p['sources']}
 if (p['phase'],p['maximum_new_calls'],p['prior_task_attempts'],p['whole_task_maximum'],p['new_Sonnet'],p['new_Haiku_Opus_Gemini_judge_retry'])!=(PHASE,CAP,PRIOR,36,CAP,0):raise SafetyStop('Scope changed')
 if PHASE==2:
  g=p['stage1_gate']
  if g['decision']!='PROCEED_STAGE2' or not g['meaningful_quality_benefit_observed'] or g['dominant_new_catastrophic_regression']:raise SafetyStop('Quality gate closed')
 if len(srcs)!=6 or sum(x['side']=='K' for x in srcs.values())!=3 or len(p['schedule'])!=CAP:raise SafetyStop('Six-source scope changed')
 for x in srcs.values():
  if hashlib.sha256(x['source'].encode()).hexdigest()!=x['source_sha256']:raise SafetyStop('Source bytes changed')
 for i,x in enumerate(p['schedule']):
  if x['slot']!=i+1 or x['variant'] not in (['SA2'] if PHASE==1 else ['SA1','SA2']) or x['side']!=srcs[x['id']]['side']:raise SafetyStop('Schedule changed')
  if x['stage']=='first':
   if x['depends_on'] is not None or x['frozen_first_payload']!=build(srcs[x['id']]['source'],x['side'],'first',x['variant']):raise SafetyStop('FIRST changed')
  elif x['stage']=='back':
   f=p['schedule'][x['depends_on']-1]
   if f['stage']!='first' or f['slot']>=x['slot'] or (f['id'],f['side'],f['variant'])!=(x['id'],x['side'],x['variant']):raise SafetyStop('BACK dependency changed')
  else:raise SafetyStop('Stage changed')
 return p
def run_approved(manifest,approval,transport,journal,persist=lambda d:None):
 authorize(approval);p=validate(manifest);srcs={x['id']:x for x in p['sources']}
 with Path(journal).open('x') as f:f.write(json.dumps({'plan_id':PLAN,'attempts':0}))
 state={'plan_id':PLAN,'phase':PHASE,'manifest_sha256':MANIFEST,'source_plan_sha256':SOURCE_PLAN_SHA,'status':'RUNNING','attempts':0,'prior_task_attempts':PRIOR,'whole_task_maximum':36,'retries':0,'per_variant':{'SA1':0,'SA2':0},'per_engine':{'S':0,'H':0,'O':0,'G':0},'slots':[]};by={};persist(copy.deepcopy(state))
 try:
  for case in p['schedule']:
   x={k:v for k,v in case.items() if k!='frozen_first_payload'};x.update(attempted=False,engine='S');state['slots'].append(x);by[x['slot']]=x
   if x['stage']=='back' and by[x['depends_on']]['status']!='SUCCESS':x.update(status='SKIPPED_DEPENDENCY',reason='FIRST failed; no refill');persist(copy.deepcopy(state));continue
   text=srcs[x['id']]['source'] if x['stage']=='first' else by[x['depends_on']]['translation'];q=build(text,x['side'],x['stage'],x['variant'])
   if state['attempts']>=CAP or state['attempts']+PRIOR>=36 or state['per_variant'][x['variant']]>=12:raise SafetyStop('Call cap')
   if q['model']!='claude-sonnet-5-5' or q['thinking']!={'type':'adaptive'} or q['max_tokens']!=2048 or q['output_config']!={'effort':'medium' if x['variant']=='SA2' else 'low'}:raise SafetyStop('Frozen settings changed')
   state['attempts']+=1;state['per_variant'][x['variant']]+=1;state['per_engine']['S']+=1;x.update(attempt=state['attempts'],attempted=True,status='SENT_OR_UNKNOWN',input=text,input_sha256=hashlib.sha256(text.encode()).hexdigest(),payload=q,payload_sha256=digest(q))
   with Path(journal).open('a') as f:f.write('\n'+json.dumps({'slot':x['slot'],'attempt':x['attempt'],'payload_sha256':x['payload_sha256']}))
   persist(copy.deepcopy(state));start=time.perf_counter();raw={}
   try:
    raw=transport(q);x['api_ms']=(time.perf_counter()-start)*1000
    x.update(response=raw,response_id=raw.get('id'),response_sha256=digest(raw),usage=raw.get('usage',{}),http_status=raw.get('http_status',200 if raw.get('type')=='message' else None),stop_reason=raw.get('stop_reason'));x['estimated_usd']=cost(x['usage'])
    if x['http_status'] in [401,403]:raise SafetyStop('Global authentication failure')
    if raw.get('type')=='message' and raw.get('model')!=q['model']:raise SafetyStop('Model mismatch')
    x.update(a.inspect_response(raw))
   except SafetyStop as exc:x.update(status='FAILED',reason=str(exc));raise
   except Exception as exc:x.update(status='FAILED',reason=type(exc).__name__,raw_visible_text=''.join(b.get('text','') for b in raw.get('content',[]) if b.get('type')=='text'))
   finally:
    x.setdefault('api_ms',(time.perf_counter()-start)*1000);x.setdefault('estimated_usd',None);persist(copy.deepcopy(state))
  state['status']='PHASE_COMPLETE_LOCAL_QUALITY_REVIEW_REQUIRED'
 except Exception:state['status']='GLOBAL_SAFETY_OR_JOURNAL_STOP';raise
 finally:persist(copy.deepcopy(state))
 return state
