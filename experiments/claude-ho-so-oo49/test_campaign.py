import importlib.util,json,unittest,tempfile,copy,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('ab42_test',ROOT/'campaign.py');c=importlib.util.module_from_spec(s);s.loader.exec_module(c)
class Contract(unittest.TestCase):
 def test_changed_approval_is_rejected(self):
  with self.assertRaises(AssertionError):c.authorize({'authorized':True,'maximum_new_attempts':42})
 def cases(self):return [dict(id=f'{side}{i}',side=side,index=i,source=f'{side} message{i}',source_sha256=hashlib.sha256(f'{side} message{i}'.encode()).hexdigest(),development_allowed=True) for side in ('K','L') for i in range(4)]
 def test_schedule_budget_and_models(self):
  rows=c.schedule(self.cases());self.assertEqual(len(rows),24);self.assertEqual({e:sum(x['engine']==e for x in rows) for e in 'HSO'},dict(H=4,S=4,O=16))
 def test_order_alternates_within_each_direction(self):
  rows=c.schedule(self.cases());self.assertEqual([[x['arm'] for x in rows if x['id']==f'K{i}' and x['stage']=='first'] for i in range(4)],[['A','B'],['B','A'],['A','B'],['B','A']])
 def test_lao_single_pair(self):
  rows=c.schedule(self.cases())
  for i in range(4):
   x=[x for x in rows if x['id']==f'L{i}'];self.assertEqual(len(x),2);self.assertEqual(x[0]['slot'],x[1]['depends_on']);self.assertEqual([z['engine'] for z in x],['O','O'])
 def test_diagnostic_only_one_opus_back(self):
  rows=c.schedule(self.cases(),{'input':'stored'});self.assertEqual(len(rows),25);self.assertEqual((rows[0]['engine'],rows[0]['stage'],rows[0]['arm']),('O','back','D'))
 def test_exact_frozen_settings(self):
  for engine,thinking in [('H','disabled'),('S','between_tools'),('O','adaptive')]:
   q=c.a.build('synthetic message','K','first',engine);self.assertEqual(q['max_tokens'],2048);self.assertEqual(q['thinking']['type'],thinking);self.assertEqual(q['output_config']['effort'],'low')
 def test_hidden_thinking_excluded_and_text_not_cleaned(self):
  raw={'stop_reason':'end_turn','content':[{'type':'thinking','thinking':'secret'},{'type':'text','text':'Correction: two drafts'}]}
  self.assertEqual(c.a.inspect(raw,'synthetic','K','first','S')['translation'],'Correction: two drafts')
 def test_incomplete_not_salvaged(self):
  with self.assertRaises(ValueError):c.a.inspect({'stop_reason':'max_tokens','content':[{'type':'text','text':'{"units":[]}'}]},'synthetic','K','first','H')
 def test_failed_shared_first_skips_both_backs_no_refill(self):
  # Full schedule dependency rule is exercised with fake transport, never a key.
  cases=self.cases();m=dict(id='MOCK',phase='P1',cap=24,whole_task_maximum=49,prior_attempts=dict(H=0,S=0,O=0),cases=cases,schedule=c.schedule(cases),frozen_file_sha256={})
  olda,oldv=c.authorize,c.validate;c.authorize=lambda x:None;c.validate=lambda x:{z['id']:z for z in cases};calls=[]
  def fake(q):
   calls.append(q);engine=next(k for k,v in c.a.MODELS.items() if v==q['model']);content=q['messages'][0]['content'];fail='L message0' in content and engine=='O'
   text=json.dumps({'units':[{'source':'synthetic','target':'visible'}]}) if engine=='H' else 'visible'
   return {'raw':{'type':'message','model':q['model'],'id':'mock','stop_reason':'max_tokens' if fail else 'end_turn','usage':{'input_tokens':1,'output_tokens':1},'content':[{'type':'text','text':text}]},'wire':{'http_status':200,'api_ms':1}}
  try:
   with tempfile.TemporaryDirectory(dir=ROOT) as d:r=c.run_approved(m,{},fake,Path(d)/'journal')
  finally:c.authorize=olda;c.validate=oldv
  self.assertEqual(r['attempts'],23);self.assertEqual(sum(x['status']=='SKIPPED_DEPENDENCY' for x in r['slots']),1);self.assertEqual(r['retries'],0)
if __name__=='__main__':unittest.main()
