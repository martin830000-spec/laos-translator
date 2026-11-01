"""Cross BACK only: immutable historical visible FIRST, bounded12 per phase."""
from pathlib import Path
import importlib.util,json,copy,hashlib,time
ROOT=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('cross56_frozen',ROOT.parent/'claude-real20-120/adapters.py');a=importlib.util.module_from_spec(s);s.loader.exec_module(a)
CONFIG=json.loads((ROOT/'config.json').read_text())
def authorize(x):
 if x!={'authorized':True,'plan_id':CONFIG['plan_id'],'maximum_new_attempts':12,'whole_task_maximum':56,'manifest_sha256':CONFIG['manifest_sha256']}:raise PermissionError('Exact new phase approval required')
def validate(m):
 assert a.core.digest(m)==CONFIG['manifest_sha256'] and m['id']==CONFIG['plan_id']
 assert m['cap']==12 and m['whole_task_maximum']==56 and m['cross_stage_maximum']==24 and m['new_FIRST']==0 and m['new_H_G_judge_probe_retry']==0
 assert m['prior_cross_attempts']+12<=24 and len(m['cases'])==12
 assert sum(x['engine']=='S' for x in m['cases'])==6 and len({(x['side'],x['id']) for x in m['cases']})==12
 for p,h in m['frozen_file_sha256'].items():assert hashlib.sha256((ROOT.parent/p).read_bytes()).hexdigest()==h
 for x in m['cases']:
  assert set(x)=={'id','side','engine','input','input_sha256','payload_sha256','first_origin_response_sha256'}
  assert x['engine']==('O' if x['side']=='K' else 'S')
  assert hashlib.sha256(x['input'].encode()).hexdigest()==x['input_sha256']
  assert a.core.digest(a.build(x['input'],x['side'],'back',x['engine']))==x['payload_sha256']
 return m['cases']
def run_approved(m,approval,transport,journal_path,persist=lambda d:None):
 authorize(approval);cases=validate(m)
 with Path(journal_path).open('x') as f:f.write('0\n')
 d={'plan_id':m['id'],'phase':m['phase'],'attempts':0,'prior_cross_attempts':m['prior_cross_attempts'],'cross_stage_cap':24,'whole_task_cap':56,'new_FIRST_calls':0,'per_engine':{'S':0,'O':0},'retries':0,'slots':[],'status':'RUNNING'};persist(copy.deepcopy(d))
 for c in cases:
  e=c['engine'];q=a.build(c['input'],c['side'],'back',e)
  assert d['attempts']<12 and d['attempts']+m['prior_cross_attempts']<24 and d['per_engine'][e]<6
  assert q['model']==a.MODELS[e] and q['max_tokens']==2048 and q['thinking']=={'type':'between_tools' if e=='S' else 'adaptive'} and q['output_config']=={'effort':'low'}
  d['attempts']+=1;d['per_engine'][e]+=1;x=dict(c,slot=len(d['slots'])+1,stage='back',attempt=d['attempts'],attempted=True,status='SENT_OR_UNKNOWN',payload=q);d['slots'].append(x)
  with Path(journal_path).open('a') as f:f.write(json.dumps({'attempt':d['attempts'],'payload_sha256':x['payload_sha256']})+'\n')
  persist(copy.deepcopy(d));start=time.perf_counter();raw={}
  try:
   raw=transport(q);x.update(response=raw,response_id=raw.get('id'),response_sha256=a.core.digest(raw),http_status=raw.get('http_status',200 if raw.get('type')=='message' else None),stop_reason=raw.get('stop_reason'),usage=raw.get('usage',{}));x['estimated_usd']=a.cost(x['usage'],e)
   if x['http_status'] in [401,403] or (raw.get('type')=='message' and raw.get('model')!=q['model']):raise PermissionError('Global auth/model mismatch')
   x.update(a.inspect(raw,c['input'],c['side'],'back',e))
  except PermissionError:d['status']='GLOBAL_SAFETY_STOP';persist(copy.deepcopy(d));raise
  except Exception as exc:x.update(status='FAILED',error_type=type(exc).__name__,raw_visible_text=''.join(b.get('text','') for b in raw.get('content',[]) if b.get('type')=='text'))
  finally:x['api_ms']=(time.perf_counter()-start)*1000;x.setdefault('estimated_usd',None);persist(copy.deepcopy(d))
 d['status']='PHASE_COMPLETE_LOCAL_QUALITY_REVIEW_REQUIRED';persist(copy.deepcopy(d));return d
