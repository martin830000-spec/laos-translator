"""Offline synthetic transport and safety regression tests: no network calls."""
import asyncio,contextlib,copy,json,os,pathlib,tempfile,unittest
from unittest.mock import patch
import httpx
import contract as c
import http_sender
import runner


def synthetic_result(text='synthetic output',tier='default'):
 response={'id':'resp_synthetic','model':c.MODEL,'service_tier':tier,'status':'completed','reasoning':{'effort':'none'},'usage':{'input_tokens':10,'output_tokens':4,'total_tokens':14,'input_tokens_details':{'cached_tokens':0},'output_tokens_details':{'reasoning_tokens':0}},'output':[{'content':[{'type':'output_text','text':text}]}]}
 return {'http_status':200,'http_attempts':1,'request_id':'req_synthetic','response_id':'resp_synthetic','actual_model':c.MODEL,'actual_service_tier':tier,'response':response,'usage':response['usage'],'success':True,'display_text':text,'terminal':'response.completed','t_first_text':0.1,'t_first_displayable_text':0.1,'t_response_done':0.2,'t_display_extract_done':0.21}
class BytesStream(httpx.AsyncByteStream):
 def __init__(self,chunks):self.chunks=chunks
 async def __aiter__(self):
  for chunk in self.chunks:yield chunk
class MemoryStore:
 def __init__(self):self.data={};self.fail_results=False
 def get(self,n,optional=False):
  if n not in self.data:
   if optional:return None
   raise KeyError(n)
  return self.data[n]
 def create(self,n,b):
  if self.fail_results and n.startswith('results/'):raise OSError('simulated storage outage')
  if n in self.data:raise AssertionError('CREATE_DUPLICATE')
  self.data[n]=b
 def same(self,n,b):
  if n in self.data:c.require(self.data[n]==b,'IMMUTABLE_OBJECT_MISMATCH')
  else:self.create(n,b)
class DummyClient:
 async def __aenter__(self):return self
 async def __aexit__(self,*args):return None

class Contracts(unittest.TestCase):
 def test_no_source_leakage_in_back(self):
  p=c.build_payload('KB','actual first','BACK instruction','fast')
  self.assertEqual(p['input'],'actual first');self.assertEqual(set(p),{'model','reasoning','instructions','input','stream','store','max_output_tokens','service_tier'})
  self.assertFalse(p['store']);self.assertTrue(p['stream']);self.assertEqual(p['max_output_tokens'],4096)
 def test_tier_alias_downgrade(self):
  r=c.validate_result_metadata(synthetic_result(tier='priority'),'fast');self.assertTrue(r['tier_verified']);self.assertTrue(r['success'])
  r=c.validate_result_metadata(synthetic_result(tier='default'),'fast');self.assertFalse(r['tier_verified']);self.assertTrue(r['success']);self.assertIn('FAST_DOWNGRADED_TO_DEFAULT',r['metadata_warnings'])
 def test_malformed_metadata_preserved(self):
  for values in (None,[],17):
   r=synthetic_result();r['usage']['input_tokens_details']=values;r['usage']['output_tokens_details']=values
   d=c.validate_result_metadata(r,'default');self.assertIn('metadata_errors',d)
  r=synthetic_result();r['response']=[];self.assertIn('metadata_warnings',c.validate_result_metadata(r,'default'))
 def test_unknown_not_retransmitted(self):
  r=synthetic_result();r['terminal']=None;r['exception']='TimeoutError';self.assertTrue(c.validate_result_metadata(r,'default')['unknown'])
 def test_budget_total_and_stage(self):
  records=[{'campaign':c.CAMPAIGN,'model':c.MODEL,'ordinal':i+1,'slot':f'A-{i+1:03d}','stage':'A'} for i in range(8)]
  with self.assertRaisesRegex(AssertionError,'STAGE_CAP'):c.budget_guard(records,{'slot':'A-009'})
  with self.assertRaisesRegex(AssertionError,'DUPLICATE_SLOT'):c.budget_guard(records,{'slot':'A-001'})
  with self.assertRaisesRegex(AssertionError,'CAMPAIGN_CAP'):c.budget_guard([{}]*240,{'slot':'F-001'})
 def test_final_overlap_rejected(self):
  def s(i,text,split):return {'source_id':i,'source':text,'sha256':c.sha(text.encode()),'direction':'KF','split':split,'event_cluster':'same','prior_exposure':False,'final_independence_verified':True}
  with self.assertRaisesRegex(AssertionError,'FINAL_EVENT_OVERLAP'):c.validate_sources({'sources':[s('a','alpha','DISCOVERY'),s('b','beta','FINAL')]})
 def test_parse_mismatched_delta(self):
  r=synthetic_result();events=[{'type':'response.output_text.delta','delta':'wrong'},{'type':'response.completed','response':r['response']}]
  self.assertFalse(c.parse_events(events)['success']);self.assertTrue(c.parse_events(events)['mismatch'])
 def test_incomplete_no_back(self):
  r=synthetic_result();events=[{'type':'response.output_text.delta','delta':'partial'},{'type':'response.incomplete','response':r['response']}]
  result=c.parse_events(events);self.assertFalse(result['success']);self.assertIsNone(c.back_input(result))
 def test_back_plan_identity(self):
  sources={'s':{'source':'synthetic','direction':'KF','split':'DISCOVERY'}};prompts={'N0':{'KF':'a','KB':'b'},'N1':{'KF':'x','KB':'b'}}
  plan={'campaign':c.CAMPAIGN,'phase':'A','slots':[{'slot':'A-001','source_id':'s','path':'KF','candidate':'N0','tier':'default'},{'slot':'A-002','source_id':'s','path':'KB','candidate':'N1','tier':'default','parent_first_id':'A-001'}]}
  with self.assertRaisesRegex(AssertionError,'BACK_PARENT_IDENTITY'):c.validate_plan(plan,sources,prompts)

class Transport(unittest.IsolatedAsyncioTestCase):
 async def test_fragmented_utf8_sse_single_post(self):
  r=synthetic_result(text='한글 synthetic',tier='priority');events=[{'type':'response.created','response':{'id':'resp_synthetic'}},{'type':'response.output_text.delta','delta':'한글 '},{'type':'response.output_text.delta','delta':'synthetic'},{'type':'response.output_text.done','text':'한글 synthetic'},{'type':'response.completed','response':r['response']}]
  data=''.join('data: '+json.dumps(e,ensure_ascii=False)+'\n\n' for e in events).encode();calls=[]
  async def handle(request):
   calls.append(request);return httpx.Response(200,headers={'x-request-id':'req_synthetic','content-type':'text/event-stream'},stream=BytesStream([data[i:i+3] for i in range(0,len(data),3)]))
  async with http_sender.make_client(httpx.MockTransport(handle)) as client:result=await http_sender.send(client,c.build_payload('KF','synthetic source','synthetic instruction','fast'),'synthetic-test-key')
  self.assertEqual(len(calls),1);self.assertEqual(result['display_text'],'한글 synthetic');self.assertTrue(result['success']);self.assertGreaterEqual(result['t_response_done'],result['t_first_text']);self.assertTrue(result['raw_chunks_base64'])
 async def test_http_error_body_no_retry(self):
  calls=[]
  async def handle(request):calls.append(request);return httpx.Response(400,json={'error':{'message':'synthetic unsupported tier'}})
  async with http_sender.make_client(httpx.MockTransport(handle)) as client:r=await http_sender.send(client,c.build_payload('KF','synthetic source','synthetic instruction','fast'),'synthetic-test-key')
  self.assertEqual(len(calls),1);self.assertEqual(r['http_status'],400);self.assertIn('http_body_base64',r);self.assertFalse(r['success'])

class Execution(unittest.IsolatedAsyncioTestCase):
 async def run_fake(self,fail_storage=False,first_fail=False,fast_reject=False):
  store=MemoryStore();store.fail_results=fail_storage
  sources={'s':{'source':'original synthetic','sha256':c.sha(b'original synthetic'),'direction':'KF'}};prompts={'N0':{'KF':'instruction first','KB':'instruction back'}}
  tasks=[{'slot':'A-001','source_id':'s','candidate':'N0','path':'KF','tier':'default'},{'slot':'A-002','source_id':'s','candidate':'N0','path':'KB','tier':'default','parent_first_id':'A-001'}]
  if fast_reject:
   tasks[0]['tier']=tasks[1]['tier']='fast'
   tasks += [dict(tasks[0],slot='A-003',tier='default'),dict(tasks[1],slot='A-004',tier='default',parent_first_id='A-003')]
  control={'mode':'EXECUTE','enabled':True,'deadline_epoch':9999999999,'prior_reserved':0,'phase':'A','max_new':2,'plan_sha256':'x','owner_token':'owner'}
  store.data['controls/A/STAGED_LOCKED.json']=c.canon({'plan_sha256':'x','reserved_total':0})
  sent=[]
  async def fake_send(client,payload,key):
   sent.append(payload);r=synthetic_result('actual synthetic first' if len(sent)==1 else 'synthetic back')
   if fast_reject and len(sent)==1:r={'http_status':400,'http_attempts':1,'request_id':'req_synthetic','success':False,'display_text':None,'http_error':{'error':{'param':'service_tier'}}}
   if first_fail and len(sent)==1:r.update(success=False,display_text=None,terminal='response.incomplete')
   return r
  with tempfile.TemporaryDirectory() as td,patch.dict(os.environ,{'OPENAI_API_KEY':'synthetic-test-key','GITHUB_RUN_ID':'123','GITHUB_SHA':'abc','RUNNER_TEMP':td}),contextlib.ExitStack() as stack:
   stack.enter_context(patch.object(runner,'verify_lease',return_value={}));stack.enter_context(patch.object(runner,'require_open',return_value=None));stack.enter_context(patch.object(runner,'verify_gate',return_value={}))
   stack.enter_context(patch.object(runner,'load_design',return_value=(sources,prompts,{})));stack.enter_context(patch.object(runner,'load_plan',return_value={'slots':tasks}))
   state=await runner.execute(store,control,sender=fake_send,client_factory=DummyClient)
  return state,sent,store
 async def test_actual_first_only_back(self):
  state,sent,store=await self.run_fake();self.assertEqual(len(sent),2);self.assertEqual(sent[1]['input'],'actual synthetic first');self.assertEqual(state['reserved_total'],2)
 async def test_failed_first_skips_dependent_back(self):
  state,sent,store=await self.run_fake(first_fail=True);self.assertEqual(len(sent),1);self.assertEqual(state['skips'],['A-002']);self.assertEqual(state['failed'],1)
 async def test_fast_rejected_continues_standard(self):
  state,sent,store=await self.run_fake(fast_reject=True);self.assertEqual(len(sent),3);self.assertEqual(state['skips'],['A-002']);self.assertTrue(state['fast_blocked']);self.assertEqual(state['status'],'CHECKPOINT_LOCKED')
 async def test_storage_failure_counts_unknown_no_replay(self):
  state,sent,store=await self.run_fake(fail_storage=True);self.assertEqual(len(sent),1);self.assertEqual(state['unknown'],1);self.assertEqual(state['status'],'PAUSED_LOCKED');self.assertIn('budget/0001.json',store.data)

if __name__=='__main__':unittest.main()
