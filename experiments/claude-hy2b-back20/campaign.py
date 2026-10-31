"""HY2B: max20 new Haiku LA1 BACK only; historical Claude FIRST is immutable.
No original Lao, answer, old BACK, donor prompt or Gemini enters new payloads.
"""
from pathlib import Path
import copy,hashlib,json,importlib.util,time
ROOT=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('hy2b_frozen_la1',ROOT.parent/'claude-real20-120/adapters.py');a=importlib.util.module_from_spec(s);s.loader.exec_module(a)
PLAN='CLAUDE_HY2B_BACK20_20261101'
SOURCE_PLAN_SHA='67e8d6407cd7a0939e881af218bc20b8c563bcaa55c36ebf839c1712b3b810a3'
MANIFEST='0b4f1c89cceff45ccb93fa57f85d5dedb6415b3fd9258da86c423a1bac8c5f98'
class SafetyStop(Exception):pass
def digest(x):return a.core.digest(x)
def authorize(x):
    if x!={'authorized':True,'plan_id':PLAN,'maximum_new_attempts':20,'manifest_sha256':MANIFEST,'source_plan_sha256':SOURCE_PLAN_SHA}:raise PermissionError('Exact HY2B20 approval required')
def build_request(text):return a.build(text,'L','back','H')
def validate(m):
    if digest(m)!=MANIFEST or m['id']!=PLAN:raise ValueError('Frozen manifest changed')
    if hashlib.sha256(m['source_plan_utf8'].encode()).hexdigest()!=SOURCE_PLAN_SHA:raise ValueError('Frozen input plan changed')
    for f,sha in m['frozen_file_sha256'].items():
        if hashlib.sha256((ROOT.parent/f).read_bytes()).hexdigest()!=sha:raise SafetyStop('Frozen candidate bytes changed')
    p=json.loads(m['source_plan_utf8'])
    if (p['maximum_new_calls'],p['new_FIRST'],p['new_Haiku_BACK'],p['new_Sonnet'],p['new_Opus'],p['new_Gemini'],p['retry'],p['judge'])!=(20,0,20,0,0,0,0,0):raise ValueError('Scope changed')
    expected=[]
    for i,cid in enumerate([17,53,67,78,92,132,144,150,15,129]):
        for donor in (['S','O'] if i%2==0 else ['O','S']):expected.append((donor,cid))
    if [(x['donor_engine'],x['id']) for x in p['cases']]!=expected:raise ValueError('Frozen source order changed')
    for i,x in enumerate(p['cases']):
        if x['slot']!=i+1 or x['side']!='L' or x['stage']!='back':raise ValueError('BACK-only scope changed')
        if hashlib.sha256(x['input'].encode()).hexdigest()!=x['input_sha256']:raise SafetyStop('FIRST display bytes changed')
        if build_request(x['input'])!=x['frozen_haiku_payload']:raise SafetyStop('Frozen Haiku payload changed')
    return p
def run_approved(manifest,approval,transport,journal,persist=lambda d:None):
    authorize(approval);plan=validate(manifest)
    with Path(journal).open('x') as f:f.write(json.dumps({'plan_id':PLAN,'attempts':0}))
    state={'plan_id':PLAN,'manifest_sha256':MANIFEST,'source_plan_sha256':SOURCE_PLAN_SHA,'status':'RUNNING','attempts':0,'retries':0,'new_FIRST_calls':0,'per_engine':{'H':0},'per_donor':{'S':0,'O':0},'slots':[]}
    seen=set();persist(copy.deepcopy(state))
    try:
        for case in plan['cases']:
            donor=case['donor_engine'];key=(donor,case['id']);q=build_request(case['input'])
            if key in seen or state['attempts']>=20 or state['per_donor'][donor]>=10:raise SafetyStop('Duplicate or cap')
            if q['model']!='claude-haiku-5-5' or q['max_tokens']!=2048 or q['thinking']!={'type':'disabled'}:raise SafetyStop('Model settings changed')
            seen.add(key);state['attempts']+=1;state['per_engine']['H']+=1;state['per_donor'][donor]+=1
            x={k:case[k] for k in ['slot','id','donor_engine','side','stage','input','input_sha256','first_origin_slot','old_back_slot','first_origin_response_sha256']}
            x.update(engine='H',attempt=state['attempts'],attempted=True,status='SENT_OR_UNKNOWN',payload=q,payload_sha256=digest(q));state['slots'].append(x)
            with Path(journal).open('a') as f:f.write('\n'+json.dumps({'slot':x['slot'],'attempt':x['attempt'],'payload_sha256':x['payload_sha256']}))
            persist(copy.deepcopy(state));started=time.perf_counter();raw={}
            try:
                raw=transport(q);x['api_ms']=(time.perf_counter()-started)*1000
                x.update(response=raw,response_id=raw.get('id'),response_sha256=digest(raw),usage=raw.get('usage',{}),http_status=raw.get('http_status',200 if raw.get('type')=='message' else None),stop_reason=raw.get('stop_reason'))
                x['estimated_usd']=a.cost(x['usage'],'H')
                if x['http_status'] in [401,403]:raise SafetyStop('Global authentication failure')
                if raw.get('type')=='message' and raw.get('model')!=q['model']:raise SafetyStop('Response model mismatch')
                x.update(a.inspect(raw,case['input'],'L','back','H'))
            except SafetyStop as exc:x.update(status='FAILED',reason=str(exc));raise
            except Exception as exc:x.update(status='FAILED',reason=type(exc).__name__,raw_visible_text=''.join(b.get('text','') for b in raw.get('content',[]) if b.get('type')=='text'))
            finally:
                x.setdefault('api_ms',(time.perf_counter()-started)*1000);x.setdefault('estimated_usd',None);persist(copy.deepcopy(state))
        state['status']='PROCEDURE_COMPLETE_QUALITY_REVIEW_REQUIRED'
    except Exception:
        state['status']='GLOBAL_SAFETY_OR_JOURNAL_STOP';raise
    finally:persist(copy.deepcopy(state))
    return state
