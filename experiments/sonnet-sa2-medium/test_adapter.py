import importlib.util
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location('sa2',Path(__file__).resolve().parent/'adapter.py')
a=importlib.util.module_from_spec(spec);spec.loader.exec_module(a)

class MediumResearch(unittest.TestCase):
    def test_only_effort_changes_all_four_routes(self):
        for side in 'KL':
            for stage in ['first','back']:
                q=a.build_request(' SOURCE\r\n ',side,stage)
                old=a.prior.build_request(' SOURCE\r\n ',side,stage)
                self.assertEqual(q['output_config']['effort'],'medium')
                q['output_config']['effort']='low';self.assertEqual(q,old)
    def test_back_only_actual_visible_text_no_reasoning_or_original(self):
        raw={'stop_reason':'end_turn','content':[{'type':'thinking','thinking':'PRIVATE_THINKING'},
            {'type':'text','text':'VISIBLE_WITH_COMMENTARY'}]}
        back=a.prepare_back(raw,'L')['payload']
        self.assertIn('VISIBLE_WITH_COMMENTARY',back['messages'][0]['content'])
        self.assertNotIn('PRIVATE_THINKING',str(back))
        self.assertEqual(back['output_config']['effort'],'medium')
    def test_refusal_still_fails_and_partial_is_not_repaired(self):
        raw={'stop_reason':'refusal','stop_details':{'category':'reasoning_extraction'},
             'content':[{'type':'text','text':'PARTIAL_VISIBLE'}]}
        self.assertEqual(a.inspect_response(raw)['translation'],'PARTIAL_VISIBLE')
        self.assertEqual(a.inspect_response(raw)['status'],'FAILED')
        self.assertEqual(a.prepare_back(raw,'K')['status'],'SKIPPED_DEPENDENCY')
    def test_wrong_meaning_and_exposed_draft_are_never_silently_fixed(self):
        for text in ['약을 먹지 말래','Wait — I need to correct: FIRST_DRAFT FINAL_DRAFT']:
            raw={'stop_reason':'end_turn','content':[{'type':'text','text':text}]}
            self.assertEqual(a.inspect_response(raw)['translation'],text)
            self.assertEqual(a.inspect_response(raw)['semantic_quality'],'UNVERIFIED')

if __name__=='__main__':unittest.main()
