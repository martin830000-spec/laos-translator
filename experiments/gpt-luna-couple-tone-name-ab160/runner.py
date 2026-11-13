"""COUPLE_TONE_NAME_AB160 private GCS runner. Never invokes more than one POST per reservation."""
import asyncio
import base64
import concurrent.futures
import datetime
import gzip
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import time
import zipfile

from contract import (APPROVED_TOTAL, CAMPAIGN, HARD_CAPS, MODEL, PHASES, back_input,
                      budget_guard, build_payload, canon, require,
                      sha, validate_design, validate_prompts, validate_result_metadata)
from http_sender import make_client, send

HERE = pathlib.Path(__file__).resolve().parent
PREFIX = 'research/gemini-model-native500-20261107/gpt-luna-couple-tone-name-ab160-20261113'
INPUT_KEY = 'research/gemini-model-native500-20261107/fidelity240-20261108/keys/input-key.pem'
SOURCE_OBJECT = 'preparation/SOURCES.json'
PROMPTS_OBJECT = 'preparation/PROMPTS.json'
FREEZE_OBJECT = 'preparation/FREEZE.json'
CODE_FILES = {'runner.py', 'contract.py', 'http_sender.py'}

def safe_code(exc):
    value = str(exc) if isinstance(exc, AssertionError) else ''
    return value if value and all(ch in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_' for ch in value) else type(exc).__name__

def metadata_log(label, value):
    print(label + '=' + json.dumps(value, sort_keys=True), flush=True)

def local_spool(name, data):
    # Preserve received evidence before attempting a remote create. Local copies
    # never establish that a remote reservation or authority was committed.
    root=pathlib.Path(os.environ['RUNNER_TEMP'])/'couple-tone-name-ab160-spool'
    require(not name.startswith('/') and '..' not in pathlib.PurePosixPath(name).parts, 'SPOOL_PATH')
    target=root/name; target.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    if target.exists():
        require(target.read_bytes()==data, 'SPOOL_IMMUTABILITY')
        return
    fd=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'wb') as handle:
        handle.write(data);handle.flush();os.fsync(handle.fileno())

class RemoteStore:
    def __init__(self):
        from google.cloud import storage
        from google.api_core.exceptions import NotFound, PreconditionFailed
        self.NotFound=NotFound; self.PreconditionFailed=PreconditionFailed
        self.bucket=storage.Client(project='gen-lang-client-0422436907').bucket('lao-translator-src-460077888071')

    def get(self, name, optional=False):
        try:
            return self.bucket.blob(PREFIX+'/'+name).download_as_bytes(timeout=30, retry=None)
        except self.NotFound:
            if optional: return None
            raise

    def create(self, name, data):
        local_spool(name,data)
        self.bucket.blob(PREFIX+'/'+name).upload_from_string(data, if_generation_match=0, timeout=30, retry=None)
        require(self.get(name)==data, 'CREATE_READBACK_MISMATCH')

    def put_same(self, name, data):
        try:
            self.create(name, data)
        except self.PreconditionFailed:
            require(self.get(name)==data, 'IMMUTABLE_OBJECT_MISMATCH')

    def input_key(self):
        return self.bucket.blob(INPUT_KEY).download_as_bytes(timeout=30, retry=None)

def runtime_control():
    require(os.environ.get('GITHUB_REF')=='refs/heads/research/gemini-model-native500-20261107', 'WRONG_BRANCH')
    require(os.environ.get('GITHUB_RUN_ATTEMPT')=='1' and os.environ.get('GITHUB_ACTOR')=='martin830000-spec', 'UNAUTHORIZED_OR_REPLAY')
    control=json.loads((HERE/'CONTROL.json').read_bytes())
    require(control['campaign']==CAMPAIGN and control['approved_total']==APPROVED_TOTAL, 'FOREIGN_CONTROL')
    require(set(control['code_sha256'])==CODE_FILES, 'CODE_FREEZE_SET')
    for name, digest in control['code_sha256'].items():
        require(sha((HERE/name).read_bytes())==digest, 'CODE_FREEZE_MISMATCH')
    return control

def read_json(store, name):
    return json.loads(store.get(name))

def verify_lease(store, control):
    lock=read_json(store,'LOCK.json'); root=read_json(store,'CONTROL.json')
    for value in (lock, root):
        require(value['campaign']==CAMPAIGN and value['owner_token']==control['owner_token'], 'CAMPAIGN_LEASE_OWNER_MISMATCH')
        require(value['approved_total']==APPROVED_TOTAL and value['enabled'] is False, 'ROOT_CONTROL_NOT_LOCKED')
    require(root['max_new']==0 and root['reserved_total']==0 and root['status']=='PREFLIGHT_LOCKED', 'ROOT_PREFLIGHT_CHANGED')
    raw=store.get(control['preflight_object'])
    require(control['preflight_object']=='preflight/PREFLIGHT.json' and sha(raw)==control['preflight_sha256'], 'PREFLIGHT_RECEIPT_SHA')
    preflight=json.loads(raw)
    require(preflight['campaign']==CAMPAIGN and preflight['owner_token']==control['owner_token'] and preflight['generation_calls']==0, 'PREFLIGHT_IDENTITY')
    access=preflight['model_access']['luna']
    require(access.get('allowed') is True and access.get('http_status')==200, 'MODEL_PREFLIGHT_NOT_PASSED')
    require(preflight.get('create_only_readback_verified') is True and preflight.get('duplicate_create_rejected') is True, 'CREATE_ONLY_PREFLIGHT_NOT_PASSED')
    return preflight

def require_no_terminal(store):
    for name in ('states/CLOSED_LOCKED.json','states/PAUSED_LOCKED.json',
                 'controls/CLOSED/CLOSED_LOCKED.json','controls/PAUSED/PAUSED_LOCKED.json'):
        require(store.get(name,True) is None, 'TERMINAL_CAMPAIGN_LOCK')

def load_design(store, control):
    source_raw=store.get(SOURCE_OBJECT); prompts_raw=store.get(PROMPTS_OBJECT); freeze_raw=store.get(FREEZE_OBJECT)
    require(sha(source_raw)==control['source_sha256'], 'SOURCE_FILE_SHA')
    require(sha(prompts_raw)==control['prompts_sha256'], 'PROMPTS_FILE_SHA')
    require(sha(freeze_raw)==control['freeze_sha256'], 'FREEZE_FILE_SHA')
    source_document=json.loads(source_raw); prompts=json.loads(prompts_raw); freeze=json.loads(freeze_raw)
    require(freeze['sources_sha256']==sha(source_raw) and freeze['prompts_sha256']==sha(prompts_raw), 'FREEZE_SOURCE_PROMPT_POINTER')
    require(set(freeze['plan_sha256_by_phase'])==set(PHASES), 'ALL_PHASE_PLANS_NOT_FROZEN')
    plans={}
    for phase,digest in freeze['plan_sha256_by_phase'].items():
        raw=store.get('plans/'+digest+'.json'); require(sha(raw)==digest, 'PLAN_BYTE_SHA')
        plans[phase]=json.loads(raw)
    selected_raw=store.get('selection/FINAL_PLAN.json',True)
    if selected_raw is not None:
        selected=json.loads(selected_raw)
        evidence_raw=store.get('selection/FINAL_SELECTION.json')
        require(sha(evidence_raw)==selected['selection_evidence_sha256'], 'FINAL_SELECTION_EVIDENCE_SHA')
        evidence=json.loads(evidence_raw)
        require(evidence['campaign']==CAMPAIGN and evidence['sources_sha256']==sha(source_raw)
                and evidence['freeze_sha256']==sha(freeze_raw) and evidence['prior_reserved']==128
                and evidence['selected_candidates']==selected['selected_candidates'], 'FINAL_SELECTION_IDENTITY')
        require(set(evidence['discovery_result_sha256_by_slot'])=={task['slot'] for ph in ('S','D') for task in plans[ph]['slots']}, 'FINAL_SELECTION_RESULT_SET')
        for slot,digest in evidence['discovery_result_sha256_by_slot'].items():
            result_raw=store.get('results/'+slot+'.json')
            require(sha(result_raw)==digest and json.loads(result_raw)['success'] is True, 'FINAL_SELECTION_RESULT_SHA')
        for ph,expected in (('S',16),('D',112)):
            state=read_json(store,'states/'+ph+'-finished.json')
            require(state['status']=='CHECKPOINT_LOCKED' and state['stage_counts'][ph]['reserved']==expected
                    and state['failed']==state['unknown']==0, 'FINAL_BEFORE_DISCOVERY_COMPLETE')
        plans['F']=selected
    if control.get('phase')=='F' and control.get('mode') in ('STAGE','EXECUTE','CLOSE'):
        require(selected_raw is not None, 'FINAL_SELECTION_NOT_RECORDED')
    by,effective=validate_design(source_document,freeze,plans)
    validate_prompts(prompts)
    if control.get('phase') in PHASES:
        expected_plan_sha=sha(selected_raw) if control['phase']=='F' and selected_raw is not None else freeze['plan_sha256_by_phase'][control['phase']]
        require(control['plan_sha256']==expected_plan_sha, 'CONTROL_PLAN_POINTER')
    return by,prompts,freeze,plans,effective

def reservations(store):
    names=[f'budget/{i:04d}.json' for i in range(1,APPROVED_TOTAL+1)]
    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as pool:
        raw=list(pool.map(lambda n:store.get(n,True),names))
    records=[json.loads(value) for value in raw if value is not None]
    require(all(value is not None for value in raw[:len(records)]) and all(value is None for value in raw[len(records):]), 'NONCONTIGUOUS_LEDGER')
    require(len({r['slot'] for r in records})==len(records), 'DUPLICATE_LEDGER_SLOT')
    for ordinal,record in enumerate(records,1):
        require(record['campaign']==CAMPAIGN and record['model']==MODEL and record['ordinal']==ordinal
                and record['stage'] in PHASES, 'LEDGER_IDENTITY_MISMATCH')
    return records

def reconcile(store):
    # Always fetch authoritative reservations. A successful upload followed by a
    # failed readback may have committed a reservation before the caller appended it.
    records=reservations(store)
    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as pool:
        raws=list(pool.map(lambda r:store.get('results/'+r['slot']+'.json',True),records))
    by_phase={phase:{'reserved':0,'success':0,'failed':0,'unknown':0,'transmitted_recorded':0} for phase in PHASES}
    results={}
    for record,raw in zip(records,raws):
        counts=by_phase[record['stage']]; counts['reserved']+=1
        if raw is None:
            counts['unknown']+=1
            continue
        result=json.loads(raw)
        require(all(result.get(k)==record[k] for k in ('campaign','model','slot','stage','ordinal','input_sha256','request_sha256')), 'RESULT_LEDGER_MISMATCH')
        require(sha(canon(result['request']))==record['request_sha256'] and sha(result['request']['input'].encode())==record['input_sha256'], 'RESULT_REQUEST_SHA')
        require(result.get('http_attempts')==1 and result.get('send_invoked') is True, 'RESULT_TRANSMISSION_METADATA')
        counts['transmitted_recorded']+=1
        counts['unknown' if result.get('unknown') else 'success' if result.get('success') else 'failed']+=1
        results[record['slot']]=result
    totals={key:sum(row[key] for row in by_phase.values()) for key in ('reserved','success','failed','unknown','transmitted_recorded')}
    return records,results,by_phase,totals

def verify_backup_gate(store, control, phase, current_reserved):
    require(control.get('backup_verified') is True, 'BACKUP_NOT_VERIFIED')
    require(control['backup_receipt_object']=='gates/'+phase+'.json', 'BACKUP_RECEIPT_PATH')
    raw=store.get(control['backup_receipt_object'])
    require(sha(raw)==control['backup_receipt_sha256'], 'BACKUP_RECEIPT_SHA')
    gate=json.loads(raw)
    require(gate['campaign']==CAMPAIGN and gate['phase']==phase and gate['verified'] is True
            and gate['prior_reserved']==current_reserved, 'BACKUP_RECEIPT_IDENTITY')
    for key in ('drive_readback_verified','owner_only','sha256_verified','zip_crc_verified','manifest_verified'):
        require(gate.get(key) is True, 'BACKUP_PROOF_INCOMPLETE')
    previous=control.get('previous_phase')
    require(gate.get('previous_phase')==previous, 'PREVIOUS_PHASE_GATE_MISMATCH')
    if previous is None:
        require(phase=='S' and current_reserved==0 and gate.get('previous_state_sha256') is None, 'INITIAL_BACKUP_GATE')
    else:
        require(previous in PHASES and (phase=='CLOSE' or phase in PHASES and PHASES.index(previous)+1==PHASES.index(phase)), 'PHASE_ORDER')
        state_raw=store.get('states/'+previous+'-finished.json')
        require(sha(state_raw)==gate['previous_state_sha256'], 'PREVIOUS_FINISHED_STATE_SHA')
        state=json.loads(state_raw)
        require(state['status'] in (('CHECKPOINT_LOCKED','PAUSED_LOCKED') if phase=='CLOSE' else ('CHECKPOINT_LOCKED',))
                and state['enabled'] is False and state['max_new']==0 and state['ledger_resolved'] is True
                and state['reserved_total']==current_reserved, 'PREVIOUS_PHASE_NOT_SAFE')
        if phase!='CLOSE':
            require(state['failed']==state['unknown']==0 and not state.get('skips'), 'PREVIOUS_PHASE_ERRORS')
        require(store.get('locks/'+previous+'.RELEASED.json',True) is not None, 'PREVIOUS_PHASE_LEASE_UNRELEASED')
    return gate

def unpack_package(store, control):
    raw=None
    with tempfile.TemporaryDirectory() as td:
        work=pathlib.Path(td)
        key_path=work/'key.pem'; key_path.write_bytes(store.input_key()); key_path.chmod(0o600)
        (work/'input.p7m').write_bytes(base64.b64decode((HERE/'input.p7m.b64').read_bytes(),validate=True))
        subprocess.run(['openssl','cms','-decrypt','-binary','-inform','DER','-in',str(work/'input.p7m'),
                        '-inkey',str(key_path),'-out',str(work/'package.bin')],check=True,capture_output=True)
        data=(work/'package.bin').read_bytes()
        raw=gzip.decompress(data) if data.startswith(b'\x1f\x8b') else data
        require(sha(raw)==control['package_sha256'], 'PACKAGE_SHA')
        package=json.loads(raw)
    require(package['campaign']==CAMPAIGN, 'FOREIGN_INPUT_PACKAGE')
    require(set(package)<= {'campaign','objects','objects_b64'}, 'PACKAGE_FIELD_SET')
    objects={name:canon(value) for name,value in package.get('objects',{}).items()}
    for name,value in package.get('objects_b64',{}).items():
        require(name not in objects, 'DUPLICATE_PACKAGE_OBJECT')
        objects[name]=base64.b64decode(value,validate=True)
    require(bool(objects), 'EMPTY_PRIVATE_PACKAGE')
    for name in objects:
        require(name.startswith(('preparation/','plans/','gates/','evaluation/','selection/')) and '..' not in name
                and name.endswith('.json') and not name.startswith('/'), 'UNAPPROVED_PACKAGE_OBJECT')
    return objects

def stage(store, control):
    require(control['mode'] in ('STAGE','EXECUTE'), 'STAGE_MODE')
    verify_lease(store,control); require_no_terminal(store)
    objects=unpack_package(store,control)
    for name,data in objects.items():
        store.put_same(name,data)
    by,prompts,freeze,plans,effective=load_design(store,control)
    phase=control['phase']; require(phase in PHASES, 'STAGE_PHASE')
    require(len(plans[phase]['slots'])==control['max_new'], 'STAGE_PLAN_COUNT')
    records=reservations(store)
    require(len(records)==control['prior_reserved'], 'STAGE_PRIOR_RESERVATIONS')
    staged={'campaign':CAMPAIGN,'phase':phase,'status':'STAGED_LOCKED','enabled':False,'max_new':0,
            'reserved_total':len(records),'plan_sha256':control['plan_sha256'],'owner_token':control['owner_token']}
    store.put_same('controls/'+phase+'/STAGED_LOCKED.json',canon(staged))
    store.put_same('checks/stage-'+phase+'.json',canon({'campaign':CAMPAIGN,'phase':phase,
                   'package_sha256':control['package_sha256'],'plan_sha256':control['plan_sha256'],
                   'source_sha256':control['source_sha256'],'prompts_sha256':control['prompts_sha256'],
                   'freeze_sha256':control['freeze_sha256'],'generation_calls':0}))
    store.put_same('checks/packages/'+control['package_sha256']+'.json',canon({'campaign':CAMPAIGN,'phase':phase,
                   'objects':{name:{'bytes':len(data),'sha256':sha(data)} for name,data in objects.items()},'generation_calls':0}))
    metadata_log('STAGED',{'phase':phase,'slots':len(plans[phase]['slots']),'generation_calls':0})

def resolve_input(task, sources, results):
    if task['path'] in ('KF','LF'):
        require(task['path']==sources[task['source_id']]['direction'], 'FIRST_DIRECTION_MISMATCH')
        return sources[task['source_id']]['source'],None
    parent=results.get(task['parent_first_id'])
    if parent is not None:
        require(parent['source_id']==task['source_id'] and parent['candidate']==task['candidate']
                and parent['path']==task['path'][0]+'F' and parent['stage']==task['slot'][0], 'BACK_PARENT_IDENTITY')
    text=back_input(parent)
    return text,parent

def record_terminal_pause(store, state):
    # Terminal state is written before a supplementary authority. Even a partial
    # terminal write blocks every future execution path via require_no_terminal.
    for name in ('states/PAUSED_LOCKED.json','controls/PAUSED/PAUSED_LOCKED.json'):
        existing=store.get(name,True)
        if existing is None: store.create(name,canon(state))
        else: require(json.loads(existing)['campaign']==CAMPAIGN, 'FOREIGN_TERMINAL_STATE')

async def execute(store, control, sender=send, client_factory=make_client):
    require(control['mode']=='EXECUTE' and control['enabled'] is True, 'EXECUTION_NOT_ENABLED')
    require(control['deadline_epoch']>time.time(), 'ACTIVATION_EXPIRED')
    require(bool(os.environ.get('OPENAI_API_KEY')), 'MISSING_EXISTING_API_SECRET')
    verify_lease(store,control); require_no_terminal(store)
    sources,prompts,freeze,plans,effective=load_design(store,control)
    phase=control['phase']; plan=plans[phase]
    require(control['max_new']==len(plan['slots'])==effective[phase], 'EXECUTION_PLAN_CAP')
    records,results,by_phase,totals=reconcile(store)
    require(totals['reserved']==control['prior_reserved'] and totals['failed']==totals['unknown']==0, 'PRIOR_LEDGER_NOT_SAFE')
    require(by_phase[phase]['reserved']==0, 'PHASE_ALREADY_ATTEMPTED')
    require(totals['reserved']+len(plan['slots'])<=APPROVED_TOTAL, 'CAMPAIGN_CAP')
    verify_backup_gate(store,control,phase,len(records))
    staged=read_json(store,'controls/'+phase+'/STAGED_LOCKED.json')
    require(staged['campaign']==CAMPAIGN and staged['owner_token']==control['owner_token']
            and staged['plan_sha256']==control['plan_sha256'] and staged['enabled'] is False
            and staged['max_new']==0 and staged['reserved_total']==len(records), 'STAGED_AUTHORITY_MISMATCH')
    lock={'campaign':CAMPAIGN,'owner_token':control['owner_token'],'phase':phase,
          'run':os.environ['GITHUB_RUN_ID'],'commit':os.environ['GITHUB_SHA'],'plan_sha256':control['plan_sha256']}
    # A committed lock whose readback failed belongs to this run and must pause.
    # A different run's existing lease is never adopted or overwritten.
    try:
        store.create('locks/'+phase+'.json',canon(lock))
    except Exception as exc:
        observed=store.get('locks/'+phase+'.json',True)
        if observed==canon(lock):
            try:
                _,_,_,current=reconcile(store)
                pause={'ledger_resolved':True,'reserved_total':current['reserved'],
                       'success':current['success'],'failed':current['failed'],'unknown':current['unknown'],
                       'unused_locked':APPROVED_TOTAL-current['reserved']}
            except Exception as read_exc:
                pause={'ledger_resolved':False,'reserved_total':None,'success':None,'failed':None,
                       'unknown':None,'unused_locked':None,'reconciliation_error':safe_code(read_exc)}
            pause.update(campaign=CAMPAIGN,phase=phase,status='PAUSED_LOCKED',enabled=False,max_new=0,
                         research_complete=False,reason=safe_code(exc),attempted_this_run=0,
                         run=os.environ['GITHUB_RUN_ID'],owner_token=control['owner_token'])
            record_terminal_pause(store,pause)
        raise
    try:
        store.create('locks/after-'+str(len(records))+'.json',canon(lock))
    except Exception as exc:
        pause={'campaign':CAMPAIGN,'phase':phase,'status':'PAUSED_LOCKED','enabled':False,'max_new':0,
               'research_complete':False,'ledger_resolved':False,'reserved_total':None,
               'reason':safe_code(exc),'run':os.environ['GITHUB_RUN_ID']}
        record_terminal_pause(store,pause)
        raise
    attempted=0; completed=False; stopped=None; skips=[]; state=None
    started=time.monotonic()
    try:
        require_no_terminal(store)
        require(reservations(store)==records, 'LEDGER_CHANGED_AFTER_LEASE')
        for task in plan['slots']:
            require(store.get('results/'+task['slot']+'.json',True) is None
                    and store.get('requests/'+task['slot']+'.json',True) is None, 'EXISTING_SLOT_OBJECT')
        running=dict(lock,status='RUNNING',enabled=True,max_new=len(plan['slots']),reserved_total=len(records))
        store.create('states/'+phase+'-running.json',canon(running))
        store.create('controls/'+phase+'/RUNNING.json',canon(running))
        async with client_factory() as client:
            for task in plan['slots']:
                require(control['deadline_epoch']>time.time(), 'ACTIVATION_EXPIRED')
                require(time.monotonic()-started<{'S':900,'D':3600,'F':1200}[phase], 'STAGE_TIME_BOUND')
                require_no_terminal(store)
                text,parent=resolve_input(task,sources,results)
                if text is None:
                    skips.append(task['slot'])
                    store.create('skips/'+task['slot']+'.json',canon({'campaign':CAMPAIGN,'slot':task['slot'],
                                  'reason':'NO_TECHNICALLY_COMPLETE_FIRST','unattempted':True}))
                    continue
                prompt_candidate=task['candidate']
                payload=build_payload(MODEL,'none',task['path'],text,prompts[prompt_candidate])
                if parent is not None:
                    require(payload['input']==parent['display_text'] and set(payload)=={'model','reasoning','instructions','input','stream','store','max_output_tokens','service_tier'}, 'BACK_REQUEST_LEAKAGE')
                record=budget_guard(records,task['slot'],phase,effective)
                record.update(source_id=task['source_id'],candidate=task['candidate'],path=task['path'],
                              repeat_index=task['repeat_index'],source_sha256=sources[task['source_id']]['sha256'],
                              source_direction=sources[task['source_id']]['direction'],
                              raw_record_number=sources[task['source_id']]['raw_record_number'],
                              prompt_sha256=sha(payload['instructions'].encode()),request_sha256=sha(canon(payload)),
                              input_sha256=sha(text.encode()),run=os.environ['GITHUB_RUN_ID'],
                              commit=os.environ['GITHUB_SHA'])
                request={'campaign':CAMPAIGN,'slot':task['slot'],'request':payload,
                         'request_sha256':record['request_sha256'],'input_sha256':record['input_sha256']}
                store.create('requests/'+task['slot']+'.json',canon(request))
                store.create(f"budget/{record['ordinal']:04d}.json",canon(record))
                records.append(record)
                # Exactly one call; the checked sender uses HTTP retries=0.
                attempted+=1
                result=await sender(client,payload,os.environ['OPENAI_API_KEY'])
                result=validate_result_metadata(result)
                result.update({k:record[k] for k in ('campaign','model','slot','stage','ordinal','source_id','candidate','path','repeat_index','source_sha256','source_direction','raw_record_number','request_sha256','input_sha256','run','commit')})
                result.update(request=payload,send_invoked=True,prompt_candidate=prompt_candidate,
                              prompt_sha256=sha(payload['instructions'].encode()),
                              parent_first_id=parent['slot'] if parent else None)
                if parent:
                    result['back_input_equals_displayed_first']=text==parent['display_text']
                    result['displayed_first_sha256']=sha(parent['display_text'].encode())
                store.create('results/'+task['slot']+'.json',canon(result))
                results[task['slot']]=result
                store.create(f"checkpoints/attempt-{record['ordinal']:04d}.json",canon({'campaign':CAMPAIGN,
                             'slot':task['slot'],'reserved':record['ordinal'],'result_sha256':sha(canon(result))}))
                metadata_log('ATTEMPT',{'slot':task['slot'],'ordinal':record['ordinal'],'success':result['success'],
                             'unknown':result['unknown'],'http_status':result.get('http_status')})
                if not result['success']:
                    stopped='TECHNICAL_FAILURE_STOP_NO_RETRY'
                    break
        completed=(stopped is None and not skips)
    except Exception as exc:
        stopped=safe_code(exc)
    finally:
        try:
            fresh_records,fresh_results,fresh_by_phase,fresh_totals=reconcile(store)
            resolved=True
            state={'campaign':CAMPAIGN,'phase':phase,'enabled':False,'max_new':0,'research_complete':False,
                   'ledger_resolved':True,'reserved_total':fresh_totals['reserved'],
                   'transmitted_attempts_recorded':fresh_totals['transmitted_recorded'],
                   'success':fresh_totals['success'],'failed':fresh_totals['failed'],'unknown':fresh_totals['unknown'],
                   'unused_locked':APPROVED_TOTAL-fresh_totals['reserved'],
                   'conditional_final_not_activated':HARD_CAPS['F']-effective['F'],
                   'stage_caps':effective,'hard_stage_caps':HARD_CAPS,'stage_counts':fresh_by_phase}
            is_pause=bool(stopped or not completed or fresh_totals['failed'] or fresh_totals['unknown'])
        except Exception as exc:
            resolved=False; is_pause=True
            state={'campaign':CAMPAIGN,'phase':phase,'enabled':False,'max_new':0,'research_complete':False,
                   'ledger_resolved':False,'reserved_total':None,'success':None,'failed':None,'unknown':None,
                   'unused_locked':None,'known_reserved_lower_bound':control['prior_reserved'],
                   'reconciliation_error':safe_code(exc)}
        state.update(status='PAUSED_LOCKED' if is_pause else 'CHECKPOINT_LOCKED',
                     reason=stopped,attempted_this_run=attempted,finished=completed,skips=skips,
                     run=os.environ['GITHUB_RUN_ID'],commit=os.environ['GITHUB_SHA'],
                     plan_sha256=control['plan_sha256'],owner_token=control['owner_token'])
        try:
            if is_pause: record_terminal_pause(store,state)
            store.create('controls/'+phase+'/'+state['status']+'.json',canon(state))
            store.create('states/'+phase+'-finished.json',canon(state))
            store.create('locks/'+phase+'.RELEASED.json',canon(lock))
        except Exception as exc:
            metadata_log('REMOTE_STATE_WRITE_UNVERIFIED',{'phase':phase,'code':safe_code(exc),'generation_stopped':True})
            raise
        metadata_log('STAGE_STATE',state)
    return state

def close(store, control):
    require(control['mode']=='CLOSE' and control['enabled'] is False and control['max_new']==0, 'CLOSE_CONTROL')
    verify_lease(store,control)
    require(store.get('states/CLOSED_LOCKED.json',True) is None and store.get('controls/CLOSED/CLOSED_LOCKED.json',True) is None, 'ALREADY_CLOSED')
    sources,prompts,freeze,plans,effective=load_design(store,control)
    records,results,by_phase,totals=reconcile(store)
    require(totals['reserved']==control['prior_reserved'], 'CLOSE_LEDGER_COUNT')
    complete=control.get('research_complete') is True
    if complete:
        require(totals['failed']==totals['unknown']==0 and totals['reserved']==sum(effective.values()), 'INCOMPLETE_CANNOT_CLOSE_AS_COMPLETE')
        require('selected_candidates' in plans['F'], 'FINAL_SELECTION_NOT_RECORDED')
        for phase in PHASES:
            prior=read_json(store,'states/'+phase+'-finished.json')
            require(prior['status']=='CHECKPOINT_LOCKED' and prior['enabled'] is False and prior['max_new']==0
                    and prior['ledger_resolved'] is True and not prior.get('skips'), 'CLOSE_PHASE_NOT_COMPLETE')
            require(by_phase[phase]['reserved']==effective[phase], 'CLOSE_STAGE_COUNT')
            require(store.get('locks/'+phase+'.RELEASED.json',True) is not None, 'CLOSE_STAGE_LEASE')
    else:
        require(isinstance(control.get('closure_reason'),str) and bool(control['closure_reason'].strip()), 'PARTIAL_CLOSE_REASON_REQUIRED')
    verify_backup_gate(store,control,'CLOSE',len(records))
    state={'campaign':CAMPAIGN,'status':'CLOSED_LOCKED','enabled':False,'max_new':0,'research_complete':complete,
           'ledger_resolved':True,'approved_total':APPROVED_TOTAL,'reserved_total':totals['reserved'],
           'actual_api_attempts_recorded':totals['transmitted_recorded'],
           'success':totals['success'],'failed':totals['failed'],'unknown':totals['unknown'],
           'unused_locked':APPROVED_TOTAL-totals['reserved'],'next_new_authorization':0,
           'stage_counts':by_phase,'stage_caps':effective,'hard_stage_caps':HARD_CAPS,
           'closure_reason':control.get('closure_reason','NORMAL_PROTOCOL_COMPLETE'),
           'selected_final_candidates':plans['F'].get('selected_candidates'),
           'owner_token':control['owner_token'],'run':os.environ['GITHUB_RUN_ID'],'commit':os.environ['GITHUB_SHA'],
           'generation_calls':0,'closed_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}
    store.create('states/CLOSED_LOCKED.json',canon(state))
    store.create('controls/CLOSED/CLOSED_LOCKED.json',canon(state))
    metadata_log('CLOSED_STATE',state)
    return state

def ingest_close(store, control):
    require(control['mode']=='CLOSE' and control['enabled'] is False and control['max_new']==0, 'CLOSE_INGEST_CONTROL')
    verify_lease(store,control)
    objects=unpack_package(store,control)
    require('gates/CLOSE.json' in objects and all(name=='gates/CLOSE.json' or name.startswith('evaluation/')
            for name in objects), 'CLOSE_INGEST_OBJECT_SET')
    require(sha(objects['gates/CLOSE.json'])==control['backup_receipt_sha256'], 'CLOSE_GATE_PACKAGE_SHA')
    for name,data in objects.items(): store.put_same(name,data)
    records,results,by_phase,totals=reconcile(store)
    require(len(records)==control['prior_reserved'], 'CLOSE_INGEST_PRIOR_RESERVATIONS')
    verify_backup_gate(store,control,'CLOSE',len(records))
    metadata_log('CLOSE_GATE_STAGED',{'generation_calls':0,'reserved_total':len(records)})

def publish(store, control):
    require(control['mode']=='PUBLISH' and control['enabled'] is False and control['max_new']==0, 'PUBLISH_CONTROL')
    verify_lease(store,control)
    objects=unpack_package(store,control)
    require(all(name.startswith('evaluation/') for name in objects), 'PUBLISH_EVALUATION_ONLY')
    for name,data in objects.items(): store.put_same(name,data)
    metadata_log('PUBLISHED',{'generation_calls':0,'objects':list(objects),
                 'sha256':{name:sha(data) for name,data in objects.items()}})

def export(store, control):
    verify_lease(store,control)
    # Export has no OpenAI client call and remains available after terminal locks.
    names={'CONTROL.json','LOCK.json','preflight/PREFLIGHT.json',SOURCE_OBJECT,PROMPTS_OBJECT,FREEZE_OBJECT,
           'states/CLOSED_LOCKED.json','states/PAUSED_LOCKED.json','controls/CLOSED/CLOSED_LOCKED.json',
           'controls/PAUSED/PAUSED_LOCKED.json','gates/CLOSE.json','evaluation/FINAL_EVALUATION.json',
           'evaluation/FINAL_REPORT.json','checks/PREFLIGHT_PROBE.json','selection/FINAL_PLAN.json','selection/FINAL_SELECTION.json'}
    freeze_raw=store.get(FREEZE_OBJECT,True)
    if freeze_raw:
        freeze=json.loads(freeze_raw)
        names.update('plans/'+digest+'.json' for digest in freeze['plan_sha256_by_phase'].values())
        for name in freeze.get('additional_export_objects',[]):
            require(name.startswith(('preparation/','evaluation/')) and '..' not in name and name.endswith('.json'), 'EXPORT_EXTRA_PATH')
            names.add(name)
    if control.get('package_sha256'): names.add('checks/packages/'+control['package_sha256']+'.json')
    for ordinal in range(1,APPROVED_TOTAL+1):
        names.add(f'budget/{ordinal:04d}.json'); names.add(f'checkpoints/attempt-{ordinal:04d}.json')
        names.add('locks/after-'+str(ordinal-1)+'.json')
    for phase,cap in HARD_CAPS.items():
        names.update({'gates/'+phase+'.json','checks/stage-'+phase+'.json','states/'+phase+'-running.json','states/'+phase+'-finished.json',
                      'locks/'+phase+'.json','locks/'+phase+'.RELEASED.json'})
        names.update('controls/'+phase+'/'+status+'.json' for status in ('STAGED_LOCKED','RUNNING','CHECKPOINT_LOCKED','PAUSED_LOCKED'))
        for index in range(1,cap+1):
            for kind in ('requests','results','skips'): names.add(f'{kind}/{phase}-{index:03d}.json')
    ordered=sorted(names)
    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as pool:
        raw=list(pool.map(lambda n:store.get(n,True),ordered))
    objects={name:data for name,data in zip(ordered,raw) if data is not None}
    spool_root=pathlib.Path(os.environ['RUNNER_TEMP'])/'couple-tone-name-ab160-spool'
    unmatched=[]
    if spool_root.exists():
        for path in spool_root.rglob('*'):
            if path.is_file():
                name=str(path.relative_to(spool_root));data=path.read_bytes()
                if name not in objects or objects[name]!=data:
                    objects['local_spool_unconfirmed_remote/'+name]=data;unmatched.append(name)
    objects['LOCAL_SPOOL_AUDIT.json']=canon({'campaign':CAMPAIGN,'remote_export_completed':True,'unmatched_local_objects':unmatched,'note':'Unmatched local objects do not prove a committed remote write.'})
    for name in sorted(CODE_FILES|{'CONTROL.json'}):
        objects['execution_code/'+name]=(HERE/name).read_bytes()
    manifest={name:{'bytes':len(data),'sha256':sha(data)} for name,data in objects.items()}
    output=pathlib.Path(os.environ['RUNNER_TEMP'])/'couple-tone-name-ab160-export.p7m'
    with tempfile.TemporaryDirectory() as td:
        raw_zip=pathlib.Path(td)/'raw.zip'
        with zipfile.ZipFile(raw_zip,'w',zipfile.ZIP_DEFLATED) as archive:
            for name,data in objects.items(): archive.writestr(name,data)
            archive.writestr('MANIFEST.json',canon(manifest))
        with zipfile.ZipFile(raw_zip) as archive:
            require(archive.testzip() is None, 'EXPORT_LOCAL_CRC')
        subprocess.run(['openssl','cms','-encrypt','-aes256','-binary','-outform','DER','-in',str(raw_zip),
                        '-out',str(output),str(HERE/'export-cert.pem')],check=True,capture_output=True)
        key='exports/'+control.get('phase',control['mode'])+'-'+os.environ['GITHUB_RUN_ID']+'.p7m'
        store.create(key,output.read_bytes())
        receipt={'campaign':CAMPAIGN,'generation_calls':0,'key':key,'plain_sha256':sha(raw_zip.read_bytes()),
                 'cipher_sha256':sha(output.read_bytes()),'objects':len(objects),'file':output.name}
        metadata_log('EXPORT_RECEIPT',receipt)
    return receipt

def fallback_export(control, error):
    # No network and no generation. A remote export failure still produces a
    # private encrypted artifact with locally spooled request/result bytes.
    root=pathlib.Path(os.environ['RUNNER_TEMP'])/'couple-tone-name-ab160-spool'
    objects={'execution_code/'+name:(HERE/name).read_bytes() for name in CODE_FILES|{'CONTROL.json'}}
    if root.exists():
        for path in root.rglob('*'):
            if path.is_file():objects['local_spool_unconfirmed_remote/'+str(path.relative_to(root))]=path.read_bytes()
    objects['REMOTE_EXPORT_INCOMPLETE.json']=canon({'campaign':CAMPAIGN,'remote_export_completed':False,
        'generation_calls':0,'error':safe_code(error),'note':'Local evidence only. Remote ledger and terminal lock require separate verification.'})
    manifest={name:{'bytes':len(data),'sha256':sha(data)} for name,data in objects.items()}
    out=pathlib.Path(os.environ['RUNNER_TEMP'])/'couple-tone-name-ab160-export.p7m'
    with tempfile.TemporaryDirectory() as td:
        plain=pathlib.Path(td)/'local-evidence.zip'
        with zipfile.ZipFile(plain,'w',zipfile.ZIP_DEFLATED) as z:
            for name,data in objects.items():z.writestr(name,data)
            z.writestr('MANIFEST.json',canon(manifest))
        subprocess.run(['openssl','cms','-encrypt','-aes256','-binary','-outform','DER','-in',str(plain),'-out',str(out),str(HERE/'export-cert.pem')],check=True,capture_output=True)
        metadata_log('EXPORT_RECEIPT',{'campaign':CAMPAIGN,'generation_calls':0,'remote_export_completed':False,
            'plain_sha256':sha(plain.read_bytes()),'cipher_sha256':sha(out.read_bytes()),'objects':len(objects),'file':out.name})

def main():
    control=runtime_control(); mode=sys.argv[1]
    if mode=='EXPORT':
        try: export(RemoteStore(),control)
        except Exception as exc: fallback_export(control,exc)
        return
    store=RemoteStore()
    if mode=='STAGE': stage(store,control)
    elif mode=='EXECUTE':
        state=asyncio.run(execute(store,control))
        if state['status']!='CHECKPOINT_LOCKED': raise SystemExit(2)
    elif mode=='INGEST_CLOSE': ingest_close(store,control)
    elif mode=='CLOSE': close(store,control)
    elif mode=='PUBLISH': publish(store,control)
    else: raise AssertionError('UNAPPROVED_COMMAND')

if __name__=='__main__':
    try: main()
    except Exception as exc:
        metadata_log('STOP',{'code':safe_code(exc),'generation_not_retried':True})
        raise SystemExit(1)
