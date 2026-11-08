import unittest,json,pathlib,tempfile
from contract import *
class ContractTests(unittest.TestCase):
 def setUp(self):self.p=json.loads(pathlib.Path('prompts.json').read_text())
 def test_payload_four_configs(self):
  for m in MODELS:
   for e in ('none','low'):
    for p in self.p:
     x=build_payload(m,e,p,' 원문 ລາວ 😀 ',self.p);self.assertEqual(x['input'],' 원문 ລາວ 😀 ');self.assertEqual(x['instructions'],self.p[p])
 def test_back_no_original_or_context(self):
  x=build_payload(MODELS[0],'none','KB','ລາວ ',self.p);assert_back_payload(x,'ລາວ ',self.p,'KB')
  for k in ['previous_response_id','conversation','metadata','tools']:
   bad=dict(x);bad[k]='LEAK'
   with self.assertRaises(AssertionError):assert_back_payload(bad,'ລາວ ',self.p,'KB')
  with self.assertRaises(AssertionError):assert_back_payload(x,'ລາວ',self.p,'KB')
 def test_model_effort_allowlist(self):
  for m,e in [('gpt-6-astra','low'),(MODELS[0],'medium')]:
   with self.assertRaises(AssertionError):build_payload(m,e,'KF','x',self.p)
 def test_caps_and_persisted_restart(self):
  r=[]
  for i in range(80):r.append(budget_guard(r,str(i),MODELS[0]))
  with self.assertRaises(AssertionError):budget_guard(r,'81',MODELS[0])
  with tempfile.TemporaryDirectory() as d:
   f=pathlib.Path(d)/'ledger.json';f.write_text(json.dumps(r));r=json.loads(f.read_text())
   with self.assertRaises(AssertionError):budget_guard(r,'0',MODELS[1])
   for i in range(80,160):r.append(budget_guard(r,str(i),MODELS[1]))
   with self.assertRaises(AssertionError):budget_guard(r,'161',MODELS[1])
 def events(self,text=' 한국어 ລາວ 😀 ',status='completed',usage=None):
  return [{'type':'response.output_text.delta','delta':text[:2]},{'type':'response.output_text.delta','delta':text[2:]},{'type':'response.output_text.done','text':text},{'type':'response.'+status,'response':{'status':status,'output':[{'content':[{'type':'output_text','text':text}]}],'usage':usage}}]
 def test_unicode_no_trim_and_missing_usage(self):
  r=parse_events(self.events());self.assertTrue(r['success']);self.assertEqual(r['display_text'],' 한국어 ລາວ 😀 ');self.assertIsNone(r['usage'])
 def test_incomplete_not_success(self):self.assertFalse(parse_events(self.events(status='incomplete'))['success'])
 def test_disconnected_partial(self):
  r=parse_events(self.events()[:2]);self.assertFalse(r['success']);self.assertEqual(r['partial_text'],' 한국어 ລາວ 😀 ')
 def test_refusal(self):self.assertFalse(parse_events([{'type':'response.refusal.delta','delta':'No'}]+self.events())['success'])
 def test_mismatch(self):
  e=self.events();e[-1]['response']['output'][0]['content'][0]['text']='altered';self.assertTrue(parse_events(e)['mismatch'])
 def test_empty(self):self.assertFalse(parse_events(self.events(' '))['success'])
 def test_plan_sample_contract(self):
  a=json.loads(pathlib.Path('evidence/SOURCE_MANIFEST.json').read_text())['selected'];p=json.loads(pathlib.Path('evidence/RUN_PLAN.json').read_text())['slots'];self.assertEqual(len(a),16);self.assertEqual(len(p),160)
  for side in ['K','L']:
   self.assertEqual(sum(x['direction']==side and x['classification']=='normal' for x in a),5)
   self.assertEqual(sum(x['direction']==side and x['classification']=='difficult' for x in a),3)
  self.assertEqual(sum(x['phase']=='FIRST' for x in p),64)
if __name__=='__main__':unittest.main()
