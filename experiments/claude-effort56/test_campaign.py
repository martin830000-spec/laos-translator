import copy,importlib.util,json,tempfile,unittest
from pathlib import Path
E=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('effort_test',E/'campaign.py');c=importlib.util.module_from_spec(s);s.loader.exec_module(c)
class Contract(unittest.TestCase):
 def test_effort_only_and_no_upfront_sonnet(self):
  for engine,side,stage in [('O','L','first'),('O','L','back'),('S','K','first'),('S','K','back')]:
   lo=c.build('arbitrary fixture',side,stage,engine,'low');md=c.build('arbitrary fixture',side,stage,engine,'medium')
   self.assertEqual(lo['thinking'],{'type':'adaptive' if engine=='O' else 'between_tools'})
   self.assertEqual(lo['max_tokens'],2048);md['output_config']['effort']='low';self.assertEqual(lo,md)
 def test_schedule_counterbalance_and_shared_dependency(self):
  cases=[{'id':str(i)} for i in range(4)]
  for ph in ['A1','A2','B1','B2']:
   ss=c.schedule(cases,ph)
   for i in range(4):
    x=[x for x in ss if x['id']==str(i)]
    variants=['LOW','MEDIUM'] if i%2==0 else ['MEDIUM','LOW']
    self.assertEqual([t['variant'] for t in x if t['stage']==('first' if ph[0]=='A' else 'back')],variants)
    if ph[0]=='A':self.assertTrue(all(t['effort']=='low' for t in x if t['stage']=='back'))
    else:self.assertEqual(x[1]['depends_on'],x[2]['depends_on'])
 def test_cap_authorization_dependency_failure_and_replay(self):
  old=copy.deepcopy(c.CONFIG)
  try:
   ph=old['phase'];cap=16 if ph[0]=='A' else 12;side='L' if ph[0]=='A' else 'K'
   cases=[dict(id=str(i),side=side,source='fixture '+str(i),source_sha256=c.hashlib.sha256(('fixture '+str(i)).encode()).hexdigest(),development_allowed=True) for i in range(4)]
   m=dict(id=old['plan_id'],phase=ph,cap=cap,whole_task_maximum=56,Opus_maximum=32,Sonnet_maximum=24,prior_Opus_attempts=0,prior_Sonnet_attempts=0,cases=cases,schedule=c.schedule(cases,ph),frozen_file_sha256={})
   c.CONFIG['manifest_sha256']=c.digest(m)
   approval=dict(authorized=True,campaign_id='CLAUDE_EFFORT56_20261101',plan_id=m['id'],maximum_new_attempts=cap,whole_task_maximum=56,Opus_maximum=32,Sonnet_maximum=24,manifest_sha256=c.digest(m))
   calls=[]
   def fail(q):calls.append(q);raise ValueError('fixture failure')
   with tempfile.TemporaryDirectory(dir=E) as d:
    j=Path(d)/'once';out=c.run_approved(m,approval,fail,j)
    self.assertEqual(len(calls),8 if ph[0]=='A' else 4);self.assertEqual(out['retries'],0)
    with self.assertRaises(FileExistsError):c.run_approved(m,approval,fail,j)
   counter=[]
   def success(q):
    counter.append(q)
    return dict(type='message',id='fixture-'+str(len(counter)),model=q['model'],stop_reason='end_turn',content=[dict(type='thinking',thinking='hidden fixture'),dict(type='text',text='  visible '+str(len(counter))+'  ')],usage=dict(input_tokens=1,output_tokens=1))
   with tempfile.TemporaryDirectory(dir=E) as d:
    out=c.run_approved(m,approval,success,Path(d)/'once');slots={x['slot']:x for x in out['slots']}
    self.assertEqual(out['attempts'],cap)
    for x in out['slots']:
     if x['stage']=='back':self.assertEqual(x['input'],slots[x['depends_on']]['translation']);self.assertNotIn('hidden fixture',x['input'])
    if ph[0]=='B':
     for case in cases:
      backs=[x for x in out['slots'] if x['id']==case['id'] and x['stage']=='back'];self.assertEqual(backs[0]['input'].encode(),backs[1]['input'].encode())
   bad=dict(approval,whole_task_maximum=57)
   with self.assertRaises(PermissionError):c.authorize(bad)
   bad=copy.deepcopy(m);bad['prior_Opus_attempts']=33;c.CONFIG['manifest_sha256']=c.digest(bad)
   with self.assertRaises(AssertionError):c.validate(bad)
  finally:c.CONFIG.clear();c.CONFIG.update(old)
if __name__=='__main__':unittest.main()
