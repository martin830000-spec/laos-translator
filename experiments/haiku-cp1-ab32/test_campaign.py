from pathlib import Path
import importlib.util,tempfile,json,unittest
from unittest.mock import patch
s=importlib.util.spec_from_file_location('test_cp_campaign',Path(__file__).parent/'campaign.py');c=importlib.util.module_from_spec(s);s.loader.exec_module(c)
class Limits(unittest.TestCase):
 def approval(self):return dict(authorized=True,plan_id=c.CONFIG['plan_id'],maximum_new_attempts=16,whole_task_maximum=56,maximum_Haiku_attempts=32,manifest_sha256=c.CONFIG['manifest_sha256'])
 def fixture(self):
  cases=[dict(id='SYNTHETIC_'+str(i),side='K' if i==2 else 'L',source='SOURCE_'+str(i)) for i in range(4)];schedule=[]
  for case in cases:
   for v in ['LA1','CP1']:
    n=len(schedule)+1;schedule.extend([dict(slot=n,id=case['id'],side=case['side'],variant=v,stage='first',depends_on=None),dict(slot=n+1,id=case['id'],side=case['side'],variant=v,stage='back',depends_on=n)])
  return dict(id=c.CONFIG['plan_id'],phase=c.CONFIG['phase'],prior_Haiku_attempts=0,prior_cross_attempts=24,cases=cases,schedule=schedule)
 def response(self,q,n,stop='end_turn'):
  text='MOCK_VISIBLE_'+str(n);source=q['messages'][0]['content'].split('<message>\n',1)[1].rsplit('\n</message>',1)[0]
  obj={'source_readings':['PRIVATE_PLAN_NOT_FOR_BACK'],'chosen_reading':0,'selection_reason':'PRIVATE_SELECTION_NOT_FOR_BACK','translation':text} if 'Whole-message interpretation contract CP1:' in q['system'] else {'units':[{'source':source,'target':text}]}
  return dict(type='message',model='claude-haiku-5-5',stop_reason=stop,content=[dict(type='text',text=json.dumps(obj))],usage={})
 def test_cap_own_visible_and_no_planning_in_back_no_second_run(self):
  calls=[]
  def send(q):calls.append(q);return self.response(q,len(calls))
  with tempfile.TemporaryDirectory() as t,patch.object(c,'validate',lambda m:{x['id']:x for x in m['cases']}):
   out=c.run_approved(self.fixture(),self.approval(),send,Path(t)/'once');self.assertEqual(out['attempts'],16);self.assertEqual(out['per_variant'],{'LA1':8,'CP1':8})
   by={x['slot']:x for x in out['slots']}
   for x in out['slots']:
    if x['stage']=='back':self.assertEqual(x['input'],by[x['depends_on']]['translation']);self.assertNotIn('PRIVATE_PLAN_NOT_FOR_BACK',json.dumps(x['payload']));self.assertNotIn('PRIVATE_SELECTION_NOT_FOR_BACK',json.dumps(x['payload']))
   with self.assertRaises(FileExistsError):c.run_approved(self.fixture(),self.approval(),send,Path(t)/'once')
   self.assertEqual(len(calls),16)
 def test_failed_first_skip_only_its_back_no_refill(self):
  calls=[]
  def send(q):calls.append(q);return self.response(q,len(calls),'max_tokens')
  with tempfile.TemporaryDirectory() as t,patch.object(c,'validate',lambda m:{x['id']:x for x in m['cases']}):out=c.run_approved(self.fixture(),self.approval(),send,Path(t)/'once')
  self.assertEqual(out['attempts'],8);self.assertEqual(sum(x['status']=='SKIPPED_DEPENDENCY' for x in out['slots']),8)
  with self.assertRaises(PermissionError):c.authorize({})
if __name__=='__main__':unittest.main()
