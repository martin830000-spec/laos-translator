#!/usr/bin/env python3
"""Read-only GCS authority recheck after REALCHAT80 CLOSE. No generation or writes."""
import hashlib
import json
import os
import pathlib

CAMPAIGN = 'GPT_LUNA_GD_REALCHAT80_20261112'
ROOT = 'research/gemini-model-native500-20261107/'
PREFIX = ROOT+'gpt-luna-gd-realchat80-20261112/'
SCREEN_PREFIX = ROOT+'gpt-luna-gd-scope-screen80-20261112/'
SCREEN_SHA = '8434a8e50989a3ffcc1854fb4ce12fe7289696fa208c17e853a3fc0adac048d1'
PREVIOUS = {
    'gpt-luna-p168a-transfer320-20261111':288,
    'gpt-luna-source-variant320-20261110':290,
    'gpt-source-vs-prompt-factorial320-20261111':264,
    'gpt-luna-lf-variance320-20261110':264,
    'gpt-luna-terra-mechanism1000-20261110':776,
}
EXPECTED_STAGE_ACTUAL = {'A':27,'B':9,'C':24,'D':8}

def sha(data):
    return hashlib.sha256(data).hexdigest()

def require(condition, code):
    if not condition:
        raise AssertionError(code)

def check_state(get, control):
    """get receives exact existing object names and must only download bytes."""
    require(control['campaign']==CAMPAIGN and control['approved_total']==80
            and control['mode']=='CLOSE' and control['enabled'] is False
            and control['max_new']==0, 'EXPECTED_DISABLED_CLOSE_CONTROL')
    require(control['preflight_object']=='preflight/PREFLIGHT.json', 'PREFLIGHT_OBJECT_PATH')
    preflight_raw=get(PREFIX+'preflight/PREFLIGHT.json')
    require(sha(preflight_raw)==control['preflight_sha256'], 'PREFLIGHT_SHA_CHANGED')
    preflight=json.loads(preflight_raw)
    require(preflight['campaign']==CAMPAIGN and preflight['generation_calls']==0
            and preflight['owner_token']==control['owner_token'], 'PREFLIGHT_IDENTITY_CHANGED')
    require(set(preflight['old_closed'])==set(PREVIOUS), 'PREVIOUS_CAMPAIGN_SET_CHANGED')
    protected={}
    for name,count in PREVIOUS.items():
        raw=get(ROOT+name+'/states/CLOSED_LOCKED.json')
        require(sha(raw)==preflight['old_closed'][name]['sha256'], 'PREVIOUS_CLOSED_BYTES_CHANGED')
        state=json.loads(raw)
        require(state['status']=='CLOSED_LOCKED' and state['enabled'] is False
                and state['max_new']==0 and state['reserved_total']==count,
                'PREVIOUS_CLOSED_STATE_CHANGED')
        dual=None
        if name!='gpt-luna-terra-mechanism1000-20261110':
            dual=get(ROOT+name+'/controls/CLOSED/CLOSED_LOCKED.json')==raw
            require(dual, 'PREVIOUS_DUAL_AUTHORITY_CHANGED')
        protected[name]={'sha256':sha(raw),'status':state['status'],'reserved_total':count,
                         'dual_authority_bytes_equal':dual,
                         'sha_equal_to_preflight':True}

    screen_raw=get(SCREEN_PREFIX+'states/PAUSED_LOCKED.json')
    require(sha(screen_raw)==SCREEN_SHA==preflight['old_screen_sha256'], 'SCREEN80_PAUSED_BYTES_CHANGED')
    require(get(SCREEN_PREFIX+'controls/PAUSED/PAUSED_LOCKED.json')==screen_raw,
            'SCREEN80_DUAL_AUTHORITY_CHANGED')
    screen=json.loads(screen_raw)
    require(screen['campaign']=='GPT_LUNA_GD_SCOPE_SCREEN80_20261112'
            and screen['status']=='PAUSED_LOCKED' and screen['enabled'] is False
            and screen['max_new']==0 and screen['actual']==screen['reserved_total']==0
            and screen['unused_locked']==80, 'SCREEN80_LOCK_STATE_CHANGED')

    authority_state=PREFIX+'states/CLOSED_LOCKED.json'
    authority_control=PREFIX+'controls/CLOSED/CLOSED_LOCKED.json'
    closed_raw=get(authority_state)
    require(get(authority_control)==closed_raw, 'NEW_CLOSED_AUTHORITY_BYTES_DIFFER')
    closed=json.loads(closed_raw)
    require(closed['campaign']==CAMPAIGN and closed['status']=='CLOSED_LOCKED'
            and closed['enabled'] is False and closed['max_new']==0
            and closed['approved_total']==80 and closed['ledger_resolved'] is True,
            'NEW_CLOSED_STATE_INVALID')
    require(closed['reserved_total']==closed['success']==68 and closed['failed']==closed['unknown']==0
            and closed['unused_locked']==12, 'NEW_CLOSED_COUNTS_INVALID')
    require(closed['owner_token']==preflight['owner_token'], 'NEW_CLOSED_OWNER_MISMATCH')
    require(set(closed['stage_counts'])==set(EXPECTED_STAGE_ACTUAL), 'NEW_STAGE_SET_INVALID')
    for phase,count in EXPECTED_STAGE_ACTUAL.items():
        row=closed['stage_counts'][phase]
        require(row['reserved']==row['success']==row['transmitted_recorded']==count
                and row['failed']==row['unknown']==0, 'NEW_STAGE_COUNTS_INVALID')

    root_raw=get(PREFIX+'CONTROL.json')
    root=json.loads(root_raw)
    require(root['campaign']==CAMPAIGN and root['owner_token']==preflight['owner_token']
            and root['status']=='PREFLIGHT_LOCKED' and root['enabled'] is False
            and root['max_new']==0 and root['approved_total']==80
            and root['reserved_total']==root['actual']==0, 'HISTORICAL_ROOT_CONTROL_CHANGED')

    return {
        'campaign':CAMPAIGN,
        'status':'PASS',
        'generation_calls':0,
        'gcs_writes':0,
        'openai_requests':0,
        'api_key_reads':0,
        'preflight_receipt_sha256':sha(preflight_raw),
        'previous_closed':protected,
        'previous_screen80':{'sha256':sha(screen_raw),'status':'PAUSED_LOCKED',
                             'actual':0,'reserved_total':0,'unused_locked':80,
                             'enabled':False,'max_new':0,'dual_authority_bytes_equal':True},
        'new_campaign_authority':{
            'objects':[authority_state,authority_control],
            'sha256':sha(closed_raw),'status':'CLOSED_LOCKED',
            'enabled':False,'max_new':0,'reserved_total':68,'success':68,
            'failed':0,'unknown':0,'unused_locked':12,
            'stage_actual':EXPECTED_STAGE_ACTUAL,'dual_authority_bytes_equal':True,
        },
        'historical_root_control':{
            'object':PREFIX+'CONTROL.json','sha256':sha(root_raw),'status':'PREFLIGHT_LOCKED',
            'reserved_total':0,'enabled':False,'max_new':0,
            'authority_status':'HISTORICAL_INITIAL_SNAPSHOT_NOT_FINAL_COUNTS',
        },
    }

def main():
    require(os.environ.get('GITHUB_REF')=='refs/heads/research/gemini-model-native500-20261107', 'WRONG_BRANCH')
    require(os.environ.get('GITHUB_RUN_ATTEMPT')=='1'
            and os.environ.get('GITHUB_ACTOR')=='martin830000-spec', 'UNAUTHORIZED_OR_REPLAY')
    control=json.loads((pathlib.Path(__file__).resolve().parent/'CONTROL.json').read_bytes())
    from google.cloud import storage
    bucket=storage.Client(project='gen-lang-client-0422436907').bucket('lao-translator-src-460077888071')
    def get(name):
        return bucket.blob(name).download_as_bytes(timeout=30,retry=None)
    result=check_state(get,control)
    print('PROTECTED_STATE_RECHECK='+json.dumps(result,sort_keys=True),flush=True)

if __name__=='__main__':
    try:
        main()
    except Exception as exc:
        value=str(exc) if isinstance(exc,AssertionError) else ''
        code=value if value and all(c in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_' for c in value) else type(exc).__name__
        print('PROTECTED_STATE_RECHECK='+json.dumps({'status':'FAIL','generation_calls':0,
              'gcs_writes':0,'openai_requests':0,'api_key_reads':0,'code':code},sort_keys=True),flush=True)
        raise SystemExit(1)
