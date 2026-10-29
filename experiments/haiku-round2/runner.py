"""TEST research controller. Default offline. No retries, repair calls or AI judge.

Paid transport is gated on explicit scoped approval; committed approval stays off.
The injected transport boundary supports free, hostile-condition verification.
"""
import csv, hashlib, importlib.util, json, os, time, urllib.request, urllib.error
from pathlib import Path
ROOT=Path(__file__).parent
spec=importlib.util.spec_from_file_location('prior_adapter',ROOT.parent/'haiku-50-steps'/'adapter.py')
adapter=importlib.util.module_from_spec(spec);spec.loader.exec_module(adapter)
PATHS=('K_first','K_back','L_first','L_back')
MAX_CALLS=800
MAX_STEPS=50
def digest(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
def check(ok, why):
    if not ok: raise ValueError(why)
def validate(cases,variants):
    check(len(cases)>0 and len(cases)%2==0,'balanced K/L required')
    check(sum(c['side']=='K' for c in cases)==len(cases)//2 and all(c['side'] in ('K','L') for c in cases),'balanced K/L required')
    check(len({c['id'] for c in cases})==len(cases),'duplicate case id')
    check(len({c['source'] for c in cases})==len(cases),'duplicate source')
    check(all(c['source'].strip() for c in cases),'empty source')
    check(0<len(variants)<=MAX_STEPS,'step limit')
    check(len({v['id'] for v in variants})==len(variants),'duplicate variant')
    check(all(v.get('hypothesis') for v in variants),'no hypothesis: STOP')
    check(len(cases)*len(variants)*2<=MAX_CALLS,'call cap')
def decision(reviews, no_gain_rounds=0, hypotheses_left=True):
    """Reviewed paired deltas per path; never turn unknown/partial data into PASS."""
    if not hypotheses_left: return 'STOP_NO_HYPOTHESIS'
    if set(reviews)!=set(PATHS): return 'HOLD_INCOMPLETE_FOUR_PATH_REVIEW'
    if any(not r.get('complete') or r.get('uncertain',True) for r in reviews.values()):
        return 'HOLD_REVIEW_REQUIRED'
    if any(r['new_p0']>0 for r in reviews.values()): return 'REJECT_NEW_P0'
    if any(r['p0_delta']>0 or r['p1_delta']>0 for r in reviews.values()): return 'REJECT_PATH_REGRESSION'
    improved=any(r['p0_delta']<0 or r['p1_delta']<0 for r in reviews.values())
    if not improved and no_gain_rounds>=1: return 'STOP_TWO_ROUNDS_NO_GAIN'
    return 'ADVANCE_TO_FROZEN_HOLDOUT' if improved else 'HOLD_NO_GAIN'
class Campaign:
    def __init__(self, directory, approved=False, approval_reference=None, cap=MAX_CALLS):
        self.root=Path(directory);self.root.mkdir(parents=True,exist_ok=True)
        check(type(cap) is int and 0<cap<=MAX_CALLS,'invalid cap')
        self.approved=approved;self.reference=approval_reference;self.cap=cap
    def append(self,event):
        with (self.root/'events.jsonl').open('a',encoding='utf-8') as f:
            f.write(json.dumps(event,ensure_ascii=False)+'\n');f.flush();os.fsync(f.fileno())
    def history(self):
        p=self.root/'events.jsonl'
        return [json.loads(x) for x in p.read_text(encoding='utf-8').splitlines()] if p.exists() else []
    def run(self,cases,variants,transport,simulation=False):
        validate(cases,variants)
        check(simulation or (self.approved and self.reference),'PAID_APPROVAL_REQUIRED')
        # Exclusive permanent campaign lock: reruns/crashes cannot silently restart spending.
        with (self.root/'started.lock').open('x',encoding='utf-8') as f:
            f.write(json.dumps({'approval':self.reference,'simulation':simulation,'cap':self.cap}))
        history=self.history();calls=sum(e['event']=='attempt' for e in history)
        check(calls+len(cases)*len(variants)*2<=self.cap,'campaign budget insufficient')
        results=[]
        for i,c in enumerate(cases):
            # Rotate arm order to avoid consistently putting the control first.
            order=variants[i%len(variants):]+variants[:i%len(variants)]
            for v in order:
                first=None
                for stage in ('first','back'):
                    visible=c['source'] if stage=='first' else first
                    q=adapter.payload(visible,c['side'],stage,v)
                    key={'case':c['id'],'variant':v['id'],'path':c['side']+'_'+stage}
                    check(calls<self.cap,'campaign call cap reached')
                    calls+=1
                    self.append(dict(event='attempt',attempt=calls,**key,input=visible,payload=q,
                                     payload_sha256=digest(q),settings=v,simulation=simulation))
                    start=time.perf_counter()
                    try:
                        response=transport(q)
                        # Raw response persists even on extraction failure.
                        self.append(dict(event='response',attempt=calls,**key,response=response))
                        translated=adapter.extract_translation(response)
                    except Exception as exc:
                        self.append(dict(event='STOP_TECHNICAL_ERROR',attempt=calls,**key,error_type=type(exc).__name__))
                        raise  # no retry, no hidden BACK, preserve partial records
                    row=dict(**key,source=c['source'],input=visible,translation=translated,
                             hypothesis=v['hypothesis'],payload_sha256=digest(q),attempt=calls,
                             ms=round((time.perf_counter()-start)*1000),usage=response.get('usage',{}),
                             estimated_usd=None,price_status='NOT_REVERIFIED',severity='UNREVIEWED',
                             regression='UNREVIEWED',simulation=simulation)
                    results.append(row);self.append(dict(event='result',**row))
                    if stage=='first': first=translated
        with (self.root/'results.csv').open('w',encoding='utf-8',newline='') as f:
            w=csv.DictWriter(f,fieldnames=results[0]);w.writeheader();w.writerows(results)
        self.append({'event':'HOLD_REVIEW_REQUIRED','calls':calls})
        return results
def live_transport(q):
    """One request, bounded timeout, no retries; call only behind paid_main approval gate."""
    request=urllib.request.Request('https://api.anthropic.com/v1/messages',
        data=json.dumps(q,ensure_ascii=False).encode(),headers={
        'x-api-key':os.environ['ANTHROPIC_API_KEY'],'anthropic-version':'2023-06-01',
        'content-type':'application/json'})
    try:
        with urllib.request.urlopen(request,timeout=90) as response:return json.loads(response.read())
    except urllib.error.HTTPError as e:
        # API error response is preserved through the normal raw-response journal.
        return {'stop_reason':'http_error','http_status':e.code,
                'error_body':e.read(65536).decode('utf-8',errors='replace')}
def paid_main():
    approval=json.loads((ROOT/'approval.json').read_text(encoding='utf-8'))
    check(approval.get('approved') is True and approval.get('user_approval_reference'), 'PAID_APPROVAL_REQUIRED')
    check(approval.get('batch')=='initial128','only initial reviewed plan is implemented')
    check(approval.get('max_calls')==128,'approval must bind initial128')
    check(approval.get('candidate_sha256')==digest(json.loads((ROOT/'candidates.json').read_text(encoding='utf-8'))),'candidate approval mismatch')
    check(approval.get('model_verified') is True,'verify model metadata before paid run')
    cases=json.loads((ROOT/'development.json').read_text(encoding='utf-8'))
    variants=json.loads((ROOT/'candidates.json').read_text(encoding='utf-8'))
    check(approval.get('cases_sha256')==digest(cases),'case approval mismatch')
    check(os.getenv('ANTHROPIC_API_KEY'),'API key missing')
    return Campaign(ROOT/'paid-output',approved=True,
        approval_reference=approval['user_approval_reference'],cap=128).run(cases,variants,live_transport)
if __name__=='__main__':
    import sys
    if '--paid' in sys.argv:
        paid_main();raise SystemExit(0)
    variants=json.loads((ROOT/'candidates.json').read_text(encoding='utf-8'))
    cases=json.loads((ROOT/'development.json').read_text(encoding='utf-8'))
    validate(cases,variants)
    print(f'OFFLINE PASS: {len(cases)} sources, {len(variants)} arms, {2*len(cases)*len(variants)} proposed calls; actual paid calls 0')

