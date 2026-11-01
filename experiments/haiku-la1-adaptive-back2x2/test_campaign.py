import unittest,json,tempfile,hashlib
from unittest.mock import patch
from pathlib import Path
import campaign as c
class Contract(unittest.TestCase):
 def test_only_settings_change(self):
  for side in ['K','L']:
   for stage in ['first','back']:
    a=c.build('exact\nsample',side,stage,'A');b=c.build('exact\nsample',side,stage,'B');self.assertEqual(a,c.a.build_request('exact\nsample',side,stage,'LA1'));b['thinking']={'type':'disabled'};b['output_config']['effort']='low';self.assertEqual(a,b)
 def test_orders_no_double_reversal(self):
  for side in ['K','L']:
   cases=[dict(id=str(i),side=side,index=i) for i in range(6)];s=c.schedule(cases);f=[x['first_setting'] for x in s if x['stage']=='first'];self.assertEqual(f[:4],['A','B','B','A'] if side=='K' else ['B','A','A','B'])
   for setting in ['A','B']:
    orders=[[x['setting'] for x in s if x['id']==str(i) and x['stage']=='back' and x['first_setting']==setting] for i in range(6)];self.assertTrue(all(orders[i]!=orders[i+1] for i in range(5)))
 def test_hidden_thinking_and_alignment_warning(self):
  raw=dict(stop_reason='end_turn',content=[dict(type='thinking',thinking='HIDDEN'),dict(type='text',text=json.dumps(dict(units=[dict(source='wrong',target='<final>draft\nCorrection: keep all')])))]);x=c.a.inspect_response(raw,'source','K','first');self.assertFalse(x['alignment_ok']);self.assertEqual(x['translation'],'<final>draft\nCorrection: keep all');self.assertNotIn('HIDDEN',x['translation'])
 def test_no_partial_salvage(self):
  for raw in [dict(stop_reason='max_tokens',content=[dict(type='text',text='{"units":[')]),dict(stop_reason='end_turn',content=[dict(type='text',text='{"units":[')])]:
   with self.assertRaises(Exception):c.a.inspect_response(raw,'x','K','first')
 def fixture(self):
  cs=[dict(id=side+str(i),side=side,index=i,diagnostic=False,source='ORIGINAL_'+side+str(i),source_sha256=hashlib.sha256(('ORIGINAL_'+side+str(i)).encode()).hexdigest(),development_allowed=True) for side in ['K','L'] for i in range(3)];m=dict(id=c.CONFIG['plan_id'],phase='P1',cap=36,whole_task_maximum=72,prior_attempts=0,cases=cs,schedule=c.schedule(cs),frozen_file_sha256={});approval=dict(authorized=True,campaign_id='HAIKU_LA1_ADAPTIVE_BACK2X2_20261101',plan_id=m['id'],maximum_new_attempts=36,whole_task_maximum=72,Haiku_maximum=72,other_models_maximum=0,manifest_sha256=c.digest(m));return m,approval
 def test_actual_same_first_and_replay(self):
  m,ap=self.fixture();sent=[]
  def live(q):
   text=q['messages'][0]['content'].split('<message>\n',1)[1].rsplit('\n</message>',1)[0];sent.append(text);target='FIRST_'+q['thinking']['type'] if text.startswith('ORIGINAL') else 'BACK';raw=dict(type='message',model='claude-haiku-5-5',id=str(len(sent)),stop_reason='end_turn',usage=dict(input_tokens=10,output_tokens=10),content=[dict(type='text',text=json.dumps(dict(units=[dict(source=text,target=target)])))]);return dict(raw=raw,http_status=200,api_ms=1)
  with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as t,patch.dict(c.CONFIG,{'phase':'P1','manifest_sha256':c.digest(m)}):
   d=c.run_approved(m,ap,live,Path(t)/'journal');self.assertEqual(len(sent),36)
   for i in range(0,36,3):self.assertEqual(sent[i+1],sent[i+2]);self.assertFalse(sent[i+1].startswith('ORIGINAL'))
   with self.assertRaises(FileExistsError):c.run_approved(m,ap,live,Path(t)/'journal')
   self.assertEqual(len(sent),36)
 def test_failed_first_skips_two_backs_no_refill(self):
  m,ap=self.fixture();sent=[]
  def live(q):sent.append(q);return dict(raw=dict(stop_reason='max_tokens',content=[]),http_status=200,api_ms=1)
  with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as t,patch.dict(c.CONFIG,{'phase':'P1','manifest_sha256':c.digest(m)}):
   d=c.run_approved(m,ap,live,Path(t)/'journal');self.assertEqual(d['attempts'],12);self.assertEqual(sum(x['status']=='SKIPPED_DEPENDENCY' for x in d['slots']),24);self.assertEqual(len(sent),12)
if __name__=='__main__':unittest.main()
