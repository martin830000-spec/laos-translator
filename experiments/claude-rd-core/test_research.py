import ast
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT=Path(__file__).resolve().parent
def load(name):
    spec=importlib.util.spec_from_file_location(name,ROOT.parent/name/'adapter.py')
    a=importlib.util.module_from_spec(spec);spec.loader.exec_module(a);return a
S=load('sonnet-sa1');O=load('opus-ob1')
def response(text,stop='end_turn'):
    return {'stop_reason':stop,'content':[{'type':'thinking','thinking':'SECRET_REASONING'},
        {'type':'text','text':text}],'usage':{'output_tokens':250,'output_tokens_details':{'thinking_tokens':200}}}

class ResearchContract(unittest.TestCase):
    def test_sonnet_only_thinking_parameter_changes_on_all_routes(self):
        for side in 'KL':
            for stage in ['first','back']:
                old=S.core.baseline(' A\r\n B ',side,stage,S.MODEL)
                new=S.build_request(' A\r\n B ',side,stage)
                self.assertEqual(new['thinking'],{'type':'adaptive'})
                new['thinking']=old['thinking'];self.assertEqual(new,old)
    def test_opus_forward_identical_back_deletes_only_role_block(self):
        for side in 'KL':
            self.assertEqual(O.build_request('SOURCE',side,'first'),O.core.baseline('SOURCE',side,'first',O.MODEL))
            old=O.core.baseline('SOURCE',side,'back',O.MODEL)
            new=O.build_request('SOURCE',side,'back')
            block='<couple_context>'+O.core.PROMPTS['CLAUDE_SONNET55_S1_ROLE_'+side]+'</couple_context>\n'
            self.assertEqual(new['system'],old['system'].replace(block,''))
            new['system']=old['system'];self.assertEqual(new,old)
    def test_back_has_own_full_visible_output_only_and_no_thinking(self):
        for a in [S,O]:
            raw=response(' ACTUAL_TARGET\nWait — correction retained. ')
            back=a.prepare_back(raw,'L')['payload']
            self.assertIn(' ACTUAL_TARGET\nWait — correction retained. ',back['messages'][0]['content'])
            self.assertNotIn('SECRET_REASONING',json.dumps(back))
            self.assertEqual(len(back['messages']),1)
    def test_failed_first_skips_back_without_repair(self):
        for stop in ['max_tokens','refusal','tool_use']:
            r=S.prepare_back(response('partial',stop),'K')
            self.assertEqual(r['status'],'SKIPPED_DEPENDENCY')
            self.assertEqual(r['visible_partial'],'partial')
            self.assertNotIn('payload',r)
    def test_suspect_output_preserved_and_not_semantic_pass(self):
        text='คำไทย Wait — I need to correct this.'
        r=S.inspect_response(response(text))
        self.assertEqual(r['translation'],text)
        self.assertEqual(len(r['warnings']),2)
        self.assertEqual(r['semantic_quality'],'UNVERIFIED')
        self.assertEqual(S.inspect_response(response('약을 먹지 말래'))['translation'],'약을 먹지 말래')
    def test_no_network_secret_or_paid_entrypoint(self):
        for file in [ROOT/'core.py',ROOT/'cli.py',ROOT.parent/'sonnet-sa1/adapter.py',ROOT.parent/'opus-ob1/adapter.py']:
            tree=ast.parse(file.read_text(encoding='utf-8'))
            names=[n.module.split('.')[0] for n in ast.walk(tree) if isinstance(n,ast.ImportFrom)]
            names += [a.name.split('.')[0] for n in ast.walk(tree) if isinstance(n,ast.Import) for a in n.names]
            self.assertFalse(set(names)&{'os','requests','httpx','urllib','socket','anthropic','subprocess'})
        with self.assertRaises(PermissionError):S.core.live({})
    def test_exact_file_input_and_no_empty_or_invalid_route(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'source.txt';p.write_bytes(b' A\r\n B ')
            self.assertEqual(S.core.read_exact(p),' A\r\n B ')
        for args in [('','K','first'),('x','Q','first'),('x','K','again')]:
            with self.assertRaises(ValueError):S.build_request(*args)

if __name__=='__main__':unittest.main()
