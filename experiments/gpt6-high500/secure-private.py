"""Protected Gemini private D3. Public issue contains RSA public handshake and ciphertext ONLY.
All personal input, requests and responses remain in ephemeral runner RAM/disk and encrypted artifact.
No retries, no plaintext GitHub logs, no accidental production writes.
"""
import base64,copy,hashlib,http.client,importlib.util,json,os,subprocess,sys,time,urllib.request,zlib
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.dont_write_bytecode=True
sp=importlib.util.spec_from_file_location('high500_crypto',ROOT.parent/'s47-realuse16/run.py')
b=importlib.util.module_from_spec(sp);sp.loader.exec_module(b)
b.PROTOCOL='gpt6-high500-private-v1'
ID='GPT6_HIGH500_20261106'; TAG='gpt6-high500-20261106-private-d3-consumed'
STATE=ROOT/'_private_state'
def check(x):
 if not x: raise ValueError('PRIVATE_D3_CONTRACT')
def sha(x):return hashlib.sha256(x.encode('utf8')).hexdigest()
def read(p):return json.loads(Path(p).read_text(encoding='utf8'))
def write(p,v):b.write(p,v)
def config():
 a=read(ROOT/'activation3.json')
 check(a['campaign']==ID and a['phase']=='PRIVATE_D3' and a['approved_total']==500 and a['prior_confirmed']==150 and a['phase_max']==120 and a['case_count']==30 and a['enabled'] is True)
 check(a['prior_confirmed']+a['phase_max']<=500)
 check(os.environ['GITHUB_REPOSITORY']==b.REPO and os.environ['GITHUB_REF_NAME']=='research/gpt6-high500-20261106' and os.environ['GITHUB_RUN_ATTEMPT']=='1')
 return a
def issue(a):
 i=b.github('/repos/'+b.REPO+'/issues/'+str(a['issue_number']))
 check(i['state']=='open' and i['user']['login']==b.OWNER and i['title']==a['issue_title'])
 d=json.loads(i['body'])
 check(d['protocol']==b.PROTOCOL and d['nonce']==a['nonce'] and len(d['nonce'])==64)
 check(d['plan_sha256']==a['plan_sha256'])
 check(d['result_public_key']==a['result_public_key'])
 b.public_key(d['result_public_key'])
 return i,d
def init(a):
 i,d=issue(a);check(d['phase']=='init')
 check(not STATE.exists());STATE.mkdir(mode=0o700)
 pub=b.keypair(STATE/'input-private.pem')
 h=dict(protocol=b.PROTOCOL,nonce=d['nonce'],run_id=os.environ['GITHUB_RUN_ID'],issue_number=i['number'],commit=os.environ['GITHUB_SHA'],input_public_key=pub,result_key_sha256=sha(d['result_public_key']))
 write(STATE/'handshake.json',h)
 write(STATE/'init.json',d)
 b.github('/repos/'+b.REPO+'/issues/'+str(i['number'])+'/comments',{'body':json.dumps(h,ensure_ascii=False)})
 print('D3 encrypted handshake public; generation attempts=0',flush=True)
 return h,d
def receive_plan(a,h,d):
 end=time.monotonic()+850
 while time.monotonic()<end:
  i,latest=issue(a)
  check(latest['nonce']==h['nonce'] and latest['result_public_key']==d['result_public_key'] and latest['plan_sha256']==d['plan_sha256'])
  if latest['phase']=='sealed':
   pack=b.unseal(latest['envelope'],STATE/'input-private.pem',b.aad_for(h,'input'))
   check(pack['format']=='zlib-json-v1')
   buf=zlib.decompress(base64.b64decode(pack['data']))
   check(len(buf)<120000 and hashlib.sha256(buf).hexdigest()==d['plan_sha256'])
   return json.loads(buf)
  check(latest['phase']=='init');time.sleep(4)
 raise TimeoutError('NO_SEALED_INPUT')
def validate(plan,a):
 check(set(plan)=={'campaign','phase','cases','repeat_policy'})
 check(plan['campaign']==ID and plan['phase']=='PRIVATE_D3' and plan['repeat_policy']=='NO_RETRIES')
 cs=plan['cases'];check(type(cs)is list and len(cs)==30)
 ids=set();n={'K':0,'L':0}
 for c in cs:
  check(set(c)=={'id','side','source','category'} and c['side'] in n and isinstance(c['source'],str) and bool(c['source'].strip()) and len(c['source'])<4000)
  check(isinstance(c['id'],str) and c['id'] not in ids);ids.add(c['id']);n[c['side']]+=1
 check(n=={'K':15,'L':15} and len(cs)*2*2==a['phase_max'])
 return True
class Node:
 def __init__(self):
  self.proc=subprocess.Popen(['node',str(ROOT/'private-worker.cjs')],cwd=ROOT.parent.parent,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True,encoding='utf8')
 def ask(self,q):
  self.proc.stdin.write(json.dumps(q,ensure_ascii=False)+'\n');self.proc.stdin.flush()
  r=json.loads(self.proc.stdout.readline());check(r['ok'])
  return r['value']
 def close(self):self.proc.terminate();self.proc.wait(timeout=10)
class Send:
 def __init__(self):self.conn=None
 def close(self):
  if self.conn:self.conn.close();self.conn=None
 def send(self,q,key):
  if not self.conn:self.conn=http.client.HTTPSConnection('generativelanguage.googleapis.com',timeout=90)
  body=json.dumps(q['payload'],ensure_ascii=False,separators=(',',':')).encode()
  start=time.perf_counter_ns()
  try:
   self.conn.request('POST','/v1beta/models/'+q['model']+':generateContent',body=body,headers={'x-goog-api-key':key,'Content-Type':'application/json'})
   res=self.conn.getresponse();wire=res.read();end=time.perf_counter_ns()
   if res.will_close:self.close()
   check(len(wire)<2000000)
   return {'http':res.status,'raw':json.loads(wire),'wire_request_utf8':body.decode(),'wire_response_utf8':wire.decode(),'api_ms':(end-start)/1e6}
  except Exception:self.close();raise
def price(raw):
 u=raw.get('usageMetadata')or{}
 p=u.get('promptTokenCount');v=u.get('candidatesTokenCount');t=u.get('thoughtsTokenCount');total=u.get('totalTokenCount');cache=u.get('cachedContentTokenCount')
 if not isinstance(t,int) and isinstance(total,int) and isinstance(p,int) and isinstance(v,int):t=total-p-v
 if not isinstance(p,int) or not isinstance(v,int) or not isinstance(t,int) or t<0:return None
 return ((p-(cache or 0))*.25+(cache or 0)*.025+(v+t)*1.5)/1e6
def execute():
 a=config(); h,d=init(a)
 result=dict(campaign=ID,phase=a['phase'],run_id=os.environ['GITHUB_RUN_ID'],approved=500,prior_confirmed=150,phase_cap=120,status='AWAITING_ENCRYPTED_INPUT',attempts=[],skipped=[],retry=0,judge=0,started_utc=time.time(),model='gemini-3.1-flash-lite')
 def persist():
  result['attempt_count']=len(result['attempts'])
  result['spent_or_reserved']=150+len(result['attempts'])
  result['remaining']=500-result['spent_or_reserved']
  write(ROOT/'results-d3.sealed.json',b.seal(result,d['result_public_key'],b.aad_for(h,'result')))
 persist()
 node=None;send=None
 try:
  plan=receive_plan(a,h,d);validate(plan,a)
  # Immutable once-only tag is created before any paid request, rejecting reruns.
  b.github('/repos/'+b.REPO+'/git/refs',{'ref':'refs/tags/'+TAG,'sha':h['commit']})
  key=os.environ.get('GEMINI_API_KEY');check(bool(key))
  node=Node();send=Send();result['status']='RUNNING';persist()
  def one(path,variant,visible,caseid,stage):
   check(len(result['attempts'])<a['phase_max'] and variant in ('KO_DEMO','LEAN_SCOPE'))
   q=node.ask({'mode':'build','path':path,'variant':variant,'text':visible})
   g=q['payload']['generationConfig']
   check(q['model']=='gemini-3.1-flash-lite' and g['maxOutputTokens']==1024 and g['thinkingConfig']['thinkingLevel']=='minimal' and 'temperature' not in g)
   item={'ordinal':151+len(result['attempts']),'caseid':caseid,'stage':stage,'path':path,'variant':variant,'actual_input':visible,'input_sha256':sha(visible),'request':q,'status':'SENT_OR_UNKNOWN','start_time':time.time()}
   result['attempts'].append(item);persist()
   try:
    packet=send.send(q,key);item['wire']=packet;item['raw']=packet['raw'];item['api_ms']=packet['api_ms']
    item['responseId']=packet['raw'].get('responseId');item['modelVersion']=packet['raw'].get('modelVersion');item['usage']=packet['raw'].get('usageMetadata',{});item['estimated_usd']=price(packet['raw'])
    if packet['http']!=200:raise ValueError('HTTP_FAILURE')
    if item['modelVersion'] and not item['modelVersion'].startswith('gemini-3.1-flash-lite'):raise ValueError('MODEL_MISMATCH')
    info=node.ask({'mode':'inspect','path':path,'variant':variant,'text':visible,'raw':packet['raw']})
    item['displayed']=info.get('displayed');item['status']=info['status'];item['failure_reason']=info.get('reason')
    return item['displayed'] if item['status']=='SUCCESS' else None
   except Exception as e:item['status']='FAILED';item['failure_type']=type(e).__name__;return None
   finally:
    item['end_time']=time.time();persist()
    if len(result['attempts'])%12==0:print('D3 calls',len(result['attempts']),'of',a['phase_max'],flush=True)
  for idx,c in enumerate(plan['cases']):
   p='KF' if c['side']=='K' else 'LF';back='KB' if c['side']=='K' else 'LB'
   order=('KO_DEMO','LEAN_SCOPE') if idx%2==0 else ('LEAN_SCOPE','KO_DEMO')
   for variant in order:
    first=one(p,variant,c['source'],c['id'],'FIRST')
    if first:one(back,variant,first,c['id'],'BACK')
    else:result['skipped'].append({'id':c['id'],'variant':variant,'stage':'BACK','reason':'FIRST_FAILED'});persist()
  result['status']='PHASE_COMPLETE_REVIEW_REQUIRED';result['finished_utc']=time.time();persist()
  print('D3 COMPLETE calls=',len(result['attempts']),'technical_success=',sum(x['status']=='SUCCESS' for x in result['attempts']),'retry=0',flush=True)
 except Exception as e:
  result['status']='HOLD_RUN_ERROR';result['error_type']=type(e).__name__;persist();print('D3 HOLD error_type=',type(e).__name__,flush=True);raise
 finally:
  if send:send.close()
  if node:node.close()
if __name__=='__main__':
 try:execute()
 except Exception as e:sys.exit(2)
