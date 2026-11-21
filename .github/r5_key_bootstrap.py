"""R5 WIF read-only identity/25-pin check and one-time private input decryption key bootstrap.
No user text, prompt bodies or model generation. This script may be temporary public GitHub code.
"""
import os,sys,json,hashlib,base64,subprocess,urllib.request,urllib.error,urllib.parse,uuid
from pathlib import Path
ROOT='sft_fourpath_paid96_r5_20261121/'
BUCKET='ko-lao-gemini35-tuning-460077888071'
MODEL='projects/460077888071/locations/us/models/4774448923710324736@1'
ENDPOINT='projects/460077888071/locations/us/endpoints/1638501023804817408'
KNAME=ROOT+'_control/INPUT_DECRYPT_RSA_PRIVATE_KEY.pem'
PINS_FILE=Path(__file__).with_name('r5_pins25.json')
sha=lambda b:hashlib.sha256(b).hexdigest()
def req(method,url,token,payload=None):
 if not url.startswith(('https://storage.googleapis.com/','https://aiplatform.us.rep.googleapis.com/v1/')):raise RuntimeError('NETWORK_HOST_DENIED')
 if ':generateContent' in url or ':predict' in url or method not in ('GET','POST'):raise RuntimeError('MODEL_GENERATION_DENIED')
 if method=='POST' and not (url.startswith('https://storage.googleapis.com/upload/') and 'ifGenerationMatch=0' in url):raise RuntimeError('STORAGE_MUTATION_DENIED')
 headers={'Authorization':'Bearer '+token,'Accept':'application/json','User-Agent':'R5-Bootstrap/1'}
 if method=='POST':headers['Content-Type']='application/octet-stream'
 r=urllib.request.Request(url,headers=headers,method=method,data=payload)
 try:
  with urllib.request.urlopen(r,timeout=40) as x:return x.status,x.read(150000)
 except urllib.error.HTTPError as e:return e.code,e.read(150000)

def mediaurl(name,generation):
 return 'https://storage.googleapis.com/storage/v1/b/'+BUCKET+'/o/'+urllib.parse.quote(name,safe='')+'?'+urllib.parse.urlencode({'alt':'media','generation':generation})
def metaurl(name):
 return 'https://storage.googleapis.com/storage/v1/b/'+BUCKET+'/o/'+urllib.parse.quote(name,safe='')+'?fields=name%2Csize%2Cgeneration'
def pinned(name,gen,expected_bytes,expected_sha,token):
 s,b=req('GET',metaurl(name),token)
 if s!=200:raise RuntimeError('PIN_METADATA_HTTP_'+str(s))
 m=json.loads(b)
 if m.get('name')!=name or str(m.get('generation'))!=str(gen) or int(m.get('size',-1))!=expected_bytes:raise RuntimeError('PIN_METADATA_MISMATCH')
 s,b=req('GET',mediaurl(name,str(gen)),token)
 if s!=200 or len(b)!=expected_bytes or sha(b)!=expected_sha:raise RuntimeError('PIN_BODY_MISMATCH')
 d=json.loads(b)
 if d.get('enabled') is not False or d.get('max_new')!=0 or d.get('next_new_authorization')!=0:raise RuntimeError('PIN_OPEN')
 return {'object':name,'generation':str(gen),'bytes':len(b),'sha256':sha(b)}

def identity(token):
 root='https://aiplatform.us.rep.googleapis.com/v1/'
 results={}
 for name,key in ((ENDPOINT,'endpoint'),(MODEL,'model')):
  s,b=req('GET',root+name,token)
  if s!=200:raise RuntimeError('MODEL_IDENTITY_'+key+'_HTTP_'+str(s))
  j=json.loads(b)
  if key=='endpoint':
   dm=j.get('deployedModels',[])
   if j.get('name')!=ENDPOINT or len(dm)!=1 or dm[0].get('model','').removesuffix('@1')!=MODEL.removesuffix('@1') or str(dm[0].get('modelVersionId'))!='1':raise RuntimeError('TUNED_DEPLOYMENT_IDENTITY_MISMATCH')
  elif j.get('name','').removesuffix('@1')!=MODEL.removesuffix('@1'):raise RuntimeError('TUNED_MODEL_IDENTITY_MISMATCH')
  results[key]={'http':s,'bytes':len(b),'sha256':sha(b)}
 return results

def bootstrap():
 for k,want in [('R5_BOOTSTRAP','true'),('ENABLE_GENERATION','false'),('ENABLE_TUNING','false')]:
  if os.environ.get(k)!=want:raise RuntimeError('ENV_GATE_'+k)
 token=subprocess.check_output(['gcloud','auth','print-access-token'],text=True,stderr=subprocess.DEVNULL,timeout=25).strip()
 if len(token)<30:raise RuntimeError('MISSING_WIF_TOKEN')
 # Abort on any pre-existing R5 object (including an existing bootstrap key); no new session bypass.
 url='https://storage.googleapis.com/storage/v1/b/'+BUCKET+'/o?'+urllib.parse.urlencode({'prefix':ROOT,'maxResults':500})
 s,b=req('GET',url,token)
 if s!=200:raise RuntimeError('R5_PREFIX_INVENTORY_HTTP_'+str(s))
 inv=json.loads(b)
 if inv.get('items') or inv.get('nextPageToken'):raise RuntimeError('R5_PREFIX_ALREADY_EXISTS_NO_REUSE')
 pins=json.loads(PINS_FILE.read_text())
 if len(pins)!=25 or len({p['object'] for p in pins})!=25:raise RuntimeError('PROTECTED_PINS_COUNT_BAD')
 proof=[pinned(p['object'],p['generation'],p['bytes'],p['sha256'],token) for p in pins]
 ident=identity(token)
 # Generate an ephemeral RSA key in runner memory, create-only private GCS (NOT GitHub Secret Manager).
 with __import__('tempfile').TemporaryDirectory() as t:
  pk=Path(t)/'private.pem'
  cmd=['openssl','genpkey','-algorithm','RSA','-pkeyopt','rsa_keygen_bits:3072','-out',str(pk)]
  subprocess.run(cmd,check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=20)
  pub=subprocess.run(['openssl','pkey','-in',str(pk),'-pubout'],capture_output=True,check=True,timeout=10).stdout
  private=pk.read_bytes()
  upload_url='https://storage.googleapis.com/upload/storage/v1/b/'+BUCKET+'/o?'+urllib.parse.urlencode({'uploadType':'media','name':KNAME,'ifGenerationMatch':0})
  code,raw=req('POST',upload_url,token,private)
  if code not in (200,201):raise RuntimeError('INPUT_RSA_CREATE_HTTP_'+str(code))
  m=json.loads(raw);name=m['name'];g=str(m['generation'])
  if name!=KNAME:raise RuntimeError('BOOTSTRAP_CREATED_WRONG_KEY')
  metadata,body=req('GET',metaurl(KNAME),token),req('GET',mediaurl(KNAME,g),token)
  if metadata[0]!=200 or body[0]!=200 or str(json.loads(metadata[1])['generation'])!=g or sha(body[1])!=sha(private):raise RuntimeError('BOOTSTRAP_READBACK_MISMATCH')
  result={'status':'R5_BOOTSTRAP_KEY_PASS','campaign':'GEMINI35_FOURPATH_PAID96_R5_20261121','key_object':KNAME,'generation':g,'bytes':len(private),'private_key_sha256':sha(private),'public_key_sha256':sha(pub),'public_key_base64':base64.b64encode(pub).decode(),'protected':len(proof),'identity':ident,'gcs_post':1,'gcs_get':len(proof)*2+2,'gcs_list':1,'model_generations':0}
  print('R5_BOOTSTRAP_RECEIPT '+json.dumps(result,sort_keys=True),flush=True)
  out=os.environ.get('R5_BOOTSTRAP_OUTPUT')
  if out:
   Path(out).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
if __name__=='__main__':bootstrap()
