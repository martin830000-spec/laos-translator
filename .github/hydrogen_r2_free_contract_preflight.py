"""R2 OFFLINE contract guard for Gemini 3.8 Flash / 4 Hydrogen.
No network, no credentials, no user input, no generation calls.
This is QA reference code, NOT a paid production runner.
"""
from __future__ import annotations
import json
import unittest
from copy import deepcopy

MODEL = {'A': 'gemini-3.8-flash', 'B': 'gemini-4-hydrogen',
         'C': 'gemini-4-hydrogen', 'D': 'gemini-4-hydrogen'}
LEVEL = {'A': 'LOW', 'B': 'LOW', 'C': 'MEDIUM', 'D': 'LOW'}
THINK_ALLOWED = {'gemini-3.8-flash': frozenset({'LOW', 'MEDIUM', 'HIGH'}),
                 'gemini-4-hydrogen': frozenset({'LOW', 'MEDIUM', 'HIGH', 'XHIGH'})}
FORBIDDEN_GENERATION = frozenset({
    'candidateCount', 'thinkingBudget', 'temperature', 'topP', 'topK',
    'frequencyPenalty', 'presencePenalty'})
MAX_OUTPUT = 8192
PROJECT = '460077888071'
LOCATION = 'us'

class ContractError(ValueError):
    pass

def require(value, reason):
    if not value:
        raise ContractError(reason)

def target_for(arm, project=PROJECT, location=LOCATION):
    require(arm in MODEL, 'UNKNOWN_ARM')
    require(location in {'us', 'global', 'eu'}, 'UNSUPPORTED_REGION')
    require(project.isdigit() and project, 'BAD_PROJECT')
    base = 'https://aiplatform.%s.rep.googleapis.com/v1beta1/' % location
    return base + 'projects/%s/locations/%s/publishers/google/models/%s:generateContent' % (
        project, location, MODEL[arm])

def config_for(arm, max_output_tokens=MAX_OUTPUT):
    require(arm in MODEL, 'UNKNOWN_ARM')
    require(isinstance(max_output_tokens, int) and not isinstance(max_output_tokens,bool) and 1024 <= max_output_tokens <= 8192, 'UNBOUNDED_OUTPUT_CAP')
    level = LEVEL[arm]
    require(level in THINK_ALLOWED[MODEL[arm]], 'THINKING_LEVEL_UNSUPPORTED')
    return {'maxOutputTokens': max_output_tokens, 'thinkingConfig': {'thinkingLevel': level}}

def build_request(arm, first_input, prompt, project=PROJECT, location=LOCATION):
    require(isinstance(first_input, str) and first_input.strip(), 'EMPTY_INPUT')
    require(isinstance(prompt, str) and prompt.strip(), 'EMPTY_PROMPT')
    body = {'contents': [{'role':'user', 'parts':[{'text':first_input}]}],
            'systemInstruction': {'parts':[{'text':prompt}]},
            'generationConfig': config_for(arm)}
    uri = target_for(arm, project, location)
    validate_request(uri, body, arm, project, location)
    return uri, body

def validate_request(uri, body, arm, project=PROJECT, location=LOCATION):
    require(arm in MODEL, 'UNKNOWN_ARM')
    require(uri == target_for(arm, project, location), 'MODEL_RESOURCE_MISMATCH')
    require(isinstance(body, dict) and set(body) == {'contents','systemInstruction','generationConfig'}, 'ROOT_FIELDS_INVALID')
    cfg = body.get('generationConfig')
    require(isinstance(cfg, dict), 'GENERATION_CONFIG_MISSING')
    require(not (set(cfg) & FORBIDDEN_GENERATION), 'FORBIDDEN_GENERATION_FIELD')
    require(set(cfg) == {'maxOutputTokens','thinkingConfig'}, 'UNEXPECTED_GENERATION_FIELD')
    require(isinstance(cfg['maxOutputTokens'], int) and not isinstance(cfg['maxOutputTokens'],bool) and 1024 <= cfg['maxOutputTokens'] <= 8192, 'UNBOUNDED_OUTPUT_CAP')
    tc = cfg['thinkingConfig']
    require(isinstance(tc, dict) and set(tc) == {'thinkingLevel'}, 'THINKING_CONFIG_FIELDS_INVALID')
    require(tc['thinkingLevel'] in THINK_ALLOWED[MODEL[arm]], 'THINKING_LEVEL_UNSUPPORTED')
    require(tc['thinkingLevel'] == LEVEL[arm], 'FROZEN_ARM_THINKING_DRIFT')
    contents=body['contents']; si=body['systemInstruction']
    require(isinstance(contents, list) and len(contents)==1 and set(contents[0])=={'role','parts'} and contents[0]['role']=='user', 'CONTENTS_NOT_SINGLE_USER')
    parts=contents[0]['parts']
    require(isinstance(parts,list) and len(parts)==1 and isinstance(parts[0].get('text'),str) and set(parts[0])=={'text'} and parts[0]['text'].strip(), 'INVALID_USER_PART')
    require(isinstance(si,dict) and set(si)=={'parts'} and isinstance(si['parts'],list) and len(si['parts'])==1 and set(si['parts'][0])=={'text'} and isinstance(si['parts'][0]['text'],str) and si['parts'][0]['text'].strip(),'INVALID_SYSTEM_INSTRUCTION')
    return True

class Tests(unittest.TestCase):
    def test_arm_count(self): self.assertEqual(len(MODEL),4)
    def test_model_mapping(self): self.assertEqual([MODEL[x] for x in 'ABCD'],['gemini-3.8-flash']+['gemini-4-hydrogen']*3)
    def test_thinking(self): self.assertEqual([LEVEL[x] for x in 'ABCD'],['LOW','LOW','MEDIUM','LOW'])
    def test_nominal_request(self):
        for a in 'ABCD':
            u,b=build_request(a,'synthetic source','synthetic system');self.assertTrue(validate_request(u,b,a))
    def test_no_candidatecount(self):
        for a in 'ABCD': self.assertNotIn('candidateCount',config_for(a))
    def test_no_minimal(self):
        for a in 'ABCD': self.assertNotEqual(config_for(a)['thinkingConfig']['thinkingLevel'],'MINIMAL')
    def test_reject_minimal_all(self):
        for a in 'ABCD':
            u,b=build_request(a,'test','prompt');b['generationConfig']['thinkingConfig']['thinkingLevel']='MINIMAL'
            with self.assertRaises(ContractError): validate_request(u,b,a)
    def test_reject_candidatecount_all(self):
        for a in 'ABCD':
            u,b=build_request(a,'test','prompt');b['generationConfig']['candidateCount']=1
            with self.assertRaises(ContractError): validate_request(u,b,a)
    def test_reject_unsupported_sampling(self):
        for f in ['temperature','topP','topK','thinkingBudget','frequencyPenalty','presencePenalty']:
            u,b=build_request('A','test','prompt');b['generationConfig'][f]=1
            with self.assertRaises(ContractError): validate_request(u,b,'A')
    def test_reject_unsupported_model_version(self):
        u,b=build_request('A','test','prompt')
        with self.assertRaises(ContractError): validate_request(u.replace('gemini-3.8-flash','gemini-4-hydrogen'),b,'A')
    def test_reject_cross_arm_thinking(self):
        u,b=build_request('B','test','prompt');b['generationConfig']['thinkingConfig']['thinkingLevel']='MEDIUM'
        with self.assertRaises(ContractError): validate_request(u,b,'B')
    def test_reject_missing_thinking(self):
        u,b=build_request('B','test','prompt');b['generationConfig']['thinkingConfig']={}
        with self.assertRaises(ContractError): validate_request(u,b,'B')
    def test_reject_high_unexpected(self):
        u,b=build_request('C','test','prompt');b['generationConfig']['thinkingConfig']['thinkingLevel']='HIGH'
        with self.assertRaises(ContractError): validate_request(u,b,'C')
    def test_reject_output_over_cap(self):
        u,b=build_request('A','test','prompt');b['generationConfig']['maxOutputTokens']=65536
        with self.assertRaises(ContractError): validate_request(u,b,'A')
    def test_reject_source_context_leak(self):
        u,b=build_request('B','actual_first_only','back_prompt');b['contents'].append({'role':'user','parts':[{'text':'original_source'}]})
        with self.assertRaises(ContractError): validate_request(u,b,'B')
    def test_reject_unknown_arm(self):
        with self.assertRaises(ContractError): config_for('E')
    def test_reject_mutation_post_validation(self):
        u,b=build_request('D','test','prompt');b['generationConfig']['maxOutputTokens']='8192'
        with self.assertRaises(ContractError): validate_request(u,b,'D')
    def test_build_returns_copy(self):
        u,b=build_request('A','one','two');x=deepcopy(b);x['contents'][0]['parts'][0]['text']='three'
        self.assertTrue(validate_request(u,b,'A'))
    def test_region(self):
        self.assertIn('/locations/us/',target_for('A',location='us'))
        with self.assertRaises(ContractError): target_for('A',location='asia-northeast3')
    def test_no_network_or_secret_dependence(self):
        self.assertTrue(json.dumps(config_for('A')).startswith('{'))

if __name__=='__main__':
    s=unittest.defaultTestLoader.loadTestsFromTestCase(Tests)
    r=unittest.TextTestRunner(verbosity=1).run(s)
    print('OFFLINE_MODEL_CONTRACT_PASS' if r.wasSuccessful() else 'OFFLINE_MODEL_CONTRACT_FAIL')
    raise SystemExit(0 if r.wasSuccessful() else 1)
