"""Synthetic-only preflight. No model-generation implementation or API key access."""
from __future__ import annotations
import concurrent.futures, dataclasses, hashlib, json, os, pathlib, re, subprocess
import sys, threading, urllib.error, urllib.parse, urllib.request, unittest

ROOT = pathlib.Path(__file__).resolve().parent
CAMPAIGN = 'KO_LAO_ASSISTED4_FREE_PREFLIGHT_R1_20261122'
PREFIX = 'ko_lao_assisted4_free_preflight_r1_20261122/'
BUCKET = 'ko-lao-gemini35-tuning-460077888071'
BRANCH = 'refs/heads/research/gemini35-tuning-test'
WORKFLOW = '.github/workflows/assisted4-free-preflight-20261122.yml'
MODEL_URLS = [
 'https://us-aiplatform.googleapis.com/v1/projects/460077888071/locations/us/publishers/google/models/gemini-3.5-flash-lite',
 'https://us-aiplatform.googleapis.com/v1/publishers/google/models/gemini-3.5-flash-lite',
 'https://us-aiplatform.googleapis.com/v1/projects/460077888071/locations/us/endpoints/1638501023804817408',
]
BACK_RULE = {'KB':'Translate the supplied Lao text into Korean only.',
             'LB':'Translate the supplied Korean text into Lao only.'}
CAP = {'GET':350, 'POST':16, 'POST_BYTES':200000}
def sha(data): return hashlib.sha256(data).hexdigest()
def canon(x): return (json.dumps(x, ensure_ascii=False, sort_keys=True, separators=(',',':'))+'\n').encode()
def need(condition, code):
 if not condition: raise RuntimeError(code)

def usable(text, finish='STOP', status='SUCCESS'):
 return (status == 'SUCCESS' and finish == 'STOP' and isinstance(text,str)
         and bool(text.strip()) and re.fullmatch(r'(?:\s*0\s*){8,}',text) is None)

@dataclasses.dataclass(frozen=True)
class First:
 slot: str
 model: str
 direction: str
 text: str
 finish: str = 'STOP'
 status: str = 'SUCCESS'

class MockEngine:
 """Only synthetic output; durable intent behavior represented by shared state."""
 def __init__(self, state=None):
  self.state = state if state is not None else {'intents':set(), 'first':{}, 'requests':[]}
 def reserve(self, slot):
  need(slot not in self.state['intents'],'DUPLICATE_OR_UNKNOWN_SEND_FORBIDDEN')
  self.state['intents'].add(slot)
 def first(self, slot, model, direction, source, expected_sha, text, finish='STOP', status='SUCCESS'):
  need(sha(source.encode()) == expected_sha,'SOURCE_SHA_MISMATCH')
  need(direction in ('KF','LF'),'FIRST_DIRECTION')
  self.reserve(slot)
  self.state['requests'].append({'slot':slot,'kind':'FIRST','input':source,'model':model})
  result=First(slot,model,direction,text,finish,status)
  self.state['first'][slot]=result
  return result
 def back(self, parent, model):
  need(self.state['first'].get(parent.slot) == parent,'PARENT_CHANGED_OR_MISSING')
  need(parent.model == model,'MODEL_PAIR_CHANGED')
  if not usable(parent.text,parent.finish,parent.status): return None
  slot=parent.slot+'/BACK'; self.reserve(slot)
  direction='KB' if parent.direction=='KF' else 'LB'
  payload={'systemInstruction':BACK_RULE[direction], 'contents':[{'role':'user','parts':[{'text':parent.text}]}]}
  self.state['requests'].append({'slot':slot,'kind':'BACK','model':model,'direction':direction,'payload':payload,'parent_sha256':sha(parent.text.encode())})
  return payload
 def real_generate(self, *args, **kwargs): raise RuntimeError('GENERATION_NOT_IMPLEMENTED_OR_AUTHORIZED')

def synthetic_plan():
 return [{'case':f'SYN{i:02}', 'direction':'KF' if i<4 else 'LF', 'model':m,
          'attempt':n,'arm':'A' if n%2 else 'B', 'source':f'SYNTHETIC INPUT {i} {"A" if n%2 else "B"}'}
         for i in range(8) for m in ('BASE35','BASE38') for n in range(1,5)]

def synthetic_chains():
 e=MockEngine();plan=synthetic_plan()
 for row in plan:
  slot=f'{row["case"]}/{row["model"]}/{row["attempt"]}'
  p=e.first(slot,row['model'],row['direction'],row['source'],sha(row['source'].encode()),'  SYNTHETIC FIRST '+slot+'\n')
  body=e.back(p,row['model'])
  need(body['contents'][0]['parts'][0]['text']==p.text,'BACK_BYTE_DRIFT')
  need(row['source'] not in json.dumps(body),'BACK_SOURCE_CONTAMINATION')
 need(len(e.state['requests'])==128,'MOCK_REQUEST_COUNT')
 return {'synthetic_chains':64,'mock_requests':128,'real_model_requests':0,'tuning_requests':0,
         'first_paths':{'KF':32,'LF':32},'back_paths':{'KB':32,'LB':32}}

class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,*args,**kwargs): raise RuntimeError('REDIRECT_FORBIDDEN')

class Network:
 def __init__(self, token, counters=None, mutex=None):
  self.token=token; self.counts=counters if counters is not None else dict.fromkeys(CAP,0)
  self.mutex=mutex or threading.Lock();self.opener=urllib.request.build_opener(NoRedirect())
 def validate(self,method,url):
  u=urllib.parse.urlsplit(url);q=urllib.parse.parse_qs(u.query)
  need(u.scheme=='https' and not u.username and not u.password,'URL_SCHEME')
  if u.hostname=='storage.googleapis.com':
   if method=='POST':
    need(u.path==f'/upload/storage/v1/b/{BUCKET}/o' and q.get('uploadType')==['media']
         and q.get('ifGenerationMatch')==['0'] and q.get('name',[''])[0].startswith(PREFIX),'GCS_CREATE_ONLY_NEW_PREFIX')
   else:
    need(method=='GET' and u.path.startswith(f'/storage/v1/b/{BUCKET}/o/'),'GCS_GET_OBJECT_ONLY')
  else: need(method=='GET' and url in MODEL_URLS,'ALL_GENERATION_AND_FOREIGN_NETWORK_BLOCKED')
 def req(self,method,url,data=None):
  self.validate(method,url)
  with self.mutex:
   self.counts[method]+=1
   if method=='POST': self.counts['POST_BYTES']+=len(data or b'')
   need(all(self.counts[k]<=CAP[k] for k in CAP),'NETWORK_CAP')
  request=urllib.request.Request(url,data=data,method=method,headers={'Authorization':'Bearer '+self.token,'Content-Type':'application/json'})
  try:
   with self.opener.open(request,timeout=45) as r: return r.status,r.read(1_000_001)
  except urllib.error.HTTPError as e: return e.code,e.read(1_000_001)
  except Exception: raise RuntimeError('NETWORK_UNKNOWN_NO_AUTOMATIC_RETRY') from None
 def read(self,name,pin=None):
  url=f'https://storage.googleapis.com/storage/v1/b/{BUCKET}/o/'+urllib.parse.quote(name,safe='')
  s,b=self.req('GET',url+'?fields=name%2Csize%2Cgeneration');need(s==200,'GCS_META_'+str(s))
  m=json.loads(b);need(m['name']==name,'GCS_NAME')
  if pin: need(str(m['generation'])==str(pin),'GENERATION_DRIFT')
  s,b=self.req('GET',url+'?'+urllib.parse.urlencode({'alt':'media','generation':m['generation']}))
  need(s==200 and len(b)==int(m['size']),'GCS_READBACK')
  return {'object':name,'generation':str(m['generation']),'bytes':len(b),'sha256':sha(b)},b
 def create_url(self,name):
  return f'https://storage.googleapis.com/upload/storage/v1/b/{BUCKET}/o?'+urllib.parse.urlencode({'uploadType':'media','name':name,'ifGenerationMatch':'0'})
 def create(self,name,obj):
  data=canon(obj);s,b=self.req('POST',self.create_url(name),data)
  need(s==200,'CREATE_'+str(s));m=json.loads(b)
  rec,read=self.read(name,m['generation']);need(read==data,'CREATE_READBACK_MISMATCH')
  return rec

def protect(net,pins):
 out=[]
 for pin in pins:
  receipt,raw=net.read(pin['object'],pin['generation'])
  need(receipt['sha256']==pin['sha256'] and receipt['bytes']==pin['bytes'],'PROTECTED_BYTES_CHANGED')
  out.append(receipt)
 return out

class Tests(unittest.TestCase):
 def setUp(self): self.e=MockEngine()
 def parent(self,**kw):
  return self.e.first('s','BASE35','KF','SYNTHETIC ORIGINAL',sha(b'SYNTHETIC ORIGINAL'),**kw)
 def test_full_schedule(self): self.assertEqual(synthetic_chains()['mock_requests'],128)
 def test_four_attempt_order(self):
  for i in range(0,64,4): self.assertEqual([(x['attempt'],x['arm']) for x in synthetic_plan()[i:i+4]],[(1,'A'),(2,'B'),(3,'A'),(4,'B')])
 def test_source_tamper(self):
  with self.assertRaisesRegex(RuntimeError,'SOURCE_SHA'): self.e.first('s','BASE35','KF','X',sha(b'Y'),'Z')
  self.assertEqual(len(self.e.state['requests']),0)
 def test_back_exact_parent_with_whitespace(self):
  p=self.parent(text='  SYN FIRST\n');body=self.e.back(p,'BASE35')
  self.assertEqual(body,{'systemInstruction':BACK_RULE['KB'],'contents':[{'role':'user','parts':[{'text':'  SYN FIRST\n'}]}]})
 def test_parent_tamper(self):
  p=self.parent(text='FIRST')
  with self.assertRaisesRegex(RuntimeError,'PARENT_CHANGED'): self.e.back(dataclasses.replace(p,text='EDITED'),'BASE35')
 def test_model_pair(self):
  p=self.parent(text='FIRST')
  with self.assertRaisesRegex(RuntimeError,'MODEL_PAIR'): self.e.back(p,'BASE38')
 def test_invalid_first_no_child(self):
  for text,finish,status in [('','STOP','SUCCESS'),('   ','STOP','SUCCESS'),('0 '*31,'STOP','SUCCESS'),('X','MAX_TOKENS','SUCCESS'),('X','STOP','HTTP_ERROR'),('X','STOP','UNKNOWN'),('X','STOP','CANCELLED')]:
   self.e=MockEngine();p=self.parent(text=text,finish=finish,status=status)
   self.assertIsNone(self.e.back(p,'BASE35'));self.assertEqual(len(self.e.state['requests']),1)
 def test_unknown_restart_no_resend(self):
  self.parent(text='',status='UNKNOWN');restarted=MockEngine(self.e.state)
  with self.assertRaisesRegex(RuntimeError,'DUPLICATE'): restarted.first('s','BASE35','KF','SYNTHETIC ORIGINAL',sha(b'SYNTHETIC ORIGINAL'),'RETRY')
 def test_ack_loss_intent_no_resend(self):
  self.e.reserve('s');restarted=MockEngine(self.e.state)
  with self.assertRaisesRegex(RuntimeError,'DUPLICATE'): restarted.reserve('s')
  self.assertEqual(len(self.e.state['requests']),0)
 def test_cancel_restart_no_resend(self):
  self.parent(text='',status='CANCELLED')
  with self.assertRaisesRegex(RuntimeError,'DUPLICATE'): MockEngine(self.e.state).reserve('s')
 def test_back_duplicate_no_resend(self):
  p=self.parent(text='FIRST');self.e.back(p,'BASE35')
  with self.assertRaisesRegex(RuntimeError,'DUPLICATE'): self.e.back(p,'BASE35')
 def test_script_mix_not_filtered(self): self.assertTrue(usable('SYN Thai ไทย Lao ລາວ'))
 def test_real_generation_never(self):
  with self.assertRaisesRegex(RuntimeError,'NOT_IMPLEMENTED'): self.e.real_generate()
 def test_network_permissions(self):
  n=Network('SYNTHETIC_NOT_TOKEN')
  for method,url in [('POST',MODEL_URLS[0]+':generateContent'),('GET','https://example.com'),('DELETE',n.create_url(PREFIX+'x')),('POST',n.create_url('prior_campaign/x')),('POST',n.create_url(PREFIX+'x').replace('ifGenerationMatch=0','ifGenerationMatch=1'))]:
   with self.assertRaises(RuntimeError): n.validate(method,url)
  n.validate('POST',n.create_url(PREFIX+'synthetic/x'))
  for u in MODEL_URLS:n.validate('GET',u)
  self.assertEqual(n.counts,dict.fromkeys(CAP,0))

def run_tests():
 suite=unittest.defaultTestLoader.loadTestsFromTestCase(Tests)
 result=unittest.TextTestRunner(verbosity=1).run(suite)
 need(result.wasSuccessful(),'OFFLINE_TESTS_FAILED')
 return {'tests':result.testsRun,'passed':result.wasSuccessful(),**synthetic_chains()}

def remote():
 need(os.getenv('ENABLE_GENERATION')=='false' and os.getenv('ENABLE_TUNING')=='false','GENERATION_ENV')
 need(not os.getenv('GEMINI_API_KEY'),'API_KEY_NOT_NEEDED')
 need(os.getenv('GITHUB_REPOSITORY')=='martin830000-spec/laos-translator' and os.getenv('GITHUB_REF')==BRANCH,'TEST_CONTEXT')
 need(os.getenv('GITHUB_RUN_ATTEMPT')=='1','NO_RERUN')
 need('/'+WORKFLOW+'@' in os.getenv('GITHUB_WORKFLOW_REF',''),'WORKFLOW_CONTEXT')
 report={'campaign_id':CAMPAIGN,'run_id':os.getenv('GITHUB_RUN_ID'),'commit':os.getenv('GITHUB_SHA'),'new_generation_requests':0,'tuning_requests':0,'model_cost_usd':0,'infrastructure_billing':'NOT_VERIFIED','tests':run_tests()}
 token=subprocess.check_output(['gcloud','auth','print-access-token'],text=True,stderr=subprocess.DEVNULL).strip()
 need(bool(token),'AUTH_EMPTY');net=Network(token)
 pins=json.loads((ROOT/'protected_pins.json').read_text());need(len(pins)==32,'PINS_COUNT')
 claimed=False
 try:
  report['protected_before']=protect(net,pins)
  report['claim']=net.create(PREFIX+'_control/FREE_ONLY_CLAIM.json',{'campaign_id':CAMPAIGN,'run_id':report['run_id'],'enabled':False,'max_new':0});claimed=True
  report['synthetic_roundtrip']=net.create(PREFIX+'synthetic/roundtrip.json',{'synthetic':True,'data':['alpha',0,False],'generation_requests':0})
  race=PREFIX+'synthetic/two_clients_claim.json';barrier=threading.Barrier(2)
  def compete(i):
   client=Network(token,net.counts,net.mutex);payload=canon({'synthetic':True,'client':i});barrier.wait(timeout=10)
   status,raw=client.req('POST',client.create_url(race),payload)
   return {'client':i,'status':status,'payload_sha256':sha(payload)}
  with concurrent.futures.ThreadPoolExecutor(2) as pool: contenders=list(pool.map(compete,[1,2]))
  need(sorted(x['status'] for x in contenders)==[200,412],'CREATE_ONLY_RACE')
  rr,rb=net.read(race);need(rr['sha256']==next(x['payload_sha256'] for x in contenders if x['status']==200),'RACE_WINNER_BYTES')
  report['race']={'clients':contenders,'winner_readback':rr,'automatic_retry':False}
  report['model_metadata_gets']=[]
  for url in MODEL_URLS:
   status,raw=net.req('GET',url)
   j=json.loads(raw) if status==200 else {}
   report['model_metadata_gets'].append({'url':url,'status':status,'body_sha256':sha(raw),'name':j.get('name'),'supported_actions':j.get('supportedActions'),'deployed_model_names':[x.get('model') for x in j.get('deployedModels',[])]})
  report['protected_after']=protect(net,pins)
  need(report['protected_before']==report['protected_after'],'PROTECTED_BEFORE_AFTER')
  report['status']='REMOTE_SYNTHETIC_PASS'
 except Exception as e:
  report['status']='BLOCKED';report['error_code']=str(e) if isinstance(e,RuntimeError) else type(e).__name__
 finally:
  report['network_counts_before_final']=dict(net.counts)
  if claimed:
   try:
    report['final_lock']=net.create(PREFIX+'_control/FINAL_STATE.json',{'campaign_id':CAMPAIGN,'status':report.get('status','BLOCKED'),'enabled':False,'max_new':0,'next_new_authorization':0,'generation_calls':0,'tuning_calls':0,'run_id':report['run_id']})
    report['remote_report']=net.create(PREFIX+'evidence/REMOTE_REPORT.json',report)
   except Exception as e: report['closure_error']=str(e) if isinstance(e,RuntimeError) else type(e).__name__;report['status']='BLOCKED'
  report['network_counts_total']=dict(net.counts)
  out=pathlib.Path(os.environ['REPORT_PATH']);out.write_bytes(canon(report))
  print(json.dumps({'status':report['status'],'generation_calls':0,'tuning_calls':0,'report_sha256':sha(out.read_bytes()),'network_counts':net.counts},sort_keys=True))
 need(report['status']=='REMOTE_SYNTHETIC_PASS','REMOTE_PREFLIGHT_BLOCKED')

if __name__=='__main__':
 if len(sys.argv)>1 and sys.argv[1]=='remote':remote()
 else:print(json.dumps(run_tests(),sort_keys=True))
