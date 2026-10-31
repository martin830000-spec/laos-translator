"""Resume only unattempted real48 slots; per-request errors never retry."""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import time

sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('original_real48',ROOT.parent/'s47-sc1-real48/run.py')
r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)
b,a=r.b,r.a
C=b.read(ROOT/'resume.json')
b.TITLE,b.PROTOCOL,b.TAG=C['title'],C['protocol'],C['tag']

class GlobalStop(Exception): pass

def plan(cases):
    slots=[]
    for i,case in enumerate(cases):
        order=('S47','SC1') if i%2==0 else ('SC1','S47')
        for variant in order:
            for stage in ('first','back'):
                slots.append(dict(slot=len(slots)+1,record_id=case['id'],side=case['side'],variant=variant,stage=stage))
    return slots

def diagnostics(raw):
    stop=raw.get('stop_reason')
    return dict(http_status=raw.get('http_status',200 if raw.get('type')=='message' else None),
        stop_reason=stop,max_tokens=stop=='max_tokens',response_complete=stop=='end_turn',
        response_sha256=b.digest(raw),response_id=raw.get('id'),
        json_validation='NOT_ATTEMPTED_INCOMPLETE' if stop!='end_turn' else 'PENDING',
        schema_validation='NOT_ATTEMPTED',usage=raw.get('usage',{}))

def inspect(raw,side,stage):
    # Keep the frozen extractor and never pick a JSON fragment out of commentary.
    result=a.inspect_response(raw,side,stage)
    obj=json.loads(''.join(x.get('text','') for x in raw.get('content',[]) if x.get('type')=='text'))
    if not isinstance(obj,dict) or set(obj)!={'source_people','source_events','translation'}:
        raise ValueError('SCHEMA_ROOT_KEYS')
    if any(not isinstance(obj[k],list) or any(not isinstance(v,str) for v in obj[k]) for k in ('source_people','source_events')):
        raise ValueError('SCHEMA_FACT_ARRAY_TYPE')
    return result

def failure_info(exc,raw):
    if raw.get('stop_reason')=='max_tokens': reason='MAX_TOKENS_INCOMPLETE_RESPONSE'
    elif raw.get('http_status'): reason='HTTP_'+str(raw['http_status'])
    elif isinstance(exc,json.JSONDecodeError): reason='JSON_PARSE_'+exc.msg+'_POSITION_'+str(exc.pos)
    elif raw.get('stop_reason')!='end_turn' and raw: reason='INCOMPLETE_STOP_'+str(raw.get('stop_reason'))
    elif isinstance(exc,ValueError) and str(exc).startswith('SCHEMA_'): reason=str(exc)
    elif isinstance(exc,TimeoutError): reason='TIMEOUT_SENT_OR_UNKNOWN_NO_RETRY'
    elif not raw: reason='TRANSPORT_'+type(exc).__name__+'_NO_RETRY'
    else: reason='EXTRACTION_'+type(exc).__name__
    return dict(reason=reason,exception_type=type(exc).__name__)

def validate(cases,prior):
    r.validate(cases)
    b.check(b.digest(cases)==C['cases_sha256'] and b.digest(prior)==C['prior_digest'])
    b.check(prior['attempts']==3 and len(prior['records'])==3 and prior['retries']==0)
    b.check(prior['github']['commit']==C['prior_commit'] and str(prior['github']['run_id'])==C['prior_run_id'])
    slots=plan(cases)
    for slot,record in zip(slots,prior['records']):
        b.check(all(slot[k]==record[k] for k in ('record_id','side','variant','stage')))
        case=next(c for c in cases if c['id']==slot['record_id'])
        visible=case['source'] if slot['stage']=='first' else prior['records'][0]['translation']
        q=a.build_request(visible,slot['side'],slot['stage'],slot['variant'])
        b.check(q==record['payload'] and b.digest(q)==record['payload_sha256'])
    b.check(prior['records'][0]['status']=='SUCCESS' and prior['records'][1]['status']=='SUCCESS')
    b.check(prior['records'][2]['response']['stop_reason']=='max_tokens' and 'translation' not in prior['records'][2])
    return slots

class Controller:
    def __init__(self,cases,prior,persist):
        self.cases=cases
        self.prior=prior
        self.persist=persist
        self.used=False
        slots=validate(cases,prior)
        for slot in slots:slot['status']='PENDING'
        for slot,old in zip(slots,prior['records']):
            slot.update(copy.deepcopy(old))
            slot['slot']=prior['records'].index(old)+1
            slot['origin']='PRIOR_REUSED'
            slot['status']='SUCCESS' if old['status']=='SUCCESS' else 'FAILED'
            slot.update(diagnostics(old['response']))
            slot['json_validation']='VALID' if slot['status']=='SUCCESS' else 'NOT_ATTEMPTED_INCOMPLETE'
            slot['schema_validation']='VALID' if slot['status']=='SUCCESS' else 'NOT_ATTEMPTED'
            slot['raw_response_location']='raw-result-prior.json#/records/'+str(slot['slot']-1)+'/response'
            slot['next_planned_slot']=slot['slot']+1
            if slot['status']=='FAILED':slot.update(failure_info(ValueError(),old['response']))
        self.data=dict(status='READY',cases=cases,config=C,prior_attempts=3,new_attempts=0,total_attempts=3,
            new_message_responses=0,retries=0,gemini_calls=0,judge_calls=0,slots=slots,
            estimated_usd=prior['estimated_usd'],actual_invoice='UNVERIFIED',ui_latency='NOT_MEASURED')

    def call(self,slot,visible,transport):
        d=self.data
        b.check(slot['status']=='PENDING' and slot['slot']>4)
        if d['new_attempts']>=44 or d['total_attempts']>=48: raise GlobalStop('CALL_CAP')
        q=a.build_request(visible,slot['side'],slot['stage'],slot['variant'])
        b.check(q['model']=='claude-haiku-5-5' and q['max_tokens']==2048 and q['thinking']=={'type':'disabled'} and q['output_config']['effort']=='low')
        d['new_attempts']+=1;d['total_attempts']+=1
        slot.update(origin='RESUME_NEW',status='SENT_OR_UNKNOWN',attempt=d['total_attempts'],
            new_attempt=d['new_attempts'],input=visible,payload=q,payload_sha256=b.digest(q),
            system_sha256=hashlib.sha256(q['system'].encode()).hexdigest(),
            schema_sha256=b.digest(q['output_config']['format']['schema']),
            next_planned_slot=slot['slot']+1 if slot['slot']<48 else None,
            raw_response_location='merged-result-private.json#/slots/'+str(slot['slot']-1)+'/response')
        self.persist(d)  # failure here is global: never send without durable journal
        slot.update(diagnostics({}))
        raw={};started=time.perf_counter();fatal=None
        try:
            raw=transport(q)
            slot['api_ms']=round((time.perf_counter()-started)*1000,3)
            slot['response']=raw;slot.update(diagnostics(raw))
            if raw.get('type')=='message':d['new_message_responses']+=1
            slot['estimated_usd']=b.cost(slot['usage'])
            d['estimated_usd']+=slot['estimated_usd']
            if raw.get('http_status') in (401,403):raise GlobalStop('GLOBAL_AUTHENTICATION_FAILURE')
            if raw.get('type')=='message' and raw.get('model')!='claude-haiku-5-5':raise GlobalStop('MODEL_ID_INTEGRITY')
            result=inspect(raw,slot['side'],slot['stage'])
            slot.update(result,status='SUCCESS',json_validation='VALID',schema_validation='VALID')
        except GlobalStop as exc:
            fatal=exc;slot.update(status='FAILED',reason=str(exc),exception_type=type(exc).__name__)
        except Exception as exc:
            slot.update(status='FAILED',**failure_info(exc,raw))
            if isinstance(exc,json.JSONDecodeError):slot['json_validation']='INVALID_WHOLE_RESPONSE'
            elif slot.get('reason','').startswith('SCHEMA_'):slot['schema_validation']='INVALID'
        finally:
            slot.setdefault('api_ms',round((time.perf_counter()-started)*1000,3))
            slot.setdefault('usage',{})
            slot.setdefault('estimated_usd',None)
            self.persist(d)
        if fatal:raise fatal

    def run(self,transport):
        b.check(not self.used);self.used=True
        d=self.data;d['status']='RUNNING'
        try:
            for slot in d['slots']:
                if slot['status'] in ('SUCCESS','FAILED','SKIPPED_DEPENDENCY'):continue
                if slot['status']!='PENDING':raise GlobalStop('UNCERTAIN_EXISTING_ATTEMPT')
                if slot['stage']=='back':
                    first=d['slots'][slot['slot']-2]
                    b.check(first['record_id']==slot['record_id'] and first['variant']==slot['variant'] and first['stage']=='first')
                    if first['status']!='SUCCESS':
                        slot.update(status='SKIPPED_DEPENDENCY',origin='DEPENDENCY',reason='FIRST_SLOT_'+str(first['slot'])+'_FAILED',
                            attempts=0,api_ms=None,usage={},estimated_usd=0,next_planned_slot=slot['slot']+1 if slot['slot']<48 else None)
                        self.persist(d);continue
                    visible=first['translation']
                else:visible=next(c for c in self.cases if c['id']==slot['record_id'])['source']
                self.call(slot,visible,transport)
                print(json.dumps({'slot':slot['slot'],'status':slot['status'],'total_attempts':d['total_attempts']}),flush=True)
            b.check(len(d['slots'])==48 and all(s['status'] in ('SUCCESS','FAILED','SKIPPED_DEPENDENCY') for s in d['slots']))
            d['status']='PROCEDURE_COMPLETE_SEMANTIC_REVIEW_REQUIRED'
        except Exception:
            d['status']='STOP_GLOBAL_SAFETY_OR_JOURNAL';raise
        finally:self.persist(d)
        return d

def execute(state):
    h,init=b.read(state/'handshake.json'),b.read(state/'init.json')
    b.check(os.environ['GITHUB_RUN_ATTEMPT']=='1' and h['commit']==os.environ['GITHUB_SHA'] and str(h['run_id'])==os.environ['GITHUB_RUN_ID'])
    persist=lambda d:b.write(state/'sealed-result.json',b.seal(d,init['result_public_key'],b.aad_for(h,'result')))
    controller=None
    try:
        metadata=b.request_json('https://api.anthropic.com/v1/models/claude-haiku-5-5',
            {'x-api-key':os.environ['ANTHROPIC_API_KEY'],'anthropic-version':'2023-06-01'},timeout=30)
        b.check(metadata['id']=='claude-haiku-5-5')
        oldtag=b.github('/repos/'+b.REPO+'/git/ref/tags/'+C['prior_tag'])
        b.check(oldtag['object']['sha']==C['prior_commit'])
        print('Authentication and existing consumed tag verified; old requests will not be sent',flush=True)
        until=time.monotonic()+900;value=None
        while time.monotonic()<until:
            issue=b.github('/repos/'+b.REPO+'/issues/'+str(h['issue_number']))
            b.check(issue['title']==b.TITLE and issue['user']['login']==b.OWNER and issue['state']=='open')
            body=json.loads(issue['body']);b.check(body['nonce']==init['nonce'] and body['result_public_key']==init['result_public_key'])
            if body['phase']=='sealed':
                value=b.unseal(body['envelope'],state/'input-private.pem',b.aad_for(h,'input'));break
            b.check(body['phase']=='init');time.sleep(5)
        b.check(value is not None and set(value)=={'cases','prior'})
        validate(value['cases'],value['prior'])
        b.github('/repos/'+b.REPO+'/git/refs',{'ref':'refs/tags/'+C['tag'],'sha':h['commit']})
        with (state/'started.lock').open('x') as f:f.write(str(h['run_id']))
        controller=Controller(value['cases'],value['prior'],persist)
        controller.data['model_metadata']=metadata
        controller.data['github']={k:h[k] for k in ('run_id','issue_number','commit')}
        controller.run(b.live)
    except Exception as exc:
        if controller is None:persist(dict(status='STOP_GLOBAL_PREFLIGHT',new_attempts=0,prior_attempts=3,error_type=type(exc).__name__))
        raise
    finally:
        if controller:
            d=controller.data
            print(json.dumps({k:d[k] for k in ('status','prior_attempts','new_attempts','total_attempts','retries','estimated_usd')}),flush=True)

def main():
    mode=sys.argv[1];state=Path(sys.argv[2])
    if mode=='prepare':b.prepare(state)
    elif mode=='execute':execute(state)
    elif mode=='client-init':b.client_init(state)
    elif mode=='client-seal':
        init=b.read(state/'init.json');h=b.read(sys.argv[3]);cases=b.read(sys.argv[4]);prior=b.read(sys.argv[5])
        validate(cases,prior)
        b.check(h['nonce']==init['nonce'] and h['result_key_sha256']==hashlib.sha256(init['result_public_key'].encode()).hexdigest())
        b.check(h['commit']==sys.argv[6] and str(h['run_id'])==sys.argv[7] and str(h['issue_number'])==sys.argv[8])
        b.write(state/'handshake.json',h)
        body=dict(init,phase='sealed',envelope=b.seal({'cases':cases,'prior':prior},h['input_public_key'],b.aad_for(h,'input')))
        b.check(len(json.dumps(body))<64000)
        b.write(state/'sealed-issue-body.json',body)
        print('Frozen cases and prior ledger encrypted; old attempts3 remain consumed')
    elif mode=='client-decrypt':
        h=b.read(state/'handshake.json')
        b.write(state/'merged-result-private.json',b.unseal(b.read(sys.argv[3]),state/'result-private.pem',b.aad_for(h,'result')))
        print('Merged ledger decrypted locally')
    else:raise ValueError()

if __name__=='__main__':
    try:main()
    except Exception as exc:
        print('RESUME GLOBAL STOP '+type(exc).__name__,flush=True);sys.exit(2)
