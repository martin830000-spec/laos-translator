"""Developer Direct2 no-model preflight. GitHub TEST only; public ASCII source.
Never print/store the Gemini API key, any part of it, its size, or hash.
"""
from __future__ import annotations
import base64,datetime,hashlib,json,os,pathlib,subprocess,tempfile,urllib.parse,urllib.request,urllib.error
BASE=pathlib.Path(__file__).resolve().parent
CAMP='GEMINI4_HYDROGEN_DEVELOPER_DIRECT2_20261122'
PREFIX='gemini4_hydrogen_developer_direct2_20261122/'
BUCKET='ko-lao-gemini35-tuning-460077888071'
PINS_SHA='a0ddc9924ccf7628fb609410726071a8106dccc4e488840ff47f4cb7d8cc5af7'
MAX={'POST':50,'GET':350,'LIST':10,'POST_BYTES':4*1024*1024}
MODEL='models/gemini-4-hydrogen'
MODEL_API='https://generativelanguage.googleapis.com/v1beta/'
sha=lambda x:hashlib.sha256(x).hexdigest()
canon=lambda x:(json.dumps(x,ensure_ascii=True,sort_keys=True,separators=(',',':'))+'\n').encode()
def need(x,s):
 if not x:raise RuntimeError(s)
def safe_context():
 need(os.getenv('GITHUB_REPOSITORY')=='martin830000-spec/laos-translator','REPOSITORY_FORBIDDEN')
 need(os.getenv('GITHUB_REF')=='refs/heads/research/gemini35-tuning-test','BRANCH_FORBIDDEN')
 need(os.getenv('GITHUB_RUN_ATTEMPT')=='1','RE_RUN_ATTEMPT_FORBIDDEN')
 need('/.github/workflows/gemini35-tuning-test.yml@' in os.getenv('GITHUB_WORKFLOW_REF',''),'EXACT_WIF_WORKFLOW_REQUIRED')
 need(os.getenv('DD2_BOOTSTRAP')=='true' and os.getenv('ENABLE_GENERATION')=='false' and os.getenv('ENABLE_TUNING')=='false','FREE_ONLY_REQUIRED')
class Net:
 def __init__(self,gcloud):self.gcloud=gcloud;self.count={'POST':0,'GET':0,'LIST':0,'POST_BYTES':0}
 def request(self,method,url,data=None):
  u=urllib.parse.urlsplit(url)
  need(u.scheme=='https' and u.hostname=='storage.googleapis.com','GCS_HOST_FORBIDDEN')
  need('/b/'+BUCKET+'/o' in u.path,'GCS_BUCKET_MISMATCH')
  if method=='POST':
   q=urllib.parse.parse_qs(u.query)
   need(u.path.startswith('/upload/storage/v1/b/'+BUCKET+'/o') and q.get('ifGenerationMatch')==['0'] and q.get('uploadType')==['media'] and q.get('name',[''])[0].startswith(PREFIX),'GCS_WRITE_FORBIDDEN')
   self.count['POST']+=1;self.count['POST_BYTES']+=len(data or b'')
  elif method=='GET':
   if u.path.endswith('/o'):self.count['LIST']+=1
   else:self.count['GET']+=1
  else:raise RuntimeError('GCS_METHOD_FORBIDDEN')
  need(all(self.count[k]<=MAX[k] for k in MAX),'GCS_LIMIT')
  r=urllib.request.Request(url,data=data,method=method,headers={'Authorization':'Bearer '+self.gcloud,'Accept':'application/json','Content-Type':'application/json'})
  try:
   with urllib.request.urlopen(r,timeout=50) as resp:return resp.status,resp.read(1_500_000)
  except urllib.error.HTTPError as e:return e.code,e.read(1_500_000)
  except Exception:raise RuntimeError('GCS_UNKNOWN_NO_RETRY') from None
 def base(self,name):return 'https://storage.googleapis.com/storage/v1/b/'+BUCKET+'/o/'+urllib.parse.quote(name,safe='')
 def read(self,name,gen=None):
  u=self.base(name);s,r=self.request('GET',u+'?fields=name%2Csize%2Cgeneration');need(s==200,'GCS_META_HTTP_'+str(s));j=json.loads(r)
  need(j.get('name')==name and (gen is None or str(j['generation'])==str(gen)),'GCS_META_DRIFT')
  qs='?'+urllib.parse.urlencode({'alt':'media','generation':j['generation']});s,b=self.request('GET',u+qs)
  need(s==200 and len(b)==int(j['size']),'GCS_BODY_DRIFT')
  return j,b
 def create(self,name,data,expect412=False):
  qs=urllib.parse.urlencode({'uploadType':'media','name':name,'ifGenerationMatch':0})
  u='https://storage.googleapis.com/upload/storage/v1/b/'+BUCKET+'/o?'+qs
  code,body=self.request('POST',u,data)
  need(code==(412 if expect412 else 200),'GCS_CREATE_HTTP_'+str(code))
  if expect412:return {'duplicate_blocked':True}
  j=json.loads(body);m,r=self.read(name,j['generation']);need(r==data,'READBACK_BYTES_SHA_BAD')
  return {'name':name,'generation':str(m['generation']),'size':len(data),'sha256':sha(data)}
 def list(self):
  qs=urllib.parse.urlencode({'prefix':PREFIX,'maxResults':100})
  status,body=self.request('GET','https://storage.googleapis.com/storage/v1/b/'+BUCKET+'/o?'+qs)
  need(status==200,'INVENTORY_HTTP');j=json.loads(body);need(not j.get('nextPageToken'),'INVENTORY_PAGINATED')
  return sorted(x['name'] for x in j.get('items',[]))
def dev_get(path):
 # key is retrieved only at call site and never stored in logs/receipts/artifacts
 need(path in ('models/gemini-4-hydrogen','models?pageSize=1000'),'DEV_GET_NOT_ALLOWED')
 url=MODEL_API+path
 req=urllib.request.Request(url,headers={'x-goog-api-key':os.environ['GEMINI_API_KEY'],'Accept':'application/json'},method='GET')
 try:
  with urllib.request.urlopen(req,timeout=45) as f:return f.status,f.read(300_000)
 except urllib.error.HTTPError as e:return e.code,e.read(300_000)
 except Exception:return None,b''
def model_discovery():
 # Only safe nonsensitive response fields are retained
 get_status,get_raw=dev_get('models/gemini-4-hydrogen')
 list_status,list_raw=dev_get('models?pageSize=1000')
 got={};listed={}
 try:
  if get_status==200:got=json.loads(get_raw)
 except Exception:pass
 try:
  if list_status==200:listed=json.loads(list_raw)
 except Exception:pass
 exact=got.get('name')==MODEL
 methods=got.get('supportedGenerationMethods') or []
 matching=[x for x in listed.get('models',[]) if isinstance(x,dict) and x.get('name')==MODEL]
 blocked=get_status in (401,403) or list_status in (401,403)
 active=exact or bool(matching)
 # if model is not in Developer model listing and cannot be looked up, no paid call
 return {'get_http':get_status,'list_http':list_status,'get_exact_model':exact,'listed_exact_model':bool(matching),'supported_generation_methods':methods if exact else [],'list_has_more_pages':bool(listed.get('nextPageToken')),'explicit_auth_or_permission_denial':blocked,'model_discovered':active,'billing_tier':'NOT_VERIFIABLE_FROM_MODEL_GET'}
def pin29(s):
 raw=(BASE/'dd2_pins29.json').read_bytes();need(sha(raw)==PINS_SHA,'PINS29_FILE_DRIFT');rows=json.loads(raw)
 need(len(rows)==len({x['object'] for x in rows})==29,'PINS29_COUNT')
 for o in rows:
  m,body=s.read(o['object'],o['generation'])
  need(int(m['size'])==o['bytes'] and sha(body)==o['sha256'],'PREVIOUS_LOCK_DRIFT')
  state=json.loads(body)
  need(state.get('enabled') is False and state.get('max_new')==0 and state.get('next_new_authorization')==0,'PREVIOUS_LOCK_REOPENED')
 return True
def main():
 safe_context();secret_present=bool(os.environ.get('GEMINI_API_KEY'))
 print('SECRET_PRESENT='+('true' if secret_present else 'false'),flush=True)
 token=subprocess.check_output(['gcloud','auth','print-access-token'],text=True,stderr=subprocess.DEVNULL,timeout=35).strip()
 need(len(token)>30,'WIF_GCS_TOKEN_ABSENT');n=Net(token)
 need(n.list()==[],'CAMPAIGN_PREFIX_COLLISION_EXISTING')
 pin29(n)
 discover=model_discovery() if secret_present else {'get_http':None,'list_http':None,'model_discovered':False,'billing_tier':'NOT_VERIFIABLE','why':'SECRET_ABSENT'}
 allow=bool(secret_present and discover['model_discovered'] and not discover.get('explicit_auth_or_permission_denial') and (not discover.get('list_has_more_pages') or discover.get('get_exact_model')))
 if not allow:
  reason='SECRET_ABSENT' if not secret_present else 'DEVELOPER_MODEL_NOT_DISCOVERED_OR_BLOCKED'
  state={'schema':'DD2_FINAL_STATE','campaign_id':CAMP,'terminal':True,'enabled':False,'max_new':0,'next_new_authorization':0,'status':'BLOCKED_FREE_PREFLIGHT','first_failure':reason,'model_calls':0,'unused_locked':2,'secret_present':secret_present,'developer_model_discovery':discover,'protected29_unmodified':True}
  receipt=n.create(PREFIX+'actual/_control/FINAL_STATE.json',canon(state))
  output={'schema':'DD2_BOOTSTRAP_PUBLIC','status':'BLOCKED_0_PAID','reason':reason,'secret_present':secret_present,'discovery':discover,'new_lock':receipt,'old_pins29_pass':True,'model_generation_calls':0,'gcs':n.count}
 else:
  smoke=n.create(PREFIX+'_freeqa/SMOKE.json',canon({'synthetic':True,'model_calls':0,'campaign_id':CAMP,'gcs_create_only':True}))
  n.create(PREFIX+'_freeqa/SMOKE.json',b'poison',expect412=True)
  _,read=n.read(PREFIX+'_freeqa/SMOKE.json',smoke['generation']);need(sha(read)==smoke['sha256'],'CREATE_ONLY_412_FAILED')
  with tempfile.TemporaryDirectory() as d:
   key=pathlib.Path(d)/'key.pem';cert=pathlib.Path(d)/'cert.pem'
   subprocess.run(['openssl','genpkey','-algorithm','RSA','-pkeyopt','rsa_keygen_bits:3072','-out',str(key)],check=True,capture_output=True,timeout=50)
   subprocess.run(['openssl','req','-new','-x509','-key',str(key),'-subj','/CN=DeveloperDirect2-Input','-days','3','-out',str(cert)],check=True,capture_output=True,timeout=30)
   certb=cert.read_bytes()
   keyreceipt=n.create(PREFIX+'_control/INPUT_PRIVATE_RSA_3072.pem',key.read_bytes())
  state={'schema':'DD2_BOOTSTRAP_STATE','campaign_id':CAMP,'phase':'FREE_READY','enabled':False,'max_new':0,'next_new_authorization':0,'model_calls':0,'protected29_unmodified':True,'secret_present':True,'developer_model_discovery':discover,'input_private_key':keyreceipt,'input_public_certificate_base64':base64.b64encode(certb).decode(),'smoke_receipt':smoke,'created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}
  state_receipt=n.create(PREFIX+'_control/BOOTSTRAP_STATE.json',canon(state))
  output={'schema':'DD2_BOOTSTRAP_PUBLIC','status':'BOOTSTRAP_FREE_READY','secret_present':True,'discovery':discover,'new_key':keyreceipt,'boot_state':state_receipt,'old_pins29_pass':True,'model_generation_calls':0,'gcs':n.count,'input_public_certificate_base64':base64.b64encode(certb).decode()}
 out=os.environ.get('DD2_BOOTSTRAP_RECEIPT');need(bool(out) and os.path.isabs(out),'BOOTSTRAP_OUTPUT_NOT_ABSOLUTE')
 pathlib.Path(out).write_bytes(canon(output))
 public={k:v for k,v in output.items() if k!='input_public_certificate_base64'}
 print('DD2_BOOTSTRAP_PUBLIC_RECEIPT '+json.dumps(public,sort_keys=True),flush=True)
if __name__=='__main__':main()
