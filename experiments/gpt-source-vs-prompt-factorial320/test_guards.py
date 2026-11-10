import unittest,hashlib,pathlib,json
from contract import budget_guard,repetition_guard,MODEL_CAPS
class Guards(unittest.TestCase):
 def test_model_caps(self):
  for model,cap in MODEL_CAPS.items():
   stage='C' if model.startswith('gemini') else 'A1'
   rs=[dict(slot=str(i),model=model,stage=stage) for i in range(cap)]
   with self.assertRaises(AssertionError):budget_guard(rs,'new',model,stage)
 def test_stage_caps(self):
  for stage,cap in [('A1',240),('B1',40),('C',40)]:
   m='gemini-3.8-flash' if stage=='C' else 'gpt-6-luna'
   with self.assertRaises(AssertionError):budget_guard([dict(slot=str(i),model=m,stage=stage) for i in range(cap)],'new',m,stage)
 def test_wrong_model(self):
  for m in ['gpt-6-terra','gemini-3.5-flash-lite','claude','gpt-6-luna']:
   with self.assertRaises(AssertionError):budget_guard([],'new',m,'C')
 def test_duplicate(self):
  with self.assertRaises(AssertionError):budget_guard([dict(slot='x',model='gpt-6-luna',stage='A1')],'x','gpt-6-luna','A1')
 def test_five(self):
  with self.assertRaises(AssertionError):repetition_guard([dict(condition_sha256='x')]*5,dict(condition_sha256='x',repeat_index=6))
if __name__=='__main__':unittest.main()
