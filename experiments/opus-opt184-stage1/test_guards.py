import contextlib,copy,hashlib,importlib.util,io,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import run as r
class Guards(unittest.TestCase):
 def setUp(self):
  self.cases=[dict(id=i,side=s,source='PRIVATE_SENTINEL_'+str(i)) for i,(s,h) in r.EXPECTED.items()]
  self.expected={x['id']:(x['side'],hashlib.sha256(x['source'].encode()).hexdigest()) for x in self.cases};self.requests=[]
 def fake(self,q):
  self.requests.append(copy.deepcopy(q))
  return dict(stop_reason='end_turn',content=[dict(type='thinking',thinking='HIDDEN_NEVER_BACK'),dict(type='text',text='VISIBLE_'+str(len(self.requests)))],usage=dict(input_tokens=500,output_tokens=100,output_tokens_details=dict(thinking_tokens=20)))
 def test_cap_balance_rotation_and_independent_back(self):
  with patch.dict(r.EXPECTED,self.expected,clear=True):c=r.Controller(self.cases,lambda d:None);c.run(self.fake)
  self.assertEqual(c.data['attempts'],r.MAX_CALLS);self.assertEqual(c.data['first_attempts'],r.MAX_CALLS//2);self.assertEqual(c.data['back_attempts'],r.MAX_CALLS//2)
  conf=c.adapter.config
  for v in conf['candidates']:
   for side in ('K','L'):
    expected=sum(x['side']==side for x in self.cases)*conf['repeats']
    for stage in ('first','back'):self.assertEqual(sum(x['variant']==v and x['path']==side+'_'+stage for x in c.data['records']),expected)
  for i,x in enumerate(c.data['records']):
   if x['path'].endswith('_back'):
    self.assertEqual(x['input'],c.data['records'][i-1]['translation']);self.assertNotIn('PRIVATE_SENTINEL',json.dumps(x['payload']));self.assertNotIn('HIDDEN_NEVER_BACK',json.dumps(x['payload']))
  groups=[c.data['records'][i]['variant'] for i in range(0,2*len(conf['candidates']),2)]
  self.assertEqual(groups,conf['candidates'])
  with self.assertRaises(ValueError):c.call(self.cases[0],1,'first','extra',self.fake,conf['candidates'][0])
  self.assertEqual(len(self.requests),r.MAX_CALLS)
 def test_A_unchanged_B_single_append_C_not_B_accumulated(self):
  spec=importlib.util.spec_from_file_location('original_s1',r.ROOT.parent/'opus-s1-min24/run.py');o=importlib.util.module_from_spec(spec);spec.loader.exec_module(o)
  current=r.load_adapter();original=o.load_adapter()
  for side in ('K','L'):
   for stage in ('first','back'):
    a=current.build_request('VISIBLE_ONLY',side,stage,'A');self.assertEqual(a,original.build_request('VISIBLE_ONLY',side,stage))
    for v in current.config['candidates']:
     q=current.build_request('VISIBLE_ONLY',side,stage,v);system=q.pop('system');prior=a.copy();old_system=prior.pop('system');self.assertEqual(q,prior)
     if v=='B':self.assertEqual(system,old_system+'\n'+current.config['variants']['B']['append'])
     if v=='C':
      self.assertLess(len(system),.75*len(old_system));self.assertNotIn(current.config['variants']['B']['append'],system);self.assertIn('original',system.lower());self.assertIn('symptoms',system);self.assertIn('Thai',system)
 def test_no_money_gate_or_double_thinking_cost(self):
  def huge(q):x=self.fake(q);x['usage']=dict(input_tokens=1000000,output_tokens=1000000,output_tokens_details=dict(thinking_tokens=999999));return x
  with patch.dict(r.EXPECTED,self.expected,clear=True):c=r.Controller(self.cases,lambda d:None);c.run(huge)
  self.assertEqual(len(self.requests),r.MAX_CALLS);self.assertEqual(r.cost(dict(input_tokens=1000000,output_tokens=1000000)),24)
  self.assertEqual(r.cost(dict(input_tokens=1000000,output_tokens=1000000,output_tokens_details=dict(thinking_tokens=999999))),24)
 def test_failed_first_counted_no_retry_no_back(self):
  sent=[];saved=[]
  def fail(q):sent.append(q);raise TimeoutError('PRIVATE_ERROR')
  with patch.dict(r.EXPECTED,self.expected,clear=True):
   c=r.Controller(self.cases,lambda d:saved.append(copy.deepcopy(d)))
   with self.assertRaises(TimeoutError):c.run(fail)
  self.assertEqual((len(sent),c.data['attempts'],c.data['back_attempts']),(1,1,0));self.assertEqual(saved[0]['records'][0]['status'],'SENT_OR_UNKNOWN')
 def test_truncation_stops(self):
  with patch.dict(r.EXPECTED,self.expected,clear=True):
   c=r.Controller(self.cases,lambda d:None)
   with self.assertRaises(ValueError):c.run(lambda q:dict(stop_reason='max_tokens',content=[]))
  self.assertEqual(c.data['attempts'],1)
 def test_hash_configuration_caps_and_unique_lock(self):
  with self.assertRaises(ValueError):r.validate_cases(self.cases)
  c=r.load_adapter().config;self.assertEqual(c['model'],'claude-opus-5-5');self.assertEqual(c['thinking'],{'type':'adaptive'});self.assertEqual(c['effort'],'low');self.assertEqual(c['max_tokens'],2048)
  self.assertLessEqual(r.MAX_CALLS,{1:72,2:64,3:48}[c['stage']]);self.assertLessEqual(c['prior_campaign_attempts']+r.MAX_CALLS,184)
  self.assertIn('opt184-stage',r.TAG);self.assertNotIn('min24',r.TAG)
 def test_crypto_run_bound(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'key';pub=r.keypair(p);v=dict(source='PRIVATE_SENTINEL');aad=dict(run='OPT184');s=r.seal(v,pub,aad);self.assertNotIn('PRIVATE_SENTINEL',json.dumps(s));self.assertEqual(r.unseal(s,p,aad),v)
   with self.assertRaises(ValueError):r.unseal(s,p,dict(run='other'))
   s['ciphertext']='AAAA'+s['ciphertext'][4:]
   with self.assertRaises(Exception):r.unseal(s,p,aad)
 def test_console_privacy(self):
  out=io.StringIO()
  with patch.dict(r.EXPECTED,self.expected,clear=True),contextlib.redirect_stdout(out):r.Controller(self.cases,lambda d:None).run(self.fake)
  self.assertEqual(out.getvalue(),'')
if __name__=='__main__':unittest.main()
