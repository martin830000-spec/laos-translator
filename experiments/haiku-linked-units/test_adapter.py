import ast
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT=Path(__file__).resolve().parent
def load(name,file):
    s=importlib.util.spec_from_file_location(name,ROOT/file);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
a=load('la1_tests_adapter','adapter.py')
c=load('la1_tests_campaign','campaign.py')
cli=load('la1_tests_cli','cli.py')

def raw(units,stop='end_turn'):
    return {'model':a.CONFIG['model'],'type':'message','stop_reason':stop,'usage':{'input_tokens':1,'output_tokens':1},
            'content':[{'type':'text','text':json.dumps({'units':units},ensure_ascii=False)}]}

def manifest():
    cases=[]
    for i in range(16):
        cohort='prior12' if i<12 else 'matched4'
        side=('K' if i<6 else 'L') if i<12 else ('K' if i<14 else 'L')
        row={'id':i,'side':side,'cohort':cohort,'source':'SYNTHETIC_SOURCE_'+str(i),'development_allowed':True}
        if i<12:row['historical_s47']={stage:{'status':'SUCCESS','translation':'REUSED_ONLY_'+str(i)+stage} for stage in ('first','back')}
        cases.append(row)
    return {'id':c.PLAN_ID,'maximum_new_attempts':40,'candidate_adapter_sha256':c.code_sha(),'cases':cases,'cases_sha256':a.digest(cases)}

def approved(m):
    return {'authorized':True,'plan_id':c.PLAN_ID,'maximum_new_attempts':40,'manifest_sha256':a.digest(m)}

class AdapterSafety(unittest.TestCase):
    def test_four_routes_and_frozen_baseline(self):
        source='  RAW_SOURCE\r\n\t😀 e\u0301  '
        for side in ('K','L'):
            for stage in ('first','back'):
                baseline=a.BASELINE.build_request(source,side,stage)
                self.assertEqual(a.build_request(source,side,stage,'S47'),baseline)
                q=a.build_request(source,side,stage)
                self.assertEqual(q['messages'],baseline['messages'])
                self.assertEqual(q['system'],baseline['system']+a.CONTRACT)
                self.assertEqual((q['model'],q['thinking'],q['max_tokens'],q['output_config']['effort']),('claude-haiku-5-5',{'type':'disabled'},2048,'low'))
                self.assertNotIn('pattern',json.dumps(q['output_config']['format']['schema']))
                self.assertNotIn('RAW_SOURCE',json.dumps(q['output_config']['format']['schema']))
        self.assertEqual([a.target_language(s,t) for s,t in [('K','first'),('K','back'),('L','first'),('L','back')]],['Lao','Korean','Korean','Lao'])
    def test_exact_render_and_lossless_source(self):
        original='A\r\n B e\u0301😀'
        response=raw([{'source':'A\r\n','target':'  first\r\n'},{'source':' B e\u0301😀','target':' second e\u0301😀  '}])
        result=a.inspect_response(response,original,'K','first')
        self.assertEqual(result['translation'],'  first\r\n second e\u0301😀  ')
        self.assertTrue(result['alignment_ok'])
    def test_alignment_warning_never_hides_or_rewrites_target(self):
        result=a.inspect_response(raw([{'source':'misquoted','target':'READABLE TARGET'}]),'actual source','L','first')
        self.assertFalse(result['alignment_ok']);self.assertEqual(result['translation'],'READABLE TARGET')
        self.assertIn('SOURCE_RECONSTRUCTION_MISMATCH',result['warnings'])
    def test_semantically_wrong_but_aligned_negative_controls(self):
        for source,target in [('Amount 630000','Amount 90000'),('Do not go','Go'),('I am tired','I cannot speak'),('Hello','Message to a spouse: hello')]:
            result=a.inspect_response(raw([{'source':source,'target':target}]),source,'L','first')
            self.assertTrue(result['alignment_ok']);self.assertEqual(result['translation'],target)
        # These passing structural cases intentionally refute a semantic guarantee.
    def test_no_whole_json_salvage_duplicate_keys_or_incomplete(self):
        good=raw([{'source':'A','target':'B'}])
        for text in [good['content'][0]['text']+'\n'+good['content'][0]['text'],
                     '{"units":[],"units":[{"source":"A","target":"B"}]}',
                     '{"units":[{"source":"A","target":"B","extra":1}]}']:
            response=copy.deepcopy(good);response['content'][0]['text']=text
            with self.assertRaises((ValueError,json.JSONDecodeError)):a.inspect_response(response,'A','K','first')
        with self.assertRaises(ValueError):a.inspect_response(raw([{'source':'A','target':'B'}],stop='max_tokens'),'A','K','first')
    def test_session_back_only_rendered_translation(self):
        requests=[];persisted=[]
        sources=['ORIGINAL_SENTINEL','VISIBLE_ONLY'];targets=['VISIBLE_ONLY','BACK_VISIBLE']
        def send(q):
            i=len(requests);requests.append(q);return raw([{'source':sources[i],'target':targets[i]}])
        session=a.SinglePassSession('K');result=session.run(sources[0],send,lambda x:persisted.append(x))
        self.assertEqual(result['attempts'],2)
        self.assertNotIn('ORIGINAL_SENTINEL',requests[1]['messages'][0]['content'])
        self.assertEqual(requests[1],a.build_request('VISIBLE_ONLY','K','back'))
        self.assertEqual(persisted[0]['status'],'SENT_OR_UNKNOWN')
        with self.assertRaises(RuntimeError):session.run('x',send)
    def test_first_failure_skips_only_dependent_back(self):
        calls=[]
        def fail(q):calls.append(q);raise TimeoutError()
        out=a.SinglePassSession('L').run('source',fail)
        self.assertEqual(out['attempts'],1);self.assertEqual(len(calls),1)
        self.assertEqual([x['status'] for x in out['stages']],['FAILED','SKIPPED_DEPENDENCY'])
    def test_cli_does_not_normalize_crlf(self):
        with tempfile.TemporaryDirectory() as t:
            path=Path(t)/'source.txt';path.write_bytes(b' A\r\n B\r\n')
            self.assertEqual(cli.read_exact(path),' A\r\n B\r\n')
    def test_no_http_or_secret_lookup_in_new_code(self):
        for name in ('adapter.py','campaign.py','cli.py'):
            tree=ast.parse((ROOT/name).read_text(encoding='utf-8'))
            imports=[x.name.split('.')[0] for n in ast.walk(tree) if isinstance(n,ast.Import) for x in n.names]
            self.assertFalse(set(imports)&{'urllib','requests','httpx','anthropic','socket'})
            self.assertNotIn('getenv',(ROOT/name).read_text(encoding='utf-8'))
    def test_cost_is_recorded_without_budget_gate_and_unknown_is_not_zero(self):
        self.assertIsNone(a.estimated_cost_usd({}))
        self.assertAlmostEqual(a.estimated_cost_usd({'input_tokens':1000,'output_tokens':500}),.00035)
        self.assertAlmostEqual(a.estimated_cost_usd({'input_tokens':1000,'output_tokens':500,'cache_creation_input_tokens':200,'cache_creation':{'ephemeral_1h_input_tokens':100}}),.0003825)

class CampaignSafety(unittest.TestCase):
    def test_prepared_actions_bridge_denies_before_state_keys_or_http(self):
        bridge=load('la1_bridge_test','actions_bridge.py');called=[]
        bridge.b.read=lambda path:{'authorized':False}
        bridge.b.request_json=lambda *args,**kwargs:called.append(args)
        with self.assertRaises(PermissionError):bridge.execute(Path('MISSING_STATE_MUST_NOT_BE_READ'))
        self.assertEqual(called,[])
    def test_unapproved_and_tampered_manifest_zero_callbacks(self):
        m=manifest();called=[]
        with tempfile.TemporaryDirectory() as t:
            with self.assertRaises(PermissionError):c.run_approved(m,{'authorized':False},lambda q:called.append(q),Path(t)/'lock')
            altered=copy.deepcopy(m);altered['cases'][0]['source']='tampered'
            with self.assertRaises(ValueError):c.run_approved(altered,approved(m),lambda q:called.append(q),Path(t)/'lock')
        self.assertEqual(called,[])
    def test_exact40_new_24_reused_and_consumed_journal(self):
        m=manifest();calls=[]
        def send(q):
            calls.append(q)
            source=q['messages'][0]['content'].split('<message>\n',1)[1].rsplit('\n</message>',1)[0]
            target='NEW_VISIBLE_'+str(len(calls))
            if 'units' in q['output_config']['format']['schema']['properties']:return raw([{'source':source,'target':target}])
            return {'model':'claude-haiku-5-5','stop_reason':'end_turn','content':[{'type':'text','text':json.dumps({'source_people':[],'source_events':[],'translation':target})}]}
        with tempfile.TemporaryDirectory() as t:
            journal=Path(t)/'once';d=c.run_approved(m,approved(m),send,journal)
            self.assertEqual(d['attempts'],40);self.assertEqual(len(calls),40)
            self.assertEqual(sum(s['status']=='REUSED_REFERENCE' for s in d['slots']),24)
            self.assertFalse(any('REUSED_ONLY_' in json.dumps(q) for q in calls))
            with self.assertRaises(FileExistsError):c.run_approved(m,approved(m),send,journal)
            self.assertEqual(len(calls),40)
    def test_individual_failures_continue_and_do_not_fill_skips(self):
        m=manifest();calls=[]
        def send(q):calls.append(q);return raw([{'source':'x','target':'y'}],stop='max_tokens')
        with tempfile.TemporaryDirectory() as t:d=c.run_approved(m,approved(m),send,Path(t)/'once')
        self.assertEqual(len(calls),20)
        self.assertEqual(sum(s['status']=='FAILED' for s in d['slots']),20)
        self.assertEqual(sum(s['status']=='SKIPPED_DEPENDENCY' for s in d['slots']),20)
        self.assertEqual(d['status'],'PROCEDURE_COMPLETE_QUALITY_REVIEW_REQUIRED')
    def test_global_authentication_failure_stops_without_retry(self):
        m=manifest();calls=[]
        def send(q):calls.append(q);return {'http_status':401,'stop_reason':'http_error'}
        with tempfile.TemporaryDirectory() as t:
            with self.assertRaises(c.a.SafetyStop):c.run_approved(m,approved(m),send,Path(t)/'once')
        self.assertEqual(len(calls),1)

if __name__=='__main__':unittest.main()
