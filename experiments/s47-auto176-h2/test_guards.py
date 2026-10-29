import contextlib, copy, hashlib, io, json, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
import run as r

class Guards(unittest.TestCase):
    def setUp(self):
        self.cases=[dict(id=i,side=s,source='PRIVATE_SENTINEL_'+str(i)) for i,(s,h) in r.EXPECTED.items()]
        self.expected={c['id']:(c['side'],hashlib.sha256(c['source'].encode()).hexdigest()) for c in self.cases}
        self.requests=[]
    def fake(self,q):
        self.requests.append(copy.deepcopy(q))
        return dict(stop_reason='end_turn',content=[dict(type='text',text=json.dumps(dict(source_people=['FACT_SENTINEL'],source_events=['EVENT_SENTINEL'],translation='VISIBLE_'+str(len(self.requests)))))],usage=dict(input_tokens=500,output_tokens=100))
    def controller(self): return r.Controller(self.cases,lambda d:None)
    def test_exact32_independent_back_and_balanced_order(self):
        with patch.dict(r.EXPECTED,self.expected,clear=True):
            c=self.controller();c.run(self.fake)
        self.assertEqual((c.data['attempts'],c.data['first_attempts'],c.data['back_attempts']),(32,16,16))
        for i,x in enumerate(c.data['records']):
            if x['path'].endswith('_back'):
                self.assertEqual(x['input'],c.data['records'][i-1]['translation'])
                self.assertNotIn('PRIVATE_SENTINEL',json.dumps(x['payload']))
                self.assertNotIn('FACT_SENTINEL',json.dumps(x['payload']))
                self.assertNotIn('EVENT_SENTINEL',json.dumps(x['payload']))
        for v in ('A','B'):
            for p in ('K_first','K_back','L_first','L_back'):
                self.assertEqual(sum(x['variant']==v and x['path']==p for x in c.data['records']),4)
        self.assertEqual([x['variant'] for x in c.data['records'][:8]],['A','A','B','B','B','B','A','A'])
        with self.assertRaises(ValueError): c.call(self.cases[0],3,'first','extra',self.fake,'B')
        self.assertEqual(len(self.requests),32)
    def test_single_delta_original_A_and_role_B(self):
        a=r.load_adapter()
        for side in ('K','L'):
            for stage in ('first','back'):
                q=r.build_request(a,'VISIBLE',side,stage,'A')
                self.assertEqual(q,a.build_request('VISIBLE',side,stage))
                b=r.build_request(a,'VISIBLE',side,stage,'B');system=b.pop('system');original=q.pop('system')
                self.assertEqual(q,b)
                if stage=='first':
                    self.assertEqual(system,original+'\n'+r.COVERAGE)
                else:
                    self.assertEqual(system,original)
                self.assertNotIn('발화자=남편',system)
                self.assertNotIn('발화자=아내',system)
    def test_no_money_gate(self):
        def huge(q):
            x=self.fake(q);x['usage']={'input_tokens':1000000,'output_tokens':1000000};return x
        with patch.dict(r.EXPECTED,self.expected,clear=True):
            c=self.controller();c.run(huge)
        self.assertEqual(len(self.requests),32);self.assertGreater(c.data['estimated_usd'],.08)
    def test_failed_attempt_counted_no_retry_no_back(self):
        def fail(q):self.requests.append(q);raise TimeoutError('SECRET_ERROR')
        with patch.dict(r.EXPECTED,self.expected,clear=True):
            c=self.controller()
            with self.assertRaises(TimeoutError):c.run(fail)
        self.assertEqual(c.data['attempts'],1);self.assertEqual(c.data['back_attempts'],0)
        self.assertEqual(len(self.requests),1)
    def test_truncated_stops(self):
        with patch.dict(r.EXPECTED,self.expected,clear=True):
            c=self.controller()
            with self.assertRaises(ValueError):c.run(lambda q:dict(stop_reason='max_tokens',content=[]))
        self.assertEqual(c.data['attempts'],1)
    def test_input_scope_and_old_scope_excluded(self):
        self.assertFalse(set(r.EXPECTED)&{386,333,258,123})
        with self.assertRaises(ValueError):r.validate_cases(self.cases)
        self.assertNotEqual(r.TAG,'s47-realuse16-20261030-consumed')
    def test_authenticated_encryption_and_run_binding(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'key';pub=r.keypair(p);v={'source':'PRIVATE_SENTINEL'};aad={'run':'H1'}
            s=r.seal(v,pub,aad);self.assertNotIn('PRIVATE_SENTINEL',json.dumps(s))
            self.assertEqual(r.unseal(s,p,aad),v)
            with self.assertRaises(ValueError):r.unseal(s,p,{'run':'other'})
            s['ciphertext']='AAAA'+s['ciphertext'][4:]
            with self.assertRaises(Exception):r.unseal(s,p,aad)
    def test_no_plaintext_core_output(self):
        out=io.StringIO()
        with patch.dict(r.EXPECTED,self.expected,clear=True),contextlib.redirect_stdout(out):self.controller().run(self.fake)
        self.assertEqual(out.getvalue(),'')

if __name__=='__main__':unittest.main()
