import unittest,importlib.util,json,copy,tempfile,hashlib
from pathlib import Path
R=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('t88',R/'campaign.py');c=importlib.util.module_from_spec(s);s.loader.exec_module(c)
class Contracts(unittest.TestCase):
 def setUp(self):self.cfg=copy.deepcopy(c.CONFIG)
 def tearDown(self):c.CONFIG=self.cfg
 def fixture(self,ph='P1'):
  cases=[dict(id=f'free:{side}{i}',side=side,index=i,source=f'FREE SOURCE {side}{i}',source_sha256=hashlib.sha256(f'FREE SOURCE {side}{i}'.encode()).hexdigest(),development_allowed=True,diagnostic=ph=='P1' and i==3,reuse_A=ph=='P1' and i==3) for side in ('K','L') for i in range(4)]
  m=dict(id='FREE',phase=ph,cap=14 if ph=='P1' else 32,whole_task_maximum=88,prior_attempts=dict(H=0,S=0,O=0),cases=cases,schedule=c.schedule(cases,ph),frozen_file_sha256={})
  c.CONFIG=dict(plan_id='FREE',phase=ph,cap=m['cap'],phase_authorized_max=24 if ph=='P1' else 32,manifest_sha256=c.digest(m))
  ap=dict(authorized=True,campaign_id='CLAUDE_AUTO88_20261102',plan_id='FREE',maximum_new_attempts=m['cap'],phase_authorized_max=c.CONFIG['phase_authorized_max'],whole_task_maximum=88,S_maximum=56,O_maximum=32,manifest_sha256=c.digest(m));return m,ap
 def fake(self,fail_at=0):
  calls=[]
  def send(q):
   calls.append(q);n=len(calls)
   if n==fail_at:raise ValueError('FREE_FAILURE')
   text=json.dumps({'translation':'DISPLAY '+str(n)}) if 'format' in q['output_config'] else 'DISPLAY '+str(n)
   return dict(raw=dict(type='message',model=q['model'],id='fake'+str(n),content=[dict(type='text',text=text)],stop_reason='end_turn',usage=dict(input_tokens=1,output_tokens=1)),wire=dict(http_status=200,api_ms=1))
  return calls,send
 def test_only_generation_contract_changes(self):
  for side in ('K','L'):
   a=c.build('source',side,'first','A');b=c.build('source',side,'first','B');assert a['system']!=b['system'];aa=copy.deepcopy(a);bb=copy.deepcopy(b);aa.pop('system');bb.pop('system');self.assertEqual(aa,bb);self.assertEqual(a['system'].replace(c.a.OLD1,c.a.NEW1).replace(c.a.OLD2,c.a.NEW2),b['system'])
 def test_display_no_cleanup_or_thinking(self):
  text='  Draft English\nsecond line  ';raw=dict(stop_reason='end_turn',content=[dict(type='thinking',thinking='secret'),dict(type='text',text=json.dumps({'translation':text}))]);self.assertEqual(c.inspect(raw,'source','K','first','B')['translation'],text)
 def test_max_tokens_no_salvage(self):
  raw=dict(stop_reason='max_tokens',content=[dict(type='text',text='{"translation":"partial')]);self.assertRaises(ValueError,c.inspect,raw,'source','K','first','B')
 def test_first_only_reuse_schedule(self):
  m,ap=self.fixture();self.assertEqual(len(m['schedule']),14);self.assertTrue(all(x['stage']=='first' for x in m['schedule']));self.assertEqual(sum(x['arm']=='A' for x in m['schedule']),6)
 def test_failure_keeps_later_cases(self):
  m,ap=self.fixture();calls,send=self.fake(2)
  with tempfile.TemporaryDirectory(dir=R) as t:d=c.run_approved(m,ap,send,Path(t)/'journal')
  self.assertEqual(d['attempts'],14);self.assertEqual(d['slots'][1]['status'],'FAILED');self.assertEqual(d['slots'][-1]['status'],'SUCCESS');self.assertEqual(len(calls),14)
 def test_back_own_first_only_and_skip(self):
  m,ap=self.fixture('P2');calls,send=self.fake(1)
  with tempfile.TemporaryDirectory(dir=R) as t:d=c.run_approved(m,ap,send,Path(t)/'journal')
  self.assertEqual(d['attempts'],31);self.assertEqual(d['slots'][1]['status'],'SKIPPED_DEPENDENCY');by={x['slot']:x for x in d['slots']}
  for x in d['slots']:
   if x['stage']=='back' and x['attempted']:self.assertEqual(x['input'],by[x['depends_on']]['translation']);self.assertNotIn('FREE SOURCE',x['payload']['messages'][0]['content'])
 def test_duplicate_journal_zero_extra(self):
  m,ap=self.fixture();calls,send=self.fake()
  with tempfile.TemporaryDirectory(dir=R) as t:
   p=Path(t)/'journal';c.run_approved(m,ap,send,p);self.assertRaises(FileExistsError,c.run_approved,m,ap,send,p)
  self.assertEqual(len(calls),14)
 def test_approval_and_manifest_tamper(self):
  m,ap=self.fixture();bad=copy.deepcopy(ap);bad['whole_task_maximum']=89;self.assertRaises(AssertionError,c.authorize,bad);m['cases'][0]['source']='tampered';self.assertRaises(AssertionError,c.validate,m)
if __name__=='__main__':unittest.main()
