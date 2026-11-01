import unittest,json,tempfile,hashlib
from unittest.mock import patch
from pathlib import Path
import campaign as c
class Contract(unittest.TestCase):
 def test_alternates_actual_models(self):
  cases=[dict(id=str(i),side=side,index=i) for side in ['K','L'] for i in range(8)]
  s=c.schedule(cases);self.assertEqual(len(s),64)
  for side in ['K','L']:
   actual=[x['engine'] for x in s if x['side']==side and x['stage']=='first'];self.assertEqual(actual[:4],['G','S' if side=='K' else 'O','S' if side=='K' else 'O','G'])
  for x in s:
   if x['stage']=='back':self.assertEqual(s[x['depends_on']-1]['engine'],x['engine'])
 def test_service_smart_and_back_only(self):
  q=c.build('나는 집에 있어. 여보 동생은?', 'K','first','G');self.assertEqual(q['smart_ids'],['SELF','REL']);self.assertEqual(q['payload']['generationConfig']['thinkingConfig']['thinkingLevel'],'low')
  b=c.build('잘 먹었어요.','L','back','G');self.assertIn('REGISTER_TARGET=POLITE',b['payload']['system_instruction']['parts'][0]['text']);self.assertEqual(b['payload']['contents'][0]['parts'][0]['text'],'잘 먹었어요.')
 def test_preserves_drafts(self):
  raw={'candidates':[{'finishReason':'STOP','content':{'parts':[{'thought':True,'text':'HIDDEN'},{'text':'<final>hello</final>\nCorrection: next'}]}}]}
  x=c.js(dict(mode='inspect',raw=raw,text='test',side='L',stage='first'));self.assertIn('<final>',x['translation']);self.assertIn('Correction:',x['translation']);self.assertNotIn('HIDDEN',x['translation'])
 def test_frozen_claude(self):
  for side,e in [('K','S'),('L','O')]:
   for stage in ['first','back']:self.assertEqual(c.build('test',side,stage,e),c.a.build('test',side,stage,e))
 def test_failed_first_skips_back_and_replay(self):
  cases=[dict(id=str(i)+side,side=side,index=i,source='test',source_sha256=hashlib.sha256(b'test').hexdigest(),development_allowed=True) for side in ['K','L'] for i in range(8)]
  m=dict(id=c.CONFIG['plan_id'],phase='P1',cap=64,whole_task_maximum=128,prior_attempts=dict(G=0,S=0,O=0),cases=cases,schedule=c.schedule(cases),frozen_file_sha256={})
  approval=dict(authorized=True,campaign_id='G38_CLAUDE_DIRECTION32_20261101',plan_id=m['id'],maximum_new_attempts=64,whole_task_maximum=128,G_maximum=64,S_maximum=32,O_maximum=32,manifest_sha256=c.digest(m));calls=[]
  with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as t,patch.dict(c.CONFIG,{'phase':'P1','manifest_sha256':c.digest(m)}):
   def transport(q):calls.append(q);return {'_transport':{'http_status':500}}
   d=c.run_approved(m,approval,transport,Path(t)/'journal');self.assertEqual(len(calls),32);self.assertEqual(sum(x['status']=='SKIPPED_DEPENDENCY' for x in d['slots']),32)
   with self.assertRaises(FileExistsError):c.run_approved(m,approval,transport,Path(t)/'journal')
   self.assertEqual(len(calls),32)
 def test_thinking_cost_once(self):self.assertEqual(c.cost(dict(promptTokenCount=100,candidatesTokenCount=20,thoughtsTokenCount=10),'G'),.0001875)
if __name__=='__main__':unittest.main()
