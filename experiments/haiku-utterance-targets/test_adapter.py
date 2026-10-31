import importlib.util
import json
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('la2_test_adapter',ROOT/'adapter.py')
a=importlib.util.module_from_spec(spec);spec.loader.exec_module(a)

def raw(items, stop='end_turn'):
    return {'stop_reason':stop,'content':[{'type':'text','text':json.dumps({'utterances':items})}]}

class UtteranceContract(unittest.TestCase):
    def test_lossless_and_no_word_segmentation(self):
        for s in ['  A. B?\r\n C!  ','ຂ້ອຍ ກໍ ພັກຜ່ອນ','10.5 700,000','\n\n A\n B']:
            self.assertEqual(''.join(a.split_utterances(s)),s)
        self.assertEqual(len(a.split_utterances('ຂ້ອຍ ກໍ ພັກຜ່ອນ')),1)
        self.assertEqual(len(a.split_utterances('10.5 700,000')),1)
    def test_explicit_boundaries_without_rewriting_targets(self):
        r=a.inspect_response(raw([{'index':0,'target':'첫 문장'},{'index':1,'target':'다음 문장'}]),'A. B.')
        self.assertEqual(r['translation'],'첫 문장\n다음 문장')
    def test_missing_duplicate_reordered_and_boolean_indexes_rejected(self):
        bad=[[],[{'index':0,'target':'a'}],[{'index':0,'target':'a'},{'index':0,'target':'b'}],
             [{'index':1,'target':'b'},{'index':0,'target':'a'}],
             [{'index':False,'target':'a'},{'index':1,'target':'b'}]]
        for items in bad:
            with self.assertRaises(ValueError):a.inspect_response(raw(items),'A. B.')
    def test_whole_json_and_end_turn_required(self):
        r=raw([{'index':0,'target':'x'}])
        for text in ['{}{}','{"utterances":[],"utterances":[]}','{"utterances":']:
            r['content'][0]['text']=text
            with self.assertRaises(ValueError):a.inspect_response(r,'A')
        with self.assertRaises(ValueError):a.inspect_response(raw([{'index':0,'target':'x'}],'max_tokens'),'A')
    def test_four_routes_and_back_uses_only_own_visible_output(self):
        for side in ['K','L']:
            for stage in ['first','back']:
                q=a.build_request('SOURCE',side,stage)
                self.assertEqual(q['max_tokens'],2048)
                self.assertEqual(q['thinking'],{'type':'disabled'})
                self.assertEqual(q['model'],'claude-haiku-5-5')
                self.assertNotIn('SOURCE',json.dumps(q['output_config']['format']['schema']))
        q=a.prepare_back(raw([{'index':0,'target':'OWN_VISIBLE'}]),'PRIVATE_ORIGINAL','L')
        self.assertIn('OWN_VISIBLE',q['messages'][0]['content'])
        self.assertNotIn('PRIVATE_ORIGINAL',json.dumps(q))
    def test_wrong_medical_meaning_is_not_detected_or_repaired(self):
        result=a.inspect_response(raw([{'index':0,'target':'약을 먹지 말래'}]),'SOURCE')
        self.assertEqual(result['translation'],'약을 먹지 말래')
        self.assertEqual(result['semantic_quality'],'UNVERIFIED')

if __name__=='__main__':unittest.main()
