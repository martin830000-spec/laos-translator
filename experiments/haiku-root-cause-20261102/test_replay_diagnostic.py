import unittest,json
from replay_diagnostic import inspect,validate_relations
def raw(units,stop='end_turn',thinking=False):
 return {'stop_reason':stop,'content':([{'type':'thinking','thinking':'private plan'}] if thinking else [])+[{'type':'text','text':json.dumps({'units':units})}]}
class Contract(unittest.TestCase):
 def test_join_is_exact_no_added_spaces(self):
  r=inspect(raw([{'source':'one','target':'A'},{'source':'two','target':'B'}]),'onetwo','AB');self.assertTrue(r['recorded_display_exact']);self.assertEqual(r['display'],'AB')
 def test_mismatch_warns_and_preserves(self):
  r=inspect(raw([{'source':'changed','target':'kept'}]),'original');self.assertFalse(r['source_aligned']);self.assertEqual(r['display'],'kept')
 def test_empty_target_is_not_automatic_omission(self):
  r=inspect(raw([{'source':'one','target':'one and two'},{'source':'two','target':''}]),'onetwo');self.assertEqual(r['semantic_verdict'],'NOT_INFERRED');self.assertEqual(r['empty_target_indices'],[1])
 def test_incomplete_valid_json_still_not_salvaged(self):
  self.assertIsNone(inspect(raw([{'source':'a','target':'b'}],'max_tokens'),'a')['display'])
 def test_hidden_thinking_excluded_from_display_and_back(self):
  r=inspect(raw([{'source':'a','target':'b'}],thinking=True),'a','b','b');self.assertTrue(r['back_input_exact']);self.assertEqual(r['thinking_blocks_excluded'],1)
 def test_back_byte_difference_detected(self):
  self.assertFalse(inspect(raw([{'source':'a','target':'b'}]),'a','b','b ')['back_input_exact'])
 def test_duplicate_keys_rejected(self):
  r=inspect({'stop_reason':'end_turn','content':[{'type':'text','text':'{"units":[],"units":[]}'}]},'a');self.assertEqual(r['status'],'INVALID_JSON_OR_SCHEMA')
 def test_exact_source_does_not_certify_semantics(self):
  r=inspect(raw([{'source':'phone','target':'physical visit'}]),'phone');self.assertTrue(r['source_aligned']);self.assertEqual(r['semantic_verdict'],'NOT_INFERRED')
 def test_relation_grounding_rejects_invented_span(self):
  with self.assertRaises(ValueError):validate_relations([{'annotator':'human','status':'PROVISIONAL','evidence':[{'start':0,'end':5,'text':'never'}]}],'phone')
 def test_provisional_grounding_not_native_verification(self):
  r=validate_relations([{'annotator':'human','status':'PROVISIONAL','evidence':[{'start':0,'end':5,'text':'phone'}]}],'phone');self.assertFalse(r['semantic_truth_verified']);self.assertFalse(r['model_quality_improvement_proven'])
if __name__=='__main__':unittest.main()
