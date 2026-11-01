"""Approved HO/SO/OO49: fresh25 + conditional24. No retries or corrections."""
from pathlib import Path
import copy,hashlib,importlib.util,json,time,os,urllib.request,urllib.error,datetime
ROOT=Path(__file__).resolve().parent
def load(n,p):
 s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
a=load('ho49_frozen',ROOT.parent/'claude-real20-120/adapters.py')
CONFIG=json.loads((ROOT/'config.json').read_text(encoding='utf-8'))
digest=a.core.digest
def authorize(x):
 assert x==dict(authorized=True,campaign_id='CLAUDE_HO_SO_OO49_20261102',plan_id=CONFIG['plan_id'],maximum_new_attempts=CONFIG['cap'],whole_task_maximum=49,H_maximum=8,S_maximum=8,O_maximum=33,manifest_sha256=CONFIG['manifest_sha256'])
def schedule(cases,diagnostic=None):
 out=[]
 def add(c,engine,stage,arm,depends=None):
  slot=len(out)+1;out.append(dict(slot=slot,id=c['id'],side=c['side'],index=c['index'],engine=engine,stage=stage,arm=arm,depends_on=depends));return slot
 if diagnostic:
  add(dict(id='app500:197',side='K',index=-1),'O','back','D')
 for c in cases:
  if c['side']=='K':
   for arm in (['A','B'] if c['index']%2==0 else ['B','A']):
    n=add(c,'H' if arm=='A' else 'S','first',arm);add(c,'O','back',arm,n)
  else:
   n=add(c,'O','first','C');add(c,'O','back','C',n)
 return out

def validate(m):
 assert digest(m)==CONFIG['manifest_sha256'] and m['id']==CONFIG['plan_id'] and m['phase']==CONFIG['phase']
 assert m['phase'] in ('P1','P2')
 cap=25 if m['phase']=='P1' else 24
 assert m['cap']==CONFIG['cap']==cap and m['whole_task_maximum']==49 and len(m['cases'])==8
 assert len({x['id'] for x in m['cases']})==8 and sum(x['side']=='K' for x in m['cases'])==4
 diag=m.get('diagnostic')
 if m['phase']=='P1':
  assert m['prior_attempts']==dict(H=0,S=0,O=0) and set(diag)=={'id','side','input','input_sha256'}
  assert diag['id']=='app500:197' and diag['side']=='K' and hashlib.sha256(diag['input'].encode()).hexdigest()==diag['input_sha256']
 else:assert diag is None and sum(m['prior_attempts'].values())<=25
 assert m['schedule']==schedule(m['cases'],diag) and len(m['schedule'])==cap
 for p,h in m['frozen_file_sha256'].items():assert hashlib.sha256((ROOT.parent/p).read_bytes()).hexdigest()==h
 for c in m['cases']:
  assert set(c)=={'id','side','index','source','source_sha256','development_allowed'} and c['development_allowed'] is True
  assert (c['index']<4)==(m['phase']=='P1')
  assert hashlib.sha256(c['source'].encode()).hexdigest()==c['source_sha256']
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
  if x['stage']=='back' and x['arm']!='D' and by[x['depends_on']]['status']!='SUCCESS':x.update(status='SKIPPED_DEPENDENCY');persist(copy.deepcopy(d));continue
  text=m['diagnostic']['input'] if x['arm']=='D' else (cases[x['id']]['source'] if x['stage']=='first' else by[x['depends_on']]['translation'])
  q=a.build(text,x['side'],x['stage'],x['engine'])
  assert d['attempts']<m['cap'] and sum(m['prior_attempts'].values())+d['attempts']<49
  assert m['prior_attempts'][x['engine']]+d['engine_attempts'][x['engine']]<dict(H=8,S=8,O=33)[x['engine']]
  d['attempts']+=1;d['engine_attempts'][x['engine']]+=1
  x.update(attempt=d['attempts'],attempted=True,status='SENT_OR_UNKNOWN',input=text,input_sha256=hashlib.sha256(text.encode()).hexdigest(),payload=q,payload_sha256=digest(q),sent_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
  with Path(journal_path).open('a') as f:f.write(json.dumps({'attempt':d['attempts'],'engine':x['engine'],'slot':x['slot'],'payload_sha256':x['payload_sha256']})+'\n')
  persist(copy.deepcopy(d));start=time.perf_counter();raw={};wire={}
  try:
   result=transport(q);raw=result['raw'];wire=result['wire'];x.update(response=raw,wire=wire,response_id=raw.get('id'),http_status=wire.get('http_status'),usage=raw.get('usage',{}),stop_reason=raw.get('stop_reason'),estimated_usd=a.cost(raw.get('usage',{}),x['engine']))
   if x['http_status'] in (401,403):raise PermissionError('GLOBAL_AUTH_STOP')
   if raw.get('type')=='message' and raw.get('model')!=q['model']:raise PermissionError('MODEL_ID_STOP')
   if x['http_status']!=200:raise ValueError('HTTP_FAILURE')
   x.update(a.inspect(raw,text,x['side'],x['stage'],x['engine']))
  except PermissionError:d['status']='GLOBAL_SAFETY_STOP';persist(copy.deepcopy(d));raise
  except Exception as exc:x.update(status='FAILED',error_type=type(exc).__name__)
  finally:x['ready_ms']=(time.perf_counter()-start)*1000;x['api_ms']=wire.get('api_ms',x['ready_ms']);persist(copy.deepcopy(d))
 d['status']='PHASE_COMPLETE_REVIEW_REQUIRED';persist(copy.deepcopy(d));return d
