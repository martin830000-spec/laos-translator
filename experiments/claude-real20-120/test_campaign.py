import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('test_real120',ROOT/'campaign.py');c=importlib.util.module_from_spec(s);s.loader.exec_module(c)
def approval():return {'authorized':True,'plan_id':c.PLAN,'maximum_new_attempts':120,'manifest_sha256':c.MANIFEST}
def fixture():
    cases=[{'id':i,'side':'K' if i%2==0 else 'L','source':'SYNTHETIC_'+str(i)} for i in range(20)]
    return {'cases':cases,'slots':c.schedule(cases)}
def response(q,n,stop='end_turn'):
    text='MOCK_VISIBLE_'+str(n)
    if q['model']==c.a.MODELS['H']:
        source=q['messages'][0]['content'].split('<message>\n',1)[1].rsplit('\n</message>',1)[0]
        text=json.dumps({'units':[{'source':source,'target':text}]})
    return {'type':'message','model':q['model'],'stop_reason':stop,'content':[{'type':'text','text':text}],'usage':{'input_tokens':0,'output_tokens':0}}
class OneShot120(unittest.TestCase):
    def test_120_per_engine40_own_back_and_journal_reuse_denial(self):
        calls=[]
        def send(q):calls.append(q);return response(q,len(calls))
        with tempfile.TemporaryDirectory() as t,patch.object(c,'validate',lambda m:m['cases']):
            path=Path(t)/'once';out=c.run_approved(fixture(),approval(),send,path)
            self.assertEqual(out['attempts'],120);self.assertEqual(out['per_engine'],{'H':40,'S':40,'O':40})
            first={}
            for r in out['slots']:
                key=(r['case_id'],r['engine'])
                if r['stage']=='first':first[key]=r['translation']
                else:self.assertEqual(r['input'],first[key])
            with self.assertRaises(FileExistsError):c.run_approved(fixture(),approval(),send,path)
            self.assertEqual(len(calls),120)
    def test_failed_first_skips_only_back_and_continues_to_end(self):
        calls=[]
        def send(q):calls.append(q);return response(q,len(calls),'max_tokens')
        with tempfile.TemporaryDirectory() as t,patch.object(c,'validate',lambda m:m['cases']):out=c.run_approved(fixture(),approval(),send,Path(t)/'once')
        self.assertEqual(len(calls),60)
        self.assertEqual(sum(s['status']=='SKIPPED_DEPENDENCY' for s in out['slots']),60)
        self.assertEqual(out['status'],'PROCEDURE_COMPLETE_QUALITY_REVIEW_REQUIRED')
    def test_unapproved_tampered_and_global_auth_no_retry(self):
        calls=[]
        with tempfile.TemporaryDirectory() as t:
            with self.assertRaises(PermissionError):c.run_approved({}, {},lambda q:calls.append(q),Path(t)/'once')
            with self.assertRaises(ValueError):c.run_approved({},approval(),lambda q:calls.append(q),Path(t)/'once')
        self.assertEqual(calls,[])
        def auth(q):calls.append(q);return {'http_status':401,'stop_reason':'http_error'}
        with tempfile.TemporaryDirectory() as t,patch.object(c,'validate',lambda m:m['cases']):
            with self.assertRaises(c.SafetyStop):c.run_approved(fixture(),approval(),auth,Path(t)/'once')
        self.assertEqual(len(calls),1)
if __name__=='__main__':unittest.main()
