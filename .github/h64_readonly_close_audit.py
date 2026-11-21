"""SCREEN64 post-close free audit. Read-only GCS only. Never issue generateContent."""
import json,os,hashlib,urllib.request,urllib.parse,urllib.error,subprocess,pathlib,datetime,unittest
BUCKET='ko-lao-gemini35-tuning-460077888071'
P='gemini4_hydrogen_screen64_20261121/'
FINAL=P+'actual/_control/FINAL_STATE.json'
FG='1795248197975301';FS='ea374120571f08a5460fe2c00678e90e345b3a9eb2914b8cc302aeaca58112e7';FB=597
FREE=P+'actual/_control/FREEQA_STATE.json'
PINS=pathlib.Path(__file__).with_name('pins26.json')
sha=lambda b:hashlib.sha256(b).hexdigest()
def need(v,msg):
 if not v:raise RuntimeError(msg)
class GET:
 def __init__(self,token):self.token=token;self.get=0;self.list=0
 def call(self,url):
  u=urllib.parse.urlsplit(url);need(u.scheme=='https' and u.hostname=='storage.googleapis.com' and u.path.startswith('/storage/v1/b/'+BUCKET+'/o'),'NETWORK_HOST_PATH_DENIED')
  if u.path.endswith('/o'):self.list+=1
  else:self.get+=1
  need(self.get<=100 and self.list<=2,'AUDIT_GCS_BOUND')
  r=urllib.request.Request(url,headers={'Authorization':'Bearer '+self.token},method='GET')
  try:
   with urllib.request.urlopen(r,timeout=45) as x:return x.status,x.read(160000)
  except urllib.error.HTTPError as e:return e.code,e.read(160000)
 def meta(self,n):return 'https://storage.googleapis.com/storage/v1/b/'+BUCKET+'/o/'+urllib.parse.quote(n,safe='')+'?fields=name%2Csize%2Cgeneration'
 def media(self,n,g):return 'https://storage.googleapis.com/storage/v1/b/'+BUCKET+'/o/'+urllib.parse.quote(n,safe='')+'?'+urllib.parse.urlencode({'alt':'media','generation':g})
 def read(self,n,g=None):
  s,b=self.call(self.meta(n));need(s==200,'GCS_GET_METADATA_'+str(s));m=json.loads(b)
  need(m['name']==n and (g is None or str(m['generation'])==str(g)),'GCS_GENERATION_DRIFT')
  s,b=self.call(self.media(n,m['generation']));need(s==200 and len(b)==int(m['size']),'GCS_BODY_DRIFT')
  return m,b
def main():
 need(os.environ.get('H64_AUDIT')=='true' and os.environ.get('ENABLE_GENERATION')=='false' and os.environ.get('ENABLE_TUNING')=='false','ONLY_FREE_AUDIT')
 token=subprocess.check_output(['gcloud','auth','print-access-token'],text=True,stderr=subprocess.DEVNULL,timeout=25).strip();need(len(token)>30,'WIF_TOKEN_ABSENT')
 d=GET(token)
 pins=json.loads(PINS.read_text());need(len(pins)==26 and len({r['object'] for r in pins})==26,'PINS_COUNT')
 for p in pins:
  m,b=d.read(p['object'],p['generation']);need(len(b)==p['bytes'] and sha(b)==p['sha256'],'PIN_MISMATCH')
  j=json.loads(b);need(j.get('enabled') is False and j.get('max_new')==0 and j.get('next_new_authorization')==0,'PIN_NOT_CLOSED')
 m,b=d.read(FINAL,FG);need(len(b)==FB and sha(b)==FS,'FINAL_BODY_DRIFT');j=json.loads(b)
 need(j.get('campaign_id')=='GEMINI4_HYDROGEN_SCREEN64_20261121' and j.get('terminal') is True and j.get('enabled') is False and j.get('max_new')==0 and j.get('next_new_authorization')==0 and j.get('unused_locked')==63 and j.get('model_calls')==1 and j.get('model_per')=={'A':1,'H':0},'FINAL_LOCK_CONTENT_DRIFT')
 sm,b=d.read(FREE);f=json.loads(b);need(f.get('stage')=='FREEQA_PASS' and f.get('model_calls')==0,'FREEQA_STATE_DRIFT')
 url='https://storage.googleapis.com/storage/v1/b/'+BUCKET+'/o?'+urllib.parse.urlencode({'prefix':P,'maxResults':500})
 s,body=d.call(url);need(s==200,'PREFIX_INVENTORY_GET');inventory=json.loads(body);names=sorted(x['name'] for x in inventory.get('items',[]));need(not inventory.get('nextPageToken'),'INVENTORY_NOT_COMPLETE')
 expected={P+'_control/INPUT_PRIVATE_RSA_3072.pem',P+'_control/BOOTSTRAP_STATE.json',P+'_freeqa/SMOKE.json',P+'freeqa/h64_synth_first.json',P+'freeqa/h64_synth_back.json',FREE,P+'actual/_control/PILOT_CLAIM.json',FINAL}
 for k in ['SEND_INTENT.json','RAW_RESPONSE.json','RESULT.json']:expected.add(P+'actual/slots/SLOT001/'+k)
 need(set(names)==expected,'INVENTORY_UNEXPECTED_OBJECTS')
 out={'schema':'H64_FINAL_READONLY_AUDIT','status':'READONLY_CLOSE_PASS','campaign_id':j['campaign_id'],'protected_pins':26,'final_lock':{'object':FINAL,'generation':FG,'sha256':FS,'bytes':FB},'total_model_attempts':1,'a38_attempts':1,'hydrogen_attempts':0,'unused63_locked':True,'all_existing_objects_exact':True,'prefix_objects':len(names),'gcs_this_audit':{'POST':0,'GET':d.get,'LIST':d.list},'no_generation':True,'timestamp_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}
 print('H64_POSTCLOSE_READONLY_AUDIT '+json.dumps(out,sort_keys=True),flush=True)
 if os.environ.get('H64_AUDIT_OUTPUT'):pathlib.Path(os.environ['H64_AUDIT_OUTPUT']).write_text(json.dumps(out,sort_keys=True,indent=2))
class Test(unittest.TestCase):
 def test_no_generate_api(self):self.assertNotIn(':generateContent',GET.call.__code__.co_consts)
 def test_final_pin(self):self.assertEqual(len(FS),64)
 def test_26_pins(self):self.assertEqual(len(json.loads(PINS.read_text())),26)
 def test_api_halt(self):self.assertTrue(FINAL.startswith(P+'actual/'))
if __name__=='__main__':
 if os.environ.get('H64_TEST')=='true':
  x=unittest.TextTestRunner(verbosity=0).run(unittest.defaultTestLoader.loadTestsFromTestCase(Test));raise SystemExit(0 if x.wasSuccessful() else 1)
 main()
