"""Approved Haiku LA1 setting-only 2x2 max72; phased36; no retries."""
import copy, hashlib, importlib.util, json, time, os, urllib.request, urllib.error
from pathlib import Path
ROOT=Path(__file__).resolve().parent
def load(n,p):
 s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
a=load('la1_adaptive_frozen',ROOT.parent/'haiku-linked-units/adapter.py')
CONFIG=json.loads((ROOT/'config.json').read_text())
digest=a.digest
def authorize(x):
 expected=dict(authorized=True,campaign_id='HAIKU_LA1_ADAPTIVE_BACK2X2_20261101',plan_id=CONFIG['plan_id'],maximum_new_attempts=36,whole_task_maximum=72,Haiku_maximum=72,other_models_maximum=0,manifest_sha256=CONFIG['manifest_sha256'])
 if x!=expected:raise PermissionError('Exact phase authorization required')
def schedule(cases):
 out=[]
 for c in cases:
  order=['A','B'] if (c['index']+(c['side']=='L'))%2==0 else ['B','A']
  for first_setting in order:
   n=len(out)+1;out.append(dict(slot=n,id=c['id'],side=c['side'],stage='first',first_setting=first_setting,setting=first_setting,depends_on=None))
   for setting in order:out.append(dict(slot=len(out)+1,id=c['id'],side=c['side'],stage='back',first_setting=first_setting,setting=setting,depends_on=n))
 return out
def build(text,side,stage,setting):
 if setting not in ['A','B']:raise ValueError('A/B only')
 q=a.build_request(text,side,stage,'LA1')
 assert q['model']=='claude-haiku-5-5' and q['max_tokens']==2048 and q['thinking']=={'type':'disabled'} and q['output_config']['effort']=='low'
 if setting=='B':q['thinking']={'type':'adaptive'};q['output_config']['effort']='medium'
 return q
def validate(m):
 assert digest(m)==CONFIG['manifest_sha256'] and m['id']==CONFIG['plan_id'] and m['phase']==CONFIG['phase']
 assert m['cap']==36 and m['whole_task_maximum']==72 and len(m['cases'])==6 and len({x['id'] for x in m['cases']})==6
 assert sum(x['side']=='K' for x in m['cases'])==3 and sum(x['side']=='L' for x in m['cases'])==3
 assert m['schedule']==schedule(m['cases']) and len(m['schedule'])==36
 assert 0<=m['prior_attempts']<=36 and (m['phase']!='P1' or m['prior_attempts']==0)
 for p,h in m['frozen_file_sha256'].items():assert hashlib.sha256((ROOT.parent/p).read_bytes()).hexdigest()==h
 for c in m['cases']:
  assert set(c)=={'id','side','index','diagnostic','source','source_sha256','development_allowed'} and c['development_allowed'] is True
  assert hashlib.sha256(c['source'].encode()).hexdigest()==c['source_sha256']
 return {c['id']:c for c in m['cases']}
class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,*args,**kwargs):raise ValueError('Redirect forbidden')
def live(q):
 assert q['model']=='claude-haiku-5-5'
 body=json.dumps(q,ensure_ascii=False).encode();url='https://api.anthropic.com/v1/messages';headers={'x-api-key':os.environ['ANTHROPIC_API_KEY'],'anthropic-version':'2023-06-01','Content-Type':'application/json'}
 req=urllib.request.Request(url,headers=headers,data=body);start=time.perf_counter()
 try:
  with urllib.request.build_opener(NoRedirect).open(req,timeout=90) as r:rawbody=r.read();status=r.status;h=r.headers
 except urllib.error.HTTPError as e:rawbody=e.read();status=e.code;h=e.headers
 api_ms=(time.perf_counter()-start)*1000
 return dict(raw=json.loads(rawbody),http_status=status,api_ms=api_ms,request=dict(url=url,method='POST',headers={'x-api-key':'<REDACTED>','anthropic-version':'2023-06-01','Content-Type':'application/json'},body_utf8=body.decode(),body_sha256=hashlib.sha256(body).hexdigest()),response_body_utf8=rawbody.decode('utf-8'),response_body_sha256=hashlib.sha256(rawbody).hexdigest(),response_headers={k:h.get(k) for k in ['request-id','date','content-type']})
def run_approved(m,approval,transport,journal_path,persist=lambda d:None):
 authorize(approval);cases=validate(m)
 with Path(journal_path).open('x') as f:f.write('0\n')
 d=dict(plan_id=m['id'],phase=m['phase'],attempts=0,prior_attempts=m['prior_attempts'],whole_task_maximum=72,retries=0,slots=[],status='RUNNING');by={};persist(copy.deepcopy(d))
 for planned in m['schedule']:
  x=dict(planned,attempted=False);d['slots'].append(x);by[x['slot']]=x
  if x['stage']=='back' and by[x['depends_on']]['status']!='SUCCESS':x.update(status='SKIPPED_DEPENDENCY',reason='Corresponding FIRST incomplete/invalid; no repair/refill');persist(copy.deepcopy(d));continue
  text=cases[x['id']]['source'] if x['stage']=='first' else by[x['depends_on']]['translation'];q=build(text,x['side'],x['stage'],x['setting'])
  assert d['attempts']<36 and m['prior_attempts']+d['attempts']<72
  d['attempts']+=1;x.update(attempt=d['attempts'],attempted=True,status='SENT_OR_UNKNOWN',input=text,input_sha256=hashlib.sha256(text.encode()).hexdigest(),payload=q,payload_sha256=digest(q),sent_at_utc=__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat())
  with Path(journal_path).open('a') as f:f.write(json.dumps({'attempt':d['attempts'],'slot':x['slot'],'payload_sha256':x['payload_sha256']})+'\n')
  persist(copy.deepcopy(d));start=time.perf_counter();raw={}
  try:
   wire=transport(q);raw=wire['raw'];x.update(wire=wire,response=raw,response_id=raw.get('id'),http_status=wire['http_status'],stop_reason=raw.get('stop_reason'),usage=raw.get('usage',{}),estimated_usd=a.estimated_cost_usd(raw.get('usage',{})),raw_text=''.join(b.get('text','') for b in raw.get('content',[]) if b.get('type')=='text'))
   if x['http_status'] in [401,403] or (raw.get('type')=='message' and raw.get('model')!=q['model']):raise a.SafetyStop('Global authentication/model mismatch')
   x.update(a.inspect_response(raw,text,x['side'],x['stage'],'LA1'));x['status']='SUCCESS'
  except a.SafetyStop:d['status']='GLOBAL_SAFETY_STOP';persist(copy.deepcopy(d));raise
  except Exception as exc:x.update(status='FAILED',reason=a.failure_reason(raw,exc),error_type=type(exc).__name__)
  finally:x['ready_ms']=(time.perf_counter()-start)*1000;x['api_ms']=x.get('wire',{}).get('api_ms',x['ready_ms']);persist(copy.deepcopy(d))
 d['status']='PHASE_COMPLETE_LOCAL_QUALITY_REVIEW_REQUIRED';persist(copy.deepcopy(d));return d
