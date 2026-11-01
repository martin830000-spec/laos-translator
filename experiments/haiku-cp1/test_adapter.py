from pathlib import Path
import importlib.util,unittest,json
s=importlib.util.spec_from_file_location('test_cp1',Path(__file__).parent/'adapter.py');a=importlib.util.module_from_spec(s);s.loader.exec_module(a)
class Contract(unittest.TestCase):
 def test_only_planning_contract_and_schema_change(self):
  for side in ['K','L']:
   for stage in ['first','back']:
    text=' \nSYNTHETIC ກ່ອນ  😘\n ';q=a.build_request(text,side,stage);b=a.la1.build_request(text,side,stage,'LA1')
    self.assertEqual(q['messages'],b['messages']);self.assertEqual(q['thinking'],b['thinking']);self.assertEqual(q['model'],b['model']);self.assertEqual(q['max_tokens'],2048);self.assertEqual(q['output_config']['effort'],'low')
    self.assertEqual(q['system'].removesuffix(a.CONTRACT),b['system'].removesuffix(a.la1.CONTRACT));self.assertNotIn('units',q['output_config']['format']['schema']['properties'])
 def test_visible_translation_exact_no_correction_or_alternative_rendering(self):
  text=' first\nCorrection: second ';obj={'source_readings':['SOURCE_READING_A','SOURCE_READING_B'],'chosen_reading':0,'selection_reason':'MOCK','translation':text};raw={'stop_reason':'end_turn','content':[{'type':'thinking','thinking':'NEVER_VISIBLE'},{'type':'text','text':json.dumps(obj)}]}
  o=a.inspect_response(raw,'CURRENT_ONLY','L','back');self.assertEqual(o['translation'],text);self.assertEqual(o['reading_count'],2);self.assertNotIn('NEVER_VISIBLE',o['raw_visible_text'])
 def test_wrong_but_valid_meaning_is_not_silently_fixed(self):
  obj={'source_readings':['MOCK wrong reading'],'chosen_reading':0,'selection_reason':'MOCK','translation':'WRONG_BUT_VALID'};raw={'stop_reason':'end_turn','content':[{'type':'text','text':json.dumps(obj)}]};self.assertEqual(a.inspect_response(raw,'UNRELATED_SOURCE','L','first')['translation'],'WRONG_BUT_VALID')
  obj['chosen_reading']=1;raw['content'][0]['text']=json.dumps(obj)
  with self.assertRaises(ValueError):a.inspect_response(raw,'CURRENT_ONLY','L','back')
if __name__=='__main__':unittest.main()
