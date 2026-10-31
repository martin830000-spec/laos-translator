import copy
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parent
def load(name,file):
    spec=importlib.util.spec_from_file_location(name,ROOT/file);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
c=load('test_sa1_campaign','campaign.py')
def approval():return {'authorized':True,'plan_id':c.PLAN,'maximum_new_attempts':24,'manifest_sha256':c.MANIFEST}
def fixture():
    cases=[{'id':str(i),'side':'K' if i%2==0 else 'L','source':'SOURCE_'+str(i)} for i in range(8)]
    slots=[]
    for i,case in enumerate(cases):
        for v in (['SA1'] if i<4 else ['S1','SA1']):
            for stage in ['first','back']:slots.append({'slot':len(slots)+1,'case_id':case['id'],'side':case['side'],'variant':v,'stage':stage})
    return {'cases':cases,'slots':slots}
def raw(text='VISIBLE',stop='end_turn'):
    return {'type':'message','model':c.MODEL,'stop_reason':stop,'content':[{'type':'thinking','thinking':'HIDDEN'},{'type':'text','text':text}],
        'usage':{'input_tokens':1000,'output_tokens':250,'output_tokens_details':{'thinking_tokens':200}}}

class ApprovedCampaign(unittest.TestCase):
    def run_mock(self,send,path,persist=lambda d:None):
        m=fixture()
        with patch.object(c,'validate',lambda m:m['cases']):return c.run_approved(m,approval(),send,path,persist)
    def test_denial_and_manifest_tamper_before_transport(self):
        called=[]
        with tempfile.TemporaryDirectory() as t:
            with self.assertRaises(PermissionError):c.run_approved({}, {},lambda q:called.append(q),Path(t)/'once')
            with self.assertRaises(ValueError):c.run_approved({},approval(),lambda q:called.append(q),Path(t)/'once')
        self.assertEqual(called,[])
    def test_exact24_cap_own_back_and_reuse_denied(self):
        calls=[]
        def send(q):calls.append(q);return raw('VISIBLE_'+str(len(calls)))
        with tempfile.TemporaryDirectory() as t:
            path=Path(t)/'once';d=self.run_mock(send,path)
            self.assertEqual(d['attempts'],24);self.assertEqual(len(calls),24)
            first={}
            for s in d['slots']:
                key=(s['case_id'],s['variant'])
                if s['stage']=='first':first[key]=s
                else:self.assertEqual(s['input'],first[key]['translation'])
                self.assertNotIn('HIDDEN',str(s['payload']))
            with self.assertRaises(FileExistsError):self.run_mock(send,path)
            self.assertEqual(len(calls),24)
    def test_failure_skips_only_own_back_and_continues_without_refill(self):
        calls=[]
        def send(q):calls.append(q);return raw('partial','max_tokens')
        with tempfile.TemporaryDirectory() as t:d=self.run_mock(send,Path(t)/'once')
        self.assertEqual(len(calls),12)
        self.assertEqual(sum(s['status']=='FAILED' for s in d['slots']),12)
        self.assertEqual(sum(s['status']=='SKIPPED_DEPENDENCY' for s in d['slots']),12)
        self.assertEqual(d['status'],'PROCEDURE_COMPLETE_QUALITY_REVIEW_REQUIRED')
    def test_authentication_stops_without_retry(self):
        calls=[]
        def send(q):calls.append(q);return {'http_status':401,'stop_reason':'http_error'}
        with tempfile.TemporaryDirectory() as t:
            with self.assertRaises(c.SafetyStop):self.run_mock(send,Path(t)/'once')
        self.assertEqual(len(calls),1)
    def test_consumption_persisted_before_callback(self):
        snapshots=[]
        def send(q):
            self.assertEqual(snapshots[-1]['attempts'],len([x for x in snapshots[-1]['slots'] if x.get('attempt')]))
            self.assertTrue(any(s['status']=='SENT_OR_UNKNOWN' for s in snapshots[-1]['slots']))
            return raw()
        with tempfile.TemporaryDirectory() as t:self.run_mock(send,Path(t)/'once',lambda d:snapshots.append(copy.deepcopy(d)))
    def test_encrypted_compressed_transport_roundtrip_and_size(self):
        bridge=load('test_sa1_bridge','actions_bridge.py');value=fixture()
        with patch.object(bridge.c,'validate',lambda m:m['cases']):
            self.assertEqual(bridge.unpack(bridge.pack(value)),value)
        self.assertNotIn('SOURCE_0',str(bridge.pack(value)))
    def test_bridge_unapproved_denies_before_state_or_http(self):
        bridge=load('test_sa1_bridge_deny','actions_bridge.py');calls=[]
        bridge.b.read=lambda path:{'authorized':False}
        bridge.b.request_json=lambda *args,**kwargs:calls.append(args)
        with self.assertRaises(PermissionError):bridge.execute(Path('MISSING_STATE'))
        self.assertEqual(calls,[])
    def test_cost_includes_thinking_once_and_unknown_is_unknown(self):
        self.assertAlmostEqual(c.cost(raw()['usage']),.0045)
        self.assertIsNone(c.cost({}))

if __name__=='__main__':unittest.main()
