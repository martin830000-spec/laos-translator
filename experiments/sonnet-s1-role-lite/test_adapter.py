from pathlib import Path
import importlib.util,unittest
s=importlib.util.spec_from_file_location('role_lite_tests',Path(__file__).resolve().parent/'adapter.py');a=importlib.util.module_from_spec(s);s.loader.exec_module(a)
class SingleFactor(unittest.TestCase):
 def test_only_FIRST_role_block_changes(self):
  for side in 'KL':
   old=a.baseline_request(' ACTUAL_ONLY\r\n ',side,'first');new=a.build_request(' ACTUAL_ONLY\r\n ',side,'first');text=new['system'];new['system']=old['system'];self.assertEqual(new,old)
   expected=old['system'].replace('<couple_context>'+a.core.PROMPTS['CLAUDE_SONNET55_S1_ROLE_'+side]+'</couple_context>','<couple_context>'+a.ROLE[side]+'</couple_context>');self.assertEqual(text,expected)
 def test_BACK_exactly_original_S1(self):
  for side in 'KL':self.assertEqual(a.build_request('UNMODIFIED_VISIBLE',side,'back'),a.baseline_request('UNMODIFIED_VISIBLE',side,'back'))
 def test_BACK_only_VISIBLE_including_drafts_no_hidden_thinking(self):
  r={'stop_reason':'end_turn','content':[{'type':'thinking','thinking':'HIDDEN_NOT_FOR_BACK'},{'type':'text','text':'FIRST_DRAFT\nWait: FINAL_DRAFT'}]};q=a.prepare_back(r,'L')['payload'];self.assertIn('FIRST_DRAFT\nWait: FINAL_DRAFT',q['messages'][0]['content']);self.assertNotIn('HIDDEN_NOT_FOR_BACK',str(q))
 def test_refusal_and_wrong_meaning_not_repaired(self):
  r={'stop_reason':'refusal','content':[{'type':'text','text':'PARTIAL'}]};self.assertEqual(a.prepare_back(r,'K')['status'],'SKIPPED_DEPENDENCY');self.assertEqual(a.inspect_response(r)['translation'],'PARTIAL')
  r={'stop_reason':'end_turn','content':[{'type':'text','text':'WRONG_MEANING Wait: SECOND_DRAFT'}]};self.assertEqual(a.inspect_response(r)['translation'],'WRONG_MEANING Wait: SECOND_DRAFT')
if __name__=='__main__':unittest.main()
