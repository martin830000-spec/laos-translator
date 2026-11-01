"""Two bounded16 phases, LA1 vs CP1, total Haiku32 inside whole56."""
from pathlib import Path
import importlib.util,json,hashlib,copy,time
ROOT=Path(__file__).resolve().parent
def load(n,p):
 s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
a=load('cp1_whole_interpretation',ROOT.parent/'haiku-cp1/adapter.py');f=load('cp1_frozen_cost',ROOT.parent/'claude-real20-120/adapters.py');CONFIG=json.loads((ROOT/'config.json').read_text())
def digest(x):return f.core.digest(x)
def build(text,side,stage,variant):
 if variant=='LA1':return a.la1.build_request(text,side,stage,'LA1')
 if variant=='CP1':return a.build_request(text,side,stage)
 raise ValueError('Unknown variant')
def inspect(raw,text,side,stage,v):return dict(a.la1.inspect_response(raw,text,side,stage,'LA1'),status='SUCCESS') if v=='LA1' else a.inspect_response(raw,text,side,stage)
def authorize(x):
 if x!={'authorized':True,'plan_id':CONFIG['plan_id'],'maximum_new_attempts':16,'whole_task_maximum':56,'maximum_Haiku_attempts':32,'manifest_sha256':CONFIG['manifest_sha256']}:raise PermissionError('Exact CP1 phase approval required')
def validate(m):
 assert digest(m)==CONFIG['manifest_sha256'] and m['id']==CONFIG['plan_id'] and m['phase']==CONFIG['phase']
 assert m['cap']==16 and m['Haiku_cap']==32 and m['whole_task_cap']==56 and m['prior_Haiku_attempts']+16<=32 and m['prior_cross_attempts']<=24 and m['prior_cross_attempts']+m['prior_Haiku_attempts']+16<=56
 assert len(m['cases'])==4 and sum(x['side']=='K' for x in m['cases'])==1 and len(m['schedule'])==16
 for p,h in m['frozen_file_sha256'].items():assert hashlib.sha256((ROOT.parent/p).read_bytes()).hexdigest()==h
 by={x['id']:x for x in m['cases']};assert len(by)==4
 for x in by.values():assert x['development_allowed'] and hashlib.sha256(x['source'].encode()).hexdigest()==x['source_sha256']
 for i,x in enumerate(m['schedule']):
  assert x['slot']==i+1 and x['variant'] in ['LA1','CP1'] and x['side']==by[x['id']]['side']
  if x['stage']=='first':assert x['depends_on'] is None and x['frozen_first_payload']==build(by[x['id']]['source'],x['side'],'first',x['variant'])
  else:
   assert x['stage']=='back';d=m['schedule'][x['depends_on']-1];assert d['stage']=='first' and d['slot']<x['slot'] and (d['id'],d['variant'],d['side'])==(x['id'],x['variant'],x['side'])
 return by
def run_approved(m,approval,transport,journal_path,persist=lambda d:None):
 authorize(approval);by=validate(m)
 with Path(journal_path).open('x') as ff:ff.write('0\n')
 d={'plan_id':m['id'],'phase':m['phase'],'attempts':0,'prior_Haiku_attempts':m['prior_Haiku_attempts'],'prior_cross_attempts':m['prior_cross_attempts'],'Haiku_cap':32,'whole_task_cap':56,'per_variant':{'LA1':0,'CP1':0},'per_engine':{'H':0},'retries':0,'status':'RUNNING','slots':[]};slots={};persist(copy.deepcopy(d))
 for planned in m['schedule']:
  x={k:v for k,v in planned.items() if k!='frozen_first_payload'};x.update(engine='H',attempted=False);d['slots'].append(x);slots[x['slot']]=x
  if x['stage']=='back' and slots[x['depends_on']]['status']!='SUCCESS':x.update(status='SKIPPED_DEPENDENCY');persist(copy.deepcopy(d));continue
  text=by[x['id']]['source'] if x['stage']=='first' else slots[x['depends_on']]['translation'];q=build(text,x['side'],x['stage'],x['variant'])
  assert d['attempts']<16 and d['attempts']+m['prior_Haiku_attempts']<32 and d['attempts']+m['prior_Haiku_attempts']+m['prior_cross_attempts']<56 and d['per_variant'][x['variant']]<8
  assert q['model']=='claude-haiku-5-5' and q['thinking']=={'type':'disabled'} and q['max_tokens']==2048 and q['output_config']['effort']=='low'
  d['attempts']+=1;d['per_variant'][x['variant']]+=1;d['per_engine']['H']+=1;x.update(attempt=d['attempts'],attempted=True,status='SENT_OR_UNKNOWN',input=text,input_sha256=hashlib.sha256(text.encode()).hexdigest(),payload=q,payload_sha256=digest(q))
  with Path(journal_path).open('a') as ff:ff.write(json.dumps({'attempt':d['attempts'],'payload_sha256':x['payload_sha256']})+'\n')
  persist(copy.deepcopy(d));start=time.perf_counter();raw={}
  try:
   raw=transport(q);x.update(response=raw,response_id=raw.get('id'),response_sha256=digest(raw),usage=raw.get('usage',{}),http_status=raw.get('http_status',200 if raw.get('type')=='message' else None),stop_reason=raw.get('stop_reason'));x['estimated_usd']=f.cost(x['usage'],'H')
   if x['http_status'] in [401,403] or (raw.get('type')=='message' and raw.get('model')!=q['model']):raise PermissionError('Global auth/model mismatch')
   x.update(inspect(raw,text,x['side'],x['stage'],x['variant']))
  except PermissionError:d['status']='GLOBAL_SAFETY_STOP';persist(copy.deepcopy(d));raise
  except Exception as exc:x.update(status='FAILED',error_type=type(exc).__name__,raw_visible_text=''.join(b.get('text','') for b in raw.get('content',[]) if b.get('type')=='text'))
  finally:x['api_ms']=(time.perf_counter()-start)*1000;x.setdefault('estimated_usd',None);persist(copy.deepcopy(d))
 d['status']='PHASE_COMPLETE_LOCAL_QUALITY_REVIEW_REQUIRED';persist(copy.deepcopy(d));return d
