"""Exact approved Opus4 FIRST + own4 BACK, one-shot maximum8 attempts."""
import copy,hashlib,importlib.util,json,time
from pathlib import Path
ROOT=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('stream8_transport',ROOT/'transport.py');t=importlib.util.module_from_spec(spec);spec.loader.exec_module(t)
a=t.a
PLAN='OPUS_C_STREAM8_ACTUAL_20261031'
MANIFEST='0d95c4021e850a6ae18e163a32bada7e9a340adfb70e70e05916cf4f0f2d3c4a'
class SafetyStop(Exception):pass
def digest(v):return hashlib.sha256(json.dumps(v,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
def authorize(v):
    if v!={'authorized':True,'plan_id':PLAN,'maximum_new_attempts':8,'manifest_sha256':MANIFEST}:raise PermissionError('Exact8 approval required')
def validate(m):
    if digest(m)!=MANIFEST or m['id']!=PLAN or m['maximum_new_attempts']!=8:raise ValueError('Manifest mismatch')
    if [(c['id'],c['side']) for c in m['cases']]!=[(37,'K'),(19,'K'),(67,'L'),(78,'L')]:raise ValueError('Frozen4 only')
    for name,sha in m['frozen_file_sha256'].items():
        if hashlib.sha256((ROOT.parent/name).read_bytes()).hexdigest()!=sha:raise SafetyStop('Frozen file changed')
    for c in m['cases']:
        if a.build_request(c['source'],c['side'],'first')!=c['first_payload']:raise SafetyStop('Prompt changed')
    return m['cases']
def run_approved(m,approval,transport,journal,persist=lambda d:None):
    authorize(approval);cases=validate(m)
    with Path(journal).open('x') as f:f.write(json.dumps({'plan':PLAN,'attempts':0}))
    state={'plan_id':PLAN,'manifest_sha256':MANIFEST,'status':'RUNNING','attempts':0,'retries':0,'slots':[]}
    persist(copy.deepcopy(state));seen=set()
    try:
        for case in cases:
            first=None
            for stage in ['first','back']:
                s={'slot':len(state['slots'])+1,'case_id':case['id'],'side':case['side'],'stage':stage,'attempted':False}
                state['slots'].append(s)
                if stage=='back' and first['status']!='SUCCESS':
                    s['status']='SKIPPED_DEPENDENCY';persist(copy.deepcopy(state));continue
                source=case['source'] if stage=='first' else first['translation']
                q=a.build_request(source,case['side'],stage);key=(case['id'],stage)
                if key in seen or state['attempts']>=8:raise SafetyStop('Duplicate or cap')
                seen.add(key);state['attempts']+=1
                s.update(attempt=state['attempts'],attempted=True,status='SENT_OR_UNKNOWN',input=source,payload=q,payload_sha256=digest(q))
                with Path(journal).open('a') as f:f.write('\n'+json.dumps({'attempt':s['attempt'],'payload_sha256':s['payload_sha256']}))
                persist(copy.deepcopy(state));started=time.perf_counter()
                try:
                    out=transport(q);s.update(out);response=out.get('response') or {};s['usage']=response.get('usage',{})
                    s['response_id']=response.get('id');s['response_sha256']=digest(response)
                    s['estimated_usd']=a.prior.cost(s['usage'],'O')
                    if out.get('http_status') in [401,403]:raise SafetyStop('Global authentication failure')
                    if response and response.get('model')!=a.MODEL:raise SafetyStop('Model mismatch')
                    if s['status']=='SUCCESS' and (not s.get('complete') or response.get('stop_reason')!='end_turn' or not s.get('translation')):raise SafetyStop('False completion')
                except SafetyStop:
                    s['status']='FAILED';raise
                except Exception as exc:s.update(status='FAILED',error={'type':type(exc).__name__})
                finally:
                    s['controller_elapsed_ms']=(time.perf_counter()-started)*1000
                    if stage=='first':first=s
                    persist(copy.deepcopy(state))
        state['status']='PROCEDURE_COMPLETE_QUALITY_REVIEW_REQUIRED'
    except Exception:
        state['status']='GLOBAL_SAFETY_OR_JOURNAL_STOP';raise
    finally:persist(copy.deepcopy(state))
    return state
