import unittest,json,copy,hashlib,tempfile
from pathlib import Path
from collections import Counter
import adapter as a,campaign as c,plan as p,data_guard as dg
CONTEXT=json.loads(a.old.build('SYNTHETIC','K','first','38D')['payload']['contents'][0]['parts'][0]['text'])['household_context']
def response(text='TEST_VISIBLE'):
 return dict(candidates=[dict(finishReason='STOP',content={'parts':[{'text':text}]})])
def successful(q):
 g=q['payload']['generationConfig'];props=g.get('responseSchema',{}).get('properties')
 v='TEST_TRANSLATION'
 if props:
  value={k:[]if x['type']=='ARRAY'else v for k,x in props.items()};v=json.dumps(value)
 return dict(raw=response(v),wire=dict(http_status=200,api_ms=1,response_headers={}))
def grant(m):
 m=copy.deepcopy(m);m['recommended_only']=False
 return m,dict(authorized=True,campaign_id=c.ID,maximum_new_attempts=len(m['tasks']),whole_campaign_limit=len(m['tasks'])+m['prior_new_attempts'],prior_new_attempts=m['prior_new_attempts'],plan_sha256=c.digest(m))
class Requests(unittest.TestCase):
 def test_service_exact(self):
  for side in ['K','L']:
   self.assertEqual(a.build_first('SYNTHETIC',side,'38SVC')['payload'],a.old.build('SYNTHETIC',side,'first','38')['payload'])
 def test_full_D_exact(self):
  for side in ['K','L']:
   self.assertEqual(a.build_first('SYNTHETIC',side,'38FD',CONTEXT)['payload'],a.old.build('SYNTHETIC',side,'first','38D')['payload'])
 def test_context_is_only_context_factor(self):
  for off,on in [('38FA','38FB'),('38FC','38FD')]:
   x=a.build_first('SOURCE', 'L',off,CONTEXT)['payload'];y=a.build_first('SOURCE','L',on,CONTEXT)['payload']
   self.assertEqual(x['system_instruction'],y['system_instruction']);self.assertEqual(x['generationConfig'],y['generationConfig'])
   xx=json.loads(x['contents'][0]['parts'][0]['text']);yy=json.loads(y['contents'][0]['parts'][0]['text'])
   self.assertEqual(xx['message'],yy['message']);self.assertEqual(xx['household_context'],{});self.assertEqual(yy['household_context'],CONTEXT)
 def test_factorial_cap_thinking_equal(self):
  for v in a.CELLS:
   g=a.build_first('SOURCE','K',v,CONTEXT)['payload']['generationConfig'];self.assertEqual(g['maxOutputTokens'],2048);self.assertEqual(g['thinkingConfig']['thinkingLevel'],'low')
 def test_structure_factor_no_context_change(self):
  for off,on in [('38FA','38FC'),('38FB','38FD')]:
   x=a.build_first('SOURCE','K',off,CONTEXT)['payload'];y=a.build_first('SOURCE','K',on,CONTEXT)['payload']
   self.assertEqual(x['contents'],y['contents']);self.assertNotIn('responseSchema',x['generationConfig']);self.assertIn('responseSchema',y['generationConfig'])
 def test_all_back_no_hidden_original(self):
  for v in ['38SVC','38FA','38FB','38FC','38FD','31D','31L','31LL','31C','38P','35M','35ML']:
   for side in ['K','L']:
    q=a.build_back('ACTUAL_FIRST_ONLY',side,v)
    self.assertEqual(q['payload']['contents'][-1]['parts'][0]['text'],'ACTUAL_FIRST_ONLY')
    self.assertNotIn('household_context',str(q));self.assertNotIn('ORIGINAL_CANARY',str(q));self.assertNotIn('TunTun',str(q))
 def test_back_rejects_extra_context(self):
  with self.assertRaises(TypeError):a.build_back('actual','K','38P',context=CONTEXT)
 def test_empty_first_rejected(self):
  with self.assertRaises(ValueError):a.build_back('','K','38P')
 def test_history_not_silently_injected(self):
  with self.assertRaises(ValueError):a.build_first('source','K','31L',CONTEXT,turns=['prior'])
 def test_31D_first_back_preserved(self):
  self.assertEqual(a.build_first('SOURCE','K','31D',CONTEXT)['payload'],a.old.build('SOURCE','K','first','31D')['payload'])
  self.assertEqual(a.build_back('FIRST','K','31D')['payload'],a.old.build('FIRST','K','back','31C')['payload'])
 def test_31_light_scaffold_removed(self):
  q=a.build_first('SOURCE','K','31L',CONTEXT);self.assertNotIn('responseSchema',q['payload']['generationConfig'])
  self.assertEqual(a.build_back('FIRST','K','31L')['payload'],a.build_back('FIRST','K','31D')['payload'])
 def test_31LL_back_plain_keeps_symptom_rules(self):
  q=a.build_back('FIRST','L','31LL');self.assertNotIn('responseSchema',q['payload']['generationConfig']);s=q['payload']['system_instruction']['parts'][0]['text'];self.assertNotIn('First copy a short list',s);self.assertIn('Symptom terminology:',s)
 def test_35_medium_changes_only_effort_vs_legacy_T(self):
  q=a.build_first('SOURCE','K','35M',CONTEXT)['payload'];old=a.old.build('SOURCE','K','first','35T')['payload'];old['generationConfig']['thinkingConfig']['thinkingLevel']='medium';self.assertEqual(q,old)
 def test_35_plain_medium_cap(self):
  q=a.build_first('SOURCE','K','35ML',CONTEXT)['payload'];self.assertEqual(q['generationConfig']['maxOutputTokens'],4096);self.assertEqual(q['generationConfig']['thinkingConfig']['thinkingLevel'],'medium');self.assertNotIn('responseSchema',q['generationConfig'])
class Parse(unittest.TestCase):
 def test_only_translation_displayed(self):
  r=a.inspect(response(json.dumps({'links':[],'states':[],'translation':'VISIBLE'})),'SOURCE','L','first','38FD');self.assertEqual(r['translation'],'VISIBLE')
 def test_foreign_text_not_deleted(self):
  text='ภาษาไทย warning';r=a.inspect(response(text),'SOURCE','K','first','38FB');self.assertEqual(r['translation'],text)
 def test_empty_stop_failure(self):self.assertEqual(a.inspect(response(''),'S','K','first','38FB')['status'],'FAILED')
 def test_no_candidate_failure(self):self.assertEqual(a.inspect({},'S','K','first','38FD')['status'],'FAILED')
 def test_max_tokens_failure(self):
  r=response('partial');r['candidates'][0]['finishReason']='MAX_TOKENS';self.assertEqual(a.inspect(r,'S','K','first','38FD')['status'],'FAILED')
 def test_bad_json_failure(self):self.assertEqual(a.inspect(response('{bad}'),'S','L','first','38FD')['status'],'FAILED')
 def test_duplicate_key_failure(self):self.assertEqual(a.inspect(response('{"links":[],"states":[],"translation":"A","translation":"B"}'),'S','L','first','38FD')['status'],'FAILED')
 def test_missing_translation_failure(self):self.assertEqual(a.inspect(response('{"links":[],"states":[]}'),'S','L','first','38FD')['status'],'FAILED')
 def test_bad_nested_schema_failure(self):
  for obj in [{'links':[{'condition':1,'outcome':'x'}],'states':[],'translation':'a'},{'links':[],'states':[{'event':'x','state':'invented'}],'translation':'a'}]:self.assertEqual(a.inspect(response(json.dumps(obj)),'S','L','first','38FD')['status'],'FAILED')
class Execution(unittest.TestCase):
 def make(self):return p.pairs([dict(id='k',side='K',source='SYNTHETIC'),dict(id='l',side='L',source='SYNTHETIC')],['38SVC'],'TEST',{})
 def test_no_approval_no_send_no_journal(self):
  m=self.make();calls=[]
  with tempfile.TemporaryDirectory()as t:
   with self.assertRaises(PermissionError):c.run(m,dict(authorized=False,maximum_new_attempts=0),lambda q:calls.append(q),Path(t)/'once')
   self.assertEqual(calls,[]);self.assertFalse((Path(t)/'once').exists())
 def test_old_campaign_approval_rejected(self):
  m,g=grant(self.make());g['campaign_id']='GEMINI_REAL400_20261102'
  with self.assertRaises(AssertionError):c.authorize(m,g)
 def test_digest_tampering_rejected(self):
  m,g=grant(self.make());m['tasks'][0]['input']='CHANGED'
  with self.assertRaises(AssertionError):c.authorize(m,g)
 def test_budget_excess_rejected(self):
  m,g=grant(self.make());g['maximum_new_attempts']=3
  with self.assertRaises(AssertionError):c.authorize(m,g)
 def test_failed_first_skip_and_continue_no_retry(self):
  m,g=grant(self.make());calls=[]
  def send(q):
   calls.append(q)
   return dict(raw={},wire=dict(http_status=503,api_ms=1))if len(calls)==1 else successful(q)
  with tempfile.TemporaryDirectory()as t:r=c.run(m,g,send,Path(t)/'once')
  self.assertEqual(len(calls),3);self.assertEqual(r['attempts'],3);self.assertEqual(r['slots'][1]['status'],'SKIPPED_DEPENDENCY');self.assertEqual(r['slots'][-1]['status'],'SUCCESS')
 def test_failed_back_continue(self):
  m,g=grant(self.make());calls=[]
  def send(q):
   calls.append(q);return dict(raw={},wire=dict(http_status=503,api_ms=1))if len(calls)==2 else successful(q)
  with tempfile.TemporaryDirectory()as t:r=c.run(m,g,send,Path(t)/'once')
  self.assertEqual(r['attempts'],4);self.assertEqual(r['slots'][-1]['status'],'SUCCESS')
 def test_journal_replay_rejected(self):
  m,g=grant(self.make())
  with tempfile.TemporaryDirectory()as t:
   f=Path(t)/'once';c.run(m,g,successful,f)
   with self.assertRaises(FileExistsError):c.run(m,g,successful,f)
 def test_fixed_back_same_input_and_balanced_order(self):
  fixed=[]
  for i in range(8):
   for side in ['K','L']:
    text='FIXED_FIRST_'+side+str(i);fixed.append(dict(id=side+str(i),side=side,fixed_first=dict(text=text,status='SUCCESS',response_id='id'+side+str(i),sha256=hashlib.sha256(text.encode()).hexdigest())))
  m=p.fixed_backs(fixed);c.validate(m)
  for side in ['K','L']:
   first=[x['profile']for x in m['tasks'][::2]if x['side']==side];self.assertEqual(Counter(first),{'31C':4,'38P':4})
  for x,y in zip(m['tasks'][::2],m['tasks'][1::2]):self.assertEqual(x['fixed_first'],y['fixed_first'])
class Final(unittest.TestCase):
 def test_final_locked(self):
  with self.assertRaises(PermissionError):dg.bind_final([],[],{})
 def test_final_metadata_matching(self):
  meta=[]
  for i in range(17):
   for side in ['K','L']:meta.append(dict(id=side+str(i),side=side,cluster=str(i),source_sha256=hashlib.sha256((side+str(i)).encode()).hexdigest()))
  out=dg.pick_final(meta);self.assertEqual(len({x['cluster']for x in out}),16);self.assertEqual(Counter(x['side']for x in out),{'K':8,'L':8});self.assertTrue(all('source'not in x for x in out))

class FreezeIntegrity(unittest.TestCase):
 def test_freeze_tampering_rejected(self):
  with tempfile.TemporaryDirectory()as t:
   base=Path(t);(base/'code.py').write_text('frozen');(base/'winner.json').write_text('{}')
   reviews={}
   for stage in ['P1','P2','P3','P4']:
    n=stage+'.json';(base/n).write_text('reviewed');reviews[n]=dg.sha_file(base/n)
   freeze=dict(candidate_frozen=True,P1_P4_review_complete=True,code_files={'code.py':dg.sha_file(base/'code.py')},review_files=reviews,winner_config_sha256=dg.sha_file(base/'winner.json'))
   self.assertTrue(dg.verify_freeze(freeze,base,base/'winner.json',base))
   (base/'code.py').write_text('modified')
   with self.assertRaises(PermissionError):dg.verify_freeze(freeze,base,base/'winner.json',base)
 def test_incomplete_review_rejected(self):
  with self.assertRaises(PermissionError):dg.verify_freeze(dict(candidate_frozen=True,P1_P4_review_complete=True,code_files={},review_files={}),'.','missing','.')
class CostMetrics(unittest.TestCase):
 def test_missing_usage_not_zero_cost(self):
  import metrics
  r=dict(attempts=2,slots=[dict(slot=1,stage='first',profile='X',side='K',attempted=True,status='SUCCESS',sent_at_utc='2026-11-03T00:00:00+00:00',api_ms=1,ready_ms=2),dict(slot=2,stage='back',depends_on=1,profile='X',side='K',attempted=True,status='SUCCESS',sent_at_utc='2026-11-03T00:00:01+00:00',api_ms=1,ready_ms=2)])
  v=metrics.summarize(r)['metrics']['X/K'];self.assertIsNone(v['translation_cost_per_1000_successful_pairs_usd']);self.assertEqual(v['roundtrip_wall']['max_ms'],1002)

if __name__=='__main__':unittest.main()

