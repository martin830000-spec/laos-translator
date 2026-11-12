"""Read-only authority check after M1/G/D head-to-head CLOSE; no generation."""
import hashlib,json,os,pathlib

CAMPAIGN='GPT_LUNA_M1_GD_HEADTOHEAD80_20261112'
ROOT='research/gemini-model-native500-20261107/'
PREFIX=ROOT+'gpt-luna-m1-gd-headtohead80-20261112/'
PREVIOUS={'gpt-luna-p168a-transfer320-20261111':288,'gpt-luna-source-variant320-20261110':290,'gpt-source-vs-prompt-factorial320-20261111':264,'gpt-luna-lf-variance320-20261110':264,'gpt-luna-terra-mechanism1000-20261110':776}
def sha(b):return hashlib.sha256(b).hexdigest()
def require(ok,code):
    if not ok:raise AssertionError(code)
def check_state(get,control):
    require(control['campaign']==CAMPAIGN and control['approved_total']==80 and control['mode']=='CLOSE' and control['enabled'] is False and control['max_new']==0,'CLOSE_CONTROL')
    raw=get(PREFIX+'preflight/PREFLIGHT.json');require(sha(raw)==control['preflight_sha256'],'PREFLIGHT_SHA_CHANGED');p=json.loads(raw)
    require(p['campaign']==CAMPAIGN and p['generation_calls']==0 and p['owner_token']==control['owner_token'],'PREFLIGHT_IDENTITY')
    protected={}
    require(set(p['old_closed'])==set(PREVIOUS),'OLD_CAMPAIGN_SET')
    for name,count in PREVIOUS.items():
        data=get(ROOT+name+'/states/CLOSED_LOCKED.json');s=json.loads(data)
        require(sha(data)==p['old_closed'][name]['sha256'],'OLD_CLOSED_BYTES_CHANGED')
        require(s['status']=='CLOSED_LOCKED' and not s['enabled'] and s['max_new']==0 and s['reserved_total']==count,'OLD_CLOSED_STATE')
        dual=None
        if name!='gpt-luna-terra-mechanism1000-20261110':
            dual=get(ROOT+name+'/controls/CLOSED/CLOSED_LOCKED.json')==data;require(dual,'OLD_DUAL_AUTHORITY')
        protected[name]={'sha256':sha(data),'status':s['status'],'reserved_total':count,'dual_authority_bytes_equal':dual,'sha_equal_to_preflight':True}
    for name,status,count,unused,key in [('gpt-luna-gd-scope-screen80-20261112','PAUSED',0,80,'old_screen_sha256'),('gpt-luna-gd-realchat80-20261112','CLOSED',68,12,'old_realchat_sha256')]:
        data=get(ROOT+name+'/states/'+status+'_LOCKED.json');s=json.loads(data)
        require(sha(data)==p[key],'PROTECTED_RECENT_BYTES_CHANGED')
        require(get(ROOT+name+'/controls/'+status+'/'+status+'_LOCKED.json')==data,'PROTECTED_RECENT_DUAL_AUTHORITY')
        require(s['status']==status+'_LOCKED' and not s['enabled'] and s['max_new']==0 and s['reserved_total']==count and s['unused_locked']==unused,'PROTECTED_RECENT_COUNTS')
        protected[name]={'sha256':sha(data),'status':s['status'],'reserved_total':count,'unused_locked':unused,'enabled':False,'max_new':0,'dual_authority_bytes_equal':True,'sha_equal_to_preflight':True}
    freeze_raw=get(PREFIX+'preparation/FREEZE.json');require(sha(freeze_raw)==control['freeze_sha256'],'FREEZE_CHANGED');f=json.loads(freeze_raw)
    caps=f['stage_caps'];require(set(caps)=={'A','B','C'},'PHASE_SET');total=sum(caps.values())
    data=get(PREFIX+'states/CLOSED_LOCKED.json');s=json.loads(data)
    require(get(PREFIX+'controls/CLOSED/CLOSED_LOCKED.json')==data,'NEW_DUAL_AUTHORITY')
    require(s['campaign']==CAMPAIGN and s['status']=='CLOSED_LOCKED' and not s['enabled'] and s['max_new']==0 and s['approved_total']==80 and s['ledger_resolved'] is True and s['research_complete'] is True,'NEW_CLOSED_STATE')
    require(s['reserved_total']==s['success']==total and s['failed']==s['unknown']==0 and s['unused_locked']==80-total and s['owner_token']==p['owner_token'],'NEW_CLOSED_COUNTS')
    require(s['stage_caps']==caps and set(s['stage_counts'])==set(caps),'NEW_STAGE_SET')
    for phase,count in caps.items():
        row=s['stage_counts'][phase]
        require(row['reserved']==row['success']==row['transmitted_recorded']==count and row['failed']==row['unknown']==0,'NEW_STAGE_COUNTS')
    root_raw=get(PREFIX+'CONTROL.json');root=json.loads(root_raw)
    require(root['campaign']==CAMPAIGN and root['owner_token']==p['owner_token'] and root['status']=='PREFLIGHT_LOCKED' and not root['enabled'] and root['max_new']==0 and root['reserved_total']==root['actual']==0,'ROOT_INITIAL_SNAPSHOT_CHANGED')
    return {'campaign':CAMPAIGN,'status':'PASS','generation_calls':0,'gcs_writes':0,'openai_requests':0,'api_key_reads':0,'previous_campaigns':protected,'new_campaign_authority':{'objects':[PREFIX+'states/CLOSED_LOCKED.json',PREFIX+'controls/CLOSED/CLOSED_LOCKED.json'],'sha256':sha(data),'status':'CLOSED_LOCKED','enabled':False,'max_new':0,'reserved_total':total,'success':total,'failed':0,'unknown':0,'unused_locked':80-total,'stage_actual':caps,'dual_authority_bytes_equal':True},'historical_root_control':{'object':PREFIX+'CONTROL.json','sha256':sha(root_raw),'status':'PREFLIGHT_LOCKED','authority_status':'HISTORICAL_INITIAL_SNAPSHOT_NOT_FINAL_COUNTS'}}
def main():
    require(os.environ.get('GITHUB_REF')=='refs/heads/research/gemini-model-native500-20261107' and os.environ.get('GITHUB_RUN_ATTEMPT')=='1' and os.environ.get('GITHUB_ACTOR')=='martin830000-spec','UNAUTHORIZED_OR_REPLAY')
    control=json.loads((pathlib.Path(__file__).resolve().parent/'CONTROL.json').read_bytes())
    from google.cloud import storage
    b=storage.Client(project='gen-lang-client-0422436907').bucket('lao-translator-src-460077888071')
    result=check_state(lambda n:b.blob(n).download_as_bytes(timeout=30,retry=None),control)
    print('PROTECTED_STATE_RECHECK='+json.dumps(result,sort_keys=True),flush=True)
if __name__=='__main__':
    try:main()
    except Exception as e:
        v=str(e) if isinstance(e,AssertionError) else ''
        code=v if v and all(c in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_' for c in v) else type(e).__name__
        print('PROTECTED_STATE_RECHECK='+json.dumps({'status':'FAIL','generation_calls':0,'gcs_writes':0,'code':code}),flush=True)
        raise SystemExit(1)
