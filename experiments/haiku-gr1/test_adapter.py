from pathlib import Path
import unittest,importlib.util,json
s=importlib.util.spec_from_file_location('gr1_test',Path(__file__).resolve().parent/'adapter.py');a=importlib.util.module_from_spec(s);s.loader.exec_module(a)
class Contracts(unittest.TestCase):
    def test_no_match_and_Korean_are_exact_LA1(self):
        for side in 'KL':
            for stage in ['first','back']:
                text='ລາວ ຮັກ ຖ້າ' if (side=='K')==(stage=='first') else 'ສະບາຍດີ'
                self.assertEqual(a.build_request(text,side,stage)['payload'],a.lb.prior.build_request(text,side,stage,'LA1'))
    def test_marker_offsets_no_answer_or_attachment_selected(self):
        text=' 😁 ຖ້າ abc/ຫຼິ້ນ\nຖ້າ'
        x=a.build_request(text,'L','first');q=x['payload'];base=a.lb.prior.build_request(text,'L','first','LA1')
        self.assertTrue(q['messages'][0]['content'].startswith(base['messages'][0]['content']))
        self.assertEqual({k:v for k,v in q.items() if k not in ['system','messages']},{k:v for k,v in base.items() if k not in ['system','messages']})
        for m in x['cues']['markers']:self.assertEqual(text[m['start']:m['end']],m['literal']);self.assertEqual(m['interpretation'],'UNSELECTED')
        self.assertNotIn('phone',q['system']);self.assertNotIn('Friday',q['system'])
    def test_BACK_only_own_display_and_refusal_preserved(self):
        visible='ຖ້າ <final>English draft</final> /';response={'stop_reason':'end_turn','content':[{'type':'text','text':json.dumps({'units':[{'source':'SECRET_ORIGINAL','target':visible}]})}]}
        for side in 'KL':
            x=a.prepare_back(response,side);self.assertEqual(x['payload'],a.build_request(visible,side,'back')['payload']);self.assertNotIn('SECRET_ORIGINAL',json.dumps(x['payload']))
        self.assertEqual(a.prepare_back({'stop_reason':'refusal'},'K')['status'],'SKIPPED_DEPENDENCY')
    def test_caps_fail_to_exact_baseline_and_no_live(self):
        for text in ['ຖ້າ'*9,'ຖ້າ'+'x'*4000]:self.assertEqual(a.build_request(text,'L','first')['payload'],a.lb.prior.build_request(text,'L','first','LA1'))
        with self.assertRaises(PermissionError):a.live()
if __name__=='__main__':unittest.main()
