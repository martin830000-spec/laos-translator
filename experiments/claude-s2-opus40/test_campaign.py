from pathlib import Path
import importlib.util,unittest,json,tempfile,hashlib
R=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('test40',R/'campaign.py');c=importlib.util.module_from_spec(s);s.loader.exec_module(c)
class Contract(unittest.TestCase):
 def cases(self):return [dict(id=side+str(i),side=side,index=i,source=side+str(i),source_sha256=hashlib.sha256((side+str(i)).encode()).hexdigest(),development_allowed=True) for side in ('K','L') for i in range(2)]
 def test_first_exact_frozen_S1_S2(self):
  for side in ('K','L'):
   for arm,v in [('A','BASE'),('B','NEW')]:self.assertEqual(c.build('source',side,'first',arm),c.a.build('source',side,'first','A',v))
 def test_back_exact_plain_Opus_for_both_arms(self):
  for side in ('K','L'):
   for arm in ('A','B','STORED_S2'):
    q=c.build('ONLY ACTUAL FIRST',side,'back',arm);self.assertEqual(q,c.a.f.build('ONLY ACTUAL FIRST',side,'back','O'));self.assertNotIn('format',q['output_config']);self.assertNotIn('ORIGINAL SECRET',json.dumps(q))
 def test_P1_eight_Opus_only(self):
  cases=[dict(id=side+str(i),side=side,index=i) for side in ('K','L') for i in range(4)];rows=c.schedule(cases,'P1');self.assertEqual(len(rows),8);self.assertTrue(all(x['engine']=='O' and x['stage']=='back' and x['depends_on'] is None for x in rows))
 def test_P2_P3_budget_and_alternation(self):
  for ph in ('P2','P3'):
   rows=c.schedule(self.cases(),ph);self.assertEqual(len(rows),16);self.assertEqual(sum(x['engine']=='S' for x in rows),8);self.assertEqual(sum(x['engine']=='O' for x in rows),8)
   for side in ('K','L'):
    for i in range(2):self.assertEqual([x['arm'] for x in rows if x['id']==side+str(i) and x['stage']=='first'],['A','B'] if i==0 else ['B','A'])
 def test_json_inside_text_not_cleaned(self):
  t=' Wait: draft <final> keep me ';raw=dict(stop_reason='end_turn',content=[dict(type='thinking',thinking='hidden'),dict(type='text',text=json.dumps({'translation':t}))]);self.assertEqual(c.inspect(raw,'x','K','first','B')['translation'],t)
 def test_partial_json_not_repaired(self):
  with self.assertRaises(ValueError):c.inspect(dict(stop_reason='max_tokens',content=[dict(type='text',text='{"translation":"x"}')]),'x','K','first','B')
 def test_settings_remain_frozen(self):
  for stage,arm,model,thinking in [('first','A','claude-sonnet-5-5','between_tools'),('first','B','claude-sonnet-5-5','between_tools'),('back','B','claude-opus-5-5','adaptive')]:
   q=c.build('source','K',stage,arm);self.assertEqual((q['model'],q['thinking']['type'],q['output_config']['effort'],q['max_tokens']),(model,thinking,'low',2048))
 def test_changed_approval_rejected(self):
  with self.assertRaises(AssertionError):c.authorize({'authorized':True,'maximum_new_attempts':40})
 def test_failed_first_skips_no_refill_and_one_use_journal(self):
  cases=self.cases();m=dict(id='MOCK',phase='P2',cap=16,prior_attempts=dict(H=0,S=0,O=8),cases=cases,schedule=c.schedule(cases,'P2'));calls=[]
  def fake(q):
   calls.append(q);fail=q['model']=='claude-sonnet-5-5' and 'K0' in q['messages'][0]['content'];t='ACTUAL_BAD_FIRST';text=json.dumps({'translation':t}) if 'format' in q['output_config'] else t
   return dict(raw=dict(type='message',model=q['model'],id='mock',stop_reason='max_tokens' if fail else 'end_turn',content=[dict(type='text',text=text)],usage=dict(input_tokens=1,output_tokens=1)),wire=dict(http_status=200,api_ms=1))
  olda,oldv=c.authorize,c.validate;c.authorize=lambda a:None;c.validate=lambda m:{x['id']:x for x in cases}
  try:
   with tempfile.TemporaryDirectory() as d:
    p=Path(d)/'journal';out=c.run_approved(m,{},fake,p);self.assertEqual(out['attempts'],14);self.assertEqual(sum(x['status']=='SKIPPED_DEPENDENCY' for x in out['slots']),2)
    for x in out['slots']:
     if x['stage']=='back' and x['attempted']:self.assertEqual(x['input'],'ACTUAL_BAD_FIRST')
    before=len(calls)
    with self.assertRaises(FileExistsError):c.run_approved(m,{},fake,p)
    self.assertEqual(before,len(calls))
  finally:c.authorize=olda;c.validate=oldv
if __name__=='__main__':unittest.main()
