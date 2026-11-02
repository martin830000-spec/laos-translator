"""Approved Gemini200 research; native model GET metadata before generation; no retry."""
from pathlib import Path
import copy,json,hashlib,importlib.util,os,time,datetime,urllib.request,urllib.error
ROOT=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('gem200_adapter',ROOT/'adapter.py');a=importlib.util.module_from_spec(s);s.loader.exec_module(a);digest=a.digest
CONFIG=json.loads((ROOT/'config.json').read_text())
def authorize(x):
 assert x==dict(authorized=True,campaign_id='GEMINI_AUTONOMOUS200_20261102',plan_id=CONFIG['plan_id'],maximum_new_attempts=CONFIG['cap'],phase_budget=CONFIG['phase_budget'],whole_task_maximum=200,manifest_sha256=CONFIG['manifest_sha256'])
def schedule(cases):
 out=[]
 for case in cases:
  if case.get('kind')=='STORED_FIRST':
   out.append(dict(slot=len(out)+1,id=case['id'],side=case['side'],index=case['index'],variant='X31_38',engine='38',stage='back',depends_on=None));continue
  variants=list(CONFIG['variants']);shift=case['index']%len(variants);variants=variants[shift:]+variants[:shift]
  if CONFIG.get('groups'):
   groups=copy.deepcopy(CONFIG['groups']);groups=groups if case['index']%2==0 else groups[::-1];variants=[]
   for group in groups:variants+=group if '38P' in group or case['index']%2==0 else group[::-1]
  for variant in variants:
   n=len(out)+1
   for stage,dep in [('first',None),('back',n)]:out.append(dict(slot=len(out)+1,id=case['id'],side=case['side'],index=case['index'],variant=variant,engine=a.engine(variant,stage),stage=stage,depends_on=dep))
 return out
build=a.build;inspect=a.inspect
def validate(m):
 assert digest(m)==CONFIG['manifest_sha256'] and m['id']==CONFIG['plan_id'] and m['phase']==CONFIG['phase'] and m['whole_task_maximum']==200
 assert m['cap']==CONFIG['cap']==len(m['schedule']) and m['schedule']==schedule(m['cases'])
 assert m['cap']<=CONFIG['phase_budget'] and CONFIG['phase_budget'] in (48,72,80)
 assert m['stage_prior_attempts']+m['cap']<=CONFIG['phase_budget'] and sum(m['prior_attempts'].values())+m['cap']<=200
 assert len({x['id'] for x in m['cases']})==len(m['cases']) and sum(x['side']=='K' for x in m['cases'])==sum(x['side']=='L' for x in m['cases'])
 for name,h in m['frozen_file_sha256'].items():assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==h
 for x in m['cases']:assert set(x) in ({'id','side','index','source','source_sha256','development_allowed'},{'id','side','index','source','source_sha256','development_allowed','kind'}) and x['development_allowed'] is True and hashlib.sha256(x['source'].encode()).hexdigest()==x['source_sha256']
 return {x['id']:x for x in m['cases']}
class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,*args,**kwargs):raise ValueError('Redirect forbidden')
def request(method,endpoint,payload=None):
 body=json.dumps(payload,ensure_ascii=False).encode() if payload is not None else None;req=urllib.request.Request(endpoint,method=method,data=body,headers={'Content-Type':'application/json','x-goog-api-key':os.environ['GEMINI_API_KEY']});start=time.perf_counter();headers={};status=None
 try:
  with urllib.request.build_opener(NoRedirect).open(req,timeout=90) as r:txt=r.read().decode('utf-8');status=r.status;headers={k:r.headers.get(k) for k in ('date','content-type','x-request-id','request-id','x-gemini-service-tier')}
 except urllib.error.HTTPError as e:txt=e.read().decode('utf-8',errors='replace');status=e.code;headers={'x-request-id':e.headers.get('x-request-id')}
 elapsed=(time.perf_counter()-start)*1000
 try:raw=json.loads(txt)
 except ValueError:raw={'error':'NON_JSON_HTTP_BODY'}
 wire=dict(method=method,endpoint=endpoint,request_body_utf8=body.decode() if body is not None else None,request_body_sha256=hashlib.sha256(body).hexdigest() if body is not None else None,request_headers={'Content-Type':'application/json','x-goog-api-key':'[REDACTED]'},response_body_utf8=txt,response_body_sha256=hashlib.sha256(txt.encode()).hexdigest(),response_headers=headers,http_status=status,api_ms=elapsed)
 return dict(raw=raw,wire=wire)
def get_model_metadata():
 out={}
 for k,model in a.MODELS.items():
  r=request('GET','https://generativelanguage.googleapis.com/v1beta/models/'+model);out[k]=r
  if r['wire']['http_status'] in (401,403):raise PermissionError('MODEL_METADATA_AUTH_STOP')
  if r['wire']['http_status']==200:assert r['raw']['name']=='models/'+model and 'generateContent' in r['raw'].get('supportedGenerationMethods',[])
 return out
def live(q):return request('POST','https://generativelanguage.googleapis.com/v1beta/models/'+q['model']+':generateContent',q['payload'])
def run_approved(m,approval,transport,journal_path,persist=lambda d:None,metadata=None):
 authorize(approval);cases=validate(m)
 with Path(journal_path).open('x') as f:f.write('0\n')
 d=dict(plan_id=m['id'],phase=m['phase'],attempts=0,prior_attempts=m['prior_attempts'],engine_attempts={k:0 for k in a.MODELS},retries=0,metadata=metadata or {},slots=[],status='RUNNING',priority_scope_disabled=False);by={};persist(copy.deepcopy(d))
 for planned in m['schedule']:
  x=dict(planned,attempted=False);d['slots'].append(x);by[x['slot']]=x
  if x['stage']=='back' and x['depends_on'] is not None and by[x['depends_on']]['status']!='SUCCESS':x.update(status='SKIPPED_DEPENDENCY');persist(copy.deepcopy(d));continue
  if d['priority_scope_disabled'] and CONFIG.get('probe_priority_once') and cases[x['id']].get('kind')!='STORED_FIRST' and x['variant'] in ('38P','38'):x.update(status='SKIPPED_PRIORITY_CAPABILITY_SCOPE');persist(copy.deepcopy(d));continue
  if metadata and x['engine'] in metadata and metadata[x['engine']]['wire']['http_status']!=200:x.update(status='SKIPPED_MODEL_UNAVAILABLE');persist(copy.deepcopy(d));continue
  text=cases[x['id']]['source'] if x['stage']=='first' or x['depends_on'] is None else by[x['depends_on']]['translation'];prep=time.perf_counter();q=build(text,x['side'],x['stage'],x['variant']);prep_ms=(time.perf_counter()-prep)*1000
  assert d['attempts']<m['cap'] and m['stage_prior_attempts']+d['attempts']<CONFIG['phase_budget'] and sum(m['prior_attempts'].values())+d['attempts']<200
  d['attempts']+=1;d['engine_attempts'][x['engine']]+=1;x.update(attempt=d['attempts'],attempted=True,status='SENT_OR_UNKNOWN',input=text,input_sha256=hashlib.sha256(text.encode()).hexdigest(),payload=q,payload_sha256=digest(q),prepare_ms=prep_ms,sent_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
  with Path(journal_path).open('a') as f:f.write(json.dumps(dict(attempt=d['attempts'],slot=x['slot'],engine=x['engine'],payload_sha256=x['payload_sha256']))+'\n')
  persist(copy.deepcopy(d));start=time.perf_counter();raw={};wire={}
  try:
   result=transport(q);raw=result['raw'];wire=result['wire'];x.update(response=raw,wire=wire,http_status=wire.get('http_status'),response_id=raw.get('responseId'),model_version=raw.get('modelVersion'),usage=raw.get('usageMetadata'),**a.usage_cost(raw,q['model'],wire))
   if x['variant']=='38P' and x['stage']=='first' and CONFIG.get('probe_priority_once'):
    msg=json.dumps(raw.get('error',{})).lower()
    if x['http_status'] in (400,403,404) and ('priority' in msg or 'tier' in msg):d['priority_scope_disabled']=True;x.update(status='FAILED_CAPABILITY',error_type='PRIORITY_NOT_AVAILABLE');continue
    if x['http_status']==200 and wire.get('response_headers',{}).get('x-gemini-service-tier')!='priority':d['priority_scope_disabled']=True;x['priority_not_confirmed']=True
   if x['http_status'] in (401,403):raise PermissionError('GLOBAL_AUTH_STOP')
   if x['http_status']!=200:raise ValueError('HTTP_FAILURE')
   if raw.get('modelVersion') and not raw['modelVersion'].startswith(q['model']):raise PermissionError('MODEL_ID_STOP')
   x.update(inspect(raw,text,x['side'],x['stage'],x['variant']))
  except PermissionError:d['status']='GLOBAL_SAFETY_STOP';persist(copy.deepcopy(d));raise
  except Exception as exc:x.update(status='FAILED',error_type=type(exc).__name__)
  finally:x['ready_ms']=(time.perf_counter()-start)*1000;x['api_ms']=wire.get('api_ms',x['ready_ms']);persist(copy.deepcopy(d))
 d['status']='PHASE_COMPLETE_REVIEW_REQUIRED';persist(copy.deepcopy(d));return d
