import unittest,tempfile,hashlib
from pathlib import Path
import controller as c
class Scope(unittest.TestCase):
 def test_unbounded_with_finite_plan_and_duplicate_journal(self):
  p=dict(campaign_id=c.ID,phase='DEV',tasks=[dict(slot=1,case_id='synthetic',path='KF',model='M31',variant='DIRECT',input='가정 2\n"3"'),dict(slot=2,case_id='synthetic',path='KB',model='M31',variant='DIRECT',depends_on=1)])
  ap=dict(campaign_id=c.ID,authorization_mode='unbounded-within-scope',approved_limit=None,actual_attempts=100000,planned_task_count=2,authorized=True,execution_enabled=True,plan_sha256=c.digest(p));inputs=[]
  def build(path,m,v,s):inputs.append(s);return dict(model='gemini-3.1-flash-lite',payload={})
  def send(q):return dict(raw={},wire=dict(http_status=200))
  def inspect(r,path,s,v):return dict(status='SUCCESS',displayed='실제 FIRST',retry_count=0)
  with tempfile.TemporaryDirectory()as d:
   j=Path(d)/'journal';r=c.run(p,ap,build,inspect,send,j,lambda r:None);self.assertEqual(r['attempts'],2);self.assertEqual(inputs[1],'실제 FIRST')
   with self.assertRaises(FileExistsError):c.run(p,ap,build,inspect,send,j,lambda r:None)
   ap['authorized']=False
   with self.assertRaises(ValueError):c.run(p,ap,build,inspect,send,Path(d)/'new',lambda r:None)
 def test_no_hidden_BACK_original(self):
  with self.assertRaises(ValueError):c.validate(dict(tasks=[dict(slot=1,case_id='x',path='KB',model='M31',variant='DIRECT',depends_on=1,input='hidden')]))
 def test_closed_session_retains_scope_consent_without_sends(self):
  a=dict(campaign_id=c.ID,authorization_mode='unbounded-within-scope',approved_limit=None,authorized=True,execution_enabled=True)
  z=c.close(a,256);self.assertTrue(z['authorized']);self.assertFalse(z['execution_enabled']);self.assertIsNone(z['approved_limit']);self.assertEqual(z['planned_task_count'],0)
  p=dict(campaign_id=c.ID,phase='DEV',tasks=[dict(slot=1,case_id='synthetic',path='KF',model='M31',variant='DIRECT',input='안녕')]);z['plan_sha256']=c.digest(p);sent=[]
  with tempfile.TemporaryDirectory() as d:
   with self.assertRaises(ValueError):c.run(p,z,lambda *a:None,lambda *a:None,lambda q:sent.append(q),Path(d)/'j',lambda r:None)
  self.assertEqual(sent,[])
if __name__=='__main__':unittest.main()
