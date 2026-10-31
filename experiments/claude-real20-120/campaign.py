"""User-approved120 maximum attempts, no retries or replacement slots."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import time
ROOT=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('real120_adapters',ROOT/'adapters.py');a=importlib.util.module_from_spec(spec);spec.loader.exec_module(a)
PLAN='CLAUDE_REAL20_120_20261031'
MANIFEST='dcef8db2c5cc69422544bc9ee06b54f82f55d2b67096ded98b5ded38c6f2db95'
class SafetyStop(Exception):pass

def authorize(approval):
    if approval!={'authorized':True,'plan_id':PLAN,'maximum_new_attempts':120,'manifest_sha256':MANIFEST}:raise PermissionError('Exact approved real20/120 required')

def schedule(cases):
    slots=[];engines=['H','S','O']
    for i,c in enumerate(cases):
        for engine in engines[i%3:]+engines[:i%3]:
            for stage in ['first','back']:slots.append({'slot':len(slots)+1,'case_id':c['id'],'side':c['side'],'engine':engine,'stage':stage,'status':'PENDING'})
    return slots

def validate(manifest):
    if a.core.digest(manifest)!=MANIFEST or manifest['id']!=PLAN or manifest['maximum_new_attempts']!=120:raise ValueError('Frozen manifest mismatch')
    cases=manifest['cases']
    if len(cases)!=20 or len({c['id'] for c in cases})!=20 or sum(c['side']=='K' for c in cases)!=10 or sum(c['side']=='L' for c in cases)!=10:raise ValueError('Balanced20 required')
    if any(c['development_allowed'] is not True for c in cases):raise ValueError('Protected source')
    if schedule(cases)!=manifest['slots']:raise ValueError('Schedule changed')
    for path,sha in manifest['frozen_file_sha256'].items():
        if hashlib.sha256((ROOT.parent/path).read_bytes()).hexdigest()!=sha:raise SafetyStop('FROZEN_CODE_CHANGED')
    return cases

def run_approved(manifest,approval,transport,journal_path,persist=lambda d:None):
    authorize(approval);cases=validate(manifest)
    with Path(journal_path).open('x',encoding='utf-8') as f:f.write(json.dumps({'manifest_sha256':MANIFEST,'attempts':0}))
    state={'plan_id':PLAN,'manifest_sha256':MANIFEST,'status':'RUNNING','attempts':0,'per_engine':{'H':0,'S':0,'O':0},'retries':0,'slots':schedule(cases)}
    persist(copy.deepcopy(state));first={};seen=set();byid={c['id']:c for c in cases}
    try:
        for s in state['slots']:
            engine=s['engine'];c=byid[s['case_id']];pair=(s['case_id'],engine)
            if s['stage']=='back' and first[pair]['status']!='SUCCESS':
                s.update(status='SKIPPED_DEPENDENCY',attempted=False);persist(copy.deepcopy(state));continue
            source=c['source'] if s['stage']=='first' else first[pair]['translation']
            q=a.build(source,c['side'],s['stage'],engine);key=pair+(s['stage'],)
            if key in seen or state['attempts']>=120 or state['per_engine'][engine]>=40:raise SafetyStop('DUPLICATE_OR_CAP')
            if q['model']!=a.MODELS[engine] or q['max_tokens']!=2048:raise SafetyStop('MODEL_OR_TOKEN_LIMIT')
            seen.add(key);state['attempts']+=1;state['per_engine'][engine]+=1
            s.update(attempt=state['attempts'],attempted=True,status='SENT_OR_UNKNOWN',input=source,payload=q,payload_sha256=a.core.digest(q))
            with Path(journal_path).open('a',encoding='utf-8') as f:f.write('\n'+json.dumps({'attempt':s['attempt'],'slot':s['slot'],'payload_sha256':s['payload_sha256']}))
            persist(copy.deepcopy(state));start=time.perf_counter();raw={}
            try:
                raw=transport(q);s['api_ms']=(time.perf_counter()-start)*1000
                s.update(response=raw,response_id=raw.get('id'),response_sha256=a.core.digest(raw),usage=raw.get('usage',{}),
                    http_status=raw.get('http_status',200 if raw.get('type')=='message' else None),stop_reason=raw.get('stop_reason'))
                s['estimated_usd']=a.cost(s['usage'],engine)
                if raw.get('http_status') in [401,403]:raise SafetyStop('GLOBAL_AUTHENTICATION_FAILURE')
                if raw.get('type')=='message' and raw.get('model')!=a.MODELS[engine]:raise SafetyStop('RESPONSE_MODEL_MISMATCH')
                s.update(a.inspect(raw,source,c['side'],s['stage'],engine))
                if s['status']!='SUCCESS':s['reason']='HTTP_'+str(raw['http_status']) if raw.get('http_status') else 'INCOMPLETE_'+str(raw.get('stop_reason'))
            except SafetyStop as exc:
                s.update(status='FAILED',reason=str(exc),exception_type=type(exc).__name__);raise
            except Exception as exc:
                s.update(status='FAILED',reason='MAX_TOKENS' if raw.get('stop_reason')=='max_tokens' else 'HTTP_'+str(raw['http_status']) if raw.get('http_status') else type(exc).__name__,exception_type=type(exc).__name__)
                s['raw_visible_text']=''.join(b.get('text','') for b in raw.get('content',[]) if b.get('type')=='text')
            finally:
                s.setdefault('api_ms',(time.perf_counter()-start)*1000);s.setdefault('estimated_usd',None)
                if s['stage']=='first':first[pair]=s
                persist(copy.deepcopy(state))
        if any(s['status'] not in ['SUCCESS','FAILED','SKIPPED_DEPENDENCY'] for s in state['slots']):raise SafetyStop('NONTERMINAL_LEDGER')
        state['status']='PROCEDURE_COMPLETE_QUALITY_REVIEW_REQUIRED'
    except Exception:
        state['status']='GLOBAL_SAFETY_OR_JOURNAL_STOP';raise
    finally:persist(copy.deepcopy(state))
    return state
