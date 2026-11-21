"""Owner-only immutable Developer Direct2 postclosure verification. GCS GET only, no model generation.
Sealed actual-first-to-back chain and raw SSE body SHA are independently rechecked.
"""
from __future__ import annotations
import base64,datetime,hashlib,json,os,pathlib,subprocess,sys,unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent))
import dd2_runner as r
from dd2_sse import SSEAssembler
BASE=pathlib.Path(__file__).resolve().parent
FINAL='gemini4_hydrogen_developer_direct2_20261122/actual/_control/FINAL_STATE.json'
FINAL_GENERATION='1795302373434867'
FINAL_SHA='7db0e23868c0d631d9cbf52757f98fa11c5778ba9f187af14170bdf9c4579409'
FINAL_BYTES=598
AUDIT_RECEIPTS_SHA='c5ede838ff929637f1a5312dad51357d1cc81f98e8a413100052bcfc93365032'
class ReadOnly(r.Net):
 def send(self,method,url,data=None,ctype=None):
  r.need(method=='GET','NO_MUTATING_GCS_POST_ALLOWED')
  return super().send(method,url,None,None)
 def stream(self,*args):raise r.SafetyStop('MODEL_GENERATION_IN_AUDIT_DENIED')
def audit():
 r.need(os.getenv('DD2_READONLY_AUDIT')=='true' and os.getenv('ENABLE_GENERATION')=='false' and os.getenv('ENABLE_TUNING')=='false','READONLY_STAGE_REQUIRED')
 r.need(os.getenv('GITHUB_REPOSITORY')=='martin830000-spec/laos-translator' and os.getenv('GITHUB_REF')=='refs/heads/research/gemini35-tuning-test' and os.getenv('GITHUB_RUN_ATTEMPT')=='1','GH_STAGE_MISMATCH')
 r.need('/.github/workflows/gemini35-tuning-test.yml@' in os.getenv('GITHUB_WORKFLOW_REF',''),'GH_WORKFLOW_MISMATCH')
 receipt_bytes=(BASE/'dd2_audit_receipts.json').read_bytes();r.need(r.sha(receipt_bytes)==AUDIT_RECEIPTS_SHA,'AUDIT_RECEIPTS_SHA_DRIFT');freeze=r.pub();z=json.loads(receipt_bytes)
 r.need(z['campaign_id']==r.CAMP and len(z['expected'])==2 and z['model_calls']==2,'AUDIT_SCOPE_BAD')
 token=subprocess.check_output(['gcloud','auth','print-access-token'],stderr=subprocess.DEVNULL,text=True,timeout=35).strip();r.need(len(token)>30,'WIF_GET_TOKEN_ABSENT')
 net=ReadOnly(token,False);b=r.Budget();s=r.gcs.Store(net,b,'actual')
 m,raw=s.read_pinned(FINAL,FINAL_GENERATION);r.need(m['name']==FINAL and len(raw)==FINAL_BYTES and r.sha(raw)==FINAL_SHA,'NEW_LOCK_GENERATION_SHA_MISMATCH')
 lock=json.loads(raw);r.need(lock['campaign_id']==r.CAMP and lock['model_calls']==2 and lock['valid']==2 and lock['invalid']==0 and lock['unused_locked']==0 and lock['terminal'] is True,'FINAL_LOCK_CONTENT_DRIFT')
 r.need(lock['enabled'] is False and lock['max_new']==0 and lock['next_new_authorization']==0 and lock['protected29_unchanged'] is True,'NEW_FINAL_LOCK_NOT_CLOSED')
 b.hydrate(lock['cumulative'])
 old=r.protected29(s);r.need(len(old)==29,'29_PRIOR_PINS_BAD')
 s_meta,s_body=s.read('_control/FREEQA_STATE.json');freeqa=json.loads(s_body)
 r.need(freeqa['stage']=='FREEQA_PASS' and freeqa['model_calls']==0,'FREEQA_STATE_CHANGED')
 actual=[];byid={};meta=[]
 for slot in z['expected']:
  sid=slot['slot_id'];base='slots/'+sid+'/';objects={}
  for k,f in [('intent','SEND_INTENT.json'),('raw','RAW_RESPONSE.json'),('result','RESULT.json')]:
   pin=slot[k];gm,gb=s.read(base+f)
   r.need(str(gm['generation'])==str(pin['generation']) and len(gb)==pin['size'] and r.sha(gb)==pin['sha256'],'SLOT_OBJECT_PIN_MISMATCH_'+sid)
   objects[k]=json.loads(gb);meta.append({'slot_id':sid,'kind':k,'generation':gm['generation'],'sha256':r.sha(gb),'bytes':len(gb)})
  it,rs,v=objects['intent'],objects['raw'],objects['result']
  r.need(it['slot_id']==sid==rs['slot_id']==v['slot_id'],'SLOT_ID_BAD')
  r.need(it['model']==v['model']==r.MODEL and v['developer_api_only'] is True,'NOT_DEVELOPER_MODEL')
  r.need(it['prompt_sha256']==v['prompt_sha256']==freeze['prompt_'+slot['action'].lower()+'_sha256'],'PROMPT_SHA_BAD')
  r.need(v['source_sha256']==it['source_sha256']==freeze['source_sha256'],'FROZEN_ORIGINAL_BAD')
  r.need(it['request_sha256']==rs['request_sha256']==v['request_sha256']==slot['request_sha256'],'REQUEST_SHA_BAD')
  r.need(it['input_sha256']==v['input_sha256'],'INPUT_SHA_BAD')
  rawbytes=base64.b64decode(rs['body_b64'],validate=True)
  r.need(r.sha(rawbytes)==rs['response_sha256']==v['response_sha256']==slot['response_sha256'],'RAW_SSE_SHA_BAD')
  r.need(v['usable'] and v['http']==200 and v['finishReason']=='STOP','NOT_VALID_SSE')
  ss=SSEAssembler(0);ss.feed(rawbytes,1.0);ss.finish(1.0);rep=ss.result()
  r.need(rep['text']==v['translation_text'] and rep['finishReason']==v['finishReason']=='STOP' and rep['modelVersion']==v['modelVersion'] and rep['events_count']==v['sse_event_count'],'RAW_SSE_REPLAY_DRIFT')
  r.need(r.sha(v['translation_text'].encode())==v['translation_sha256']==slot['translation_sha256'],'OUTPUT_TRANSLATION_SHA_BAD')
  if slot['action']=='FIRST':r.need(v['input_sha256']==freeze['source_sha256'] and v['parent_first_slot_id'] is None,'FIRST_NOT_EXACT_FROZEN_SOURCE')
  else:
   parent=byid['SLOT001'];r.need(v['parent_first_slot_id']=='SLOT001' and v['input_sha256']==r.sha(parent['translation_text'].encode()),'BACK_NOT_ACTUAL_FIRST')
  byid[sid]=v
  actual.append({'slot':slot,'intent':it,'raw':rs,'result':v})
 expected={r.PREFIX+'_control/INPUT_PRIVATE_RSA_3072.pem',r.PREFIX+'_control/BOOTSTRAP_STATE.json',r.PREFIX+'_freeqa/SMOKE.json',r.PREFIX+'freeqa/SYNTHETIC_FIRST.json',r.PREFIX+'freeqa/SYNTHETIC_BACK.json',r.PREFIX+'actual/_control/FREEQA_STATE.json',r.PREFIX+'actual/_control/PILOT_CLAIM.json',FINAL}
 for slot in z['expected']:
  for n in ['SEND_INTENT.json','RAW_RESPONSE.json','RESULT.json']:expected.add(r.PREFIX+'actual/slots/'+slot['slot_id']+'/'+n)
 inventory=set(s.inventory(r.PREFIX));r.need(inventory==expected and len(inventory)==14,'GCS_EXACT_PREFIX_INVENTORY_CHANGED')
 out={'schema':'DD2_POSTCLOSE_OWNER_AUDIT','campaign_id':r.CAMP,'status':'PASS','new_final_lock':{'name':FINAL,'generation':m['generation'],'sha256':r.sha(raw),'size':len(raw),'state':lock},'previous29_pins':old,'actual_slots':actual,'receipt_meta':meta,'freeqa':freeqa,'object_count':len(inventory),'model_calls_this_audit':0,'gcs':b.snapshot(),'audit_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}
 receipt=r.crypto_archive(out)
 public={'status':'AUDIT_PASS','campaign_id':r.CAMP,'old_locks29':29,'model_attempts':2,'first_valid':True,'back_valid':True,'sha_parent_match':True,'raw_sse_replay_2_of_2':True,'inventory_objects':14,'new_lock':{'generation':m['generation'],'sha256':r.sha(raw),'size':len(raw)},'gcs':b.snapshot(),'model_generation_calls':0,'gcs_post_calls':0,'cms_receipt':receipt}
 print('DD2_READONLY_PUBLIC_AUDIT '+json.dumps(public,sort_keys=True),flush=True)
 if os.getenv('DD2_PUBLIC_AUDIT_RECEIPT'):pathlib.Path(os.environ['DD2_PUBLIC_AUDIT_RECEIPT']).write_bytes(r.canon(public))
class Tests(unittest.TestCase):
 def test_lock(self):self.assertEqual(len(FINAL_SHA),64);self.assertEqual(FINAL_BYTES,598)
 def test_receipts(self):self.assertEqual(len(json.loads((BASE/'dd2_audit_receipts.json').read_text())['expected']),2)
 def test_readonly(self):
  net=ReadOnly('dummy',False)
  with self.assertRaises(r.SafetyStop):net.send('POST','https://storage.googleapis.com',b'{}')
  with self.assertRaises(r.SafetyStop):net.stream('any',b'{}')
 def test_old_pins(self):self.assertEqual(len(json.loads((BASE/'dd2_pins29.json').read_text())),29)
 def test_api_key_not_needed(self):self.assertNotIn('GEMINI_API_KEY',audit.__code__.co_names)
 def test_budget(self):self.assertLess(214+29*2+2*3*2+8,350)
if __name__=='__main__':
 if len(sys.argv)>1 and sys.argv[1]=='TEST':
  result=unittest.TextTestRunner(verbosity=0).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests));print('DD2_READONLY_TESTS',result.testsRun,'PASS' if result.wasSuccessful() else 'FAIL');raise SystemExit(0 if result.wasSuccessful() else 1)
 audit()
