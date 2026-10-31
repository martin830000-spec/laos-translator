import copy
import importlib.util
import json
from pathlib import Path
import unittest

s=importlib.util.spec_from_file_location('resume48',Path(__file__).with_name('run.py'))
r=importlib.util.module_from_spec(s);s.loader.exec_module(r)

def response(text='VALID_VISIBLE',stop='end_turn'):
    return dict(type='message',model='claude-haiku-5-5',stop_reason=stop,id='mock',usage={'input_tokens':2,'output_tokens':3},
        content=[{'type':'text','text':json.dumps({'source_people':[],'source_events':[],'translation':text})}])

class Safety(unittest.TestCase):
    def setUp(self):
        self.saved=copy.deepcopy(r.C);self.old=r.r.C['cases_sha256']
        self.cases=[dict(id=21 if i==0 else 1000+i,side='K' if i<6 else 'L',group='ordinary' if i%6<4 else 'risk',source='SOURCE_ONLY_'+str(i)) for i in range(12)]
        r.C['cases_sha256']=r.b.digest(self.cases);r.r.C['cases_sha256']=r.C['cases_sha256']
        records=[]
        for i,(variant,stage,text) in enumerate([('S47','first',self.cases[0]['source']),('S47','back','PRIOR_VISIBLE'),('SC1','first',self.cases[0]['source'])]):
            q=r.a.build_request(text,'K',stage,variant)
            raw=response('PRIOR_VISIBLE',stop='max_tokens' if i==2 else 'end_turn')
            rec=dict(record_id=21,side='K',variant=variant,stage=stage,payload=q,payload_sha256=r.b.digest(q),input=text,response=raw,status='SUCCESS' if i<2 else 'STOP_TECHNICAL_OR_UNKNOWN',usage=raw['usage'],estimated_usd=0.0,api_ms=1)
            if i<2:rec['translation']='PRIOR_VISIBLE'
            records.append(rec)
        self.prior=dict(attempts=3,retries=0,records=records,estimated_usd=0.0,github={'commit':r.C['prior_commit'],'run_id':r.C['prior_run_id']})
        r.C['prior_digest']=r.b.digest(self.prior)
    def tearDown(self):
        r.C.clear();r.C.update(self.saved);r.r.C['cases_sha256']=self.old
    def test_reuses3_skips4_exact44_new_back_independence(self):
        requests=[]
        def send(q):requests.append(q);return response('VISIBLE_'+str(len(requests)))
        c=r.Controller(self.cases,self.prior,lambda d:None);d=c.run(send)
        self.assertEqual(len(requests),44);self.assertEqual(d['total_attempts'],47)
        self.assertEqual(d['slots'][3]['status'],'SKIPPED_DEPENDENCY')
        self.assertTrue(all(s['origin']=='PRIOR_REUSED' for s in d['slots'][:3]))
        for s in d['slots'][4:]:
            if s['stage']=='back':
                self.assertEqual(s['input'],d['slots'][s['slot']-2]['translation'])
                self.assertNotIn('SOURCE_ONLY_',s['payload']['messages'][0]['content'])
        with self.assertRaises(ValueError):c.run(send)
    def test_first_and_back_failures_continue_without_retry(self):
        calls=[]
        def send(q):
            calls.append(q)
            if len(calls)==1:return response(stop='max_tokens')
            if len(calls)==3:return response(stop='max_tokens')
            return response()
        d=r.Controller(self.cases,self.prior,lambda d:None).run(send)
        self.assertEqual(d['slots'][4]['status'],'FAILED')
        self.assertEqual(d['slots'][5]['status'],'SKIPPED_DEPENDENCY')
        self.assertEqual(d['slots'][7]['status'],'FAILED')
        self.assertEqual(d['slots'][8]['status'],'SUCCESS')
        self.assertEqual(d['slots'][-1]['status'],'SUCCESS')
        self.assertEqual(len(calls),43)
    def test_individual_http_timeout_bad_json_no_salvage(self):
        calls=[]
        def send(q):
            calls.append(q)
            if len(calls)==1:return {'http_status':500,'stop_reason':'http_error','error_body':'mock'}
            if len(calls)==2:raise TimeoutError()
            if len(calls)==3:
                raw=response();raw['content'][0]['text']+='\n'+raw['content'][0]['text'];return raw
            return response()
        d=r.Controller(self.cases,self.prior,lambda d:None).run(send)
        self.assertEqual(d['slots'][4]['reason'],'HTTP_500')
        self.assertEqual(d['slots'][6]['reason'],'TIMEOUT_SENT_OR_UNKNOWN_NO_RETRY')
        self.assertTrue(d['slots'][8]['reason'].startswith('JSON_PARSE_'))
        self.assertEqual(d['slots'][-1]['status'],'SUCCESS')
    def test_prior_tamper_and_global_auth_fail_closed(self):
        bad=copy.deepcopy(self.prior);bad['attempts']=2
        with self.assertRaises(ValueError):r.Controller(self.cases,bad,lambda d:None)
        calls=[]
        def deny(q):calls.append(q);return {'http_status':401,'stop_reason':'http_error'}
        c=r.Controller(self.cases,self.prior,lambda d:None)
        with self.assertRaises(r.GlobalStop):c.run(deny)
        self.assertEqual(len(calls),1)
    def test_cap_and_journal_no_send(self):
        calls=[]
        c=r.Controller(self.cases,self.prior,lambda d:None);c.data['new_attempts']=44
        with self.assertRaises(r.GlobalStop):c.run(lambda q:calls.append(q))
        self.assertEqual(calls,[])
        def failpersist(d):raise OSError()
        c=r.Controller(self.cases,self.prior,failpersist)
        with self.assertRaises(OSError):c.run(lambda q:calls.append(q))
        self.assertEqual(calls,[])

if __name__=='__main__':unittest.main()
