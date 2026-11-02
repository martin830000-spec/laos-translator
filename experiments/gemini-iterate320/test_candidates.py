import unittest,json,copy,tempfile,os
from pathlib import Path
import adapter as a,campaign as c
CTX={'aliases':['PRIVATE_ALIAS_CANARY'],'context':'SYNTHETIC_CONTEXT_ONLY'}
def response(text,finish='STOP'):return {'candidates':[{'finishReason':finish,'content':{'parts':[{'text':text}]}}]}
class First(unittest.TestCase):
 def test_inherited_baselines_exact(self):
  for side in ['K','L']:
   for v in ['38SVC','31D','31L','38FB']:self.assertEqual(a.build_first('SYNTHETIC',side,v,CTX),a.base.build_first('SYNTHETIC',side,v,CTX))
 def test_clock_plain_settings_preserved(self):
  for side in ['K','L']:
   x=a.build_first('CONTROL_19','K','31T1',CTX);y=a.base.build_first('CONTROL_19','K','31L',CTX)
   self.assertEqual(x['payload']['contents'],y['payload']['contents']);self.assertEqual(x['payload']['generationConfig'],y['payload']['generationConfig'])
   self.assertIn('equivalent24-hour',x['payload']['system_instruction']['parts'][0]['text'])
 def test_clock_rules_are_not_numeric_copy_postprocessor(self):
  self.assertNotIn('4pm',a.CLOCK);self.assertNotIn('10pm',a.CLOCK);self.assertIn('meaning',a.CLOCK)
 def test_full_structure_retained_for_T3(self):
  x=a.build_first('SYNTHETIC','K','31T3',CTX);y=a.base.build_first('SYNTHETIC','K','31D',CTX)
  self.assertEqual(x['payload']['generationConfig'],y['payload']['generationConfig']);self.assertEqual(x['payload']['contents'],y['payload']['contents'])
 def test_T2_same_cap_and_thinking(self):
  x=a.build_first('CONTROL_19','K','31T2',CTX)['payload']['generationConfig'];self.assertEqual(x['maxOutputTokens'],2048);self.assertEqual(x['thinkingConfig']['thinkingLevel'],'minimal')
 def test_context_scope_only_system(self):
  x=a.build_first('SYNTHETIC','L','38CS',CTX)['payload'];y=a.base.build_first('SYNTHETIC','L','38FB',CTX)['payload']
  self.assertEqual(x['contents'],y['contents']);self.assertEqual(x['generationConfig'],y['generationConfig'])
 def test_alias_only_context_no_narrative(self):
  q=a.build_first('SYNTHETIC','L','38CA',CTX);x=json.loads(q['payload']['contents'][-1]['parts'][0]['text']);self.assertEqual(x['household_context']['aliases'],CTX['aliases']);self.assertNotIn('SYNTHETIC_CONTEXT_ONLY',str(q))
 def test_no_history(self):
  with self.assertRaises(ValueError):a.build_first('S','K','31T1',CTX,turns=['HISTORY'])
class Back(unittest.TestCase):
 def test_current_first_only_all_back_profiles(self):
  for side in ['K','L']:
   for v in ['31C','31TB','31RB','38P','38CB']:
    q=a.build_back('ACTUAL_FIRST_ONLY',side,v);self.assertEqual(q['payload']['contents'][-1]['parts'][0]['text'],'ACTUAL_FIRST_ONLY');self.assertNotIn('PRIVATE_ALIAS_CANARY',str(q));self.assertNotIn('household_context',str(q))
 def test_back_rejects_original_context(self):
  with self.assertRaises(TypeError):a.build_back('FIRST','K','31RB',context=CTX)
 def test_empty_back(self):
  with self.assertRaises(ValueError):a.build_back('','K','31RB')
 def test_RB_keeps_cap(self):
  q=a.build_back('FIRST','K','31RB')['payload']['generationConfig'];self.assertEqual(q['maxOutputTokens'],2048);self.assertEqual(q['thinkingConfig']['thinkingLevel'],'minimal')
 def test_CB_keeps_plain_standard(self):
  q=a.build_back('FIRST','K','38CB')['payload']['generationConfig'];self.assertEqual(q['maxOutputTokens'],1024);self.assertNotIn('responseSchema',q)
class Parse(unittest.TestCase):
 def test_plain_T1_foreign_text_preserved(self):
  x=a.inspect(response('FOREIGN_TEXT_STILL_VISIBLE'),'SOURCE','K','first','31T1');self.assertEqual(x['translation'],'FOREIGN_TEXT_STILL_VISIBLE')
 def test_fact_translation_only(self):
  raw=response(json.dumps({'facts':[{'span':'CONTROL_19','role':'time_point','scope':''}],'translation':'VISIBLE'}))
  out=a.inspect(raw,'CONTROL_19','K','first','31T2');self.assertEqual(out['translation'],'VISIBLE');self.assertTrue(out['span_verbatim'])
 def test_binding_translation_only(self):
  raw=response(json.dumps({'bindings':[{'span':'LABEL','predicate':'VERB','relation':'target'}],'translation':'VISIBLE'}))
  out=a.inspect(raw,'LABEL VERB','K','back','31RB');self.assertEqual(out['translation'],'VISIBLE')
 def test_unknown_relation_failure(self):
  raw=response(json.dumps({'bindings':[{'span':'LABEL','predicate':'V','relation':'invented'}],'translation':'VISIBLE'}))
  self.assertEqual(a.inspect(raw,'LABEL','K','back','31RB')['status'],'FAILED')
 def test_duplicate_key_failure(self):
  x=a.inspect(response('{"facts":[],"translation":"A","translation":"B"}'),'S','K','first','31T2');self.assertEqual(x['status'],'FAILED')
 def test_empty_and_truncated_fail(self):
  for v,stage in [('31T1','first'),('31T2','first'),('31RB','back')]:
   self.assertEqual(a.inspect(response('','MAX_TOKENS'),'S','K',stage,v)['status'],'FAILED')
 def test_metadata_never_needed_by_back(self):
  first=a.inspect(response('{"facts":[],"translation":"ACTUAL_FIRST_ONLY"}'),'ORIGINAL_CANARY','K','first','31T2')
  self.assertNotIn('ORIGINAL_CANARY',str(a.build_back(first['translation'],'K','31RB')))
class Gates(unittest.TestCase):
 def fixture(self):
  m={'campaign_id':c.ID,'recommended_only':False,'data_bound':True,'prior_new_attempts':0,'tasks':[{'slot':1,'stage':'first','side':'K','profile':'31T1','input':'SYNTHETIC','case_id':'SYN'}],'context':CTX}
  g={'authorized':True,'campaign_id':c.ID,'maximum_new_attempts':1,'prior_new_attempts':0,'whole_campaign_limit':320,'plan_sha256':c.digest(m)}
  return m,g
 def test_new_campaign_accepts_exact_synthetic_contract(self):
  m,g=self.fixture();c.authorize(m,g);c.validate(m)
 def test_old_approval_rejected(self):
  m,g=self.fixture();g['campaign_id']='GEMINI_FOLLOWUP272_20261103'
  with self.assertRaises(AssertionError):c.authorize(m,g)
 def test_unbound_data_rejected(self):
  m,g=self.fixture();m['data_bound']=False;g['plan_sha256']=c.digest(m)
  with self.assertRaises(AssertionError):c.authorize(m,g)
 def test_whole320_not_exceeded(self):
  m,g=self.fixture();m['prior_new_attempts']=320;g['prior_new_attempts']=320;g['plan_sha256']=c.digest(m)
  with self.assertRaises(AssertionError):c.authorize(m,g)
 def test_current_runtime_lock_no_send(self):
  m,g=self.fixture();actual=json.loads(Path(__file__).with_name('approval.json').read_text())
  with tempfile.TemporaryDirectory()as d:
   calls=[]
   with self.assertRaises(PermissionError):c.run(m,actual,lambda q:calls.append(q),Path(d)/'journal')
   self.assertEqual(calls,[]);self.assertFalse((Path(d)/'journal').exists())
 def test_failed_first_no_retry(self):
  m,g=self.fixture();m['tasks'].append({'slot':2,'stage':'back','side':'K','profile':'38P','depends_on':1,'case_id':'SYN'});g['maximum_new_attempts']=2;g['plan_sha256']=c.digest(m)
  with tempfile.TemporaryDirectory()as d:r=c.run(m,g,lambda q:{'raw':{},'wire':{'http_status':503,'api_ms':1}},Path(d)/'once')
  self.assertEqual(r['attempts'],1);self.assertEqual(r['slots'][1]['status'],'SKIPPED_DEPENDENCY');self.assertEqual(r['automatic_retries'],0)
class Crypto(unittest.TestCase):
 def test_inherited_synthetic_crypto_roundtrip_tamper(self):
  import importlib.util
  p=Path(__file__).resolve().parent.parent/'s47-realuse16/run.py'
  s=importlib.util.spec_from_file_location('crypto_only',p);b=importlib.util.module_from_spec(s);s.loader.exec_module(b)
  with tempfile.TemporaryDirectory()as d:
   key=Path(d)/'ephemeral.pem';pub=b.keypair(key);aad={'purpose':'SYNTHETIC_FREE_TEST'};sealed=b.seal({'synthetic':True},pub,aad)
   self.assertEqual(b.unseal(sealed,key,aad),{'synthetic':True})
   with self.assertRaises(ValueError):b.unseal(sealed,key,{'purpose':'WRONG'})
   self.assertNotIn('GEMINI_API_KEY',os.environ)
if __name__=='__main__':unittest.main()
