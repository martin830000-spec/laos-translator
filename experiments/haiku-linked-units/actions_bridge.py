"""Prepared encrypted Actions bridge; false approval denies before any network/key access."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parent
def load(name,path):
    s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
c=load('la1_bridge_campaign',ROOT/'campaign.py')
b=load('la1_reused_crypto',ROOT.parent/'s47-realuse16/run.py')
b.TITLE='WORK_LA1_REAL16_AB40_20261031_APPROVED_V1'
b.PROTOCOL='la1-real16-ab40-v1'
b.TAG='la1-real16-ab40-20261031-consumed-v1'

def approval_guard():
    approval=b.read(ROOT/'approval.json')
    if approval.get('authorized') is not True or approval.get('plan_id')!=c.PLAN_ID or approval.get('maximum_new_attempts')!=40 or not approval.get('manifest_sha256'):
        raise PermissionError('New A/B40 not approved; zero probes/generation')
    return approval

def execute(state):
    # This line precedes state/key reads, HTTP, GitHub authentication and model probes.
    approval=approval_guard()
    h,init=b.read(state/'handshake.json'),b.read(state/'init.json')
    b.check(os.environ['GITHUB_RUN_ATTEMPT']=='1' and h['commit']==os.environ['GITHUB_SHA'] and str(h['run_id'])==os.environ['GITHUB_RUN_ID'])
    persist=lambda data:b.write(state/'sealed-result.json',b.seal(dict(data,execution={k:h[k] for k in ('run_id','issue_number','commit')}),init['result_public_key'],b.aad_for(h,'result')))
    try:
        metadata=b.request_json('https://api.anthropic.com/v1/models/claude-haiku-5-5',
            {'x-api-key':os.environ['ANTHROPIC_API_KEY'],'anthropic-version':'2023-06-01'},timeout=30)
        b.check(metadata['id']=='claude-haiku-5-5')
        until=time.monotonic()+900;manifest=None
        while time.monotonic()<until:
            issue=b.github('/repos/'+b.REPO+'/issues/'+str(h['issue_number']))
            b.check(issue['title']==b.TITLE and issue['user']['login']==b.OWNER and issue['state']=='open')
            body=json.loads(issue['body']);b.check(body['nonce']==init['nonce'] and body['result_public_key']==init['result_public_key'])
            if body['phase']=='sealed':
                value=b.unseal(body['envelope'],state/'input-private.pem',b.aad_for(h,'input'))
                b.check(set(value)=={'manifest'});manifest=value['manifest'];break
            b.check(body['phase']=='init');time.sleep(5)
        b.check(manifest is not None)
        c.validate(manifest)
        b.check(c.a.digest(manifest)==approval['manifest_sha256'])
        # New campaign only, no completed-experiment tag is deleted or moved.
        b.github('/repos/'+b.REPO+'/git/refs',{'ref':'refs/tags/'+b.TAG,'sha':h['commit']})
        state_data=c.run_approved(manifest,approval,b.live,state/'new-ab40-once.journal',persist)
        print(json.dumps({k:state_data[k] for k in ('plan_id','status','attempts','retries')}),flush=True)
    except Exception as exc:
        if not (state/'sealed-result.json').exists():persist({'status':'GLOBAL_PREFLIGHT_STOP','attempts':0,'error_type':type(exc).__name__})
        raise

def main():
    mode=sys.argv[1];state=Path(sys.argv[2])
    if mode=='prepare':b.prepare(state)
    elif mode=='execute':execute(state)
    elif mode=='client-init':b.client_init(state)
    elif mode=='client-seal':
        init=b.read(state/'init.json');h=b.read(sys.argv[3]);manifest=b.read(sys.argv[4])
        c.validate(manifest)
        b.check(h['nonce']==init['nonce'] and h['result_key_sha256']==hashlib.sha256(init['result_public_key'].encode()).hexdigest())
        b.check(h['commit']==sys.argv[5] and str(h['run_id'])==sys.argv[6] and str(h['issue_number'])==sys.argv[7])
        body=dict(init,phase='sealed',envelope=b.seal({'manifest':manifest},h['input_public_key'],b.aad_for(h,'input')))
        b.check(len(json.dumps(body))<64000)
        b.write(state/'handshake.json',h);b.write(state/'sealed-issue-body.json',body)
        print('Approved-manifest transport prepared locally; no API calls')
    elif mode=='client-decrypt':
        h=b.read(state/'handshake.json');data=b.unseal(b.read(sys.argv[3]),state/'result-private.pem',b.aad_for(h,'result'))
        b.write(state/'decrypted-result-private.json',data);print('Result decrypted locally')
    else:raise ValueError()

if __name__=='__main__':
    try:main()
    except Exception as exc:print('LA1 STOP '+type(exc).__name__,flush=True);sys.exit(2)
