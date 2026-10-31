"""Offline scheduler and gated transport interface for proposed A/B40, not authorization."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('la1_adapter',ROOT/'adapter.py')
a=importlib.util.module_from_spec(spec);spec.loader.exec_module(a)
PLAN_ID='LA1_REAL16_AB40_20261031'

def code_sha():return hashlib.sha256((ROOT/'adapter.py').read_bytes()).hexdigest()

def validate(manifest):
    if manifest.get('id')!=PLAN_ID or manifest.get('maximum_new_attempts')!=40:
        raise ValueError('Wrong proposed campaign or cap')
    if manifest.get('candidate_adapter_sha256')!=code_sha():raise ValueError('Candidate code not frozen')
    cases=manifest['cases']
    if len(cases)!=16 or len({c['id'] for c in cases})!=16:raise ValueError('Sixteen unique cases required')
    if a.digest(cases)!=manifest.get('cases_sha256'):raise ValueError('Case manifest changed')
    for cohort,n in [('prior12',12),('matched4',4)]:
        selected=[c for c in cases if c['cohort']==cohort]
        if len(selected)!=n or any(sum(c['side']==side for c in selected)!=n//2 for side in ('K','L')):
            raise ValueError('Unbalanced source cohorts')
    for c in cases:
        if c.get('development_allowed') is not True or not isinstance(c['source'],str) or not c['source'].strip():
            raise ValueError('Unverified development source')
        if c['cohort']=='prior12':
            if set(c['historical_s47'])!={'first','back'}:raise ValueError('Missing reused S47 pair')
            for stage in ('first','back'):
                h=c['historical_s47'][stage]
                if h['status']!='SUCCESS' or not h['translation'].strip():raise ValueError('Invalid historical reference')
    return cases

def schedule(manifest):
    cases=validate(manifest);slots=[]
    for i,c in enumerate(cases):
        variants=('S47','LA1') if i%2==0 else ('LA1','S47')
        for v in variants:
            for stage in ('first','back'):
                historical=c['cohort']=='prior12' and v=='S47'
                slots.append(dict(slot=len(slots)+1,record_id=c['id'],side=c['side'],variant=v,stage=stage,
                    status='REUSED_REFERENCE' if historical else 'PENDING',chargeable=not historical))
    if sum(s['chargeable'] for s in slots)!=40 or len(slots)!=64:raise ValueError('A/B slot budget mismatch')
    return slots

def run_approved(manifest,approval,transport,journal_path,persist=lambda record:None):
    """No built-in network transport. Denied approvals must make zero callbacks."""
    slots=schedule(manifest)
    if approval.get('authorized') is not True or approval.get('plan_id')!=PLAN_ID or approval.get('maximum_new_attempts')!=40:
        raise PermissionError('New A/B40 is not authorized')
    if approval.get('manifest_sha256')!=a.digest(manifest):raise PermissionError('Approval is for another manifest')
    # Independent persistent one-shot journal; no old campaign tag can be reused.
    path=Path(journal_path)
    with path.open('x',encoding='utf-8') as f:json.dump({'plan_id':PLAN_ID,'manifest_sha256':a.digest(manifest),'attempts':0},f)
    state=dict(status='RUNNING',plan_id=PLAN_ID,manifest_sha256=a.digest(manifest),attempts=0,retries=0,slots=slots)
    persist(copy.deepcopy(state))
    used=set()
    def send(q,slot):
        key=(slot['record_id'],slot['variant'],slot['stage'])
        if key in used or state['attempts']>=40:raise a.SafetyStop('DUPLICATE_OR_CALL_CAP')
        used.add(key);state['attempts']+=1
        # Persist consumed attempt locally before any external callback, even on unknown send.
        with path.open('a',encoding='utf-8') as f:f.write('\n'+json.dumps({'attempt':state['attempts'],'slot':slot['slot'],'payload_sha256':a.digest(q)}))
        slot['attempt']=state['attempts']
        persist(copy.deepcopy(state))
        return transport(q)
    try:
        for c in manifest['cases']:
            variants=('S47','LA1') if manifest['cases'].index(c)%2==0 else ('LA1','S47')
            for variant in variants:
                pair=[s for s in slots if s['record_id']==c['id'] and s['variant']==variant]
                if c['cohort']=='prior12' and variant=='S47':
                    for s in pair:s['reference']=copy.deepcopy(c['historical_s47'][s['stage']])
                    persist(copy.deepcopy(state));continue
                bystage={s['stage']:s for s in pair}
                def record(item):
                    slot=bystage[item['stage']]
                    slot.update(copy.deepcopy(item))
                    persist(copy.deepcopy(state))
                # Closure receives only source; session's BACK crosses actual translation alone.
                session=a.SinglePassSession(c['side'],variant)
                current_stage=['first']
                def transport_once(q):
                    stage=current_stage[0];current_stage[0]='back'
                    return send(q,bystage[stage])
                session.run(c['source'],transport_once,record)
        if any(s['status'] not in ('SUCCESS','FAILED','SKIPPED_DEPENDENCY','REUSED_REFERENCE') for s in slots):
            raise a.SafetyStop('NONTERMINAL_LEDGER')
        state['status']='PROCEDURE_COMPLETE_QUALITY_REVIEW_REQUIRED'
    except Exception:
        state['status']='GLOBAL_SAFETY_OR_JOURNAL_STOP';raise
    finally:persist(copy.deepcopy(state))
    return state
