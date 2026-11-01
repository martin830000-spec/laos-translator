import importlib.util,unittest,tempfile
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).parent
s=importlib.util.spec_from_file_location('test_cross',ROOT/'campaign.py');c=importlib.util.module_from_spec(s);s.loader.exec_module(c)
class Safety(unittest.TestCase):
 def fixture(self):
  cases=[dict(id='PUBLIC'+str(i),side='K' if i%2==0 else 'L',engine='O' if i%2==0 else 'S',input='MOCK_UNMODIFIED_VISIBLE_'+str(i)) for i in range(12)]
  for x in cases:x['payload_sha256']=c.a.core.digest(c.a.build(x['input'],x['side'],'back',x['engine']))
  return dict(id=c.CONFIG['plan_id'],phase=c.CONFIG['phase'],prior_cross_attempts=0,cases=cases)
 def approval(self):return dict(authorized=True,plan_id=c.CONFIG['plan_id'],maximum_new_attempts=12,whole_task_maximum=56,manifest_sha256=c.CONFIG['manifest_sha256'])
 def test_bound_no_first_same_visible_and_no_reuse(self):
  calls=[]
  def send(q):calls.append(q);return dict(type='message',model=q['model'],stop_reason='end_turn',content=[dict(type='text',text='MOCK')],usage={})
  with tempfile.TemporaryDirectory() as t,patch.object(c,'validate',lambda m:m['cases']):
   m=self.fixture();out=c.run_approved(m,self.approval(),send,Path(t)/'once');self.assertEqual(out['attempts'],12);self.assertEqual(out['per_engine'],{'S':6,'O':6});self.assertEqual(out['new_FIRST_calls'],0)
   for x in out['slots']:self.assertEqual(x['payload'],c.a.build(x['input'],x['side'],'back',x['engine']))
   with self.assertRaises(FileExistsError):c.run_approved(m,self.approval(),send,Path(t)/'once')
   self.assertEqual(len(calls),12)
 def test_failure_count_continue_no_refill_and_old_approval_denied(self):
  calls=[]
  def fail(q):calls.append(q);return dict(type='message',model=q['model'],stop_reason='max_tokens',content=[],usage={})
  with tempfile.TemporaryDirectory() as t,patch.object(c,'validate',lambda m:m['cases']):out=c.run_approved(self.fixture(),self.approval(),fail,Path(t)/'once')
  self.assertEqual(out['attempts'],12);self.assertTrue(all(x['status']=='FAILED' for x in out['slots']))
  with self.assertRaises(PermissionError):c.authorize({})
if __name__=='__main__':unittest.main()
