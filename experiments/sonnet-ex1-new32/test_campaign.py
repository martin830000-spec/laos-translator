import importlib.util,json,tempfile,unittest
from unittest.mock import patch
from pathlib import Path
sp=importlib.util.spec_from_file_location('ab64_tests',Path(__file__).resolve().parent/'campaign.py');c=importlib.util.module_from_spec(sp);sp.loader.exec_module(c)
def approval():return {'authorized':True,'plan_id':c.PLAN,'maximum_new_attempts':32,'manifest_sha256':c.MANIFEST,'source_plan_sha256':c.SOURCE_PLAN_SHA}
def plan():
    plans=[]
    for e in ['S']:
        sources=[{'id':i,'side':'K' if i<4 else 'L','source':'SYNTHETIC_'+str(i)} for i in range(8)];slots=[]
        for i,s in enumerate(sources):
            for v in (['BASELINE','EXEMPLARS'] if i%2==0 else ['EXEMPLARS','BASELINE']):
                for stage in ['first','back']:slots.append({'slot':len(slots)+1,'id':s['id'],'side':s['side'],'variant':v,'stage':stage})
        plans.append({'engine':e,'sources':sources,'schedule':slots})
    return {'plans':plans}
def response(q,n,stop='end_turn'):
    text='VISIBLE_'+str(n)
    if q['model']=='claude-haiku-5-5':
        src=q['messages'][0]['content'].split('<message>\n',1)[1].rsplit('\n</message>',1)[0];text=json.dumps({'units':[{'source':src,'target':text}]})
    return {'type':'message','model':q['model'],'id':'TEST_'+str(n),'stop_reason':stop,'content':[{'type':'text','text':text}],'usage':{'input_tokens':1,'output_tokens':2}}
class OneShot64(unittest.TestCase):
    def test_64_caps_order_and_own_arm_back_no_reuse(self):
        calls=[]
        def send(q):calls.append(q);return response(q,len(calls))
        with tempfile.TemporaryDirectory() as td,patch.object(c,'validate',lambda m:plan()):
            path=Path(td)/'once';d=c.run_approved({},approval(),send,path)
            self.assertEqual(d['attempts'],32);self.assertEqual(d['per_engine'],{'S':32});self.assertEqual(set(d['per_arm'].values()),{16})
            first={}
            for s in d['slots']:
                key=(s['engine'],s['variant'],s['id'])
                if s['stage']=='first':first[key]=s['translation']
                else:self.assertEqual(s['input'],first[key])
            with self.assertRaises(FileExistsError):c.run_approved({},approval(),send,path)
            self.assertEqual(len(calls),32)
    def test_first_failure_skips_own_back_continue_no_refill(self):
        calls=[]
        def send(q):calls.append(q);return response(q,len(calls),'max_tokens')
        with tempfile.TemporaryDirectory() as td,patch.object(c,'validate',lambda m:plan()):d=c.run_approved({},approval(),send,Path(td)/'once')
        self.assertEqual(d['attempts'],16);self.assertEqual(sum(s['status']=='SKIPPED_DEPENDENCY' for s in d['slots']),16)
    def test_unapproved_and_auth_stop_without_retry(self):
        calls=[]
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(PermissionError):c.run_approved({},dict(approval(),maximum_new_attempts=33),lambda q:calls.append(q),Path(td)/'a')
            def fail(q):calls.append(q);return {'http_status':401}
            with patch.object(c,'validate',lambda m:plan()):
                with self.assertRaises(c.SafetyStop):c.run_approved({},approval(),fail,Path(td)/'b')
        self.assertEqual(len(calls),1)
if __name__=='__main__':unittest.main()
