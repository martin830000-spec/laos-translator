import contextlib,copy,hashlib,io,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import run as r
class Guards(unittest.TestCase):
 def setUp(self):
  self.cases=[dict(id=i,side=s,source='PRIVATE_SENTINEL_'+str(i)) for i,(s,h) in r.EXPECTED.items()]
  self.expected={x['id']:(x['side'],hashlib.sha256(x['source'].encode()).hexdigest()) for x in self.cases}
  self.requests=[]
 def fake(self,q):
  self.requests.append(copy.deepcopy(q))
  return dict(stop_reason='end_turn',content=[dict(type='thinking',thinking='THINKING_NEVER_BACK'),dict(type='text',text='  VISIBLE_'+str(len(self.requests))+'  ')],usage=dict(input_tokens=500,output_tokens=100))
 def test_exact24_no_repeats_four_routes_independent_back(self):
  saved=[]
  with patch.dict(r.EXPECTED,self.expected,clear=True):
   c=r.Controller(self.cases,lambda d:saved.append(copy.deepcopy(d)));c.run(self.fake)
  self.assertEqual((c.data['attempts'],c.data['first_attempts'],c.data['back_attempts']),(24,12,12))
  self.assertEqual({x['repeat'] for x in c.data['records']},{1})
  for p in ('K_first','K_back','L_first','L_back'):self.assertEqual(sum(x['path']==p for x in c.data['records']),6)
  for i,x in enumerate(c.data['records']):
   if x['path'].endswith('_back'):
    self.assertEqual(x['input'],c.data['records'][i-1]['translation'])
    self.assertNotIn('PRIVATE_SENTINEL',json.dumps(x['payload']));self.assertNotIn('THINKING_NEVER_BACK',json.dumps(x['payload']))
  with self.assertRaises(ValueError):c.call(self.cases[0],2,'first','extra',self.fake)
  self.assertEqual(len(self.requests),24)
 def test_s1_prompt_shape_all_paths_and_only_required_model_change(self):
  a=r.load_adapter();p=a.config['prompts']
  for side in ('K','L'):
   for stage in ('first','back'):
    q=a.build_request('VISIBLE_ONLY',side,stage)
    expected='<translation_task>'+p['CLAUDE_SONNET55_S1_COMMON']+'</translation_task>\n<couple_context>'+p['CLAUDE_SONNET55_S1_ROLE_'+side]+'</couple_context>\n<translation_stage>'+p['CLAUDE_SONNET55_S1_BACK' if stage=='back' else 'CLAUDE_SONNET55_S1_FORWARD']+'</translation_stage>'
    self.assertEqual(q['system'],expected);self.assertEqual(q['model'],'claude-opus-5-5');self.assertEqual(q['thinking'],{'type':'adaptive'});self.assertEqual(q['output_config'],{'effort':'low'});self.assertEqual(q['max_tokens'],2048)
    self.assertEqual(len(q['messages']),1);self.assertNotIn('temperature',q);self.assertNotIn('tools',q);self.assertNotIn('source_people',json.dumps(q))
 def test_no_money_gate(self):
  def huge(q):
   d=self.fake(q);d['usage']=dict(input_tokens=1000000,output_tokens=1000000);return d
  with patch.dict(r.EXPECTED,self.expected,clear=True):c=r.Controller(self.cases,lambda d:None);c.run(huge)
  self.assertEqual(len(self.requests),24);self.assertGreater(c.data['estimated_usd'],.04)
 def test_attempt_uncertain_counted_no_retry_no_back(self):
  sent=[];saved=[]
  def fail(q):sent.append(q);raise TimeoutError('PRIVATE_ERROR')
  with patch.dict(r.EXPECTED,self.expected,clear=True):
   c=r.Controller(self.cases,lambda d:saved.append(copy.deepcopy(d)))
   with self.assertRaises(TimeoutError):c.run(fail)
  self.assertEqual((len(sent),c.data['attempts'],c.data['back_attempts']),(1,1,0));self.assertEqual(saved[0]['records'][0]['status'],'SENT_OR_UNKNOWN')
 def test_incomplete_output_stops(self):
  with patch.dict(r.EXPECTED,self.expected,clear=True):
   c=r.Controller(self.cases,lambda d:None)
   with self.assertRaises(ValueError):c.run(lambda q:dict(stop_reason='max_tokens',content=[]))
  self.assertEqual(c.data['attempts'],1)
 def test_case_and_configuration_hash_guards(self):
  with self.assertRaises(ValueError):r.validate_cases(self.cases)
  self.assertEqual(r.digest(r.load_adapter().config),r.CONFIG_SHA)
  self.assertNotIn(r.TAG,['s47-realuse16-20261030-consumed','haiku-round2-initial128-20261029-consumed','s47-auto176-h1-20261030-consumed','s47-auto176-h2-20261030-consumed'])
 def test_crypto_run_binding(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t)/'k';pub=r.keypair(p);v=dict(private='PRIVATE_SENTINEL');aad=dict(run='Opus24');s=r.seal(v,pub,aad)
   self.assertNotIn('PRIVATE_SENTINEL',json.dumps(s));self.assertEqual(r.unseal(s,p,aad),v)
   with self.assertRaises(ValueError):r.unseal(s,p,dict(run='other'))
   s['ciphertext']='AAAA'+s['ciphertext'][4:]
   with self.assertRaises(Exception):r.unseal(s,p,aad)
 def test_no_plaintext_console_output(self):
  out=io.StringIO()
  with patch.dict(r.EXPECTED,self.expected,clear=True),contextlib.redirect_stdout(out):r.Controller(self.cases,lambda d:None).run(self.fake)
  self.assertEqual(out.getvalue(),'')
if __name__=='__main__':unittest.main()
