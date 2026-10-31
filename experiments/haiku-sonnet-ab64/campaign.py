"""Approved frozen H LA1/RE1 and S S1/EX1, max64 new attempts, no retries."""
import copy,hashlib,importlib.util,json,time
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sp=importlib.util.spec_from_file_location('ab64_frozen_examples',ROOT.parent/'relation-exemplars/adapter.py');a=importlib.util.module_from_spec(sp);sp.loader.exec_module(a)
PLAN='HAIKU_RE1_SONNET_EX1_AB64_20261031'
SOURCE_PLAN_SHA='40ca0dd1c0465c93cd6fbfbebc410e31e544388034f078272522cc7f5cab6dce'
MANIFEST='313aac72d31687ffbe1600700d9ec267ffaf0907d39e8a95c8f5578c8e370b4d'
class SafetyStop(Exception):pass
def digest(x):return a.prior.core.digest(x)
def authorize(x):
    if x!={'authorized':True,'plan_id':PLAN,'maximum_new_attempts':64,'manifest_sha256':MANIFEST,'source_plan_sha256':SOURCE_PLAN_SHA}:raise PermissionError('Exact approved64 required')
def schedule(plan):
    out=[]
    for p in plan['plans']:
        for s in p['schedule']:out.append(dict(s,planned_arm_slot=s['slot'],slot=len(out)+1,engine=p['engine'],status='PENDING'))
    return out
def validate(m):
    if digest(m)!=MANIFEST or m['id']!=PLAN:raise ValueError('Frozen manifest changed')
    if hashlib.sha256(m['source_plan_utf8'].encode()).hexdigest()!=SOURCE_PLAN_SHA:raise ValueError('Frozen source plan changed')
    plan=json.loads(m['source_plan_utf8'])
    if plan['total_new_calls']!=64 or plan['Haiku']!=32 or plan['Sonnet']!=32 or plan['Opus_additional']!=0:raise ValueError('Scope changed')
    for filename,sha in m['frozen_file_sha256'].items():
        if hashlib.sha256((ROOT.parent/filename).read_bytes()).hexdigest()!=sha:raise SafetyStop('Frozen candidate bytes changed')
    expected={'H':[(37,'K'),(19,'K'),(33,'K'),(54,'K'),(92,'L'),(67,'L'),(78,'L'),(1,'L')],'S':[(37,'K'),(104,'K'),(33,'K'),(54,'K'),(1,'L'),(55,'L'),(23,'L'),(9,'L')]}
    if [p['engine'] for p in plan['plans']]!=['H','S']:raise ValueError('Model order changed')
    for p in plan['plans']:
        e=p['engine'];sources=p['sources']
        if [(x['id'],x['side']) for x in sources]!=expected[e] or p['maximum_new_calls']!=32:raise ValueError('Frozen source8 changed')
        prescribed=[]
        for i,s in enumerate(sources):
            for v in (['BASELINE','EXEMPLARS'] if i%2==0 else ['EXEMPLARS','BASELINE']):
                for stage in ['first','back']:prescribed.append({'slot':len(prescribed)+1,'id':s['id'],'side':s['side'],'variant':v,'stage':stage})
            for v,k in [('BASELINE','baseline_first_payload'),('EXEMPLARS','candidate_first_payload')]:
                if a.build_request(s['source'],s['side'],'first',e,v)!=s[k]:raise SafetyStop('Frozen FIRST payload changed')
        if p['schedule']!=prescribed:raise ValueError('Order changed')
    return plan
def run_approved(m,approval,transport,journal,persist=lambda d:None):
    authorize(approval);plan=validate(m)
    with Path(journal).open('x') as f:f.write(json.dumps({'plan':PLAN,'attempts':0}))
    state={'plan_id':PLAN,'manifest_sha256':MANIFEST,'source_plan_sha256':SOURCE_PLAN_SHA,'status':'RUNNING','attempts':0,'retries':0,'per_engine':{'H':0,'S':0},'per_arm':{},'slots':schedule(plan)}
    byid={(p['engine'],s['id']):s for p in plan['plans'] for s in p['sources']};first={};seen=set();persist(copy.deepcopy(state))
    try:
        for s in state['slots']:
            e=s['engine'];v=s['variant'];pair=(e,v,s['id']);sourcecase=byid[(e,s['id'])];key=pair+(s['stage'],);arm=e+'_'+v
            if s['stage']=='back' and first[pair]['status']!='SUCCESS':
                s.update(status='SKIPPED_DEPENDENCY',attempted=False);persist(copy.deepcopy(state));continue
            source=sourcecase['source'] if s['stage']=='first' else first[pair]['translation'];q=a.build_request(source,s['side'],s['stage'],e,v)
            if key in seen or state['attempts']>=64 or state['per_engine'][e]>=32 or state['per_arm'].get(arm,0)>=16:raise SafetyStop('Duplicate or cap')
            if q['model']!=a.prior.MODELS[e] or q['max_tokens']!=2048:raise SafetyStop('Model mismatch')
            seen.add(key);state['attempts']+=1;state['per_engine'][e]+=1;state['per_arm'][arm]=state['per_arm'].get(arm,0)+1
            s.update(attempt=state['attempts'],attempted=True,status='SENT_OR_UNKNOWN',input=source,payload=q,payload_sha256=digest(q))
            with Path(journal).open('a') as f:f.write('\n'+json.dumps({'attempt':s['attempt'],'slot':s['slot'],'payload_sha256':s['payload_sha256']}))
            persist(copy.deepcopy(state));started=time.perf_counter();raw={}
            try:
                raw=transport(q);s['api_ms']=(time.perf_counter()-started)*1000
                s.update(response=raw,response_id=raw.get('id'),response_sha256=digest(raw),usage=raw.get('usage',{}),http_status=raw.get('http_status',200 if raw.get('type')=='message' else None),stop_reason=raw.get('stop_reason'))
                s['estimated_usd']=a.prior.cost(s['usage'],e)
                if s['http_status'] in [401,403]:raise SafetyStop('Global authentication failure')
                if raw.get('type')=='message' and raw.get('model')!=q['model']:raise SafetyStop('Response model mismatch')
                s.update(a.inspect_response(raw,source,s['side'],s['stage'],e))
                if s['status']!='SUCCESS':s['reason']='HTTP_'+str(s['http_status']) if raw.get('http_status') else 'INCOMPLETE_'+str(raw.get('stop_reason'))
            except SafetyStop as exc:s.update(status='FAILED',reason=str(exc));raise
            except Exception as exc:
                s.update(status='FAILED',reason=type(exc).__name__,raw_visible_text=''.join(b.get('text','') for b in raw.get('content',[]) if b.get('type')=='text'))
            finally:
                s.setdefault('api_ms',(time.perf_counter()-started)*1000);s.setdefault('estimated_usd',None)
                if s['stage']=='first':first[pair]=s
                persist(copy.deepcopy(state))
        if any(s['status'] not in ['SUCCESS','FAILED','SKIPPED_DEPENDENCY'] for s in state['slots']):raise SafetyStop('Nonterminal ledger')
        state['status']='PROCEDURE_COMPLETE_QUALITY_REVIEW_REQUIRED'
    except Exception:
        state['status']='GLOBAL_SAFETY_OR_JOURNAL_STOP';raise
    finally:persist(copy.deepcopy(state))
    return state
