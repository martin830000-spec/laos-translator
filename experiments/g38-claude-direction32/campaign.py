"""Approved128 in two bounded64 phases; frozen service contract, no retry."""
import copy,hashlib,importlib.util,json,time,subprocess,os,urllib.request,urllib.error
from pathlib import Path
ROOT=Path(__file__).resolve().parent
def load(n,p):
 s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
a=load('direction32_frozen',ROOT.parent/'claude-real20-120/adapters.py')
CONFIG=json.loads((ROOT/'config.json').read_text())
digest=a.core.digest
def authorize(x):
 assert x==dict(authorized=True,campaign_id='G38_CLAUDE_DIRECTION32_20261101',plan_id=CONFIG['plan_id'],maximum_new_attempts=64,whole_task_maximum=128,G_maximum=64,S_maximum=32,O_maximum=32,manifest_sha256=CONFIG['manifest_sha256'])
def js(q):
 p=subprocess.run(['node',str(ROOT/'gemini-contract.cjs')],input=json.dumps(q,ensure_ascii=False),text=True,encoding='utf-8',capture_output=True,check=True)
 return json.loads(p.stdout)
def schedule(cases):
 out=[]
 for c in cases:
  engines=['G','S' if c['side']=='K' else 'O']
  if c['index']%2:engines.reverse()
  for engine in engines:
   n=len(out)+1
   out.extend([dict(slot=n,id=c['id'],side=c['side'],engine=engine,stage='first',depends_on=None),dict(slot=n+1,id=c['id'],side=c['side'],engine=engine,stage='back',depends_on=n)])
 return out
def build(text,side,stage,engine):
 return dict(model='gemini-3.8-flash',**js(dict(mode='build',text=text,side=side,stage=stage))) if engine=='G' else a.build(text,side,stage,engine)
def validate(m):
 assert digest(m)==CONFIG['manifest_sha256'] and m['id']==CONFIG['plan_id'] and m['phase']==CONFIG['phase']
 assert m['cap']==64 and m['whole_task_maximum']==128 and len(m['cases'])==16
 assert len({x['id'] for x in m['cases']})==16 and sum(x['side']=='K' for x in m['cases'])==8
 assert m['schedule']==schedule(m['cases']) and len(m['schedule'])==64
 assert m['prior_attempts']==(dict(G=0,S=0,O=0) if m['phase']=='P1' else dict(G=32,S=16,O=16))
 for p,h in m['frozen_file_sha256'].items():assert hashlib.sha256((ROOT.parent/p).read_bytes()).hexdigest()==h
 for c in m['cases']:
  assert set(c)=={'id','side','index','source','source_sha256','development_allowed'} and c['development_allowed'] is True
  assert hashlib.sha256(c['source'].encode()).hexdigest()==c['source_sha256']
 return {c['id']:c for c in m['cases']}
class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,*args,**kwargs):raise ValueError('Redirect forbidden')
def live(q):
 if q['model']=='gemini-3.8-flash':
  endpoint='https://generativelanguage.googleapis.com/v1beta/models/gemini-3.8-flash:generateContent';headers={'x-goog-api-key':os.environ['GEMINI_API_KEY']};body=q['payload']
 else:endpoint='https://api.anthropic.com/v1/messages';headers={'x-api-key':os.environ['ANTHROPIC_API_KEY'],'anthropic-version':'2023-06-01'};body=q
 headers['Content-Type']='application/json'
 req=urllib.request.Request(endpoint,headers=headers,data=json.dumps(body,ensure_ascii=False).encode())
 start=time.perf_counter()
 try:
  with urllib.request.build_opener(NoRedirect).open(req,timeout=90) as r:
   data=json.loads(r.read());data['_transport']={'http_status':r.status,'request_id':r.headers.get('request-id') or r.headers.get('x-request-id'),'api_ms':(time.perf_counter()-start)*1000,'endpoint':endpoint,'protocol':'JSON generateContent' if q['model'].startswith('gemini') else 'JSON messages'};return data
 except urllib.error.HTTPError as e:
  return dict(_transport=dict(http_status=e.code,api_ms=(time.perf_counter()-start)*1000),error_body=e.read().decode('utf-8',errors='replace'))
def cost(u,engine):
 if engine!='G':return a.cost(u,engine)
 if 'promptTokenCount' not in u:return None
 p=u['promptTokenCount'];cached=u.get('cachedContentTokenCount',0);out=u.get('candidatesTokenCount',0)+u.get('thoughtsTokenCount',0)
 return round(((p-cached)*.75+cached*.075+out*3.75)/1e6,9)
def run_approved(m,approval,transport,journal_path,persist=lambda d:None):
 authorize(approval);cases=validate(m)
 with Path(journal_path).open('x') as f:f.write('0\n')
 d=dict(plan_id=m['id'],phase=m['phase'],attempts=0,prior_attempts=m['prior_attempts'],engine_attempts=dict(G=0,S=0,O=0),retries=0,slots=[],status='RUNNING');by={};persist(copy.deepcopy(d))
 for planned in m['schedule']:
  x=dict(planned,attempted=False);d['slots'].append(x);by[x['slot']]=x
  if x['stage']=='back' and by[x['depends_on']]['status']!='SUCCESS':x.update(status='SKIPPED_DEPENDENCY');persist(copy.deepcopy(d));continue
  text=cases[x['id']]['source'] if x['stage']=='first' else by[x['depends_on']]['translation']
  q=build(text,x['side'],x['stage'],x['engine'])
  assert d['attempts']<64 and sum(m['prior_attempts'].values())+d['attempts']<128
  assert m['prior_attempts'][x['engine']]+d['engine_attempts'][x['engine']]<{'G':64,'S':32,'O':32}[x['engine']]
  d['attempts']+=1;d['engine_attempts'][x['engine']]+=1;x.update(attempt=d['attempts'],attempted=True,status='SENT_OR_UNKNOWN',input=text,input_sha256=hashlib.sha256(text.encode()).hexdigest(),payload=q,payload_sha256=digest(q),sent_at_utc=__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat())
  with Path(journal_path).open('a') as f:f.write(json.dumps({'attempt':d['attempts'],'engine':x['engine'],'slot':x['slot'],'payload_sha256':x['payload_sha256']})+'\n')
  persist(copy.deepcopy(d));start=time.perf_counter();raw={}
  try:
   raw=transport(q);u=raw.get('usageMetadata',{}) if x['engine']=='G' else raw.get('usage',{});x.update(response=raw,response_id=raw.get('responseId',raw.get('id')),http_status=raw.get('_transport',{}).get('http_status'),usage=u,estimated_usd=cost(u,x['engine']))
   if x['http_status'] in [401,403]:raise PermissionError('Authentication stop')
   if x['engine']=='G':
    if raw.get('modelVersion') and not raw['modelVersion'].startswith('gemini-3.8-flash'):raise PermissionError('Model mismatch')
    x.update(js(dict(mode='inspect',raw=raw,text=text,side=x['side'],stage=x['stage'])))
   else:
    if raw.get('type')=='message' and raw.get('model')!=q['model']:raise PermissionError('Model mismatch')
    x.update(a.inspect(raw,text,x['side'],x['stage'],x['engine']))
  except PermissionError:d['status']='GLOBAL_SAFETY_STOP';persist(copy.deepcopy(d));raise
  except Exception as exc:x.update(status='FAILED',error_type=type(exc).__name__)
  finally:x['wall_ms']=(time.perf_counter()-start)*1000;x['api_ms']=raw.get('_transport',{}).get('api_ms',x['wall_ms']);persist(copy.deepcopy(d))
 d['status']='PHASE_COMPLETE_LOCAL_QUALITY_REVIEW_REQUIRED';persist(copy.deepcopy(d));return d
