"""Effort-only approved56; independent BACK, phased caps, no retries."""
import copy,hashlib,importlib.util,json,time
from pathlib import Path
ROOT=Path(__file__).resolve().parent
def load(n,p):
 s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
a=load('effort56_frozen',ROOT.parent/'claude-real20-120/adapters.py')
CONFIG=json.loads((ROOT/'config.json').read_text())
def digest(x):return a.core.digest(x)
def authorize(x):
 if x!={'authorized':True,'campaign_id':'CLAUDE_EFFORT56_20261101','plan_id':CONFIG['plan_id'],'maximum_new_attempts':CONFIG['cap'],'whole_task_maximum':56,'Opus_maximum':32,'Sonnet_maximum':24,'manifest_sha256':CONFIG['manifest_sha256']}:raise PermissionError('Exact new phase approval required')
def schedule(cases,phase):
 out=[]
 for i,c in enumerate(cases):
  variants=['LOW','MEDIUM'] if i%2==0 else ['MEDIUM','LOW']
  if phase.startswith('A'):
   for v in variants:
    n=len(out)+1
    out.extend([dict(slot=n,id=c['id'],side='L',engine='O',variant=v,stage='first',effort=v.lower(),depends_on=None),dict(slot=n+1,id=c['id'],side='L',engine='O',variant=v,stage='back',effort='low',depends_on=n)])
  else:
   n=len(out)+1;out.append(dict(slot=n,id=c['id'],side='K',engine='S',variant='SHARED',stage='first',effort='low',depends_on=None))
   for v in variants:out.append(dict(slot=len(out)+1,id=c['id'],side='K',engine='S',variant=v,stage='back',effort=v.lower(),depends_on=n))
 return out
def build(text,side,stage,engine,effort):
 q=a.build(text,side,stage,engine);q['output_config']['effort']=effort;return q
def validate(m):
 assert digest(m)==CONFIG['manifest_sha256'] and m['id']==CONFIG['plan_id'] and m['phase']==CONFIG['phase']
 ph=m['phase'];cap={'A1':16,'A2':16,'B1':12,'B2':12}[ph]
 assert m['whole_task_maximum']==56 and m['Opus_maximum']==32 and m['Sonnet_maximum']==24 and m['cap']==CONFIG['cap']==cap
 assert m['prior_Opus_attempts']>=0 and m['prior_Sonnet_attempts']>=0
 assert m['prior_Opus_attempts']+m['prior_Sonnet_attempts']+cap<=56
 assert (m['prior_Opus_attempts']+cap<=32) if ph.startswith('A') else (m['prior_Sonnet_attempts']+cap<=24)
 assert len(m['cases'])==4 and len({c['id'] for c in m['cases']})==4
 assert m['schedule']==schedule(m['cases'],ph) and len(m['schedule'])==cap
 for p,h in m['frozen_file_sha256'].items():assert hashlib.sha256((ROOT.parent/p).read_bytes()).hexdigest()==h
 for c in m['cases']:
  assert set(c)=={'id','side','source','source_sha256','development_allowed'} and c['development_allowed'] is True
  assert c['side']==('L' if ph.startswith('A') else 'K') and hashlib.sha256(c['source'].encode()).hexdigest()==c['source_sha256']
 return {c['id']:c for c in m['cases']}
def run_approved(m,approval,transport,journal_path,persist=lambda d:None):
 authorize(approval);cases=validate(m)
 with Path(journal_path).open('x') as f:f.write('0\n')
 d=dict(plan_id=m['id'],phase=m['phase'],attempts=0,whole_task_maximum=56,prior_Opus_attempts=m['prior_Opus_attempts'],prior_Sonnet_attempts=m['prior_Sonnet_attempts'],retries=0,slots=[],status='RUNNING');by={};persist(copy.deepcopy(d))
 for planned in m['schedule']:
  x=dict(planned,attempted=False);d['slots'].append(x);by[x['slot']]=x
  if x['stage']=='back' and by[x['depends_on']]['status']!='SUCCESS':x.update(status='SKIPPED_DEPENDENCY');persist(copy.deepcopy(d));continue
  text=cases[x['id']]['source'] if x['stage']=='first' else by[x['depends_on']]['translation']
  q=build(text,x['side'],x['stage'],x['engine'],x['effort'])
  baseline=a.build(text,x['side'],x['stage'],x['engine']);baseline['output_config']['effort']=x['effort'];assert q==baseline
  assert d['attempts']<m['cap'] and d['attempts']+m['prior_Opus_attempts']+m['prior_Sonnet_attempts']<56
  assert q['model']==a.MODELS[x['engine']] and q['max_tokens']==2048 and q['thinking']=={'type':'adaptive' if x['engine']=='O' else 'between_tools'}
  d['attempts']+=1;x.update(attempt=d['attempts'],attempted=True,status='SENT_OR_UNKNOWN',input=text,input_sha256=hashlib.sha256(text.encode()).hexdigest(),payload=q,payload_sha256=digest(q))
  with Path(journal_path).open('a') as f:f.write(json.dumps({'attempt':d['attempts'],'slot':x['slot'],'payload_sha256':x['payload_sha256']})+'\n')
  persist(copy.deepcopy(d));start=time.perf_counter();raw={}
  try:
   raw=transport(q);x.update(response=raw,response_id=raw.get('id'),response_sha256=digest(raw),http_status=raw.get('http_status',200 if raw.get('type')=='message' else None),stop_reason=raw.get('stop_reason'),usage=raw.get('usage',{}));x['estimated_usd']=a.cost(x['usage'],x['engine'])
   if x['http_status'] in [401,403] or (raw.get('type')=='message' and raw.get('model')!=q['model']):raise PermissionError('Global auth/model mismatch')
   x.update(a.inspect(raw,text,x['side'],x['stage'],x['engine']))
  except PermissionError:d['status']='GLOBAL_SAFETY_STOP';persist(copy.deepcopy(d));raise
  except Exception as exc:x.update(status='FAILED',error_type=type(exc).__name__,raw_visible_text=''.join(b.get('text','') for b in raw.get('content',[]) if b.get('type')=='text'))
  finally:x['api_ms']=(time.perf_counter()-start)*1000;x.setdefault('estimated_usd',None);persist(copy.deepcopy(d))
 d['status']='PHASE_COMPLETE_LOCAL_QUALITY_REVIEW_REQUIRED';persist(copy.deepcopy(d));return d
