"""Bounded, replay-protected SINGLE_PASS prompt research; failures consume budget."""
from pathlib import Path
import copy,json,hashlib,importlib.util,os,time,datetime,urllib.request,urllib.error
ROOT=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('p320adapter',ROOT/'adapter.py');a=importlib.util.module_from_spec(s);s.loader.exec_module(a);digest=a.digest
CONFIG=json.loads((ROOT/'config.json').read_text())
def authorize(x):
 assert x==dict(authorized=True,campaign_id='GEMINI_PROMPT320_20261102',plan_id=CONFIG['plan_id'],maximum_new_attempts=CONFIG['cap'],phase_budget=CONFIG['phase_budget'],whole_task_maximum=320,manifest_sha256=CONFIG['manifest_sha256'])
def schedule(cases):
 out=[]
 for case in cases:
  vs=list(CONFIG['variants']);shift=case['index']%len(vs);vs=vs[shift:]+vs[:shift]
  for v in vs:
   n=len(out)+1
   for st,dep in [('first',None),('back',n)]:out.append(dict(slot=len(out)+1,id=case['id'],side=case['side'],index=case['index'],variant=v,engine=a.engine(v,st),stage=st,depends_on=dep))
 return out
build=a.build;inspect=a.inspect
def validate(m):
 assert digest(m)==CONFIG['manifest_sha256'] and m['id']==CONFIG['plan_id'] and m['phase']==CONFIG['phase'] and m['whole_task_maximum']==320
 assert m['cap']==CONFIG['cap']==len(m['schedule']) and m['schedule']==schedule(m['cases'])
 assert m['cap']<=CONFIG['phase_budget'] and m['prior_attempts']==CONFIG['prior'] and m['prior_attempts']+m['cap']<=320
 assert len({x['id'] for x in m['cases']})==len(m['cases']) and sum(x['side']=='K' for x in m['cases'])==sum(x['side']=='L' for x in m['cases'])
 for name,h in m['frozen_file_sha256'].items():assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==h
 for x in m['cases']:assert x['development_allowed'] is True and hashlib.sha256(x['source'].encode()).hexdigest()==x['source_sha256']
 return {x['id']:x for x in m['cases']}
class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,*args,**kwargs):raise ValueError('Redirect forbidden')
def live(q):
 endpoint='https://generativelanguage.googleapis.com/v1beta/models/'+q['model']+':generateContent';body=json.dumps(q['payload'],ensure_ascii=False).encode();req=urllib.request.Request(endpoint,data=body,headers={'Content-Type':'application/json','x-goog-api-key':os.environ['GEMINI_API_KEY']});start=time.perf_counter()
 try:
  with urllib.request.build_opener(NoRedirect).open(req,timeout=90) as r:txt=r.read().decode();status=r.status;headers={k:r.headers.get(k) for k in ['date','content-type','x-request-id','x-gemini-service-tier']}
 except urllib.error.HTTPError as e:txt=e.read().decode(errors='replace');status=e.code;headers={}
 try:raw=json.loads(txt)
 except ValueError:raw={}
 return dict(raw=raw,wire=dict(endpoint=endpoint,request_body_utf8=body.decode(),response_body_utf8=txt,http_status=status,response_headers=headers,api_ms=(time.perf_counter()-start)*1000))
def run_approved(m,approval,transport,journal_path,persist=lambda d:None,metadata=None):
 authorize(approval);cases=validate(m)
 with Path(journal_path).open('x') as f:f.write('0\n')
 d=dict(plan_id=m['id'],phase=m['phase'],attempts=0,prior_attempts=m['prior_attempts'],retries=0,slots=[],status='RUNNING');by={};persist(copy.deepcopy(d))
 for planned in m['schedule']:
  x=dict(planned,attempted=False);d['slots'].append(x);by[x['slot']]=x
  if x['stage']=='back' and by[x['depends_on']]['status']!='SUCCESS':x.update(status='SKIPPED_DEPENDENCY');persist(copy.deepcopy(d));continue
  text=cases[x['id']]['source'] if x['stage']=='first' else by[x['depends_on']]['translation'];q=build(text,x['side'],x['stage'],x['variant'])
  assert d['attempts']<m['cap'] and m['prior_attempts']+d['attempts']<320
  d['attempts']+=1;x.update(attempt=d['attempts'],attempted=True,status='SENT_OR_UNKNOWN',input=text,input_sha256=hashlib.sha256(text.encode()).hexdigest(),payload=q,payload_sha256=digest(q),sent_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
  with Path(journal_path).open('a') as f:f.write(json.dumps(dict(attempt=d['attempts'],slot=x['slot'],payload_sha256=x['payload_sha256']))+'\n')
  persist(copy.deepcopy(d));start=time.perf_counter()
  try:
   result=transport(q);raw=result['raw'];wire=result['wire'];x.update(response=raw,wire=wire,http_status=wire['http_status'],response_id=raw.get('responseId'),model_version=raw.get('modelVersion'),usage=raw.get('usageMetadata'),api_ms=wire['api_ms'],**a.usage_cost(raw,q['model'],wire))
   if x['http_status'] in (401,403):raise PermissionError('AUTH_STOP')
   if x['http_status']!=200:raise ValueError('HTTP_FAILURE')
   if raw.get('modelVersion') and not raw['modelVersion'].startswith(q['model']):raise PermissionError('MODEL_ID_STOP')
   x.update(inspect(raw,text,x['side'],x['stage'],x['variant']))
  except PermissionError:d['status']='AUTH_OR_MODEL_STOP';persist(copy.deepcopy(d));raise
  except Exception as exc:x.update(status='FAILED',error_type=type(exc).__name__)
  finally:x['ready_ms']=(time.perf_counter()-start)*1000;persist(copy.deepcopy(d))
 d['status']='PHASE_COMPLETE_REVIEW_REQUIRED';persist(copy.deepcopy(d));return d
