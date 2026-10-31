"""Reuse tested authenticated encryption/HTTP; new SA1 locks and exact approval."""
import base64
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import time
import zlib
ROOT=Path(__file__).resolve().parent
def load(name,path):
    s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
c=load('sa1_campaign',ROOT/'campaign.py')
b=load('sa1_reused_crypto',ROOT.parent/'s47-realuse16/run.py')
b.TITLE='WORK_HAIKU_LA1_LB1_NORMAL8_AB32_20261101_APPROVED_V1'
b.PROTOCOL='haiku-lb1-normal32-v1'
b.TAG='haiku-lb1-normal32-20261101-consumed-v1'
b.load_adapter=lambda:c.a

def approval_guard():
    approval=b.read(ROOT/'approval.json');c.authorize(approval);return approval

def pack(manifest):
    return {'zlib_manifest_b64':base64.b64encode(zlib.compress(b.canonical(manifest),9)).decode('ascii')}

def unpack(value):
    b.check(set(value)=={'zlib_manifest_b64'})
    compressed=base64.b64decode(value['zlib_manifest_b64'],validate=True)
    b.check(len(compressed)<64000)
    dec=zlib.decompressobj();plain=dec.decompress(compressed,600001)
    b.check(len(plain)<=600000 and dec.eof and not dec.unused_data)
    manifest=json.loads(plain);c.validate(manifest);return manifest

def execute(state):
    approval=approval_guard()  # before keys, authentication or HTTP
    h,init=b.read(state/'handshake.json'),b.read(state/'init.json')
    b.check(os.environ['GITHUB_RUN_ATTEMPT']=='1' and h['commit']==os.environ['GITHUB_SHA'] and str(h['run_id'])==os.environ['GITHUB_RUN_ID'])
    persist=lambda d:b.write(state/'sealed-result.json',b.seal(dict(d,execution={k:h[k] for k in ['run_id','issue_number','commit']}),init['result_public_key'],b.aad_for(h,'result')))
    try:
        until=time.monotonic()+900;manifest=None
        while time.monotonic()<until:
            issue=b.github('/repos/'+b.REPO+'/issues/'+str(h['issue_number']))
            b.check(issue['title']==b.TITLE and issue['user']['login']==b.OWNER and issue['state']=='open')
            body=json.loads(issue['body']);b.check(body['nonce']==init['nonce'] and body['result_public_key']==init['result_public_key'])
            if body['phase']=='sealed':
                manifest=unpack(b.unseal(body['envelope'],state/'input-private.pem',b.aad_for(h,'input')));break
            b.check(body['phase']=='init');time.sleep(5)
        b.check(manifest is not None)
        # No model metadata/auth probe: only the approved /messages calls.
        b.github('/repos/'+b.REPO+'/git/refs',{'ref':'refs/tags/'+b.TAG,'sha':h['commit']})
        data=c.run_approved(manifest,approval,b.live,state/'haiku-lb1-normal-once.journal',persist)
        print(json.dumps({k:data[k] for k in ['plan_id','status','attempts','retries']}),flush=True)
    except Exception as exc:
        if not (state/'sealed-result.json').exists():persist({'status':'GLOBAL_PREFLIGHT_STOP','attempts':0,'error_type':type(exc).__name__})
        raise

def main():
    mode=sys.argv[1];state=Path(sys.argv[2])
    if mode=='prepare':approval_guard();b.prepare(state)
    elif mode=='execute':execute(state)
    elif mode=='client-init':b.client_init(state)
    elif mode=='client-seal':
        init=b.read(state/'init.json');h=b.read(sys.argv[3]);manifest=b.read(sys.argv[4]);c.validate(manifest)
        b.check(h['nonce']==init['nonce'] and h['result_key_sha256']==hashlib.sha256(init['result_public_key'].encode()).hexdigest())
        b.check(h['commit']==sys.argv[5] and str(h['run_id'])==sys.argv[6] and str(h['issue_number'])==sys.argv[7])
        body=dict(init,phase='sealed',envelope=b.seal(pack(manifest),h['input_public_key'],b.aad_for(h,'input')))
        b.check(len(json.dumps(body))<64000)
        b.write(state/'handshake.json',h);b.write(state/'sealed-issue-body.json',body)
        print('Frozen approved manifest sealed; no model calls')
    elif mode=='client-decrypt':
        h=b.read(state/'handshake.json');data=b.unseal(b.read(sys.argv[3]),state/'result-private.pem',b.aad_for(h,'result'))
        b.write(state/'decrypted-result-private.json',data);print('Result decrypted locally')
    else:raise ValueError('Unknown mode')
if __name__=='__main__':
    try:main()
    except Exception as exc:print('HAIKU_LB32 STOP '+type(exc).__name__,flush=True);sys.exit(2)
