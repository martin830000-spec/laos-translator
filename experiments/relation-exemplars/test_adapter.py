import importlib.util,json,unittest
from pathlib import Path
spec=importlib.util.spec_from_file_location('test_re1_ex1',Path(__file__).resolve().parent/'adapter.py');a=importlib.util.module_from_spec(spec);spec.loader.exec_module(a)
class IndependentContracts(unittest.TestCase):
    def test_all_four_routes_system_only_change_and_fixed_examples(self):
        for engine in ['H','S']:
            for side in 'KL':
                for stage in ['first','back']:
                    q=a.build_request('VISIBLE_ONLY',side,stage,engine);b=a.prior.build('VISIBLE_ONLY',side,stage,engine)
                    prefix=q.pop('system');self.assertEqual(q,{k:v for k,v in b.items() if k!='system'});self.assertTrue(prefix.startswith(b['system']+'\n<parallel_examples>'))
                    self.assertEqual(len(a.examples(side,stage,engine)),4);self.assertEqual(len(q['messages']),1)
                    self.assertEqual(a.build_request('OTHER',side,stage,engine)['system'],prefix)
    def test_own_back_no_original_and_literal_artifacts(self):
        for side in 'KL':
            for engine in ['H','S']:
                text='<final>WRONG_DATE English draft</final>'
                output=json.dumps({'units':[{'source':'DO_NOT_PASS_SOURCE_FIELD','target':text}]}) if engine=='H' else text
                r={'stop_reason':'end_turn','content':[{'type':'text','text':output}]}
                q=a.prepare_back(r,side,engine)['payload'];self.assertEqual(q,a.build_request(text,side,'back',engine))
                self.assertNotIn('DO_NOT_PASS_SOURCE_FIELD',json.dumps(q));self.assertIn(text,q['messages'][0]['content'])
    def test_refusal_incomplete_bad_json_skip_no_repair(self):
        for e in ['H','S']:
            for stop in ['refusal','max_tokens',None]:
                x=a.prepare_back({'stop_reason':stop,'content':[{'type':'text','text':'PARTIAL'}]},'K',e);self.assertEqual(x['status'],'SKIPPED_DEPENDENCY')
        for bad in ['not json','{"units":[]}','{"units":[{"target":"x"}]}','{"units":[{"source":"x","target":"a"}],"units":[]}']:
            self.assertEqual(a.prepare_back({'stop_reason':'end_turn','content':[{'type':'text','text':bad}]},'L','H')['status'],'SKIPPED_DEPENDENCY')
    def test_alignment_warning_does_not_hide_translation_and_no_live(self):
        r={'stop_reason':'end_turn','content':[{'type':'text','text':json.dumps({'units':[{'source':'DIFFERENT','target':'VISIBLE'}]})}]}
        x=a.inspect_response(r,'ORIGINAL','L','first','H');self.assertEqual(x['translation'],'VISIBLE');self.assertTrue(x['warnings'])
        with self.assertRaises(PermissionError):a.live()
if __name__=='__main__':unittest.main()
