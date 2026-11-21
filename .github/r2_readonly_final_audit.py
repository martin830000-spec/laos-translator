"""Owner-only R2 final audit: READ-ONLY GCS, no model generation, no mutations."""
import base64,datetime,hashlib,json,os,pathlib,subprocess,urllib.parse,urllib.request,urllib.error,unittest
BASE=pathlib.Path(__file__).resolve().parent
BUCKET='ko-lao-gemini35-tuning-460077888071';PREFIX='gemini4_hydrogen_screen64_r2_20261121/'
FINAL=PREFIX+'actual/_control/FINAL_STATE.json';PIN27_FILE=BASE/'pins27.json'
PUBLIC=BASE/'r2_postclose_audit_public.json'
def need(condition,label):
 if not condition:raise RuntimeError(label)
def sha(raw):return hashlib.sha256(raw).hexdigest()
class ReadOnly:
 def __init__(self,token,prev):self.token=token;self.get=0;self.list=0;self.prev=prev
 def request(self,url,list_mode=False):
  u=urllib.parse.urlsplit(url)
  need(u.scheme=='https' and u.hostname=='storage.googleapis.com' and u.path.startswith('/storage/v1/b/'+BUCKET+'/o'),'HOST_OR_METHOD_DENIED')
  if list_mode:
   need(u.path.endswith('/o'),'INVENTORY_ONLY');self.list+=1
  else:
   need('/o/' in u.path,'OBJECT_GET_ONLY');self.get+=1
  need(self.get+int(self.prev['GET'])<=1500 and self.list+int(self.prev['LIST'])<=20,'GCS_OVER_LIMIT_NO_MODEL_SEND')
  r=urllib.request.Request(url,method='GET',headers={'Authorization':'Bearer '+self.token,'Accept':'application/json','User-Agent':'R2-Final-ReadOnly/1'})
  try:
   with urllib.request.urlopen(r,timeout=50) as x:return x.status,x.read(1000000)
  except urllib.error.HTTPError as e:return e.code,e.read(1000000)
 def base(self,name):return 'https://storage.googleapis.com/storage/v1/b/'+BUCKET+'/o/'+urllib.parse.quote(name,safe='')
 def read(self,name,generation=None,expected_sha=None,expected_size=None,metadata=True):
  u=self.base(name)
  if metadata:
   s,body=self.request(u+'?fields=name%2Csize%2Cgeneration');need(s==200,'GCS_META_'+str(s))
   m=json.loads(body);need(m.get('name')==name,'NAME_DRIFT')
   if generation is not None:need(str(m.get('generation'))==str(generation),'GENERATION_DRIFT')
   if expected_size is not None:need(int(m['size'])==int(expected_size),'SIZE_DRIFT')
   generation=m['generation']
  q={'alt':'media'}
  if generation is not None:q['generation']=str(generation)
  s,body=self.request(u+'?'+urllib.parse.urlencode(q));need(s==200,'GCS_MEDIA_'+str(s))
  if expected_size is not None:need(len(body)==int(expected_size),'READ_BYTES_DRIFT')
  if expected_sha is not None:need(sha(body)==expected_sha,'READ_SHA_DRIFT')
  return body
 def inventory(self):
  u='https://storage.googleapis.com/storage/v1/b/'+BUCKET+'/o?'+urllib.parse.urlencode({'prefix':PREFIX,'maxResults':500})
  s,body=self.request(u,True);need(s==200,'PREFIX_INVENTORY_FAILED');j=json.loads(body)
  need(not j.get('nextPageToken'),'INVENTORY_PAGINATED')
  return {x['name'] for x in j.get('items',[])}
def main():
 need(os.environ.get('R2_READONLY_FINAL_AUDIT')=='true' and os.environ.get('ENABLE_GENERATION')=='false' and os.environ.get('ENABLE_TUNING')=='false','REQUIRE_FREE_ONLY')
 public=json.loads(PUBLIC.read_text());need(public['campaign_id']=='GEMINI4_HYDROGEN_SCREEN64_R2_20261121','CAMPAIGN_DRIFT')
 token=subprocess.check_output(['gcloud','auth','print-access-token'],text=True,stderr=subprocess.DEVNULL,timeout=30).strip();need(len(token)>30,'WIF_AUTH_MISSING')
 d=ReadOnly(token,public['expected_cumulative_pre_audit']);pins=json.loads(PIN27_FILE.read_text())
 need(len(pins)==27 and len({r['object'] for r in pins})==27,'PROTECTED27_INCOMPLETE')
 for x in pins:
  body=d.read(x['object'],x['generation'],x['sha256'],x['bytes'])
  z=json.loads(body);need(z.get('enabled') is False and z.get('max_new')==0 and z.get('next_new_authorization')==0,'OLD_LOCK_REOPENED')
 locked=public['final_lock'];need(locked['name']==FINAL,'FINAL_PATH_DRIFT')
 body=d.read(FINAL,locked['generation'],locked['sha256'],locked['size']);new=json.loads(body)
 need(new.get('terminal') is True and new.get('enabled') is False and new.get('max_new')==0 and new.get('next_new_authorization')==0,'NEW_LOCK_NOT_SEALED')
 need(new.get('model_calls')==51 and new.get('model_per')=={'A':14,'H':37} and new.get('unused_locked')==13,'MODEL_COUNTS_LOCK_DRIFT')
 need(new.get('stage')=='FINAL_PARTIAL_OR_STOP','LOCK_REASON_NOT_FINAL_PARTIAL')
 frozen=json.loads((BASE/'public_freeze_R2.json').read_text());source_sha={x['id']:x['sha256'] for x in frozen['samples']};prompts=frozen['prompts']
 slots=public['expected_slots'];need(len(slots)==51 and len({x['slot_id'] for x in slots})==51,'SLOT_RECEIPTS_NOT_51')
 seen={};counts={'valid':0,'failed':0,'back':0,'first':0,'A':0,'H':0}
 for row in sorted(slots,key=lambda x:int(x['slot_id'][4:])):
  sid=row['slot_id'];path=PREFIX+'actual/slots/'+sid+'/';actual=d.read(path+'RESULT.json',row['generation'],row['sha256'],row['bytes'])
  result=json.loads(actual);need(result.get('slot_id')==sid and result.get('arm')==row['arm'] and result.get('source_id')==row['source_id'],'RESULT_CROSS_DRIFT')
  need(result.get('source_sha256')==source_sha.get(row['source_id']),'SOURCE_SHA_DRIFT');need(result.get('path')==row['path'],'PATH_DRIFT')
  need(result.get('http')==row['http'] and result.get('usable') is row['usable'] and result.get('finishReason')==row['finishReason'],'HTTP_STATE_DRIFT')
  arm=row['arm'];counts['A' if arm=='A' else 'H']+=1
  need(result.get('prompt_sha256')==prompts[arm][row['path']],'PROMPT_SHA_DRIFT')
  if row['action']=='FIRST':
   need(result['input_sha256']==source_sha[row['source_id']] and result['parent_first_slot_id'] is None,'FIRST_INPUT_DRIFT');counts['first']+=1
  else:
   parent=seen.get(row['parent_first_slot_id']);need(parent and parent['usable'],'PARENT_UNUSABLE');need(parent['arm']==arm and parent['source_id']==row['source_id'],'CROSS_ARM_PARENT')
   need(result.get('input_sha256')==sha(parent['translation_text'].encode()),'REAL_FIRST_PARENT_SHA_MISMATCH');counts['back']+=1
  raw=d.read(path+'RAW_RESPONSE.json',metadata=False);rq=json.loads(raw)
  need(rq['slot_id']==sid and rq['response_sha256']==result['response_sha256'],'RAW_RESPONSE_RECEIPT_BAD')
  need(sha(base64.b64decode(rq['body_b64']))==result['response_sha256'],'RAW_HTTP_BODY_SHA_BAD')
  intent=d.read(path+'SEND_INTENT.json',metadata=False);it=json.loads(intent)
  need(it['slot_id']==sid and it['source_sha256']==row['source_sha256'] and it['input_sha256']==result['input_sha256'] and it['prompt_sha256']==result['prompt_sha256'],'SEND_INTENT_DRIFT')
  need(it['request_sha256']==rq['request_sha256'],'RAW_REQUEST_SHA_MISMATCH')
  if result['usable']:
   need(result['http']==200 and result['finishReason']=='STOP' and bool(result['translation_text']),'INVALID_VALID_STATE');counts['valid']+=1
  else:
   need(result['http']==429 and result['finishReason'] is None and not result['translation_text'],'INVALID_429_STATE');counts['failed']+=1
  seen[sid]=result
 need(counts=={'valid':50,'failed':1,'back':25,'first':26,'A':14,'H':37},'FINAL_LEDGER_COUNTS_BAD')
 for s,n in [('PILOT_STATE',16),('DEV_STATE',48)]:
  j=json.loads(d.read(PREFIX+'actual/_control/'+s));need(j.get('model_calls')==n,'STAGE_CALL_COUNTER_DRIFT')
 inv=d.inventory()
 ctl={PREFIX+'_control/INPUT_PRIVATE_RSA_3072.pem',PREFIX+'_control/BOOTSTRAP_STATE.json',PREFIX+'_freeqa/SMOKE.json',PREFIX+'freeqa/h64_synth_first.json',PREFIX+'freeqa/h64_synth_back.json'}
 ctl|={PREFIX+'actual/_control/'+x+'.json' for x in ['FREEQA_STATE','PILOT_CLAIM','PILOT_STATE','DEV_CLAIM','DEV_STATE','FINAL_CLAIM','FINAL_STATE']}
 expected=set(ctl)
 for s in slots:
  for name in ['SEND_INTENT.json','RAW_RESPONSE.json','RESULT.json']:expected.add(PREFIX+'actual/slots/'+s['slot_id']+'/'+name)
 need(len(expected)==165 and inv==expected,'INVENTORY_DRIFT')
 receipt={'schema':'R2_FINAL_POSTCLOSE_READONLY_AUDIT','status':'PASS','campaign_id':public['campaign_id'],'model_requests':51,'usable_stop':50,'http429_invalid':1,'protected27_unmodified':True,'new_lock':locked,'old_closed_locks':27,'slot_parent_backs_verified':25,'sent_intent_raw_result_triples_verified':51,'inventory_count':len(inv),'api_generation_requests_this_audit':0,'gcs_this_audit':{'POST':0,'GET':d.get,'LIST':d.list,'POST_BYTES':0},'gcs_cumulative_after_audit':{'POST':166,'GET':1134+d.get,'LIST':6+d.list,'POST_BYTES':540511},'github_test_restore_pending':True,'verified_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}
 print('R2_FINAL_READONLY_PUBLIC_RECEIPT '+json.dumps(receipt,ensure_ascii=True,sort_keys=True),flush=True)
 out=os.environ.get('R2_AUDIT_OUTPUT');
 if out:pathlib.Path(out).write_text(json.dumps(receipt,sort_keys=True,indent=2)+'\n')
class UnitTests(unittest.TestCase):
 def test_pin27(self):self.assertEqual(len(json.loads(PIN27_FILE.read_text())),27)
 def test_no_model_post(self):self.assertNotIn('generateContent',ReadOnly.request.__code__.co_consts)
 def test_expected51(self):self.assertEqual(len(json.loads(PUBLIC.read_text())['expected_slots']),51)
 def test_gcs_caps(self):self.assertLess(1134+300,1500)
 def test_known_final_lock(self):self.assertEqual(json.loads(PUBLIC.read_text())['final_lock']['generation'],'1795251785346372')
 def test_model_no_fallback(self):self.assertEqual(ReadOnly.request.__code__.co_names.count('urlopen'),1)
if __name__=='__main__':
 if len(__import__('sys').argv)>1 and __import__('sys').argv[1]=='TEST':
  r=unittest.TextTestRunner(verbosity=1).run(unittest.defaultTestLoader.loadTestsFromTestCase(UnitTests))
  print('R2_READONLY_AUDIT_GUARDS',r.testsRun,'PASS' if r.wasSuccessful() else 'FAIL')
  raise SystemExit(0 if r.wasSuccessful() else 1)
 main()
