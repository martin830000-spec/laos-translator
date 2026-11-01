from pathlib import Path
import tempfile,unittest,importlib.util
from unittest.mock import patch
s=importlib.util.spec_from_file_location('sa2_phase_tests',Path(__file__).resolve().parent/'campaign.py');c=importlib.util.module_from_spec(s);s.loader.exec_module(c)
def approval():return {'authorized':True,'plan_id':c.PLAN,'maximum_new_attempts':c.CAP,'manifest_sha256':c.MANIFEST,'source_plan_sha256':c.SOURCE_PLAN_SHA}
def plan():
 src=[];rows=[]
 for i in range(8 if c.PHASE==1 else 6):
  side='K' if i%2==0 else 'L';src.append(dict(id=i,side=side,source='ORIGINAL_ONLY_'+str(i)))
  for v in (['ROLE_LITE'] if c.PHASE==1 else ['S1','ROLE_LITE']):
   n=len(rows)+1;rows.extend([dict(slot=n,id=i,side=side,variant=v,stage='first',depends_on=None),dict(slot=n+1,id=i,side=side,variant=v,stage='back',depends_on=n)])
 return dict(sources=src,schedule=rows)
def response(n,stop='end_turn'):return dict(type='message',model='claude-sonnet-5-5',id='SYNTHETIC_'+str(n),stop_reason=stop,content=[dict(type='thinking',thinking='NOT_FOR_BACK'),dict(type='text',text='UNCHANGED_VISIBLE_'+str(n))],usage=dict(input_tokens=1,output_tokens=2))
class ExecutionSafety(unittest.TestCase):
 def test_cap_no_second_run_and_only_own_visible_FIRST(self):
  calls=[]
  def send(q):calls.append(q);return response(len(calls))
  with tempfile.TemporaryDirectory() as td,patch.object(c,'validate',lambda _:plan()):
   p=Path(td)/'once';d=c.run_approved({},approval(),send,p);self.assertEqual(d['attempts'],c.CAP);self.assertEqual(d['per_engine']['S'],c.CAP)
   for x in d['slots']:
    if x['stage']=='back':self.assertEqual(x['input'],d['slots'][x['depends_on']-1]['translation']);self.assertNotIn('NOT_FOR_BACK',str(x['payload']));self.assertNotIn('ORIGINAL_ONLY',str(x['payload']))
   with self.assertRaises(FileExistsError):c.run_approved({},approval(),send,p)
   self.assertEqual(len(calls),c.CAP)
 def test_failed_FIRST_skips_only_its_BACK_and_no_refill(self):
  calls=[]
  def send(q):calls.append(q);return response(len(calls),'max_tokens' if len(calls)==1 else 'end_turn')
  with tempfile.TemporaryDirectory() as td,patch.object(c,'validate',lambda _:plan()):d=c.run_approved({},approval(),send,Path(td)/'once')
  self.assertEqual(d['attempts'],c.CAP-1);self.assertEqual(sum(x['status']=='SKIPPED_DEPENDENCY' for x in d['slots']),1);self.assertEqual(d['retries'],0)
 def test_refusal_counts_and_other_cases_continue_and_old_approval_denied(self):
  calls=[]
  def send(q):calls.append(q);return response(len(calls),'refusal' if len(calls)==2 else 'end_turn')
  with tempfile.TemporaryDirectory() as td,patch.object(c,'validate',lambda _:plan()):
   with self.assertRaises(PermissionError):c.run_approved({},dict(approval(),maximum_new_attempts=40),send,Path(td)/'bad')
   d=c.run_approved({},approval(),send,Path(td)/'once')
  self.assertEqual(d['attempts'],c.CAP);self.assertEqual(d['slots'][1]['status'],'FAILED');self.assertEqual(d['slots'][1]['translation'],'UNCHANGED_VISIBLE_2')
if __name__=='__main__':unittest.main()
