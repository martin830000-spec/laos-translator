from pathlib import Path
import importlib.util,tempfile,unittest,json
from unittest.mock import patch
s=importlib.util.spec_from_file_location('test_s60',Path(__file__).parent/'campaign.py');c=importlib.util.module_from_spec(s);s.loader.exec_module(c)
class Contract(unittest.TestCase):
 def fixture(self):
  cases=[dict(id=str(i),side='K' if i%2==0 else 'L',source='ORIGINAL_SECRET_'+str(i)) for i in range(6)]
  return dict(id=c.CONFIG['plan_id'],phase='A',cap=18,prior_cross_attempts=0,prior_Haiku_attempts=0,cases=cases,schedule=c.schedule(cases,'A'))
 def approval(self):return dict(authorized=True,campaign_id='CLAUDE_STABILITY60_20261101',plan_id=c.CONFIG['plan_id'],maximum_new_attempts=c.CONFIG['cap'],whole_task_maximum=60,cross_maximum=36,Haiku_maximum=24,manifest_sha256=c.CONFIG['manifest_sha256'])
 def test_same_visible_two_backs_preserve_extraneous_no_replay(self):
  calls=[]
  def send(q):calls.append(q);return dict(type='message',model=q['model'],stop_reason='end_turn',content=[dict(type='text',text='<final>VISIBLE '+str(len(calls))+' English draft</final>')],usage={})
  with tempfile.TemporaryDirectory() as t,patch.object(c,'validate',lambda m:{x['id']:x for x in m['cases']}):
   m=self.fixture();d=c.run_approved(m,self.approval(),send,Path(t)/'once');self.assertEqual(len(calls),18)
   by={x['slot']:x for x in d['slots']}
   for x in d['slots']:
    if x['stage']=='back':self.assertEqual(x['input'],by[x['depends_on']]['translation']);self.assertNotIn('ORIGINAL_SECRET',str(x['payload']));self.assertIn('English draft',str(x['payload']))
   with self.assertRaises(FileExistsError):c.run_approved(m,self.approval(),send,Path(t)/'once')
   self.assertEqual(len(calls),18)
 def test_failed_first_skips_two_back_no_refill(self):
  calls=[]
  def send(q):calls.append(q);return dict(type='message',model=q['model'],stop_reason='max_tokens',content=[],usage={})
  with tempfile.TemporaryDirectory() as t,patch.object(c,'validate',lambda m:{x['id']:x for x in m['cases']}):d=c.run_approved(self.fixture(),self.approval(),send,Path(t)/'once')
  self.assertEqual(len(calls),6);self.assertEqual(sum(x['status']=='SKIPPED_DEPENDENCY' for x in d['slots']),12)
  with self.assertRaises(PermissionError):c.authorize({})
 def test_Haiku_own_first_only_and_no_second_call_per_stage(self):
  cases=[dict(id=str(i),side='K' if i==2 else 'L',source='H_ORIGINAL_'+str(i)) for i in range(4)]
  m=dict(id=c.CONFIG['plan_id'],phase='H1',cap=16,prior_cross_attempts=36,prior_Haiku_attempts=0,cases=cases,schedule=c.schedule(cases,'H1'));calls=[]
  def send(q):
   calls.append(q);source=q['messages'][0]['content'].split('<message>\n',1)[1].split('\n</message>',1)[0]
   return dict(type='message',model=q['model'],stop_reason='end_turn',content=[dict(type='text',text=json.dumps({'units':[{'source':source,'target':'VISIBLE_'+str(len(calls))}]}))],usage={})
  with tempfile.TemporaryDirectory() as t,patch.object(c,'validate',lambda m:{x['id']:x for x in m['cases']}):d=c.run_approved(m,self.approval(),send,Path(t)/'once')
  self.assertEqual(len(calls),16);by={x['slot']:x for x in d['slots']}
  for x in d['slots']:
   if x['stage']=='back':self.assertEqual(x['input'],by[x['depends_on']]['translation']);self.assertNotIn('H_ORIGINAL_',str(x['payload']))
if __name__=='__main__':unittest.main()
