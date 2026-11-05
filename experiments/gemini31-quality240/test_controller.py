import unittest,controller as c,tempfile,pathlib
class T(unittest.TestCase):
 def make(self):
  p={'campaign_id':c.ID,'phase':'A','freeze_sha256':'a'*64,'tasks':[dict(slot=1,case_id='synthetic',path='KF',variant='ECHO',input='synthetic'),dict(slot=2,case_id='synthetic',path='KB',variant='FROZEN',from_slot=1)]};a=dict(campaign_id=c.ID,authorized=True,execution_enabled=True,approved_limit=240,phase='A',actual_attempts=0,actual_by_path={p:0 for p in c.CAP},actual_38=0,plan_sha256=c.digest(p));return p,a
 def test_valid(self):p,a=self.make();self.assertTrue(c.validate(p,a))
 def test_lock(self):
  p,a=self.make();a['authorized']=False
  with self.assertRaises(ValueError):c.validate(p,a)
 def test_limit(self):
  p,a=self.make();a.update(actual_attempts=239,actual_by_path=dict(KF=239,LF=0,KB=0,LB=0))
  with self.assertRaises(ValueError):c.validate(p,a)
 def test_control_limit(self):
  p,a=self.make();p['phase']=a['phase']='CONTROL';p['tasks'][0]['variant']=p['tasks'][1]['variant']='SERVICE';a['actual_38']=23;a['plan_sha256']=c.digest(p)
  with self.assertRaises(ValueError):c.validate(p,a)
 def test_dependency(self):
  p,a=self.make();p['tasks'][1]['case_id']='other';a['plan_sha256']=c.digest(p)
  with self.assertRaises(ValueError):c.validate(p,a)
 def test_fail_no_back_retry(self):
  p,a=self.make()
  class W:
   def call(self,q):return {'model':'gemini-3.1-flash-lite','payload':{'generationConfig':{'maxOutputTokens':1536,'thinkingConfig':{'thinkingLevel':'minimal','includeThoughts':False}},'contents':[{'parts':[{'text':'{"current_message":"synthetic"}'}]}]}}
  sent=[]
  def send(q):sent.append(q);raise TimeoutError()
  with tempfile.TemporaryDirectory()as d:r=c.run(p,a,W(),send,pathlib.Path(d)/'journal',lambda x:None)
  self.assertEqual(len(sent),1);self.assertEqual(r['attempts'],1);self.assertEqual(r['slots'][1]['status'],'SKIPPED_DEPENDENCY')
if __name__=='__main__':unittest.main()
