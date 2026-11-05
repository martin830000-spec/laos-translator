import unittest,tempfile,json
from pathlib import Path
import controller as c
def fixture():
 p=dict(campaign_id=c.ID,phase='A',tasks=[dict(slot=1,case_id='synthetic',path='KF',variant='KO_TEXT',input='source'),dict(slot=2,case_id='synthetic',path='KB',variant='FROZEN',from_slot=1)],freeze_sha256='x')
 a=dict(campaign_id=c.ID,authorized=True,execution_enabled=True,approved_limit=1000,phase='A',actual_attempts=0,actual_by_path={p:0 for p in c.CAP},actual_38=0,plan_sha256=c.digest(p));return p,a
class Tests(unittest.TestCase):
 def test_cap(self):
  p,a=fixture();a['actual_attempts']=999;a['actual_by_path']['KF']=999
  with self.assertRaises(ValueError):c.validate(p,a)
 def test_lock(self):
  p,a=fixture();a['authorized']=False
  with self.assertRaises(ValueError):c.validate(p,a)
 def test_no_original_input(self):
  p,a=fixture();p['tasks'][1]['input']='hidden original';a['plan_sha256']=c.digest(p)
  with self.assertRaises(ValueError):c.validate(p,a)
 def test_failed_first_skips_back_no_retry(self):
  p,a=fixture();sent=[]
  class Worker:
   def call(self,q):return dict(model='gemini-3.1-flash-lite',payload=dict(contents=[dict(parts=[dict(text=q['text'])])],generationConfig=dict(maxOutputTokens=1024,thinkingConfig=dict(thinkingLevel='minimal',includeThoughts=False))))
  def send(q):sent.append(q);raise TimeoutError()
  with tempfile.TemporaryDirectory()as d:
   r=c.run(p,a,Worker(),send,Path(d)/'once',lambda r:None)
   self.assertEqual(r['attempts'],1);self.assertEqual(len(sent),1);self.assertEqual(r['slots'][1]['status'],'SKIPPED_DEPENDENCY')
   with self.assertRaises(FileExistsError):c.run(p,a,Worker(),send,Path(d)/'once',lambda r:None)
