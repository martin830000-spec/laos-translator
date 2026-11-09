import unittest,json,pathlib,hashlib
from contract import *
P=json.loads((pathlib.Path(__file__).parent/'prompts.json').read_bytes())
class Contracts320(unittest.TestCase):
 def reservations(self,n,stage='P1'):
  return [dict(slot=f'S{i:03d}',model=MODELS[0],stage=stage) for i in range(n)]
 def test_321_blocked(self):
  rs=self.reservations(96)+[dict(slot=f'P2-{i}',model=MODELS[0],stage='P2') for i in range(64)]+[dict(slot=f'F-{i}',model=MODELS[0],stage='FINAL') for i in range(160)]
  with self.assertRaisesRegex(AssertionError,'TOTAL_CAP'):budget_guard(rs,'NEW',MODELS[0],'FINAL')
 def test_each_stage_blocked(self):
  for stage,cap in CAPS.items():
   with self.assertRaisesRegex(AssertionError,'STAGE_CAP'):budget_guard(self.reservations(cap,stage),'NEW',MODELS[0],stage)
 def test_no_model80_limit(self):self.assertEqual(budget_guard(self.reservations(80),'NEW',MODELS[0],'P1')['stage'],'P1')
 def test_duplicate(self):
  with self.assertRaisesRegex(AssertionError,'DUPLICATE_SLOT'):budget_guard(self.reservations(1),'S000',MODELS[1],'P2')
 def test_unknown_is_consumed_on_resume(self):
  rs=self.reservations(96)
  for r in rs:r['state']='RESERVED_TRANSMISSION_UNKNOWN'
  self.assertEqual(json.loads(json.dumps(rs)),rs)
  with self.assertRaisesRegex(AssertionError,'STAGE_CAP'):budget_guard(json.loads(json.dumps(rs)),'OTHER',MODELS[0],'P1')
 def test_wrong_meaning_complete_first_still_back(self):
  text='wrong meaning but complete ລາວ'
  self.assertEqual(back_input({'success':True,'display_text':text,'semantic_grade':'P0'}),text)
 def test_technical_failure_skips(self):
  for p in [None,{'success':False,'display_text':'partial'},{'success':True,'display_text':''},{'success':True,'display_text':'  '}]:self.assertIsNone(back_input(p))
 def test_exact_back_and_no_state(self):
  text=' ລາວ\n한글  '
  p=build_payload(MODELS[0],'none','KB',text,P);assert_back_payload(p,text,P,'KB');self.assertEqual(p['input'].encode(),text.encode())
  for k in ['previous_response_id','conversation','source','metadata']:
   q=p.copy();q[k]='original'
   with self.assertRaises(AssertionError):assert_back_payload(q,text,P,'KB')
 def test_none_explicit(self):self.assertEqual(build_payload(MODELS[0],'none','KF','x',P)['reasoning'],{'effort':'none'})
 def test_sharing_requires_every_setting_and_parser(self):
  p=build_payload(MODELS[0],'none','LF','x',P);key=shared_request_key(p,'parser1')
  self.assertEqual(key,shared_request_key(p.copy(),'parser1'))
  for k,v in [('model',MODELS[1]),('input','other FIRST'),('instructions','other'),('reasoning',{'effort':'low'}),('max_output_tokens',2048)]:
   q=p.copy();q[k]=v;self.assertNotEqual(key,shared_request_key(q,'parser1'))
  self.assertNotEqual(key,shared_request_key(p,'parser2'))
 def test_parser_failure_and_incomplete(self):
  for ev in [[{'type':'response.incomplete','response':{'status':'incomplete'}}],[{'type':'response.completed','response':{'status':'completed','output':[]}}],[{'type':'response.refusal.delta','delta':'no'}]]:self.assertFalse(parse_events(ev)['success'])
if __name__=='__main__':unittest.main()
