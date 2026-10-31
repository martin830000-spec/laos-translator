"""Explicitly approved frozen SA1/S1 A/B24; bounded one-shot injected transport."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import time

ROOT=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('approved_frozen_sa1',ROOT.parent/'sonnet-sa1/adapter.py')
a=importlib.util.module_from_spec(spec);spec.loader.exec_module(a)
PLAN='SONNET_SA1_REAL8_NEW24_PROPOSED_20261031'
MANIFEST='a50d5e145205855da078dc25729990332b39caa954019e77f6537b2db36f4d49'
MODEL='claude-sonnet-5-5'

class SafetyStop(Exception):pass

def validate_code():
    expected={'sonnet-sa1/adapter.py':'14de4aef5ca81bc5abe94cafd8b0bb87962bdf610b84c08eaa2d17bca52b8086',
        'claude-rd-core/core.py':'b255d18d774e18db9fef170ce7c6eb8c02885b0b134ad3d1aedad86ee8e80a1c'}
    for path,sha in expected.items():
        if hashlib.sha256((ROOT.parent/path).read_bytes()).hexdigest()!=sha:raise SafetyStop('FROZEN_CODE_MISMATCH')
    if a.core.digest(a.core.PROMPTS)!='38fd75fad361355b4b3604ab14168c54b9e652d12bf6c39c5d96790f4c133762':raise SafetyStop('FROZEN_PROMPTS_MISMATCH')

def authorize(approval):
    if approval!={'authorized':True,'plan_id':PLAN,'maximum_new_attempts':24,'manifest_sha256':MANIFEST}:
        raise PermissionError('Exact user-approved A/B24 scope required')

def validate(manifest):
    validate_code()
    if a.core.digest(manifest)!=MANIFEST:raise ValueError('Frozen manifest mismatch')
    expected=['historical65:23','historical65:15','app500:62','app500:82','historical65:61','historical65:18','app500:87','app500:105']
    if manifest['id']!=PLAN or manifest['maximum_new_attempts']!=24 or [c['id'] for c in manifest['cases']]!=expected:raise ValueError('Wrong source scope')
    if len(manifest['slots'])!=24 or any(not c['development_allowed'] for c in manifest['cases']):raise ValueError('Invalid planned slots')
    return manifest['cases']

def cost(usage):
    if not all(type(usage.get(k)) is int for k in ['input_tokens','output_tokens']):return None
    cc=usage.get('cache_creation_input_tokens',0);cr=usage.get('cache_read_input_tokens',0)
    hour=usage.get('cache_creation',{}).get('ephemeral_1h_input_tokens',0)
    return round((usage['input_tokens']*2+usage['output_tokens']*10+max(0,cc-hour)*2.5+hour*4+cr*.1)/1e6,9)

def run_approved(manifest,approval,transport,journal_path,persist=lambda d:None):
    authorize(approval);cases=validate(manifest)
    with Path(journal_path).open('x',encoding='utf-8') as f:f.write(json.dumps({'manifest_sha256':MANIFEST,'attempts':0}))
    slots=copy.deepcopy(manifest['slots'])
    for s in slots:s['status']='PENDING'
    state={'plan_id':PLAN,'manifest_sha256':MANIFEST,'attempts':0,'retries':0,'status':'RUNNING','slots':slots}
    persist(copy.deepcopy(state));seen=set();first={};byid={c['id']:c for c in cases}
    try:
        for s in slots:
            c=byid[s['case_id']];key=(s['case_id'],s['variant'])
            if s['stage']=='back' and first[key]['status']!='SUCCESS':
                s.update(status='SKIPPED_DEPENDENCY',attempted=False)
                persist(copy.deepcopy(state));continue
            visible=c['source'] if s['stage']=='first' else first[key]['translation']
            q=a.build_request(visible,c['side'],s['stage']) if s['variant']=='SA1' else a.core.baseline(visible,c['side'],s['stage'],MODEL)
            unique=(s['case_id'],s['variant'],s['stage'])
            if unique in seen or state['attempts']>=24:raise SafetyStop('DUPLICATE_OR_CAP')
            if q['model']!=MODEL or q['max_tokens']!=2048:raise SafetyStop('REQUEST_MODEL_OR_LIMIT')
            seen.add(unique);state['attempts']+=1
            s.update(status='SENT_OR_UNKNOWN',attempted=True,attempt=state['attempts'],input=visible,
                payload=q,payload_sha256=a.core.digest(q))
            # Consumed attempt and encrypted state are durable BEFORE model transport.
            with Path(journal_path).open('a',encoding='utf-8') as f:f.write('\n'+json.dumps({'attempt':s['attempt'],'slot':s['slot'],'payload_sha256':s['payload_sha256']}))
            persist(copy.deepcopy(state));start=time.perf_counter();raw={}
            try:
                raw=transport(q)
                s['api_ms']=(time.perf_counter()-start)*1000
                s.update(response=raw,response_id=raw.get('id'),response_sha256=a.core.digest(raw),
                    usage=raw.get('usage',{}),http_status=raw.get('http_status',200 if raw.get('type')=='message' else None),stop_reason=raw.get('stop_reason'))
                s['estimated_usd']=cost(s['usage'])
                if raw.get('http_status') in [401,403]:raise SafetyStop('GLOBAL_AUTHENTICATION_FAILURE')
                if raw.get('type')=='message' and raw.get('model')!=MODEL:raise SafetyStop('RESPONSE_MODEL_MISMATCH')
                inspected=a.inspect_response(raw);s.update(inspected)
                if s['status']!='SUCCESS':s['reason']='HTTP_'+str(raw['http_status']) if raw.get('http_status') else 'INCOMPLETE_'+str(raw.get('stop_reason'))
            except SafetyStop as e:
                s.update(status='FAILED',reason=str(e),exception_type=type(e).__name__);raise
            except Exception as e:
                s.update(status='FAILED',reason=type(e).__name__,exception_type=type(e).__name__)
            finally:
                s.setdefault('api_ms',(time.perf_counter()-start)*1000);s.setdefault('estimated_usd',None)
                if s['stage']=='first':first[key]=s
                persist(copy.deepcopy(state))
        if any(s['status'] not in ['SUCCESS','FAILED','SKIPPED_DEPENDENCY'] for s in slots):raise SafetyStop('NONTERMINAL_LEDGER')
        state['status']='PROCEDURE_COMPLETE_QUALITY_REVIEW_REQUIRED'
    except Exception:
        state['status']='GLOBAL_SAFETY_OR_JOURNAL_STOP';raise
    finally:persist(copy.deepcopy(state))
    return state
