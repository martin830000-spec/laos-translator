import contextlib
import copy
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import run as r


class Guards(unittest.TestCase):
    def setUp(self):
        self.cases = [dict(id=i,side=side,source='SYNTHETIC_PRIVATE_SENTINEL_'+str(i)) for i,(side,sha) in r.EXPECTED.items()]
        self.expected = {c['id']:(c['side'],hashlib.sha256(c['source'].encode()).hexdigest()) for c in self.cases}

    def fake(self, q):
        text = 'VISIBLE_ONLY_'+str(self.calls)
        self.calls += 1
        self.requests.append(copy.deepcopy(q))
        return dict(stop_reason='end_turn', content=[dict(type='text',text=json.dumps(dict(source_people=['FACT_NOT_BACK_INPUT'],source_events=['EVENT_NOT_BACK_INPUT'],translation=text)))],usage={'input_tokens':500,'output_tokens':100})

    def test_exact16_four_paths_and_independent_back(self):
        self.calls=0;self.requests=[];saved=[]
        with patch.dict(r.EXPECTED,self.expected,clear=True):
            c=r.Controller(self.cases,lambda d:saved.append(copy.deepcopy(d)))
            c.run(self.fake)
        self.assertEqual((c.data['attempts'],c.data['first_attempts'],c.data['back_attempts']),(16,8,8))
        for i,q in enumerate(self.requests):
            if i%2:
                self.assertIn('VISIBLE_ONLY_'+str(i-1),q['messages'][0]['content'])
                self.assertNotIn('SYNTHETIC_PRIVATE_SENTINEL',json.dumps(q))
                self.assertNotIn('FACT_NOT_BACK_INPUT',json.dumps(q))
                self.assertNotIn('EVENT_NOT_BACK_INPUT',json.dumps(q))
        self.assertEqual({p:sum(x['path']==p for x in c.data['records']) for p in ['K_first','K_back','L_first','L_back']},{p:4 for p in ['K_first','K_back','L_first','L_back']})
        self.assertEqual(c.data['status'],'HOLD_FOUR_PATH_SEMANTIC_REVIEW')
        with self.assertRaises(ValueError):c.call(self.cases[0],3,'first','extra',self.fake)
        self.assertEqual(self.calls,16)

    def test_no_money_gate(self):
        self.calls=0;self.requests=[]
        def expensive(q):
            v=self.fake(q);v['usage']={'input_tokens':1000000,'output_tokens':1000000};return v
        with patch.dict(r.EXPECTED,self.expected,clear=True):
            c=r.Controller(self.cases,lambda d:None);c.run(expensive)
        self.assertEqual(self.calls,16)
        self.assertGreater(c.data['estimated_usd'],.08)
        self.assertIsNone(c.data['money_limit'])

    def test_failed_first_has_no_back_or_retry(self):
        sent=[];saved=[]
        def fail(q):sent.append(q);raise TimeoutError('PRIVATE_ERROR_SENTINEL')
        with patch.dict(r.EXPECTED,self.expected,clear=True):
            c=r.Controller(self.cases,lambda d:saved.append(copy.deepcopy(d)))
            with self.assertRaises(TimeoutError):c.run(fail)
        self.assertEqual((len(sent),c.data['attempts'],c.data['back_attempts']),(1,1,0))
        self.assertEqual(saved[0]['records'][0]['status'],'SENT_OR_UNKNOWN')

    def test_truncated_response_stops_without_back(self):
        saved=[]
        with patch.dict(r.EXPECTED,self.expected,clear=True):
            c=r.Controller(self.cases,lambda d:saved.append(copy.deepcopy(d)))
            with self.assertRaises(ValueError):c.run(lambda q:dict(stop_reason='max_tokens',content=[]))
        self.assertEqual(c.data['attempts'],1)
        self.assertEqual(c.data['responses'],1)

    def test_scope_tampering_rejected_before_transport(self):
        cases=copy.deepcopy(self.cases);cases[0]['source']='WRONG'
        with self.assertRaises(ValueError):r.validate_cases(cases)
        cases.append(cases[0])
        with self.assertRaises(ValueError):r.validate_cases(cases)

    def test_encryption_integrity_and_run_binding(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'key.pem';pem=r.keypair(p)
            aad={'run':'approved','purpose':'result'}
            value={'private':'PRIVATE_PLAINTEXT_SENTINEL'}
            sealed=r.seal(value,pem,aad)
            self.assertNotIn('PRIVATE_PLAINTEXT_SENTINEL',json.dumps(sealed))
            self.assertEqual(r.unseal(sealed,p,aad),value)
            with self.assertRaises(ValueError):r.unseal(sealed,p,dict(aad,run='wrong'))
            sealed['ciphertext']='AAAA'+sealed['ciphertext'][4:]
            with self.assertRaises(Exception):r.unseal(sealed,p,aad)

    def test_original_adapter_unchanged(self):
        a=r.load_adapter();q=a.build_request('AUDIT_VISIBLE','K','first')
        self.assertEqual(q['output_config']['effort'],'low')
        self.assertEqual(q['thinking'],{'type':'disabled'})
        self.assertEqual(q['max_tokens'],2048)
        self.assertNotIn('HUSBAND',q['system'])

    def test_core_prints_no_private_text(self):
        self.calls=0;self.requests=[];stdout=io.StringIO()
        with patch.dict(r.EXPECTED,self.expected,clear=True), contextlib.redirect_stdout(stdout):
            c=r.Controller(self.cases,lambda d:None);c.run(self.fake)
        self.assertEqual(stdout.getvalue(),'')


if __name__=='__main__':unittest.main()
