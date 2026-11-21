"""GEMINI4_HYDROGEN_SCREEN64_20261121 free-only bootstrap. No model generation or private user text."""
import base64,hashlib,json,os,pathlib,subprocess,tempfile,urllib.parse,urllib.request,urllib.error
CAMP='GEMINI4_HYDROGEN_SCREEN64_20261121'
PREFIX='gemini4_hydrogen_screen64_20261121/'
BUCKET='ko-lao-gemini35-tuning-460077888071'
KEY=PREFIX+'_control/INPUT_PRIVATE_RSA_3072.pem'
STATE=PREFIX+'_control/BOOTSTRAP_STATE.json'
PINS=pathlib.Path(__file__).with_name('pins26.json')
sha=lambda b:hashlib.sha256(b).hexdigest()
def canonical(x):return (json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False)+'\n').encode()
def ensure(b,msg):
 if not b:raise RuntimeError(msg)
class Network:
 def __init__(self,token):self.t=token;self.c={'POST':0,'GET':0,'LIST':0,'POST_BYTES':0}
 def send(self,m,u,data=None):
  v=urllib.parse.urlsplit(u);ensure(v.scheme=='https' and v.hostname in ('storage.googleapis.com','aiplatform.us.rep.googleapis.com'),'URL_DENIED')
  if ':generateContent' in u or ':predict' in u:raise RuntimeError('MODEL_GENERATION_DENIED_FREE')
  if v.hostname=='storage.googleapis.com':
   if m=='POST':
    ensure(v.path.startswith('/upload/storage/v1/b/'+BUCKET+'/o') and urllib.parse.parse_qs(v.query).get('ifGenerationMatch')==['0'] and urllib.parse.parse_qs(v.query).get('name',[''])[0].startswith(PREFIX),'GCS_MUTATION_DENIED')
    self.c['POST']+=1;self.c['POST_BYTES']+=len(data or b'')
   elif m=='GET':
    if v.path.endswith('/o'):self.c['LIST']+=1
    else:self.c['GET']+=1
   else:raise RuntimeError('GCS_METHOD_DENIED')
   ensure(self.c['POST']<=350 and self.c['GET']<=1500 and self.c['LIST']<=20 and self.c['POST_BYTES']<=16*1024*1024,'BUDGET_LIMIT')
  else:ensure(m=='GET' and v.path.startswith('/v1beta1/projects/460077888071/locations/us/publishers/google/models/'),'VERTEX_FREE_ONLY_GET_DENIED')
  r=urllib.request.Request(u,headers={'Authorization':'Bearer '+self.t,'Accept':'application/json','Content-Type':'application/octet-stream'},data=data,method=m)
  try:
   with urllib.request.urlopen(r,timeout=45) as a:return a.status,a.read(150000)
  except urllib.error.HTTPError as e:return e.code,e.read(150000)
  except Exception:raise RuntimeError('NETWORK_ACK_UNKNOWN_NO_RETRY') from None
 def meta(self,n):return 'https://storage.googleapis.com/storage/v1/b/'+BUCKET+'/o/'+urllib.parse.quote(n,safe='')+'?fields=name%2Csize%2Cgeneration'
 def media(self,n,g):return 'https://storage.googleapis.com/storage/v1/b/'+BUCKET+'/o/'+urllib.parse.quote(n,safe='')+'?'+urllib.parse.urlencode({'alt':'media','generation':g})
 def read(self,n,gen=None):
  s,raw=self.send('GET',self.meta(n));ensure(s==200,'META_HTTP_'+str(s));j=json.loads(raw)
  ensure(j.get('name')==n and (gen is None or str(j['generation'])==str(gen)),'META_IDENTITY_DRIFT')
  code,body=self.send('GET',self.media(n,j['generation']));ensure(code==200 and len(body)==int(j['size']),'BODY_MISMATCH')
  return j,body
 def create(self,n,b,may_duplicate=False):
  u='https://storage.googleapis.com/upload/storage/v1/b/'+BUCKET+'/o?'+urllib.parse.urlencode({'uploadType':'media','name':n,'ifGenerationMatch':0})
  status,out=self.send('POST',u,b);ensure(status==(412 if may_duplicate else 200),'GCS_CREATE_EXPECTED_'+str(status))
  if status==412:return {'duplicate_refused':True}
  j=json.loads(out);m,got=self.read(n,j['generation']);ensure(got==b,'CREATE_READBACK_BAD')
  return {'name':n,'generation':str(j['generation']),'bytes':len(b),'sha256':sha(b)}
def main():
 ensure(os.environ.get('H64_BOOTSTRAP')=='true' and os.environ.get('ENABLE_GENERATION')=='false' and os.environ.get('ENABLE_TUNING')=='false','BOOTSTRAP_ENV_DENIED')
 token=subprocess.check_output(['gcloud','auth','print-access-token'],text=True,stderr=subprocess.DEVNULL,timeout=25).strip();ensure(len(token)>30,'WIF_TOKEN_ABSENT')
 t=Network(token);url='https://storage.googleapis.com/storage/v1/b/'+BUCKET+'/o?'+urllib.parse.urlencode({'prefix':PREFIX,'maxResults':500});status,raw=t.send('GET',url);ensure(status==200,'PREFIX_LIST_FAILED');listing=json.loads(raw);ensure(not listing.get('items') and not listing.get('nextPageToken'),'EXISTING_CAMPAIGN_NO_NEW_SESSION')
 pins=json.loads(PINS.read_text());ensure(len(pins)==26 and len({x['object'] for x in pins})==26,'PINS_COUNT')
 for row in pins:
  m,body=t.read(row['object'],row['generation']);ensure(len(body)==row['bytes'] and sha(body)==row['sha256'],'PIN_DRIFT')
  v=json.loads(body);ensure(v.get('enabled') is False and v.get('max_new')==0 and v.get('next_new_authorization')==0,'PIN_REOPENED')
 identity={}
 for name in ('gemini-3.8-flash','gemini-4-hydrogen'):
  path=f'projects/460077888071/locations/us/publishers/google/models/{name}'
  s,body=t.send('GET','https://aiplatform.us.rep.googleapis.com/v1beta1/'+path)
  identity[name]={'read_only_get_http':s,'response_sha256':sha(body),'response_bytes':len(body),'publisher_resource':path}
  ensure(s in (200,404,403),'UNEXPECTED_MODEL_DISCOVERY_HTTP')
 smoke=PREFIX+'_freeqa/SMOKE.json';sr=t.create(smoke,canonical({'schema':'H64_SMOKE','synthetic':True,'no_model_generation':True,'gcs_create_only':True}));t.create(smoke,b'poison',may_duplicate=True);_,got=t.read(smoke);ensure(sha(got)==sr['sha256'],'DUPLICATE_OVERWRITE')
 with tempfile.TemporaryDirectory() as td:
  k=pathlib.Path(td)/'priv.pem';crt=pathlib.Path(td)/'public.crt'
  subprocess.run(['openssl','genpkey','-algorithm','RSA','-pkeyopt','rsa_keygen_bits:3072','-out',str(k)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=30)
  subprocess.run(['openssl','req','-new','-x509','-key',str(k),'-subj','/CN=Hydrogen64-R6-private-input','-days','3','-out',str(crt)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=20)
  key_bytes=k.read_bytes();cert=crt.read_bytes()
  keyreceipt=t.create(KEY,key_bytes)
 info={'schema':'H64_BOOTSTRAP_STATE','campaign_id':CAMP,'enabled':False,'max_new':0,'next_new_authorization':0,'phase':'FREE_BOOTSTRAP_ONLY','input_private_key':keyreceipt,'public_certificate_base64':base64.b64encode(cert).decode(),'protected26':True,'models':identity,'synthetic_receipt':sr,'dup_412':True,'model_calls':0,'gcs':dict(t.c)}
 info['gcs']['POST']+=1;info['gcs']['GET']+=2
 init_bytes=info['gcs']['POST_BYTES']
 for i in range(10):info['gcs']['POST_BYTES']=init_bytes+len(canonical(info))
 ensure(info['gcs']['POST_BYTES']==init_bytes+len(canonical(info)),'STATE_FIXEDPOINT_FAIL')
 state=t.create(STATE,canonical(info));ensure(t.c==info['gcs'],'COUNTERS_DRIFT')
 receipt={'status':'H64_FREE_BOOTSTRAP_SUCCESS','campaign_id':CAMP,'key':keyreceipt,'state':state,'protected26':26,'models':identity,'gcs':t.c,'public_certificate_base64':base64.b64encode(cert).decode(),'gemini_generation_calls':0}
 print('H64_BOOTSTRAP_PUBLIC_RECEIPT '+json.dumps(receipt,sort_keys=True),flush=True)
 if os.environ.get('H64_BOOTSTRAP_RECEIPT'):
  pathlib.Path(os.environ['H64_BOOTSTRAP_RECEIPT']).write_text(json.dumps(receipt,sort_keys=True,indent=2))
if __name__=='__main__':main()
