"""One approved private real12 S47/SC1 comparison; reuse established crypto only."""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import time

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent
def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value

b = module('existing_private16_crypto', ROOT.parent/'s47-realuse16/run.py')
C = b.read(ROOT/'experiment.json')
b.TITLE, b.PROTOCOL, b.TAG = C['title'], C['protocol'], C['tag']
a = module('frozen_sc1_real48', ROOT.parent/'haiku-script-contract/adapter.py')

def validate(cases):
    b.check(b.digest(cases) == C['cases_sha256'] and len(cases) == 12)
    b.check(len({c['id'] for c in cases}) == 12)
    for side in ('K','L'):
        for group, count in (('ordinary',4),('risk',2)):
            b.check(sum(c['side']==side and c['group']==group for c in cases)==count)
    for c in cases:
        b.check(set(c)=={'id','side','group','source'} and isinstance(c['source'],str) and c['source'].strip())

class Controller:
    def __init__(self, cases, persist):
        validate(cases)
        self.persist = persist
        self.used = False
        self.data = dict(status='READY', attempts=0, responses=0, retries=0,
            gemini_calls=0, judge_calls=0, max_attempts=48, cases=cases,
            config=C, records=[], counts={v:{s:0 for s in ('first','back')} for v in ('S47','SC1')},
            estimated_usd=0.0, actual_invoice='UNVERIFIED', ui_latency='NOT_MEASURED')

    def call(self, case, variant, stage, visible, transport):
        d = self.data
        b.check(d['attempts'] < 48 and d['counts'][variant][stage] < 12)
        q = a.build_request(visible, case['side'], stage, variant)
        b.check(q['model']==C['model'] and q['max_tokens']==2048 and q['thinking']=={'type':'disabled'} and q['output_config']['effort']=='low')
        d['attempts'] += 1
        d['counts'][variant][stage] += 1
        rec = dict(attempt=d['attempts'], record_id=case['id'], variant=variant,
            side=case['side'], stage=stage, input=visible, payload=q, payload_sha256=b.digest(q),
            system_sha256=hashlib.sha256(q['system'].encode()).hexdigest(),
            schema_sha256=b.digest(q['output_config']['format']['schema']), status='SENT_OR_UNKNOWN')
        d['records'].append(rec)
        self.persist(d)  # durable encrypted journal BEFORE every possible transmission
        started = time.perf_counter()
        try:
            raw = transport(q)
            rec['api_ms'] = round((time.perf_counter()-started)*1000,3)
            rec['response'] = raw
            if raw.get('type')=='message': d['responses'] += 1
            rec['usage'] = raw.get('usage',{})
            rec['estimated_usd'] = b.cost(rec['usage'])
            d['estimated_usd'] += rec['estimated_usd']
            b.check(raw.get('model')==C['model'])
            result = a.inspect_response(raw,case['side'],stage)
            rec.update(result)
            rec['status']='SUCCESS'
            return result['translation']
        except Exception as exc:
            rec['error_type']=type(exc).__name__
            rec['status']='STOP_TECHNICAL_OR_UNKNOWN'
            d['status']='HOLD_TECHNICAL_OR_UNKNOWN'
            raise
        finally:
            rec.setdefault('api_ms',round((time.perf_counter()-started)*1000,3))
            self.persist(d)

    def run(self, transport):
        b.check(not self.used)
        self.used=True
        self.data['status']='RUNNING'
        try:
            for index, case in enumerate(self.data['cases']):
                order=('S47','SC1') if index%2==0 else ('SC1','S47')
                for variant in order:
                    first=self.call(case,variant,'first',case['source'],transport)
                    # Only this candidate's actual visible output crosses the BACK boundary.
                    self.call(case,variant,'back',first,transport)
            b.check(self.data['attempts']==48)
            self.data['status']='COMPLETE_SEMANTIC_REVIEW_REQUIRED'
        finally:
            self.persist(self.data)
        return self.data

def execute(state):
    h, init = b.read(state/'handshake.json'), b.read(state/'init.json')
    b.check(os.environ['GITHUB_RUN_ATTEMPT']=='1' and h['commit']==os.environ['GITHUB_SHA'])
    b.check(str(h['run_id'])==os.environ['GITHUB_RUN_ID'])
    persist=lambda d:b.write(state/'sealed-result.json',b.seal(d,init['result_public_key'],b.aad_for(h,'result')))
    controller=None
    try:
        b.check(bool(os.environ.get('ANTHROPIC_API_KEY')))
        metadata=b.request_json('https://api.anthropic.com/v1/models/'+C['model'],
            {'x-api-key':os.environ['ANTHROPIC_API_KEY'],'anthropic-version':'2023-06-01'},timeout=30)
        b.check(metadata['id']==C['model'])
        print('Current authentication/model access verified; generation attempts 0',flush=True)
        until=time.monotonic()+900
        cases=None
        while time.monotonic()<until:
            issue=b.github('/repos/'+b.REPO+'/issues/'+str(h['issue_number']))
            b.check(issue['title']==b.TITLE and issue['user']['login']==b.OWNER and issue['state']=='open')
            body=json.loads(issue['body'])
            b.check(body['nonce']==init['nonce'] and body['result_public_key']==init['result_public_key'])
            if body['phase']=='sealed':
                value=b.unseal(body['envelope'],state/'input-private.pem',b.aad_for(h,'input'))
                b.check(set(value)=={'cases'})
                cases=value['cases'];validate(cases);break
            b.check(body['phase']=='init')
            time.sleep(5)
        b.check(cases is not None)
        # Atomic tag creation fails closed if already present; no previous locks touched.
        b.github('/repos/'+b.REPO+'/git/refs',{'ref':'refs/tags/'+C['tag'],'sha':h['commit']})
        with (state/'started.lock').open('x') as f:f.write(str(h['run_id']))
        controller=Controller(cases,persist)
        controller.data['model_metadata']=metadata
        controller.data['github']={k:h[k] for k in ('run_id','issue_number','commit')}
        controller.run(b.live)
    except Exception as exc:
        if controller is None:
            persist(dict(status='HOLD_PREFLIGHT_NO_GENERATIONS',attempts=0,responses=0,error_type=type(exc).__name__))
        raise
    finally:
        if controller is not None:
            d=controller.data
            print(json.dumps({k:d[k] for k in ('status','attempts','responses','retries','counts','estimated_usd')}),flush=True)

def main():
    mode=sys.argv[1];state=Path(sys.argv[2])
    if mode=='prepare':b.prepare(state)
    elif mode=='execute':execute(state)
    elif mode=='client-init':b.client_init(state)
    elif mode=='client-seal':
        init=b.read(state/'init.json');h=b.read(sys.argv[3]);cases=b.read(sys.argv[4])
        b.check(h['nonce']==init['nonce'] and h['result_key_sha256']==hashlib.sha256(init['result_public_key'].encode()).hexdigest())
        b.check(h['commit']==sys.argv[5] and str(h['run_id'])==sys.argv[6] and str(h['issue_number'])==sys.argv[7])
        validate(cases)
        b.write(state/'handshake.json',h)
        b.write(state/'sealed-issue-body.json',dict(init,phase='sealed',envelope=b.seal({'cases':cases},h['input_public_key'],b.aad_for(h,'input'))))
        print('Encrypted real12 input prepared; generation attempts 0')
    elif mode=='client-decrypt':
        h=b.read(state/'handshake.json')
        b.write(state/'decrypted-result.json',b.unseal(b.read(sys.argv[3]),state/'result-private.pem',b.aad_for(h,'result')))
        print('Result decrypted locally; generation attempts 0')
    else:raise ValueError()

if __name__=='__main__':
    try:main()
    except Exception as exc:
        print('REAL48 HOLD '+type(exc).__name__,flush=True)
        sys.exit(2)
