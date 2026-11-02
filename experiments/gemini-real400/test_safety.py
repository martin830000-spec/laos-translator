import unittest,copy,tempfile
from pathlib import Path
import campaign as c
class Safety(unittest.TestCase):
 def test_household_and_source_metadata_first_only(self):
  for v in ('31D','38D','35T'):
   first=c.build('TEST_CURRENT_MESSAGE','K','first',v)
   self.assertIn('household_context',str(first['payload']['contents']))
   back=c.build('TEST_ACTUAL_FIRST_ONLY','K','back',v)
   self.assertNotIn('household_context',str(back))
   self.assertNotIn('TunTun',str(back))
   self.assertEqual(back['payload']['contents'][-1]['parts'][0]['text'],'TEST_ACTUAL_FIRST_ONLY')
 def test_back_payload_independence(self):
  for v in c.CONFIG['variants']:
   q=c.build('TEST_ACTUAL_FIRST_ONLY','L','back',v)
   self.assertEqual(q['payload']['contents'][-1]['parts'][0]['text'],'TEST_ACTUAL_FIRST_ONLY')
   self.assertNotIn('UNSEEN_ORIGINAL',str(q))
 def test_cap_authorization_exact(self):
  import json
  a=json.loads((c.ROOT/'approval.json').read_text());c.authorize(a)
  a['maximum_new_attempts']+=1
  with self.assertRaises(AssertionError):c.authorize(a)
 def test_first_then_back_dependency(self):
  s=c.schedule([dict(id='synthetic',side='K',index=0)])
  for i in range(0,len(s),2):self.assertEqual(s[i+1]['depends_on'],s[i]['slot'])
 def test_skip_failed_first_without_retry(self):
  import json
  oldconf=copy.deepcopy(c.CONFIG);oldvalidate=c.validate
  try:
   c.CONFIG.update(cap=2,phase_budget=2,prior=398)
   a=dict(authorized=True,campaign_id='GEMINI_REAL400_20261102',plan_id=c.CONFIG['plan_id'],maximum_new_attempts=2,phase_budget=2,whole_task_maximum=400,manifest_sha256=c.CONFIG['manifest_sha256'])
   case=dict(id='synthetic',side='K',source='안녕',index=0);c.validate=lambda m:{case['id']:case}
   slots=[dict(slot=1,id='synthetic',side='K',index=0,variant='38',engine='38',stage='first',depends_on=None),dict(slot=2,id='synthetic',side='K',index=0,variant='38',engine='38',stage='back',depends_on=1)]
   calls=[]
   def fake(q):
    calls.append(q);return dict(raw={},wire=dict(http_status=503,api_ms=1))
   with tempfile.TemporaryDirectory() as t:d=c.run_approved(dict(id=c.CONFIG['plan_id'],phase='TEST',prior_attempts=398,cap=2,schedule=slots),a,fake,Path(t)/'once')
   self.assertEqual(len(calls),1);self.assertEqual(d['attempts'],1);self.assertEqual(d['slots'][1]['status'],'SKIPPED_DEPENDENCY')
  finally:c.CONFIG.clear();c.CONFIG.update(oldconf);c.validate=oldvalidate
if __name__=='__main__':unittest.main()
