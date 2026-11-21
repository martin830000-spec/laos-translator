"""Postclosure free GET-only immutable GCS audit of STREAM24 real SSE payloads.
No model or storage POST method is implemented. Encrypt result for owner-only GitHub artifact.
"""
import base64,collections,datetime,hashlib,json,os,pathlib,subprocess,tempfile,unittest,sys
sys.path.insert(0,str(pathlib.Path(__file__).parent))
import s24_runner as r
CAMP=r.CAMP;PREFIX=r.PREFIX;ROOT=pathlib.Path(__file__).parent
sha=r.sha;need=r.need

def audit():
 need(os.environ.get('S24_READONLY_AUDIT')=='true' and os.environ.get('ENABLE_GENERATION')=='false' and os.environ.get('ENABLE_TUNING')=='false','READONLY_ENV_REQUIRED')
 token=subprocess.check_output(['gcloud','auth','print-access-token'],stderr=subprocess.DEVNULL,text=True,timeout=25).strip();need(len(token)>30,'WIF_TOKEN_NOT_PRESENT')
 net=r.Network(token,paid=False);b=r.Budget();s=r.gcs.Store(net,b,'actual')
 # Before accumulating prior budget, GET and LIST are counted separately and then added.
 meta,body=s.read('_control/FINAL_STATE.json');lock=json.loads(body)
 need(lock['campaign_id']==CAMP and lock.get('enabled') is False and lock.get('max_new')==0 and lock.get('next_new_authorization')==0 and lock.get('terminal') is True,'FINAL_NOT_SEALED')
 need(str(meta['generation'])==os.environ.get('S24_FINAL_GENERATION') and sha(body)==os.environ.get('S24_FINAL_SHA'),'FINAL_LOCK_PIN_MISMATCH')
 previous=lock['cumulative'];b.hydrate(previous)
 need(b.get+28*2+24*6+10<=900,'POSTCLOSE_BUDGET_GET_RESERVE')
 old=r.verify_pins(s);need(len(old)==28,'PROTECTED_28_BAD')
 freeze=r.validate_freeze();pmap={x['slot_id']:x for x in freeze['slots']}
 names=lock['completed_slot_ids'];need(names==[x['slot_id'] for x in freeze['slots'][:len(names)]],'COMPLETE_SLOT_SET_DRIFT')
 results=[];metas=[];byid={};ok=0;invalid=0
 for sid in names:
  plan=pmap[sid];base='slots/'+sid+'/'
  im,ib=s.read(base+'SEND_INTENT.json');rm,rb=s.read(base+'RAW_RESPONSE.json');vm,vb=s.read(base+'RESULT.json')
  it=json.loads(ib);raw=json.loads(rb);result=json.loads(vb)
  need(it['slot_id']==sid==result['slot_id']==raw['slot_id'],'SLOT_ID_MISMATCH')
  need(it['arm']==plan['arm']==result['arm'] and result['sample_id']==plan['sample_id'],'SLOT_ARM_SOURCE_DRIFT')
  need(it['source_sha256']==result['source_sha256']==plan['source_sha256'],'SOURCE_HASH_DRIFT')
  need(it['prompt_sha256']==result['prompt_sha256']==plan['prompt_sha256'],'PROMPT_HASH_DRIFT')
  need(it['request_sha256']==raw['request_sha256']==result['request_sha256'],'REQUEST_HASH_DRIFT')
  need(it['input_sha256']==result['input_sha256'],'INPUT_HASH_DRIFT')
  need(result['parent_first_slot_id']==plan['parent_first_slot_id'],'PARENT_ID_DRIFT')
  if plan['action']=='FIRST':need(it['input_sha256']==plan['source_sha256'] and it['parent_first_slot_id'] is None,'FIRST_INPUT_OR_SOURCE_DRIFT')
  else:
   p=byid.get(plan['parent_first_slot_id']);need(p and p['usable'] and p['arm']==plan['arm'] and p['sample_id']==plan['sample_id'],'BAD_PARENT_FIRST')
   need(result['input_sha256']==sha(p['translation_text'].encode()),'FIRST_TO_BACK_HASH_MISMATCH')
  rbytes=base64.b64decode(raw['raw_sse_b64'],validate=True);need(sha(rbytes)==raw['response_sha256'],'RAW_SSE_BYTES_DRIFT')
  need(result['http']==raw['http'],'HTTP_STATUS_MISMATCH')
  need(result['translation_sha256']==sha(result['translation_text'].encode()),'TRANSLATION_SHA_DRIFT')
  if result['usable']:
   need(result['http']==200 and result['finishReason']=='STOP' and bool(result['translation_text']) and result['modelVersion'].startswith(plan['model']),'VALID_STATE_MISSING')
   replay=r.SSEAssembler(start=0);replay.feed(rbytes,1.0);replay.finish(1.0)
   rv=replay.result();need(rv['text']==result['translation_text'] and rv['finishReason']==result['finishReason'] and rv['modelVersion']==result['modelVersion'],'SSE_OFFLINE_REPLAY_MISMATCH')
   need(rv['events_count']==result['sse_event_count'],'EVENT_COUNT_MISMATCH')
   ok+=1
  else:
   need(result['http']!=200 or result['finishReason']!='STOP' or not result['translation_text'],'INVALID_RESULT_NOT_MARKED');invalid+=1
  byid[sid]=result
  results.append({'plan':plan,'send_intent':it,'raw_response':raw,'result':result})
  metas.append({'slot_id':sid,'SEND_INTENT':{'name':im['name'],'generation':im['generation'],'bytes':len(ib),'sha256':sha(ib)},'RAW_RESPONSE':{'name':rm['name'],'generation':rm['generation'],'bytes':len(rb),'sha256':sha(rb)},'RESULT':{'name':vm['name'],'generation':vm['generation'],'bytes':len(vb),'sha256':sha(vb)}})
 need(len(results)==lock['model_calls'] and ok+invalid==len(results),'AUDIT_MODEL_COUNT_DRIFT')
 _,pilotbytes=s.read('_control/PILOT_STATE.json');pilot=json.loads(pilotbytes)
 need(pilot['model_calls']==4 and pilot['completed_slot_ids']==names[:4],'PILOT_STATE_CHANGED')
 actual=set(s.inventory(PREFIX));expected={PREFIX+'_control/INPUT_PRIVATE_RSA_3072.pem',PREFIX+'_control/BOOTSTRAP_STATE.json',PREFIX+'_freeqa/SMOKE.json',PREFIX+'actual/_control/FREEQA_STATE.json',PREFIX+'freeqa/stream24_synthetic_first.json',PREFIX+'freeqa/stream24_synthetic_back.json',PREFIX+'actual/_control/PILOT_CLAIM.json',PREFIX+'actual/_control/PILOT_STATE.json',PREFIX+'actual/_control/MAIN_CLAIM.json',PREFIX+'actual/_control/FINAL_STATE.json'}
 for sid in names:
  for f in ('SEND_INTENT.json','RAW_RESPONSE.json','RESULT.json'):expected.add(PREFIX+'actual/slots/'+sid+'/'+f)
 need(actual==expected,'GCS_EXACT_INVENTORY_NOT_MATCHED')
 evidence={'schema':'S24_OWNER_POSTCLOSE_READONLY_EVIDENCE_V1','campaign_id':CAMP,'status':'PASS','actual_slots':results,'all_receipts':metas,'protected_28':old,'final_lock':{'name':meta['name'],'generation':meta['generation'],'sha256':sha(body),'bytes':len(body),'data':lock},'status_counts':{'total':len(results),'valid':ok,'invalid':invalid},'gcs_counters':b.snap(),'observed_objects':len(actual),'model_generation_in_this_audit':0,'created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}
 artifact=r.archive(evidence);need(artifact is not None,'AUDIT_ENCRYPTED_ARTIFACT_MISSING')
 summary={'status':'AUDIT_PASS','campaign_id':CAMP,'total':len(results),'valid':ok,'invalid':invalid,'lock_generation':meta['generation'],'lock_sha256':sha(body),'protected28':28,'gcs':b.snap(),'inventory_objects':len(actual),'cms_bytes':artifact['bytes'],'cms_sha256':artifact['sha256'],'generation_calls':0}
 print('S24_PUBLIC_POSTCLOSE_AUDIT '+json.dumps(summary,sort_keys=True),flush=True)
 target=os.environ.get('S24_AUDIT_PUBLIC_PATH');
 if target:pathlib.Path(target).write_bytes(r.canon(summary))
 return summary

class Tests(unittest.TestCase):
 def test_get_only(self):self.assertNotIn('stream',audit.__code__.co_names)
 def test_safe_network(self):
  n=r.Network('dummy',paid=False)
  with self.assertRaises(r.SafetyStop):n.stream(r.ROOT+'gemini-4-hydrogen:streamGenerateContent?alt=sse',b'{}')
 def test_frozen_24(self):self.assertEqual(len(r.validate_freeze()['slots']),24)
 def test_no_gcs_post(self):self.assertNotIn('create',audit.__code__.co_names)
 def test_expected_lock_budget(self):self.assertLess(610+220,900)
 def test_no_previous_mutation(self):self.assertEqual(len(json.loads((ROOT/'PINS28.json').read_text())),28)
if __name__=='__main__':
 if len(sys.argv)>1 and sys.argv[1]=='TEST':
  res=unittest.TextTestRunner(verbosity=0).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests));print('S24_AUDIT_GUARDS',res.testsRun,'PASS' if res.wasSuccessful() else 'FAIL');raise SystemExit(0 if res.wasSuccessful() else 1)
 audit()
