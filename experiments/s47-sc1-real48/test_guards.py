import copy
import importlib.util
from pathlib import Path
import tempfile
import unittest

s=importlib.util.spec_from_file_location('real48',Path(__file__).with_name('run.py'))
r=importlib.util.module_from_spec(s);s.loader.exec_module(r)

class Guards(unittest.TestCase):
    def setUp(self):
        self.old=r.C['cases_sha256']
        self.cases=[dict(id=i,side='K' if i<6 else 'L',group='ordinary' if i%6<4 else 'risk',source='PRIVATE_SOURCE_SENTINEL_'+str(i)) for i in range(12)]
        r.C['cases_sha256']=r.b.digest(self.cases)
    def tearDown(self):r.C['cases_sha256']=self.old
    def test_full48_independent_and_cross_order(self):
        requests=[];snapshots=[]
        def send(q):
            requests.append(q)
            return {'type':'message','model':r.C['model'],'stop_reason':'end_turn','usage':{'input_tokens':1,'output_tokens':1},'content':[{'type':'text','text':'{"translation":"VISIBLE_'+str(len(requests))+'"}'}]}
        c=r.Controller(self.cases,lambda d:snapshots.append(copy.deepcopy(d)))
        d=c.run(send)
        self.assertEqual(d['attempts'],48)
        self.assertEqual(d['counts'],{v:{'first':12,'back':12} for v in ('S47','SC1')})
        self.assertEqual([d['records'][i]['variant'] for i in [0,2,4,6]],['S47','SC1','SC1','S47'])
        for i in range(0,48,2):
            self.assertEqual(d['records'][i+1]['input'],d['records'][i]['translation'])
            self.assertNotIn('PRIVATE_SOURCE_SENTINEL',requests[i+1]['messages'][0]['content'])
        self.assertEqual(snapshots[0]['records'][0]['status'],'SENT_OR_UNKNOWN')
        with self.assertRaises(ValueError):c.run(send)
    def test_failure_no_retry_or_back_or_next_candidate(self):
        calls=[]
        def fail(q):calls.append(q);raise TimeoutError()
        c=r.Controller(self.cases,lambda d:None)
        with self.assertRaises(TimeoutError):c.run(fail)
        self.assertEqual(len(calls),1)
        self.assertEqual(c.data['attempts'],1)
    def test_pattern_refusal_retained_no_fallback(self):
        def refusal(q):return {'http_status':400,'stop_reason':'http_error','error_body':'mock pattern rejected'}
        c=r.Controller(self.cases,lambda d:None)
        with self.assertRaises(ValueError):c.run(refusal)
        self.assertEqual(c.data['attempts'],1)
        self.assertEqual(c.data['records'][0]['response']['http_status'],400)
    def test_frozen_sources_and_budget_fail_closed(self):
        changed=copy.deepcopy(self.cases);changed[0]['source']='different'
        with self.assertRaises(ValueError):r.Controller(changed,lambda d:None)
        c=r.Controller(self.cases,lambda d:None);c.data['attempts']=48
        with self.assertRaises(ValueError):c.call(self.cases[0],'S47','first','x',lambda q:None)
    def test_reused_authenticated_encryption_tamper(self):
        with tempfile.TemporaryDirectory() as tmp:
            private=Path(tmp)/'private.pem';pem=r.b.keypair(private)
            aad={'purpose':'test','protocol':r.b.PROTOCOL}
            env=r.b.seal({'sentinel':'private'},pem,aad)
            self.assertEqual(r.b.unseal(env,private,aad),{'sentinel':'private'})
            env['aad']={'purpose':'tampered'}
            with self.assertRaises(ValueError):r.b.unseal(env,private,aad)

if __name__=='__main__':unittest.main()
