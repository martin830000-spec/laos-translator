import importlib.util,json,tempfile,unittest
from pathlib import Path
spec=importlib.util.spec_from_file_location('test_stream8',Path(__file__).resolve().parent/'campaign.py');c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)
class SafetyContract(unittest.TestCase):
    def test_eight_own_back_and_no_reuse(self):
        cases=[{'id':i,'side':s,'source':'SOURCE'+str(i)} for i,s in [(37,'K'),(19,'K'),(67,'L'),(78,'L')]]
        old=c.validate;c.validate=lambda _:cases
        seen=[]
        def transport(q):
            seen.append(q);return {'status':'SUCCESS','complete':True,'translation':'VISIBLE'+str(len(seen)),'http_status':200,'response':{'model':c.a.MODEL,'stop_reason':'end_turn','usage':{'input_tokens':1,'output_tokens':2}}}
        try:
            with tempfile.TemporaryDirectory() as td:
                approval={'authorized':True,'plan_id':c.PLAN,'maximum_new_attempts':8,'manifest_sha256':c.MANIFEST};journal=Path(td)/'once'
                d=c.run_approved({},approval,transport,journal);self.assertEqual(d['attempts'],8)
                for i in range(0,8,2):self.assertEqual(seen[i+1],c.a.build_request('VISIBLE'+str(i+1),cases[i//2]['side'],'back'))
                with self.assertRaises(FileExistsError):c.run_approved({},approval,transport,journal)
                self.assertEqual(len(seen),8)
        finally:c.validate=old
    def test_individual_failure_skip_back_continue_no_refill_auth_stop(self):
        cases=[{'id':i,'side':s,'source':'SOURCE'} for i,s in [(37,'K'),(19,'K'),(67,'L'),(78,'L')]]
        old=c.validate;c.validate=lambda _:cases
        try:
            with tempfile.TemporaryDirectory() as td:
                ap={'authorized':True,'plan_id':c.PLAN,'maximum_new_attempts':8,'manifest_sha256':c.MANIFEST};calls=[]
                def fail(q):calls.append(q);return {'status':'FAILED','http_status':529,'response':None}
                d=c.run_approved({},ap,fail,Path(td)/'a');self.assertEqual(d['attempts'],4);self.assertEqual(sum(s['status']=='SKIPPED_DEPENDENCY' for s in d['slots']),4)
                with self.assertRaises(c.SafetyStop):c.run_approved({},ap,lambda q:{'status':'FAILED','http_status':401},Path(td)/'b')
                with self.assertRaises(PermissionError):c.run_approved({},dict(ap,maximum_new_attempts=9),fail,Path(td)/'c')
        finally:c.validate=old
    def test_timing_wire_and_display_preserve_tags(self):
        events=[{'type':'message_start','message':{'model':c.a.MODEL,'usage':{'input_tokens':2},'content':[]}}, {'type':'content_block_start','index':0,'content_block':{'type':'text','text':''}}, {'type':'content_block_delta','index':0,'delta':{'type':'text_delta','text':'<final>ລາວ</final>'}}, {'type':'content_block_stop','index':0}, {'type':'message_delta','delta':{'stop_reason':'end_turn'},'usage':{'output_tokens':4}}, {'type':'message_stop'}]
        class Response:
            status=200
            def __init__(self):self.chunks=[('data: '+json.dumps(e,ensure_ascii=False)+'\n\n').encode() for e in events]
            def read1(self,n):return self.chunks.pop(0) if self.chunks else b''
        tick=[0.0]
        def clock():tick[0]+=.001;return tick[0]
        x=c.t.consume(Response(),0,clock);self.assertEqual(x['status'],'SUCCESS');self.assertEqual(x['translation'],'<final>ລາວ</final>')
        self.assertLessEqual(x['first_text_received_ms'],x['display_ready_ms']);self.assertLess(x['display_ready_ms'],x['api_complete_ms']);self.assertIsNone(x['actual_app_render_ms'])
if __name__=='__main__':unittest.main()
