import unittest,copy,json,tempfile
from pathlib import Path
import controller as c
class Checks(unittest.TestCase):
 def setup_plan(self):
  t=[dict(slot=1,case_id='synthetic',path='KF',variant='SPAN_FOCUS31',input='나도 8시에 갈까?\r\n"안 가"'),dict(slot=2,case_id='synthetic',path='KB',variant='FROZEN',from_slot=1)];p=dict(campaign_id=c.ID,phase='A',tasks=t,freeze_sha256='synthetic');a=dict(campaign_id=c.ID,approved_limit=124,authorized=True,execution_enabled=True,phase='A',actual_attempts=0,actual_by_path=dict(KF=0,LF=0,KB=0,LB=0),plan_sha256=c.digest(p));return p,a
 def test_plan(self):p,a=self.setup_plan();self.assertTrue(c.validate(p,a))
 def test_zero_lock(self):p,a=self.setup_plan();a['authorized']=False;self.assertRaises(ValueError,c.validate,p,a)
 def test_cap(self):p,a=self.setup_plan();a['actual_attempts']=124;self.assertRaises(ValueError,c.validate,p,a)
 def test_extra_original_back_channel(self):
  p,a=self.setup_plan();p['tasks'][1]['original']='secret';a['plan_sha256']=c.digest(p);self.assertRaises(ValueError,c.validate,p,a)
 def test_cross_case_dependency(self):
  p,a=self.setup_plan();p['tasks'][1]['case_id']='other';a['plan_sha256']=c.digest(p);self.assertRaises(ValueError,c.validate,p,a)
 def test_first_failure_skip_no_retry(self):
  p,a=self.setup_plan()
  class W:
   def call(self,q):return {'model':'gemini-3.1-flash-lite','payload':{'generationConfig':{'maxOutputTokens':1024,'thinkingConfig':{'thinkingLevel':'minimal','includeThoughts':False}},'contents':[{'parts':[{'text':json.dumps({'current_message':q['text'],'focus':[]})}]}]}}
  with tempfile.TemporaryDirectory() as d:
   r=c.run(p,a,W(),lambda q:(_ for _ in ()).throw(TimeoutError()),Path(d)/'journal',lambda r:None);self.assertEqual(r['attempts'],1);self.assertEqual(r['slots'][1]['status'],'SKIPPED_DEPENDENCY');self.assertEqual(r['retry'],0)
 def test_journal_once(self):
  p,a=self.setup_plan()
  with tempfile.TemporaryDirectory() as d:
   j=Path(d)/'once';j.touch();self.assertRaises(FileExistsError,c.run,p,a,None,None,j,lambda r:None)
if __name__=='__main__':unittest.main()
