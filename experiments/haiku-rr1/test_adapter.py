import importlib.util,unittest,json
from pathlib import Path
s=importlib.util.spec_from_file_location('test_rr',Path(__file__).parent/'adapter.py');a=importlib.util.module_from_spec(s);s.loader.exec_module(a)
class Contract(unittest.TestCase):
 def test_all_routes_exact_duplicate_unchanged_schema_settings(self):
  text='  SENTINEL ໂທລົມ  내일 🥲\n'
  for side in ['K','L']:
   for stage in ['first','back']:
    b=a.la1.build_request(text,side,stage,'LA1');q=a.build_request(text,side,stage)
    self.assertEqual(q['messages'][0]['content'],b['messages'][0]['content']+'\n\n'+b['messages'][0]['content'])
    for key in ['output_config','model','max_tokens','thinking']:self.assertEqual(q[key],b[key])
    self.assertEqual(q['system'],b['system']+a.REREAD)
 def test_exact_output_no_semantic_success_claim_no_hidden_plan(self):
  visible=' Wrong but structurally valid meaning <final> English draft\n'
  raw=dict(stop_reason='end_turn',content=[dict(type='thinking',thinking='PRIVATE_HIDDEN'),dict(type='text',text=json.dumps({'units':[{'source':'VISIBLE_ONLY','target':visible}]}))])
  x=a.inspect_response(raw,'VISIBLE_ONLY','L','first');self.assertEqual(x['translation'],visible)
  q=a.build_request(x['translation'],'L','back');self.assertNotIn('PRIVATE_HIDDEN',str(q));self.assertNotIn('ORIGINAL_SECRET',str(q))
  with self.assertRaises(ValueError):a.inspect_response(dict(raw,stop_reason='max_tokens'),'VISIBLE_ONLY','L','first')
if __name__=='__main__':unittest.main()
