import json,pathlib,subprocess,copy,unittest
import runner
P=pathlib.Path(__file__).parent
class Contracts(unittest.TestCase):
 def test_frozen_base_payload(self):
  q=subprocess.Popen(['node',str(P/'worker.cjs'),'35'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True)
  try:
   for path,b in json.loads((P/'BASE_REQUESTS.json').read_text()).items():
    a=runner.worker_call(q,{'mode':'build','path':path,'variant':'BASE','input':'SYNTHETIC'});expected=copy.deepcopy(b['payload']);expected['contents'][0]['parts'][0]['text']='SYNTHETIC';self.assertEqual(a['payload'],expected)
  finally:q.terminate();q.wait();q.stdin.close();q.stdout.close()
 def test_back_is_source_only(self):
  q=subprocess.Popen(['node',str(P/'worker.cjs'),'35'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True)
  try:
   for v in ('BASE','SCOPE','SURFACE','ANCHOR'):
    for path in ('KB','LB'):
     a=runner.worker_call(q,{'mode':'build','path':path,'variant':v,'input':'ACTUAL_FIRST_ONLY'});self.assertEqual(a['payload']['contents'],[{'role':'user','parts':[{'text':'ACTUAL_FIRST_ONLY'}]}]);self.assertEqual(a['model'],'gemini-3.5-flash-lite')
  finally:q.terminate();q.wait();q.stdin.close();q.stdout.close()
 def test_reject_back_original(self):
  with self.assertRaises(RuntimeError):runner.validate_tasks([{'case_id':'s','slot':'b','path':'KB','variant':'BASE','input':'original'}],'35',{'max_new':1})
 def test_reject_wrong_dependency(self):
  with self.assertRaises(RuntimeError):runner.validate_tasks([{'case_id':'s','slot':'f','path':'KF','variant':'BASE','input':'synthetic'},{'case_id':'s','slot':'b','path':'LB','variant':'BASE','from_slot':'f'}],'35',{'max_new':2})
 def test_reject_other_model_reference(self):
  with self.assertRaises(RuntimeError):runner.validate_tasks([{'case_id':'s','slot':'b','path':'KB','variant':'BASE','frozen_first':{'model':'36','plan_sha256':'a'*64,'slot':'f','index':1,'displayed_sha256':'b'*64}}],'35',{'max_new':1,'frozen_sources':[['36','a'*64]]})
 def test_no_paid_config(self):
  c=json.loads((P/'35/config.json').read_text());self.assertFalse(c['enabled']);self.assertEqual(c['max_new'],0)
 def test_no_hidden_models_or_500_cap(self):
  self.assertEqual(runner.MODELS,{'35':'gemini-3.5-flash-lite'});s=(P/'runner.py').read_text();self.assertNotIn('attempted<320',s);self.assertIn('attempted<500',s)
 def test_s1_plan(self):
  p=json.loads(pathlib.Path('mprivate/S1-plan.json').read_text());self.assertTrue(runner.validate_tasks(p['tasks'],'35',{'max_new':96}));self.assertEqual(len({x['case_id'] for x in p['tasks']}),24)
if __name__=='__main__':unittest.main()
