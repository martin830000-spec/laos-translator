from pathlib import Path
import importlib.util,tempfile,unittest,hashlib
from unittest.mock import patch
s=importlib.util.spec_from_file_location('hy2_quality_tests',Path(__file__).resolve().parent/'campaign.py');c=importlib.util.module_from_spec(s);s.loader.exec_module(c)
def approval():return {'authorized':True,'plan_id':c.PLAN,'maximum_new_attempts':10,'manifest_sha256':c.MANIFEST,'source_plan_sha256':c.SOURCE_PLAN_SHA}
def plan():
 return {'cases':[dict(slot=i+1,id=i,namespace='TEST_ONLY',side='K',stage='back',engine='S',input='CURRENT_DISPLAY_'+str(i),input_sha256=hashlib.sha256(('CURRENT_DISPLAY_'+str(i)).encode()).hexdigest(),first_origin_slot=i,old_back_slot=i+1,first_origin_response_sha256='TEST_HASH') for i in range(10)]}
def response(n,stop='end_turn'):return {'type':'message','model':'claude-sonnet-5-5','id':'SYNTHETIC_'+str(n),'stop_reason':stop,'content':[{'type':'text','text':'UNMODIFIED_VISIBLE_'+str(n)}],'usage':{'input_tokens':1,'output_tokens':2}}
class SafetyContracts(unittest.TestCase):
 def test_exact_ten_back_same_input_and_no_second_run(self):
  calls=[]
  def send(q):calls.append(q);return response(len(calls))
  with tempfile.TemporaryDirectory() as td,patch.object(c,'validate',lambda _:plan()):
   path=Path(td)/'once';d=c.run_approved({},approval(),send,path)
   self.assertEqual(d['attempts'],10);self.assertEqual(d['per_engine'],{'S':10,'H':0,'O':0,'G':0});self.assertEqual(d['new_FIRST_calls'],0)
   for x,case in zip(d['slots'],plan()['cases']):self.assertEqual(x['payload'],c.build_request(case['input']));self.assertEqual(x['input'],case['input']);self.assertEqual(x['translation'],'UNMODIFIED_VISIBLE_'+str(x['attempt']))
   with self.assertRaises(FileExistsError):c.run_approved({},approval(),send,path)
   self.assertEqual(len(calls),10)
 def test_failure_continues_without_refill_and_never_stage2(self):
  calls=[]
  def send(q):calls.append(q);return response(len(calls),'max_tokens' if len(calls)==3 else 'end_turn')
  with tempfile.TemporaryDirectory() as td,patch.object(c,'validate',lambda _:plan()):d=c.run_approved({},approval(),send,Path(td)/'once')
  self.assertEqual(len(calls),10);self.assertEqual(sum(x['status']=='FAILED' for x in d['slots']),1);self.assertEqual(d['retries'],0);self.assertIn('NO_STAGE2_CALLS',d['status'])
 def test_consumed_or_changed_approval_denied_and_global_auth_stop(self):
  calls=[]
  with tempfile.TemporaryDirectory() as td:
   for bad in [dict(approval(),maximum_new_attempts=38),dict(approval(),plan_id='CLAUDE_HY2B_BACK20_20261101')]:
    with self.assertRaises(PermissionError):c.run_approved({},bad,lambda q:calls.append(q),Path(td)/'a')
   def send(q):calls.append(q);return {'http_status':401}
   with patch.object(c,'validate',lambda _:plan()):
    with self.assertRaises(c.SafetyStop):c.run_approved({},approval(),send,Path(td)/'b')
  self.assertEqual(len(calls),1)
if __name__=='__main__':unittest.main()
