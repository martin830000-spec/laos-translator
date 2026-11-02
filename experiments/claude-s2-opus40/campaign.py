"""Frozen S1/S2 FIRST -> frozen Opus BACK; approved8+16+16, no retry."""
from pathlib import Path
import copy,hashlib,importlib.util,json,time,os,urllib.request,urllib.error,datetime
ROOT=Path(__file__).resolve().parent
def load(n,p):
 s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
a=load('s2opus40_frozen',ROOT.parent/'claude-quality-improvement64/adapter.py');digest=a.f.core.digest
CONFIG=json.loads((ROOT/'config.json').read_text())
def authorize(x):
 assert x==dict(authorized=True,campaign_id='CLAUDE_S2_OPUS40_20261102',plan_id=CONFIG['plan_id'],maximum_new_attempts=CONFIG['cap'],whole_task_maximum=40,H_maximum=0,S_maximum=16,O_maximum=24,manifest_sha256=CONFIG['manifest_sha256'])
def schedule(cases,phase):
 out=[]
 for case in cases:
  if phase=='P1':out.append(dict(slot=len(out)+1,id=case['id'],side=case['side'],index=case['index'],engine='O',stage='back',arm='STORED_S2',depends_on=None));continue
  for arm in (['A','B'] if case['index']%2==0 else ['B','A']):
   n=len(out)+1
   for stage,dep in [('first',None),('back',n)]:out.append(dict(slot=len(out)+1,id=case['id'],side=case['side'],index=case['index'],engine='S' if stage=='first' else 'O',stage=stage,arm=arm,depends_on=dep))
 return out
def build(text,side,stage,arm):
 if stage=='back':return a.f.build(text,side,'back','O')
 assert arm in ('A','B')
 return a.build(text,side,'first','A','BASE' if arm=='A' else 'NEW')
def inspect(raw,text,side,stage,arm):
 if stage=='back':return a.f.inspect(raw,text,side,'back','O')
 return a.inspect(raw,text,side,'first','A','BASE' if arm=='A' else 'NEW')
def validate(m):
 assert digest(m)==CONFIG['manifest_sha256'] and m['id']==CONFIG['plan_id'] and m['phase']==CONFIG['phase']
 assert m['phase'] in ('P1','P2','P3') and m['whole_task_maximum']==40
 cap=8 if m['phase']=='P1' else 16
 assert m['cap']==CONFIG['cap']==cap and m['schedule']==schedule(m['cases'],m['phase']) and len(m['schedule'])==cap
 assert len(m['cases'])==(8 if m['phase']=='P1' else 4) and len({x['id'] for x in m['cases']})==len(m['cases'])
 assert sum(x['side']=='K' for x in m['cases'])==len(m['cases'])//2 and m['prior_attempts']['H']==0
 assert sum(m['prior_attempts'].values())<=dict(P1=0,P2=8,P3=24)[m['phase']]
 for p,h in m['frozen_file_sha256'].items():assert hashlib.sha256((ROOT.parent/p).read_bytes()).hexdigest()==h
 for x in m['cases']:
  assert x['development_allowed'] is True
  if m['phase']=='P1':
   assert set(x)=={'id','side','index','input','input_sha256','development_allowed'}
   assert hashlib.sha256(x['input'].encode()).hexdigest()==x['input_sha256']
  else:
   assert set(x)=={'id','side','index','source','source_sha256','development_allowed'}
   assert hashlib.sha256(x['source'].encode()).hexdigest()==x['source_sha256']
   assert (x['index']<2)==(m['phase']=='P2')
 return {x['id']:x for x in m['cases']}
class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,*a,**k):raise ValueError('Redirect forbidden')
def live(q):
 endpoint='https://api.anthropic.com/v1/messages';data=json.dumps(q,ensure_ascii=False).encode();request=urllib.request.Request(endpoint,headers={'Content-Type':'application/json','x-api-key':os.environ['ANTHROPIC_API_KEY'],'anthropic-version':'2023-06-01'},data=data)
 start=time.perf_counter();headers={};status=None
 try:
  with urllib.request.build_opener(NoRedirect).open(request,timeout=90) as r:
   body=r.read().decode('utf-8');status=r.status;headers={k:r.headers.get(k) for k in ('request-id','date','content-type')}
 except urllib.error.HTTPError as e:body=e.read().decode('utf-8',errors='replace');status=e.code;headers={'request-id':e.headers.get('request-id')}
 elapsed=(time.perf_counter()-start)*1000
 try:raw=json.loads(body)
 except ValueError:raw={'error':'NON_JSON_HTTP_BODY'}
 return {'raw':raw,'wire':{'endpoint':endpoint,'request_body_utf8':data.decode(),'request_body_sha256':hashlib.sha256(data).hexdigest(),'request_headers':{'Content-Type':'application/json','anthropic-version':'2023-06-01','x-api-key':'[REDACTED]'},'response_body_utf8':body,'response_body_sha256':hashlib.sha256(body.encode()).hexdigest(),'http_status':status,'response_headers':headers,'api_ms':elapsed}}

def run_approved(m,approval,transport,journal_path,persist=lambda d:None):
 authorize(approval);cases=validate(m)
 with Path(journal_path).open('x') as f:f.write('0\n')
 d=dict(plan_id=m['id'],phase=m['phase'],attempts=0,prior_attempts=m['prior_attempts'],engine_attempts=dict(H=0,S=0,O=0),retries=0,slots=[],status='RUNNING');by={};persist(copy.deepcopy(d))
 for planned in m['schedule']:
  x=dict(planned,attempted=False);d['slots'].append(x);by[x['slot']]=x
  if x['stage']=='back' and x['depends_on'] is not None and by[x['depends_on']]['status']!='SUCCESS':x.update(status='SKIPPED_DEPENDENCY');persist(copy.deepcopy(d));continue
  text=cases[x['id']]['input'] if m['phase']=='P1' else (cases[x['id']]['source'] if x['stage']=='first' else by[x['depends_on']]['translation'])
  q=build(text,x['side'],x['stage'],x['arm'])
  assert d['attempts']<m['cap'] and sum(m['prior_attempts'].values())+d['attempts']<40
  assert m['prior_attempts'][x['engine']]+d['engine_attempts'][x['engine']]<dict(H=0,S=16,O=24)[x['engine']]
  d['attempts']+=1;d['engine_attempts'][x['engine']]+=1
  x.update(attempt=d['attempts'],attempted=True,status='SENT_OR_UNKNOWN',input=text,input_sha256=hashlib.sha256(text.encode()).hexdigest(),payload=q,payload_sha256=digest(q),sent_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
  with Path(journal_path).open('a') as f:f.write(json.dumps({'attempt':d['attempts'],'engine':x['engine'],'slot':x['slot'],'payload_sha256':x['payload_sha256']})+'\n')
  persist(copy.deepcopy(d));start=time.perf_counter();raw={};wire={}
  try:
   result=transport(q);raw=result['raw'];wire=result['wire'];x.update(response=raw,wire=wire,response_id=raw.get('id'),http_status=wire.get('http_status'),usage=raw.get('usage',{}),stop_reason=raw.get('stop_reason'),estimated_usd=a.f.cost(raw.get('usage',{}),x['engine']))
   if x['http_status'] in (401,403):raise PermissionError('GLOBAL_AUTH_STOP')
   if raw.get('type')=='message' and raw.get('model')!=q['model']:raise PermissionError('MODEL_ID_STOP')
   if x['http_status']!=200:raise ValueError('HTTP_FAILURE')
   x.update(inspect(raw,text,x['side'],x['stage'],x['arm']))
  except PermissionError:d['status']='GLOBAL_SAFETY_STOP';persist(copy.deepcopy(d));raise
  except Exception as exc:x.update(status='FAILED',error_type=type(exc).__name__)
  finally:x['ready_ms']=(time.perf_counter()-start)*1000;x['api_ms']=wire.get('api_ms',x['ready_ms']);persist(copy.deepcopy(d))
 d['status']='PHASE_COMPLETE_REVIEW_REQUIRED';persist(copy.deepcopy(d));return d
