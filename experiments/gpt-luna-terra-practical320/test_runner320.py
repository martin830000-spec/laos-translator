import unittest,os,time,json,asyncio,pathlib
from unittest.mock import patch
import runner320 as r
class MemoryStore:
 def __init__(self):self.data={'states/P1-finished.json':r.canon({'enabled':False,'max_new':0,'reserved_total':0}),'locks/P1.RELEASED.json':b'{}'}
 def get(self,n,optional=False):
  if optional:return self.data.get(n)
  return self.data[n]
 def create(self,n,b):
  if n in self.data:raise r.PreconditionFailed('duplicate')
  self.data[n]=b
 def put(self,n,b):
  if n in self.data:assert self.data[n]==b
  else:self.create(n,b)
def ledger(s):return [json.loads(v) for k,v in sorted(s.data.items()) if k.startswith('budget/')]
class RunnerTests(unittest.IsolatedAsyncioTestCase):
 def control(self):return dict(enabled=True,mode='EXECUTE',deadline_epoch=time.time()+60,backup_verified=True,phase='P2',max_new=2,prior_reserved=0,previous_state_object='states/P1-finished.json',previous_phase='P1',plan_sha256='mock')
 def tasks(self):return {'slots':[{'slot':'P2-001','model':'gpt-6-luna','path':'KF','effort':'none','input':'original secret','input_sha256':r.sha(b'original secret')},{'slot':'P2-002','model':'gpt-6-luna','path':'KB','effort':'none','parent_first_id':'P2-001'}]}
 async def run_case(self,s,send):
  with patch.dict(os.environ,{'OPENAI_API_KEY':'SYNTHETIC','GITHUB_RUN_ID':'MOCK','GITHUB_SHA':'MOCK'}),patch.object(r,'plan',lambda s,c:self.tasks()),patch.object(r,'reservations',ledger),patch.object(r,'send',send):await r.execute(s,self.control())
 async def test_real_runner_bad_semantics_back_exact(self):
  calls=[];s=MemoryStore()
  async def fake(c,p,k):
   self.assertEqual(len(ledger(s)),len(calls)+1);calls.append(p)
   return {'success':True,'display_text':'technically complete wrong meaning','http_status':200,'t_request_start_monotonic':float(len(calls)),'t_response_done':.1}
  await self.run_case(s,fake)
  self.assertEqual(len(calls),2);self.assertEqual(calls[1]['input'],'technically complete wrong meaning');self.assertNotIn('original secret',json.dumps(calls[1]));self.assertEqual(len(ledger(s)),2)
  with self.assertRaises(AssertionError):await self.run_case(s,fake)
  self.assertEqual(len(calls),2)
 async def test_http_failure_charged_back_skipped_no_retry(self):
  calls=[];s=MemoryStore()
  async def fake(c,p,k):calls.append(p);return {'success':False,'display_text':None,'http_status':429,'exception':'HTTP429'}
  await self.run_case(s,fake);self.assertEqual(len(calls),1);self.assertEqual(len(ledger(s)),1);self.assertIn('skips/P2-002.json',s.data)
 async def test_process_failure_preserves_unknown(self):
  s=MemoryStore()
  async def fake(c,p,k):raise RuntimeError('simulated abrupt transport interruption')
  with self.assertRaises(RuntimeError):await self.run_case(s,fake)
  self.assertEqual(len(ledger(s)),1);state=json.loads(s.data['states/P2-finished.json']);self.assertEqual(state['unknown'],1);self.assertEqual(state['unused_locked'],319)
 async def test_existing_lock_stops_before_reservation(self):
  s=MemoryStore();s.data['locks/P2.json']=b'other live or unresolved run'
  async def fake(c,p,k):self.fail('must not send')
  with self.assertRaises(r.PreconditionFailed):await self.run_case(s,fake)
  self.assertFalse(ledger(s))
 def test_reservation_create_never_adopts_duplicate(self):
  s=MemoryStore();s.create('budget/0001.json',b'same')
  with self.assertRaises(r.PreconditionFailed):s.create('budget/0001.json',b'same')
 def test_frozen_plan_hash_detects_mutation(self):
  s=MemoryStore();s.data['plans/incorrect.json']=b'{"changed":true}'
  with self.assertRaises(AssertionError):r.plan(s,{'plan_sha256':'incorrect'})
if __name__=='__main__':unittest.main()
