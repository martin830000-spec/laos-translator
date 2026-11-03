"""Synthetic-only; no secret and no network. Contract and one-shot bounded simulation."""
from pathlib import Path
import unittest,tempfile,json,importlib.util,sys,hashlib
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
import engine as e
import campaign as c
SYN={'K':'여보 오늘 비가 와?','L':'ວັນນີ້ຝົນຕົກບໍ?' }

def plan(phase='DISCOVERY_A'):
 ts=[]
 for side in 'KL':
  for arm,profile in [('SERVICE','38SVC'),('BOUND','K_BOUND_31' if side=='K' else 'L_BOUND_38')]:
   slot=len(ts)+1
   ts.append({'slot':slot,'case_id':'SYNTHETIC-'+side,'side':side,'arm':arm,'stage':'first','profile':profile,'input':SYN[side]})
   ts.append({'slot':slot+1,'case_id':'SYNTHETIC-'+side,'side':side,'arm':arm,'stage':'back','profile':e.BACK_PROFILE,'depends_on':slot})
 return {'campaign_id':c.ID,'phase':phase,'tasks':ts,'prior_actual_attempts':0,'source_manifest_sha256':'SYNTHETIC_HASH','recommended_only':False,'data_bound':True}
def guarded(p):
 return {'campaign_id':c.ID,'authorized':True,'execution_enabled':True,'whole_campaign_limit':128,'user_approved_limit':128,'maximum_new_attempts':128,'actual_consumed':p['prior_actual_attempts'],'plan_sha256':c.digest(p)}
def config(p):return {'stage':p['phase'],'phase_cap':c.PHASES[p['phase']],'prior_actual_attempts':p['prior_actual_attempts'],'plan_sha256':c.digest(p),'source_manifest_sha256':p['source_manifest_sha256']}
def response(t):return {'raw':{'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':t}]}}],'modelVersion':'gemini-3.8-flash','usageMetadata':{'promptTokenCount':200,'candidatesTokenCount':20,'totalTokenCount':220}},'wire':{'http_status':200,'api_ms':11.2,'response_body_utf8':'{}','response_headers':{},'request_body_utf8':'{}','endpoint':'https://generativelanguage.googleapis.com/v1beta/models/38:generateContent'}}
class Contracts(unittest.TestCase):
 def test_id_and_caps(self):
  self.assertEqual(c.ID,'GEMINI_NEXTGEN_REAL128_20261103');self.assertEqual(c.PHASES,{'DISCOVERY_A':48,'REFINEMENT_B':32,'INDEPENDENT_FINAL':48})
 def test_approval_defaults_locked(self):
  a=json.loads((ROOT/'approval.json').read_text());self.assertFalse(a['authorized']);self.assertFalse(a['execution_enabled']);self.assertEqual(a['maximum_new_attempts'],0)
 def test_old_sources_not_modified_in_engine(self):
  self.assertIn('K_BOUND_31',e.FIRST_PROFILES['K']);self.assertIn('L_BOUND_38',e.FIRST_PROFILES['L']);self.assertNotIn('K_BOUND_35L',e.FIRST_PROFILES['K'])
 def test_first_service_matches_inherited(self):
  for side in 'KL':
   q=e.build_first(SYN[side],side,'38SVC')
   self.assertEqual(q['model'],'gemini-3.8-flash');self.assertEqual(q['payload']['generationConfig']['maxOutputTokens'],1024)
 def test_new_first_boundary_json(self):
  for side in 'KL':
   profile='K_BOUND_31' if side=='K' else 'L_BOUND_38'
   q=e.build_first(SYN[side],side,profile)
   self.assertIn('contents',q['payload']);self.assertIn('current_message',q['payload']['contents'][0]['parts'][0]['text'])
   self.assertIn('systemInstruction',q['payload'])
 def test_new_first_fixed_thinking(self):
  q=e.build_first('SYNTHETIC','K','K_BOUND_31');self.assertEqual(q['payload']['generationConfig']['thinkingConfig']['thinkingLevel'],'minimal')
  q=e.build_first('SYNTHETIC','L','L_BOUND_38');self.assertEqual(q['payload']['generationConfig']['thinkingConfig']['thinkingLevel'],'low')
 def test_fewshot_only_delta(self):
  a=e.build_first('hello','K','K_BOUND_31');b=e.build_first('hello','K','K_FEWSHOT_31')
  self.assertEqual(a['payload']['contents'],b['payload']['contents']);self.assertEqual(a['payload']['generationConfig'],b['payload']['generationConfig']);self.assertNotEqual(a['payload']['systemInstruction'],b['payload']['systemInstruction'])
 def test_independent_back_no_original(self):
  q=e.build_back('SYNTHETIC VISIBLE','K');self.assertEqual(q['model'],'gemini-3.8-flash');self.assertNotIn('household_context',str(q['payload']));self.assertIn('SYNTHETIC VISIBLE',str(q['payload']))
 def test_back_refuses_other_kwargs(self):
  with self.assertRaises(TypeError):e.build_back('SYNTHETIC VISIBLE','K',original='SECRET')
 def test_back_requires_visible(self):
  with self.assertRaises(ValueError):e.build_back('','L')
 def test_stops_only(self):
  raw={'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':'ok'}]}}]}
  self.assertEqual(e.inspect(raw,'hi','K','first','38SVC')['translation'],'ok')
 def test_max_tokens_never_retries(self):
  raw={'candidates':[{'finishReason':'MAX_TOKENS','content':{'parts':[{'text':'partial'}]}}]}
  self.assertEqual(e.inspect(raw,'hi','K','first','38SVC')['status'],'FAILED')
 def test_no_history_in_back_task(self):
  p=plan();p['tasks'][1]['original']='SECRET'
  with self.assertRaises(AssertionError):c.validate(p)
 def test_no_unknown_profile(self):
  with self.assertRaises(ValueError):e.build_first('hi','K','35L')
 def test_valid_four_paths(self):self.assertTrue(c.validate(plan()))
 def test_no_paid_without_approval(self):
  p=plan();a=guarded(p);a['authorized']=False
  with self.assertRaises(PermissionError):c.authorize(p,a,config(p))
 def test_no_over_cap(self):
  p=plan();p['prior_actual_attempts']=126
  with self.assertRaises(AssertionError):c.authorize(p,guarded(p),config(p))
 def test_no_mismatched_manifest(self):
  p=plan();co=config(p);co['source_manifest_sha256']='BAD'
  with self.assertRaises(AssertionError):c.authorize(p,guarded(p),co)
 def test_case_paired_back_independence(self):
  p=plan();p['tasks'][1]['depends_on']=3
  with self.assertRaises(AssertionError):c.validate(p)
 def test_single_send_per_task(self):
  p=plan();a=guarded(p);co=config(p);sent=[]
  def send(q):
   sent.append(q)
   v=response('SYNTHETIC_REPLY');v['raw']['modelVersion']=q['model'];return v
  with tempfile.TemporaryDirectory() as td:
   x=c.run(p,a,co,send,Path(td)/'journal')
  self.assertEqual(x['attempts'],8);self.assertEqual(len(sent),8);self.assertEqual(x['automatic_retries'],0)
 def test_failed_first_skips_dependent_back(self):
  p=plan();a=guarded(p);co=config(p);sent=[]
  def send(q):
   sent.append(q)
   v=response('SYNTHETIC_REPLY');v['raw']['modelVersion']=q['model']
   if len(sent)==1:v['raw']['candidates'][0]['finishReason']='MAX_TOKENS'
   return v
  with tempfile.TemporaryDirectory() as td:x=c.run(p,a,co,send,Path(td)/'journal')
  self.assertEqual(x['attempts'],7);self.assertEqual(x['slots'][1]['status'],'SKIPPED_DEPENDENCY')
 def test_readme_no_secret(self):
  z=(ROOT/'README.md').read_text()
  self.assertNotIn('AIza',z)
if __name__=='__main__':unittest.main(verbosity=2)