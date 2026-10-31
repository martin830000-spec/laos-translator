import importlib.util,json,unittest
from pathlib import Path
s=importlib.util.spec_from_file_location('lb1_tests',Path(__file__).resolve().parent/'adapter.py');a=importlib.util.module_from_spec(s);s.loader.exec_module(a)
class LosslessContracts(unittest.TestCase):
    def test_four_routes_no_setting_or_original_change(self):
        for side in 'KL':
            for stage in ['first','back']:
                source='ລາວ  😘\nຖ້າ 123 한국어';x=a.build_request(source,side,stage,list);base=a.prior.build_request(source,side,stage,'LA1');q=x['payload']
                self.assertEqual({k:v for k,v in q.items() if k!='messages'},{k:v for k,v in base.items() if k!='messages'})
                self.assertTrue(q['messages'][0]['content'].startswith(base['messages'][0]['content']))
                if (side=='K')==(stage=='first'):self.assertEqual(q,base)
                else:self.assertEqual(''.join(x['hints']['tokens']),source)
    def test_bad_segmentation_preserves_original_no_hint_repair(self):
        x=a.build_request('ລາວ','L','first',lambda _:['DIFFERENT']);self.assertEqual(x['payload'],a.prior.build_request('ລາວ','L','first','LA1'));self.assertEqual(x['hints']['status'],'NO_HINT_LOSSLESS_CHECK_FAILED')
    def test_back_only_actual_display_and_artifacts_preserved(self):
        text='<final>ລາວ English draft</final>';r={'stop_reason':'end_turn','content':[{'type':'text','text':json.dumps({'units':[{'source':'SECRET_ORIGINAL_UNIT','target':text}]})}]}
        for side in 'KL':
            out=a.prepare_back(r,side,list);self.assertEqual(out['payload'],a.build_request(text,side,'back',list)['payload']);self.assertNotIn('SECRET_ORIGINAL_UNIT',json.dumps(out['payload']))
    def test_incomplete_refusal_skip_and_no_live(self):
        for reason in ['max_tokens','refusal',None]:self.assertEqual(a.prepare_back({'stop_reason':reason,'content':[]},'K',list)['status'],'SKIPPED_DEPENDENCY')
        with self.assertRaises(PermissionError):a.live()
if __name__=='__main__':unittest.main()
