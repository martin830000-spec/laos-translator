import importlib.util,unittest
from pathlib import Path
s=importlib.util.spec_from_file_location('ki1_test',Path(__file__).parent/'adapter.py');a=importlib.util.module_from_spec(s);s.loader.exec_module(a)
class LocalizedContract(unittest.TestCase):
 def test_settings_source_and_full_roles(self):
  for side in ['K','L']:
   for stage in ['first','back']:
    text=' \nSYNTHETIC <tag> ກ່ອນ 😘\n ';b=a.baseline_request(text,side,stage);q=a.build_request(text,side,stage)
    self.assertEqual({k:v for k,v in q.items() if k not in ['system','messages']},{k:v for k,v in b.items() if k not in ['system','messages']})
    self.assertEqual(q['messages'][0]['content'].split('<source>\n',1)[1].rsplit('\n</source>',1)[0],text)
    self.assertIn('명확히 달리' if side=='L' else '명시적으로 달리',q['system']);self.assertIn('친족' if side=='L' else '제3자',q['system'])
 def test_back_cannot_receive_original_and_output_not_cleaned(self):
  q=a.build_request('VISIBLE_FIRST_ONLY','L','back');self.assertEqual(len(q['messages']),1);self.assertIn('이전 원문을 모릅니다',q['system'])
  t=' first\nCorrection, final answer only:\nsecond ';raw={'type':'message','stop_reason':'end_turn','content':[{'type':'text','text':t}]};self.assertEqual(a.inspect_response(raw)['translation'],t)
if __name__=='__main__':unittest.main()
