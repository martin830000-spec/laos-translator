import unittest,json,tempfile,copy
from pathlib import Path
import controller as c
from transport import Session
class Contracts(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.j=Path(self.tmp.name)/'journal'
  self.p={'campaign_id':c.ID,'tasks':[dict(slot=1,case_id='synthetic',path='KF',model='M31',variant='CONTRAST',input='source'),dict(slot=2,case_id='synthetic',path='KB',model='M31',variant='CONTRAST',depends_on=1)]};self.calls=[]
  self.a=dict(campaign_id=c.ID,approved_new=2,actual_attempts=0,authorized=True,execution_enabled=True,plan_sha256=c.digest(self.p))
 def builder(self,p,m,v,s):return dict(model='gemini-3.1-flash-lite',payload=dict(contents=[dict(role='user',parts=[dict(text=s)])]))
 def inspector(self,r):return dict(status='SUCCESS'if r['finish']=='STOP'else'FAILED',displayed=r.get('text')if r['finish']=='STOP'else None)
 def send(self,q):self.calls.append(q);return dict(raw=dict(finish='STOP',text='FIRST_VISIBLE'if len(self.calls)==1 else'BACK_VISIBLE'),wire=dict(http_status=200))
 def runp(self,send=None,a=None):return c.run(self.p,a or self.a,self.builder,self.inspector,send or self.send,self.j,lambda x:None)
 def test_zero_approval_prevents_sender_and_journal(self):
  a=json.loads((Path(__file__).parent/'approval.json').read_text())
  with self.assertRaises(ValueError):self.runp(a=a)
  self.assertEqual(self.calls,[]);self.assertFalse(self.j.exists())
 def test_success_single_pass_back_only_first(self):
  r=self.runp();self.assertEqual(r['attempts'],2);self.assertEqual(self.calls[1]['payload']['contents'][0]['parts'][0]['text'],'FIRST_VISIBLE');self.assertEqual(r['automatic_retries'],0)
 def test_timeout_count_and_skip(self):
  def timeout(q):self.calls.append(q);raise TimeoutError('synthetic')
  r=self.runp(timeout);self.assertEqual(r['attempts'],1);self.assertEqual(len(self.calls),1);self.assertEqual(r['slots'][1]['status'],'SKIPPED_DEPENDENCY');self.assertIsNone(r['slots'][0]['estimated_usd'])
 def test_http503_count_no_back_or_retry(self):
  def err(q):self.calls.append(q);return dict(raw={},wire=dict(http_status=503))
  r=self.runp(err);self.assertEqual(r['attempts'],1);self.assertEqual(r['slots'][0]['status'],'FAILED')
 def test_max_tokens_skips_back(self):
  r=self.runp(lambda q:dict(raw=dict(finish='MAX_TOKENS',text='unfinished'),wire=dict(http_status=200)));self.assertEqual(r['attempts'],1)
 def test_repeat_journal_fails_closed(self):
  self.runp()
  with self.assertRaises(FileExistsError):self.runp()
  self.assertEqual(len(self.calls),2)
 def test_plan_hash_budget_and_old_campaign_rejected(self):
  for changes in [dict(approved_new=1),dict(plan_sha256='bad'),dict(campaign_id='GEMINI_FULL_AUTONOMOUS300_20261104')]:
   with self.assertRaises(ValueError):self.runp(a=dict(self.a,**changes))
  self.assertEqual(self.calls,[])
 def test_back_hidden_input_rejected(self):
  for k in ['original','source','input','hash','context','grade','history']:
   p=copy.deepcopy(self.p);p['tasks'][1][k]='LEAK'
   with self.assertRaises(ValueError):c.validate(p)
 def test_final_requires_bound_candidate_and_case_freeze(self):
  self.p['phase']='FINAL';self.a['plan_sha256']=c.digest(self.p)
  with self.assertRaises(ValueError):self.runp()
  self.assertFalse(self.j.exists());self.assertEqual(self.calls,[])
 def test_close_counts_unused_without_reauthorization(self):
  a=c.close(self.a,1);self.assertEqual(a['unused'],1);self.assertEqual(a['maximum_new_attempts'],0);self.assertFalse(a['authorized'])
 def test_session_reuses_connection_no_header_or_key_in_wire(self):
  class Res:
   status=200;will_close=False
   def read(self):return b'{"responseId":"synthetic"}'
  class Conn:
   count=0
   def request(self,*a,**k):self.count+=1
   def getresponse(self):return Res()
   def close(self):pass
  con=Conn();created=[]
  def factory():created.append(1);return con
  s=Session(factory);a=s.send(self.builder('KF','M31','CONTROL','x'),{'x-goog-api-key':'FAKE_KEY'});b=s.send(self.builder('KF','M31','CONTROL','x'),{'x-goog-api-key':'FAKE_KEY'})
  self.assertEqual(len(created),1);self.assertFalse(a['wire']['connection_reuse_attempted']);self.assertTrue(b['wire']['connection_reuse_attempted']);self.assertNotIn('FAKE_KEY',json.dumps(b));self.assertEqual(con.count,2)
 def test_stale_connection_never_resends(self):
  class Bad:
   calls=0
   def request(self,*a,**k):self.calls+=1;raise OSError('STALE')
   def close(self):pass
  b=Bad();s=Session(lambda:b)
  with self.assertRaises(OSError):s.send(self.builder('KF','M31','CONTROL','x'),{})
  self.assertEqual(b.calls,1);self.assertIsNone(s.conn)
 def test_frozen_first_seed_generates_only_BACK(self):
  import hashlib
  seed=dict(slot=1,case_id='synthetic',path='KF',displayed_seed='PRIOR_VISIBLE',seed_response_id='prior_response',seed_sha256=hashlib.sha256(b'PRIOR_VISIBLE').hexdigest());self.p.update(phase='C_BACK',tasks=[seed,dict(slot=2,case_id='synthetic',path='KB',model='M31',variant='QUOTE',depends_on=1)]);self.a['plan_sha256']=c.digest(self.p);r=self.runp();self.assertEqual(r['attempts'],1);self.assertEqual(len(self.calls),1);self.assertEqual(self.calls[0]['payload']['contents'][0]['parts'][0]['text'],'PRIOR_VISIBLE');self.assertFalse(r['slots'][0]['attempted'])
 def test_seed_cannot_leak_original_or_be_used_in_FINAL(self):
  import hashlib
  seed=dict(slot=1,case_id='synthetic',path='KF',displayed_seed='x',seed_response_id='id',seed_sha256=hashlib.sha256(b'x').hexdigest(),original='LEAK')
  with self.assertRaises(ValueError):c.validate(dict(phase='C_BACK',tasks=[seed]))
  seed.pop('original')
  with self.assertRaises(ValueError):c.validate(dict(phase='FINAL',tasks=[seed]))
if __name__=='__main__':unittest.main()
