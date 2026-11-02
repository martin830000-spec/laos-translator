"""New independent A/B studies, bounded32+conditional32; never retries."""
from pathlib import Path
import copy,hashlib,importlib.util,json,time,os,urllib.request,urllib.error,datetime
ROOT=Path(__file__).resolve().parent
def load(n,p):
 s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
a=load('quality64_adapter',ROOT/'adapter.py');digest=a.f.core.digest
CONFIG=json.loads((ROOT/'config.json').read_text())
def authorize(x):
 assert x==dict(authorized=True,campaign_id='CLAUDE_QUALITY_IMPROVEMENT64_20261102',plan_id=CONFIG['plan_id'],maximum_new_attempts=CONFIG['cap'],whole_task_maximum=64,H_maximum=32,S_maximum=32,O_maximum=0,manifest_sha256=CONFIG['manifest_sha256'])
def schedule(cases):
 out=[]
 for c in cases:
  for variant in (['BASE','NEW'] if c['index']%2==0 else ['NEW','BASE']):
   n=len(out)+1
   for stage,dep in [('first',None),('back',n)]:out.append(dict(slot=len(out)+1,id=c['id'],side=c['side'],index=c['index'],study=c['study'],engine='S' if c['study']=='A' else 'H',stage=stage,variant=variant,depends_on=dep))
 return out
def validate(m):
 assert digest(m)==CONFIG['manifest_sha256'] and m['id']==CONFIG['plan_id'] and m['phase']==CONFIG['phase']
 assert m['phase'] in ('P1','P2') and m['whole_task_maximum']==64 and m['cap']==CONFIG['cap']==len(m['schedule'])<=32
 assert m['active_studies'] in (['A'],['B'],['A','B']) and len(m['cases'])==4*len(m['active_studies'])
 assert m['schedule']==schedule(m['cases']) and m['cap']==16*len(m['active_studies'])
 assert sum(m['prior_attempts'].values())<=32
 if m['phase']=='P1':assert m['prior_attempts']==dict(H=0,S=0,O=0)
 for p,h in m['frozen_file_sha256'].items():assert hashlib.sha256((ROOT.parent/p).read_bytes()).hexdigest()==h
 for c in m['cases']:
  assert c['study'] in m['active_studies'] and c['development_allowed'] is True and (c['index']<2)==(m['phase']=='P1')
  assert hashlib.sha256(c['source'].encode()).hexdigest()==c['source_sha256']
  if c['study']=='B':
   im=m['images'][c['id']];assert im['source_sha256']==c['source_sha256']
   a.build(c['source'],c['side'],'first','B','NEW',im)
 for study in m['active_studies']:
  assert sum(c['side']=='K' and c['study']==study for c in m['cases'])==2
  assert sum(c['side']=='L' and c['study']==study for c in m['cases'])==2
 return {(x['study'],x['id']):x for x in m['cases']}
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
  if x['stage']=='back' and by[x['depends_on']]['status']!='SUCCESS':x.update(status='SKIPPED_DEPENDENCY');persist(copy.deepcopy(d));continue
  text=cases[(x['study'],x['id'])]['source'] if x['stage']=='first' else by[x['depends_on']]['translation']
  image=m['images'].get(x['id']) if x['study']=='B' and x['variant']=='NEW' and x['stage']=='first' else None
  q=a.build(text,x['side'],x['stage'],x['study'],x['variant'],image)
  assert d['attempts']<m['cap'] and sum(m['prior_attempts'].values())+d['attempts']<64
  assert m['prior_attempts'][x['engine']]+d['engine_attempts'][x['engine']]<dict(H=32,S=32,O=0)[x['engine']]
  d['attempts']+=1;d['engine_attempts'][x['engine']]+=1
  x.update(attempt=d['attempts'],attempted=True,status='SENT_OR_UNKNOWN',input=text,input_sha256=hashlib.sha256(text.encode()).hexdigest(),payload=q,payload_sha256=digest(q),sent_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
  with Path(journal_path).open('a') as f:f.write(json.dumps({'attempt':d['attempts'],'engine':x['engine'],'study':x['study'],'slot':x['slot'],'payload_sha256':x['payload_sha256']})+'\n')
  persist(copy.deepcopy(d));start=time.perf_counter();raw={};wire={}
  try:
   result=transport(q);raw=result['raw'];wire=result['wire'];x.update(response=raw,wire=wire,response_id=raw.get('id'),http_status=wire.get('http_status'),usage=raw.get('usage',{}),stop_reason=raw.get('stop_reason'),estimated_usd=a.f.cost(raw.get('usage',{}),x['engine']))
   if x['http_status'] in (401,403):raise PermissionError('GLOBAL_AUTH_STOP')
   if raw.get('type')=='message' and raw.get('model')!=q['model']:raise PermissionError('MODEL_ID_STOP')
   if x['http_status']!=200:raise ValueError('HTTP_FAILURE')
   x.update(a.inspect(raw,text,x['side'],x['stage'],x['study'],x['variant']))
  except PermissionError:d['status']='GLOBAL_SAFETY_STOP';persist(copy.deepcopy(d));raise
  except Exception as exc:x.update(status='FAILED',error_type=type(exc).__name__)
  finally:x['ready_ms']=(time.perf_counter()-start)*1000;x['api_ms']=wire.get('api_ms',x['ready_ms']);persist(copy.deepcopy(d))
 d['status']='PHASE_COMPLETE_REVIEW_REQUIRED';persist(copy.deepcopy(d));return d
