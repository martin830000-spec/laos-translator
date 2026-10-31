from pathlib import Path
import importlib.util,json,tempfile,unittest
from unittest.mock import patch
s=importlib.util.spec_from_file_location('hy2b_test',Path(__file__).resolve().parent/'campaign.py');c=importlib.util.module_from_spec(s);s.loader.exec_module(c)
def approval():return {'authorized':True,'plan_id':c.PLAN,'maximum_new_attempts':20,'manifest_sha256':c.MANIFEST,'source_plan_sha256':c.SOURCE_PLAN_SHA}
def plan():
    cases=[]
    for i in range(10):
        for donor in ['S','O']:
            text='CURRENT_DISPLAY_'+str(i)+'_'+donor
            cases.append({'slot':len(cases)+1,'id':i,'donor_engine':donor,'side':'L','stage':'back','input':text,'input_sha256':__import__('hashlib').sha256(text.encode()).hexdigest(),'first_origin_slot':i,'old_back_slot':i+1,'first_origin_response_sha256':'FROZEN_HASH'})
    return {'cases':cases}
def response(q,n,stop='end_turn'):
    text=q['messages'][0]['content'].split('<message>\n',1)[1].rsplit('\n</message>',1)[0]
    return {'type':'message','model':'claude-haiku-5-5','id':'SYNTHETIC_'+str(n),'stop_reason':stop,'content':[{'type':'text','text':json.dumps({'units':[{'source':text,'target':'VISIBLE_'+str(n)}]})}],'usage':{'input_tokens':1,'output_tokens':2}}
class SafetyContracts(unittest.TestCase):
    def test_twenty_back_only_same_display_no_reuse(self):
        calls=[]
        def send(q):calls.append(q);return response(q,len(calls))
        with tempfile.TemporaryDirectory() as td,patch.object(c,'validate',lambda _:plan()):
            path=Path(td)/'once';d=c.run_approved({},approval(),send,path)
            self.assertEqual(d['attempts'],20);self.assertEqual(d['per_donor'],{'S':10,'O':10});self.assertEqual(d['new_FIRST_calls'],0)
            for x,case in zip(d['slots'],plan()['cases']):self.assertEqual(x['payload'],c.build_request(case['input']));self.assertEqual(x['input'],case['input']);self.assertEqual(x['stage'],'back')
            with self.assertRaises(FileExistsError):c.run_approved({},approval(),send,path)
            self.assertEqual(len(calls),20)
    def test_one_failure_continue_no_retry_or_replacement(self):
        calls=[]
        def send(q):calls.append(q);return response(q,len(calls),'max_tokens' if len(calls)==3 else 'end_turn')
        with tempfile.TemporaryDirectory() as td,patch.object(c,'validate',lambda _:plan()):d=c.run_approved({},approval(),send,Path(td)/'once')
        self.assertEqual(len(calls),20);self.assertEqual(sum(x['status']=='FAILED' for x in d['slots']),1);self.assertEqual(d['retries'],0)
    def test_unapproved_denied_and_auth_stops_no_retry(self):
        calls=[]
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(PermissionError):c.run_approved({},dict(approval(),maximum_new_attempts=21),lambda q:calls.append(q),Path(td)/'a')
            def send(q):calls.append(q);return {'http_status':401}
            with patch.object(c,'validate',lambda _:plan()):
                with self.assertRaises(c.SafetyStop):c.run_approved({},approval(),send,Path(td)/'b')
        self.assertEqual(len(calls),1)
if __name__=='__main__':unittest.main()
