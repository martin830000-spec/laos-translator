import importlib.util,unittest,json
from pathlib import Path
s=importlib.util.spec_from_file_location('lb1c_test',Path(__file__).resolve().parent/'adapter.py');a=importlib.util.module_from_spec(s);s.loader.exec_module(a)
class Contracts(unittest.TestCase):
    def test_punctuation_unknown_emoji_and_bad_lao_tokenizer(self):
        text='ລາວ/ລາວ IV 123 한국어\n😢';out=a.preserve_runs(text,lambda _:['CHANGED'])
        self.assertEqual(''.join(out),text);self.assertIn('/'+'', ''.join(out));self.assertIn(' IV 123 한국어\n😢',out)
    def test_four_routes_settings_and_Korean_unchanged(self):
        for side in 'KL':
            for stage in ['first','back']:
                text='ລາວ/ລາວ';x=a.build_request(text,side,stage,list);base=a.lb.prior.build_request(text,side,stage,'LA1')
                if (side=='K')==(stage=='first'):self.assertEqual(x['payload'],base)
                else:self.assertEqual(''.join(x['hints']['tokens']),text)
                self.assertEqual({k:v for k,v in x['payload'].items() if k!='messages'},{k:v for k,v in base.items() if k!='messages'})
    def test_own_BACK_artifacts_preserved_no_original_and_no_live(self):
        visible='ລາວ/ລາວ draft';raw={'stop_reason':'end_turn','content':[{'type':'text','text':json.dumps({'units':[{'source':'SECRET_ORIGINAL','target':visible}]})}]}
        for side in 'KL':
            x=a.prepare_back(raw,side,list);self.assertEqual(x['payload'],a.build_request(visible,side,'back',list)['payload']);self.assertNotIn('SECRET_ORIGINAL',json.dumps(x['payload']))
        self.assertEqual(a.prepare_back({'stop_reason':'max_tokens'},'K',list)['status'],'SKIPPED_DEPENDENCY')
        with self.assertRaises(PermissionError):a.live()
if __name__=='__main__':unittest.main()
