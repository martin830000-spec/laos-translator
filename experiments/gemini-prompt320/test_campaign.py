import unittest,tempfile,copy,hashlib
from pathlib import Path
import campaign as c
class GuardTests(unittest.TestCase):
 def test_contracts(self):
  for side in ['K','L']:
   for stage in ['first','back']:
    for e in ['31','35','38']:
     a=c.build('FREE',side,stage,e);b=c.build('FREE',side,stage,e+'N')
     self.assertEqual(a['payload']['contents'],b['payload']['contents']);self.assertEqual(a['payload']['generationConfig'],b['payload']['generationConfig'])
     self.assertEqual(len(b['payload']['contents']),1)
 def test_missing_usage(self):self.assertIsNone(c.a.usage_cost({},c.a.MODELS['31'])['estimated_usd'])
 def test_failure_and_replay(self):
  old=copy.deepcopy(c.CONFIG)
  try:
   cases=[dict(id=s,side=s,index=i,source='SOURCE'+s,source_sha256=hashlib.sha256(('SOURCE'+s).encode()).hexdigest(),development_allowed=True) for i,s in enumerate(['K','L'])]
   c.CONFIG=dict(plan_id='FREE',phase='FREE',cap=4,phase_budget=96,variants=['31N'],prior=0)
   m=dict(id='FREE',phase='FREE',cap=4,whole_task_maximum=320,prior_attempts=0,cases=cases,schedule=c.schedule(cases),frozen_file_sha256={});c.CONFIG['manifest_sha256']=c.digest(m)
   ap=dict(authorized=True,campaign_id='GEMINI_PROMPT320_20261102',plan_id='FREE',maximum_new_attempts=4,phase_budget=96,whole_task_maximum=320,manifest_sha256=c.digest(m));seen=[]
   def fake(q):
    seen.append(q)
    if len(seen)==1:raise ValueError('Injected failure')
    return dict(raw=dict(responseId=str(len(seen)),modelVersion=q['model'],candidates=[dict(finishReason='STOP',content=dict(parts=[dict(text='VISIBLE')]))]),wire=dict(http_status=200,api_ms=1))
   with tempfile.TemporaryDirectory(dir=c.ROOT) as t:
    p=Path(t)/'once';d=c.run_approved(m,ap,fake,p);self.assertEqual(d['attempts'],3);self.assertEqual(d['slots'][1]['status'],'SKIPPED_DEPENDENCY');self.assertEqual(seen[-1]['payload']['contents'][0]['parts'][0]['text'],'VISIBLE');self.assertRaises(FileExistsError,c.run_approved,m,ap,fake,p)
   self.assertEqual(len(seen),3)
  finally:c.CONFIG=old
if __name__=='__main__':unittest.main()
