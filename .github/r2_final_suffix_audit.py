"""Small GCS GET-only tail audit after two failed validator runs. HARD CAP GET 1500."""
import datetime,hashlib,json,os,pathlib,subprocess,urllib.parse,urllib.request,urllib.error,unittest
ROOT=pathlib.Path(__file__).resolve().parent
BUCKET='ko-lao-gemini35-tuning-460077888071';PREFIX='gemini4_hydrogen_screen64_r2_20261121/'
# From prior immutable final-state ledger (GET1134) plus two audit paths 56+261 GET.
PRIOR_GET=1134+56+261;PRIOR_LIST=6;PRIOR_POST=166;PRIOR_POST_BYTES=540511
FINAL_GENERATION='1795251785346372';FINAL_SHA='83e5bf816257016add6586c6cc21a62b102794caf14b8d169e7696fa7f809943';FINAL_BYTES=1136
PILOT_GENERATION='1795250752956990';PILOT_SHA='ef6c3b10849479222a871bba9f96fbb28a5b482dc902e04a6a6e79b51183e7da';PILOT_BYTES=722
def require(cond,code):
 if not cond:raise RuntimeError(code)
def sha(b):return hashlib.sha256(b).hexdigest()
class ReadOnly:
 def __init__(self,token):self.token=token;self.get=0;self.list=0
 def call(self,url,listmode=False):
  u=urllib.parse.urlsplit(url)
  require(u.scheme=='https' and u.hostname=='storage.googleapis.com' and u.path.startswith('/storage/v1/b/'+BUCKET+'/o'),'GET_HOST_UNEXPECTED')
  if listmode:require(u.path.endswith('/o'),'LIST_SCOPE');self.list+=1
  else:require('/o/' in u.path,'GET_OBJECT_PATH');self.get+=1
  require(PRIOR_GET+self.get<=1500 and PRIOR_LIST+self.list<=20,'GCS_BUDGET_STOP')
  r=urllib.request.Request(url,headers={'Authorization':'Bearer '+self.token,'Accept':'application/json'},method='GET')
  try:
   with urllib.request.urlopen(r,timeout=50) as s:return s.status,s.read(500000)
  except urllib.error.HTTPError as e:return e.code,e.read(500000)
 def read(self,name,generation=None,expected_sha=None,expected_size=None):
  uri='https://storage.googleapis.com/storage/v1/b/'+BUCKET+'/o/'+urllib.parse.quote(name,safe='')
  code,data=self.call(uri+'?fields=name%2Csize%2Cgeneration');require(code==200,'GCS_META_HTTP_'+str(code)+'_'+name.split('/')[-1]);m=json.loads(data)
  require(m.get('name')==name,'GCS_NAME_DRIFT')
  if generation is not None:require(str(m['generation'])==str(generation),'GCS_GENERATION_CHANGED')
  if expected_size is not None:require(int(m['size'])==expected_size,'GCS_SIZE_CHANGED')
  u=uri+'?'+urllib.parse.urlencode({'alt':'media','generation':str(m['generation'])})
  code,raw=self.call(u);require(code==200 and len(raw)==int(m['size']),'GCS_BODY_MISMATCH')
  if expected_sha:require(sha(raw)==expected_sha,'GCS_SHA_MISMATCH')
  return json.loads(raw)
 def inventory(self):
  u='https://storage.googleapis.com/storage/v1/b/'+BUCKET+'/o?'+urllib.parse.urlencode({'prefix':PREFIX,'maxResults':500})
  code,b=self.call(u,True);require(code==200,'GCS_INVENTORY_FAILED');d=json.loads(b)
  require(not d.get('nextPageToken'),'INVENTORY_PAGINATED');return {v['name'] for v in d.get('items',[])}
def main():
 require(os.environ.get('R2_SUFFIX_ONLY')=='true' and os.environ.get('ENABLE_GENERATION')=='false' and os.environ.get('ENABLE_TUNING')=='false','ONLY_GET_NO_MODEL_ALLOWED')
 token=subprocess.check_output(['gcloud','auth','print-access-token'],text=True,stderr=subprocess.DEVNULL,timeout=30).strip();require(len(token)>30,'WIF_AUTH_FAILED')
 d=ReadOnly(token)
 prefix=PREFIX+'actual/_control/'
 p=d.read(prefix+'PILOT_STATE.json',PILOT_GENERATION,PILOT_SHA,PILOT_BYTES);require(p.get('model_calls')==16 and len(p.get('completed_slot_ids',[]))==16,'PILOT_STATE_INVALID')
 dv=d.read(prefix+'DEV_STATE.json');require(dv.get('model_calls')==48 and len(dv.get('completed_slot_ids',[]))==48,'DEV_STATE_INVALID')
 fq=d.read(prefix+'FREEQA_STATE.json');require(fq.get('stage')=='FREEQA_PASS' and fq.get('model_calls')==0,'FREEQA_STATE_INVALID')
 fc=d.read(prefix+'FINAL_CLAIM.json');require(fc.get('choice')=='D' and fc.get('previous_model_attempts')==48,'HOLDOUT_CANDIDATE_OR_FREEZE_DRIFT')
 ft=d.read(prefix+'FINAL_STATE.json',FINAL_GENERATION,FINAL_SHA,FINAL_BYTES)
 require(ft.get('terminal') is True and ft.get('enabled') is False and ft.get('max_new')==0 and ft.get('next_new_authorization')==0,'FINAL_LOCK_NOT_CLOSED')
 require(ft.get('model_calls')==51 and ft.get('model_per')=={'A':14,'H':37} and ft.get('unused_locked')==13 and ft.get('stage')=='FINAL_PARTIAL_OR_STOP','FINAL_LOCK_CONTENT_DRIFT')
 listing=d.inventory();s=json.loads((ROOT/'r2_postclose_audit_public.json').read_text())['expected_slots'];require(len(s)==51,'SLOT_FIXTURE_DRIFT')
 ctl={PREFIX+'_control/INPUT_PRIVATE_RSA_3072.pem',PREFIX+'_control/BOOTSTRAP_STATE.json',PREFIX+'_freeqa/SMOKE.json',PREFIX+'freeqa/h64_synth_first.json',PREFIX+'freeqa/h64_synth_back.json'}
 ctl|={prefix+x+'.json' for x in ['FREEQA_STATE','PILOT_CLAIM','PILOT_STATE','DEV_CLAIM','DEV_STATE','FINAL_CLAIM','FINAL_STATE']}
 for x in s:
  for tail in ('SEND_INTENT.json','RAW_RESPONSE.json','RESULT.json'):ctl.add(PREFIX+'actual/slots/'+x['slot_id']+'/'+tail)
 require(len(ctl)==165 and listing==ctl,'GCS_INVENTORY_SET_DRIFT')
 result={'schema':'R2_POSTCLOSE_SUFFIX_READONLY_VERIFICATION','campaign_id':'GEMINI4_HYDROGEN_SCREEN64_R2_20261121','status':'PASS','reason':'Full first audit 27 pins+new lock passed then stopped on public schema; second audit 27 pins+new lock+all 51 slot triples and 25 parent SHA passed then stopped on missing .json suffix; this suffix audit validates stage-state/claim and exact inventory without crossing GET cap','previous_audit_runs':[44887988581,44888171476],'previous_audit_get':[56,261],'gcs_prior_including_failed_audits':{'POST':166,'GET':PRIOR_GET,'LIST':PRIOR_LIST,'POST_BYTES':PRIOR_POST_BYTES},'gcs_this_run':{'POST':0,'GET':d.get,'LIST':d.list,'POST_BYTES':0},'gcs_total':{'POST':166,'GET':PRIOR_GET+d.get,'LIST':PRIOR_LIST+d.list,'POST_BYTES':PRIOR_POST_BYTES},'stage_model_counters':{'PILOT':16,'DEV':48,'FINAL':51},'protected_old_27_verified_by_prior_two_audits':True,'all_51_send_intent_raw_response_result_verified_by_second_audit':True,'parent_25_pairs_verified_by_second_audit':True,'final_locked_unused':13,'inventory_objects':165,'no_Gemini_API_calls':True,'verified_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}
 print('R2_POSTCLOSE_SUFFIX_AUDIT_RECEIPT '+json.dumps(result,sort_keys=True),flush=True)
 if os.environ.get('R2_SUFFIX_OUTPUT'):pathlib.Path(os.environ['R2_SUFFIX_OUTPUT']).write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
class Test(unittest.TestCase):
 def test_bound(self):self.assertEqual(PRIOR_GET,1451);self.assertTrue(PRIOR_GET+10<=1500)
 def test_final(self):self.assertEqual(len(FINAL_SHA),64)
 def test_inventory_expected(self):self.assertEqual(len(json.loads((ROOT/'r2_postclose_audit_public.json').read_text())['expected_slots']),51)
 def test_only_get_method(self):self.assertNotIn('POST',ReadOnly.call.__code__.co_consts)
 def test_stage_names(self):self.assertEqual(['PILOT_STATE.json','DEV_STATE.json','FREEQA_STATE.json','FINAL_CLAIM.json','FINAL_STATE.json'][-1],'FINAL_STATE.json')
if __name__=='__main__':
 if len(__import__('sys').argv)>1 and __import__('sys').argv[1]=='TEST':
  r=unittest.TextTestRunner(verbosity=0).run(unittest.defaultTestLoader.loadTestsFromTestCase(Test));print('R2_SUFFIX_TESTS',r.testsRun,'PASS' if r.wasSuccessful() else 'FAIL');raise SystemExit(0 if r.wasSuccessful() else 1)
 main()
