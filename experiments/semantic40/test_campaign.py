import unittest,tempfile,copy,hashlib,json
from pathlib import Path
import campaign as c
class Contracts(unittest.TestCase):
 def fixture(self):
  p=dict(campaign_id=c.ID,phase='DISCOVERY',prior_actual_attempts=0,source_manifest_sha256='s',data_bound=True,tasks=[dict(slot=1,case_id='synthetic',side='K',stage='first',arm='NEW',profile='K_NEUTRAL_31',input='내일 9시에 갈까?'),dict(slot=2,case_id='synthetic',side='K',stage='back',arm='NEW',profile='SERVICE_BACK',depends_on=1)])
  a=dict(campaign_id=c.ID,authorized=True,execution_enabled=True,user_approved_limit=40,whole_campaign_limit=40,actual_consumed=0,maximum_new_attempts=12,plan_sha256=c.digest(p));config=dict(stage='DISCOVERY',phase_cap=12,prior_actual_attempts=0,plan_sha256=c.digest(p),source_manifest_sha256='s');return p,a,config
 def test_approval_and_old_campaign_rejected(self):
  p,a,f=self.fixture();a['campaign_id']='GEMINI_NEXTGEN_REAL128_20261103'
  with self.assertRaises(ValueError):c.authorize(p,a,f)
 def test_locked_approval(self):
  p,a,f=self.fixture();a['authorized']=False
  with self.assertRaises(ValueError):c.authorize(p,a,f)
 def test_total40_hard_cap(self):
  p,a,f=self.fixture();p['prior_actual_attempts']=39;a['actual_consumed']=39;f['prior_actual_attempts']=39;a['plan_sha256']=f['plan_sha256']=c.digest(p)
  with self.assertRaises(ValueError):c.authorize(p,a,f)
 def test_payload_hash_tamper(self):
  p,a,f=self.fixture();p['tasks'][0]['input']='changed'
  with self.assertRaises(ValueError):c.authorize(p,a,f)
 def test_back_reject_original(self):
  p,a,f=self.fixture();p['tasks'][1]['original']='leak'
  with self.assertRaises(ValueError):c.validate(p)
 def test_first_failure_skips_back_no_retry(self):
  p,a,f=self.fixture();calls=[]
  def sender(q):calls.append(q);return dict(raw={'candidates':[{'finishReason':'MAX_TOKENS','content':{'parts':[{'text':'partial'}]}}]},wire={'http_status':200,'api_ms':1})
  with tempfile.TemporaryDirectory()as d:r=c.run(p,a,f,sender,Path(d)/'once',lambda x:None)
  self.assertEqual(len(calls),1);self.assertEqual(r['attempts'],1);self.assertEqual(r['slots'][1]['status'],'SKIPPED_DEPENDENCY')
 def test_actual_display_first_only_two_calls(self):
  p,a,f=self.fixture();calls=[]
  def sender(q):calls.append(q);return dict(raw={'responseId':str(len(calls)),'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':'ຂໍ້ຄວາມ\n'}]}}]},wire={'http_status':200,'api_ms':1})
  with tempfile.TemporaryDirectory()as d:r=c.run(p,a,f,sender,Path(d)/'once',lambda x:None)
  self.assertEqual(len(calls),2);self.assertEqual(r['slots'][1]['input'],r['slots'][0]['translation']);self.assertEqual(calls[1]['payload']['contents'][0]['parts'][0]['text'],'ຂໍ້ຄວາມ\n')
 def test_once_journal_blocks_replay(self):
  p,a,f=self.fixture()
  with tempfile.TemporaryDirectory()as d:
   j=Path(d)/'once';j.write_text('already')
   with self.assertRaises(FileExistsError):c.run(p,a,f,lambda q:self.fail('sent'),j,lambda x:None)
 def test_thinking_charged_once(self):
  r=c.cost({'usageMetadata':{'promptTokenCount':100,'candidatesTokenCount':20,'thoughtsTokenCount':10,'totalTokenCount':130}},'gemini-3.8-flash')
  self.assertAlmostEqual(r['estimated_usd'],(100*.75+30*3.75)/1e6)
if __name__=='__main__':unittest.main()
