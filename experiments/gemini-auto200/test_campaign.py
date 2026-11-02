from pathlib import Path
import json,copy,hashlib,tempfile,unittest,importlib.util
R=Path(__file__).resolve().parent;s=importlib.util.spec_from_file_location('tg200',R/'campaign.py');c=importlib.util.module_from_spec(s);s.loader.exec_module(c)
class Contracts(unittest.TestCase):
 def setUp(self):self.cfg=copy.deepcopy(c.CONFIG)
 def tearDown(self):c.CONFIG=self.cfg
 def fixture(self):
  cases=[dict(id=f'free:{s}{i}',side=s,index=i,source=f'FREE SOURCE {s}{i}',source_sha256=hashlib.sha256(f'FREE SOURCE {s}{i}'.encode()).hexdigest(),development_allowed=True) for s in ('K','L') for i in range(4)]
  c.CONFIG=dict(plan_id='FREE',phase='P1',cap=48,phase_budget=48,variants=['31','35','38'],manifest_sha256='');m=dict(id='FREE',phase='P1',cap=48,whole_task_maximum=200,stage_prior_attempts=0,prior_attempts={'31':0,'35':0,'38':0},cases=cases,schedule=c.schedule(cases),frozen_file_sha256={});c.CONFIG['manifest_sha256']=c.digest(m);ap=dict(authorized=True,campaign_id='GEMINI_AUTONOMOUS200_20261102',plan_id='FREE',maximum_new_attempts=48,phase_budget=48,whole_task_maximum=200,manifest_sha256=c.digest(m));return m,ap
 def fake(self,fail=0):
  calls=[]
  def send(q):
   calls.append(q);n=len(calls)
   if n==fail:raise ValueError('FREE_FAILURE')
   return dict(raw=dict(modelVersion=q['model'],responseId='fake'+str(n),candidates=[dict(finishReason='STOP',content=dict(parts=[dict(text='DISPLAY '+str(n))]))],usageMetadata=dict(promptTokenCount=1,candidatesTokenCount=1,totalTokenCount=2)),wire=dict(http_status=200,api_ms=1))
  return calls,send
 def test_service_request_parity(self):
  for side in ('K','L'):
   for stage in ('first','back'):
    q=c.build('FREE SOURCE',side,stage,'38');self.assertEqual(q['payload'],c.a.js(dict(mode='build',text='FREE SOURCE',side=side,stage=stage))['payload']);self.assertEqual(q['payload']['contents'][0]['parts'][0]['text'],'FREE SOURCE')
 def test_only_model_and_thinking_vary_in_phase1(self):
  base=c.build('source','K','first','38')
  for v in ('31','35'):
   q=c.build('source','K','first',v);q['payload']['generationConfig']['thinkingConfig']['thinkingLevel']='low';self.assertEqual(base['payload'],q['payload'])
 def test_failure_skip_dependency_continue_no_retry(self):
  m,ap=self.fixture();calls,send=self.fake(1)
  with tempfile.TemporaryDirectory(dir=R) as t:d=c.run_approved(m,ap,send,Path(t)/'journal')
  self.assertEqual(d['attempts'],47);self.assertEqual(len(calls),47);self.assertEqual(d['slots'][1]['status'],'SKIPPED_DEPENDENCY');self.assertEqual(d['slots'][-1]['status'],'SUCCESS')
  by={x['slot']:x for x in d['slots']}
  for x in d['slots']:
   if x['stage']=='back' and x['attempted']:self.assertEqual(x['input'],by[x['depends_on']]['translation']);self.assertNotIn('FREE SOURCE',x['payload']['payload']['contents'][0]['parts'][0]['text'])
 def test_duplicate_journal_zero_extra(self):
  m,ap=self.fixture();calls,send=self.fake()
  with tempfile.TemporaryDirectory(dir=R) as t:
   p=Path(t)/'journal';c.run_approved(m,ap,send,p);self.assertRaises(FileExistsError,c.run_approved,m,ap,send,p)
  self.assertEqual(len(calls),48)
 def test_count_cap_and_authority_tamper(self):
  m,ap=self.fixture();b=copy.deepcopy(ap);b['whole_task_maximum']=201;self.assertRaises(AssertionError,c.authorize,b);m['cap']=49;self.assertRaises(AssertionError,c.validate,m)
 def test_thinking_hidden_and_max_tokens_failure(self):
  raw=dict(candidates=[dict(finishReason='STOP',content=dict(parts=[dict(thought=True,text='HIDDEN'),dict(text='Visible')]))]);x=c.inspect(raw,'x','K','first','38');self.assertEqual(x['translation'],'Visible');raw['candidates'][0]['finishReason']='MAX_TOKENS';self.assertEqual(c.inspect(raw,'x','K','first','38')['status'],'FAILED')
 def test_missing_usage_not_zero(self):
  self.assertIsNone(c.a.usage_cost({},c.a.MODELS['31'])['estimated_usd']);self.assertIsNone(c.a.usage_cost(dict(usageMetadata=dict(promptTokenCount=3)),c.a.MODELS['31'])['estimated_usd'])
 def test_thinking_counted_once_from_total(self):
  a=c.a.usage_cost(dict(usageMetadata=dict(promptTokenCount=1,candidatesTokenCount=1,totalTokenCount=3)),c.a.MODELS['31']);b=c.a.usage_cost(dict(usageMetadata=dict(promptTokenCount=1,candidatesTokenCount=1,thoughtsTokenCount=1,totalTokenCount=3)),c.a.MODELS['31']);self.assertEqual(a['derived_thinking_tokens'],1);self.assertEqual(a['estimated_usd'],b['estimated_usd']);self.assertEqual(a['estimated_usd'],.00000325)
 def test_native_json_preserves_content_without_cleanup(self):
  text='  English draft ສະບາຍ  ';raw=dict(candidates=[dict(finishReason='STOP',content=dict(parts=[dict(text=json.dumps({'translation':text}))]))]);x=c.inspect(raw,'source','K','first','35J');self.assertEqual(x['raw_translation_field'],text);self.assertIn('English draft',x['translation']);raw['candidates'][0]['finishReason']='MAX_TOKENS';self.assertEqual(c.inspect(raw,'source','K','first','35J')['status'],'FAILED')
 def test_priority_unavailable_one_attempt_no_retry(self):
  m,ap=self.fixture();m['phase']='P2A';m['cases']=[m['cases'][0],m['cases'][4]];c.CONFIG.update(phase='P2A',variants=['38P','38'],groups=[['38P','38']],probe_priority_once=True,cap=8,phase_budget=72);m['schedule']=c.schedule(m['cases']);m['cap']=8;c.CONFIG['manifest_sha256']=c.digest(m);ap.update(maximum_new_attempts=8,phase_budget=72,manifest_sha256=c.digest(m));calls=[]
  def send(q):calls.append(q);return dict(raw={'error':{'message':'Priority tier unavailable'}},wire=dict(http_status=403,api_ms=1))
  with tempfile.TemporaryDirectory(dir=R) as t:d=c.run_approved(m,ap,send,Path(t)/'journal')
  self.assertEqual(len(calls),1);self.assertEqual(d['attempts'],1);self.assertEqual(d['slots'][0]['status'],'FAILED_CAPABILITY');self.assertTrue(d['priority_scope_disabled'])
if __name__=='__main__':unittest.main()
