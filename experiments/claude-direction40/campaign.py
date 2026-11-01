"""Bounded direction-specific and output-format-only experiments."""
from pathlib import Path
import importlib.util,json,copy,hashlib,time
ROOT=Path(__file__).resolve().parent
def load(n,p):
 s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
a=load('dir40_frozen',ROOT.parent/'claude-real20-120/adapters.py')
CONFIG=json.loads((ROOT/'config.json').read_text())
SCHEMA={'type':'json_schema','schema':{'type':'object','properties':{'translation':{'type':'string'}},'required':['translation'],'additionalProperties':False}}
def build(text,side,stage,engine,variant):
 q=a.build(text,side,stage,engine)
 if variant=='JSON':
  assert engine=='O';q['output_config']['format']=copy.deepcopy(SCHEMA)
 else:assert variant=='BASE'
 return q
def inspect(raw,text,side,stage,engine,variant):
 out=a.inspect(raw,text,side,stage,engine)
 if variant=='BASE':return out
 out['raw_visible_text']=''.join(x.get('text','') for x in raw.get('content',[]) if x.get('type')=='text')
 out['translation']='';out['schema_valid']=False
 if out['status']!='SUCCESS':return out
 def pairs(items):
  d={}
  for k,v in items:
   if k in d:raise ValueError('Duplicate JSON property')
   d[k]=v
  return d
 try:
  v=json.loads(out['raw_visible_text'],object_pairs_hook=pairs)
  assert isinstance(v,dict) and set(v)=={'translation'} and type(v['translation']) is str and v['translation'].strip()
  out.update(translation=v['translation'],schema_valid=True)
 except Exception:out.update(status='FAILED',parse_error='INVALID_SINGLE_TRANSLATION_JSON')
 return out
def authorize(x):
 expected={'authorized':True,'plan_id':CONFIG['plan_id'],'maximum_new_attempts':CONFIG['cap'],'whole_task_maximum':40,'manifest_sha256':CONFIG['manifest_sha256']}
 if x!=expected:raise PermissionError('Exact phase approval required')
def validate(m):
 assert a.core.digest(m)==CONFIG['manifest_sha256'] and m['id']==CONFIG['plan_id'] and m['cap']==CONFIG['cap']
 assert m['whole_task_maximum']==40 and m['prior_attempts']+m['cap']<=40
 assert len(m['cases'])*2==m['cap'] and len({x['id'] for x in m['cases']})==len(m['cases'])
 for p,h in m['frozen_file_sha256'].items():assert hashlib.sha256((ROOT.parent/p).read_bytes()).hexdigest()==h
 for c in m['cases']:
  assert c['development_allowed'] and hashlib.sha256(c['source'].encode()).hexdigest()==c['source_sha256']
  assert c['engine']==('S' if c['side']=='K' else 'O')
  if m['variant']=='JSON':assert c['side']=='L' and c['engine']=='O'
 return m['cases']
def run_approved(m,approval,transport,journal_path,persist=lambda d:None):
 authorize(approval);cases=validate(m)
 with Path(journal_path).open('x') as f:f.write('0\n')
 d={'plan_id':m['id'],'variant':m['variant'],'phase':m['phase'],'attempts':0,'prior_attempts':m['prior_attempts'],'cap':m['cap'],'retries':0,'per_engine':{'S':0,'O':0},'slots':[],'status':'RUNNING'}
 persist(copy.deepcopy(d))
 for c in cases:
  first=None
  for stage in ['first','back']:
   x={'slot':len(d['slots'])+1,'case_id':c['id'],'side':c['side'],'engine':c['engine'],'stage':stage,'attempted':False};d['slots'].append(x)
   if stage=='back' and first is None:x['status']='SKIPPED_DEPENDENCY';persist(copy.deepcopy(d));continue
   text=c['source'] if stage=='first' else first;q=build(text,c['side'],stage,c['engine'],m['variant'])
   assert d['attempts']<m['cap'] and d['attempts']+m['prior_attempts']<40
   assert q['model']==a.MODELS[c['engine']] and q['max_tokens']==2048 and q['output_config']['effort']=='low'
   assert q['thinking']=={'type':'between_tools' if c['engine']=='S' else 'adaptive'} and 'stream' not in q
   d['attempts']+=1;d['per_engine'][c['engine']]+=1
   x.update(attempted=True,attempt=d['attempts'],input=text,input_sha256=hashlib.sha256(text.encode()).hexdigest(),payload=q,payload_sha256=a.core.digest(q),status='SENT_OR_UNKNOWN')
   with Path(journal_path).open('a') as f:f.write(json.dumps({'attempt':d['attempts'],'payload_sha256':x['payload_sha256']})+'\n')
   persist(copy.deepcopy(d));started=time.perf_counter();raw={}
   try:
    raw=transport(q);x.update(response=raw,response_id=raw.get('id'),response_sha256=a.core.digest(raw),usage=raw.get('usage',{}),http_status=raw.get('http_status',200 if raw.get('type')=='message' else None),stop_reason=raw.get('stop_reason'))
    x['estimated_usd']=a.cost(x['usage'],c['engine']);x.update(inspect(raw,text,c['side'],stage,c['engine'],m['variant']))
    if x['http_status'] in [401,403] or (raw.get('type')=='message' and raw.get('model')!=q['model']):raise PermissionError('GLOBAL_AUTH_OR_MODEL_FAILURE')
    if stage=='first' and x['status']=='SUCCESS':first=x['translation']
   except PermissionError:
    d['status']='GLOBAL_SAFETY_STOP';persist(copy.deepcopy(d));raise
   except Exception as exc:x.update(status='FAILED',error_type=type(exc).__name__)
   finally:x['api_ms']=(time.perf_counter()-started)*1000;persist(copy.deepcopy(d))
 d['status']='PHASE_COMPLETE_LOCAL_QUALITY_REVIEW_REQUIRED';persist(copy.deepcopy(d));return d
