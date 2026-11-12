"""Synthetic, offline safety tests. No real prompts, source messages, or network."""
import asyncio
import contextlib
import copy
import io
import json
import os
import time
import unittest
from unittest.mock import patch

import httpx
import contract
import http_sender
import runner
from contract import CAMPAIGN, MODEL, PHASES, canon, sha

def synthetic_design():
    sources=[]
    for split,ids,direction in [('DEVELOPMENT',['dev1','dev2'],'LF'),('FINAL',['final1','final2'],'LF'),('SAFETY',['safe1'],'KF')]:
        for sid in ids:
            value='Synthetic '+sid
            sources.append({'source_id':sid,'source':value,'sha256':sha(value.encode()),
                            'direction':direction,'split':split,'eligible':True})
    document={'campaign':CAMPAIGN,'sources':sources}
    plans={phase:{'campaign':CAMPAIGN,'phase':phase,'slots':[]} for phase in PHASES}
    def add(phase,sid,candidate,path,repeat=1,**extra):
        slot={'slot':f'{phase}-{len(plans[phase]["slots"])+1:03d}','source_id':sid,
              'candidate':candidate,'path':path,'repeat_index':repeat,**extra}
        plans[phase]['slots'].append(slot)
        return slot['slot']
    cs=['BASE','G','D']
    for sid in ['dev1','dev2']:
        for rep in (1,2,3):
            for c in cs[rep-1:]+cs[:rep-1]: add('A',sid,c,'LF',rep)
    for sid in ['dev1','dev2']:
        for c in cs:
            parents=[t['slot'] for t in plans['A']['slots'] if t['source_id']==sid and t['candidate']==c]
            add('B',sid,c,'LB',first_success_of=parents)
    for sid in ['final1','final2']:
        for c in cs:
            parent=add('C',sid,c,'LF'); add('C',sid,c,'LB',parent_first_id=parent)
    parent=add('D','safe1','BASE','KF'); add('D','safe1','BASE','KB',parent_first_id=parent)
    prompts={c:{path:'Synthetic instruction '+c+' '+path for path in ['LF','LB','KF','KB']} for c in cs}
    for c in ['G','D']:
        for path in ['LB','KF','KB']: prompts[c][path]=prompts['BASE'][path]
    freeze={'campaign':CAMPAIGN,'approved_total':80,'stage_caps':{'A':18,'B':6,'C':12,'D':2},
            'sources_sha256':sha(canon(document)),'prompts_sha256':sha(canon(prompts)),
            'plan_sha256_by_phase':{phase:sha(canon(plan)) for phase,plan in plans.items()}}
    return document,prompts,freeze,plans

class MemoryStore:
    def __init__(self): self.data={}; self.fail_after_create=None; self.break_budget_reads=False; self.break_after_fault=False
    def get(self,name,optional=False):
        if self.break_budget_reads and name.startswith('budget/'): raise RuntimeError('simulated unavailable')
        if name not in self.data:
            if optional: return None
            raise KeyError(name)
        return self.data[name]
    def create(self,name,data):
        if name in self.data: raise FileExistsError(name)
        self.data[name]=data
        if name==self.fail_after_create:
            self.fail_after_create=None
            if self.break_after_fault: self.break_budget_reads=True
            raise AssertionError('SIMULATED_READBACK_FAILURE_AFTER_CREATE')
    def put_same(self,name,data):
        if name in self.data:
            if self.data[name]!=data: raise AssertionError('IMMUTABLE_OBJECT_MISMATCH')
        else: self.create(name,data)

class DummyClient:
    async def __aenter__(self): return self
    async def __aexit__(self,*args): pass

def fixture():
    doc,prompts,freeze,plans=synthetic_design(); store=MemoryStore()
    owner='synthetic-owner'
    root={'campaign':CAMPAIGN,'owner_token':owner,'approved_total':80,'enabled':False,
          'max_new':0,'status':'PREFLIGHT_LOCKED','reserved_total':0}
    lock={'campaign':CAMPAIGN,'owner_token':owner,'approved_total':80,'enabled':False}
    preflight={'campaign':CAMPAIGN,'owner_token':owner,'generation_calls':0,
               'model_access':{'luna':{'allowed':True,'http_status':200}},
               'create_only_readback_verified':True,'duplicate_create_rejected':True}
    gate={'campaign':CAMPAIGN,'phase':'A','verified':True,'prior_reserved':0,
          'previous_phase':None,'previous_state_sha256':None,'drive_readback_verified':True,
          'owner_only':True,'sha256_verified':True,'zip_crc_verified':True,'manifest_verified':True}
    objects={'CONTROL.json':root,'LOCK.json':lock,'preflight/PREFLIGHT.json':preflight,
             'preparation/SOURCES.json':doc,'preparation/PROMPTS.json':prompts,
             'preparation/FREEZE.json':freeze,'gates/A.json':gate}
    for phase,plan in plans.items(): objects['plans/'+sha(canon(plan))+'.json']=plan
    for name,obj in objects.items(): store.data[name]=canon(obj)
    control={'campaign':CAMPAIGN,'approved_total':80,'mode':'EXECUTE','phase':'A','enabled':True,'max_new':18,
             'prior_reserved':0,'owner_token':owner,'deadline_epoch':time.time()+300,
             'plan_sha256':freeze['plan_sha256_by_phase']['A'],'source_sha256':sha(canon(doc)),
             'prompts_sha256':sha(canon(prompts)),'freeze_sha256':sha(canon(freeze)),
             'preflight_object':'preflight/PREFLIGHT.json','preflight_sha256':sha(canon(preflight)),
             'backup_verified':True,'backup_receipt_object':'gates/A.json','backup_receipt_sha256':sha(canon(gate)),
             'previous_phase':None}
    store.data['controls/A/STAGED_LOCKED.json']=canon({'campaign':CAMPAIGN,'owner_token':owner,'phase':'A',
        'status':'STAGED_LOCKED','enabled':False,'max_new':0,'reserved_total':0,'plan_sha256':control['plan_sha256']})
    return store,control

def good_result():
    return {'success':True,'display_text':'Synthetic output','partial_text':'Synthetic output',
            'actual_model':MODEL,'actual_service_tier':'default','response_id':'resp_synthetic',
            'usage':{'input_tokens':10,'output_tokens':3,'total_tokens':13},'http_attempts':1,
            'http_status':200,'terminal':'response.completed','events':[],'raw_chunks_base64':[]}

def run_fake(store,control,result_factory=good_result):
    calls=[]
    async def fake_sender(client,payload,key):
        calls.append(copy.deepcopy(payload)); return result_factory()
    env={'OPENAI_API_KEY':'synthetic-key-not-real','GITHUB_RUN_ID':'1','GITHUB_SHA':'synthetic-commit'}
    with patch.dict(os.environ,env),patch.object(runner,'validate_prompts',lambda _:None),contextlib.redirect_stdout(io.StringIO()):
        state=asyncio.run(runner.execute(store,control,sender=fake_sender,client_factory=DummyClient))
    return state,calls

class ContractTests(unittest.TestCase):
    def test_reduced_budget_and_complete_design(self):
        doc,_,freeze,plans=synthetic_design()
        _,caps=contract.validate_design(doc,freeze,plans)
        self.assertEqual(sum(caps.values()),38)
        records=[{'campaign':CAMPAIGN,'model':MODEL,'stage':'A','slot':f'A-{i:03d}'} for i in range(1,19)]
        with self.assertRaisesRegex(AssertionError,'STAGE_CAP_NO_REALLOCATION'):
            contract.budget_guard(records,'A-019','A',caps)
        self.assertEqual(contract.budget_guard(records,'B-001','B',caps)['ordinal'],19)

    def test_total_cap_and_duplicate(self):
        r=[{'campaign':CAMPAIGN,'model':MODEL,'stage':'A','slot':f's{i}'} for i in range(80)]
        with self.assertRaisesRegex(AssertionError,'CAMPAIGN_CAP'): contract.budget_guard(r,'new','B',contract.HARD_CAPS)
        with self.assertRaisesRegex(AssertionError,'DUPLICATE_SLOT'): contract.budget_guard(r[:1],'s0','B',contract.HARD_CAPS)

    def test_b_requires_all_repetitions_in_fixed_order(self):
        doc,_,freeze,plans=synthetic_design()
        plans['B']['slots'][0]['first_success_of']=plans['B']['slots'][0]['first_success_of'][1:]
        with self.assertRaisesRegex(AssertionError,'B_FIRST_SUCCESS_ORDER_OR_COVERAGE'):
            contract.validate_design(doc,freeze,plans)

    def test_final_cannot_use_development_source(self):
        doc,_,freeze,plans=synthetic_design()
        plans['C']['slots'][0]['source_id']=plans['C']['slots'][1]['source_id']='dev1'
        with self.assertRaisesRegex(AssertionError,'FINAL_OR_SAFETY_COVERAGE'):
            contract.validate_design(doc,freeze,plans)

    def test_chain_cannot_point_to_another_first(self):
        doc,_,freeze,plans=synthetic_design(); plans['C']['slots'][1]['parent_first_id']='C-003'
        with self.assertRaisesRegex(AssertionError,'CHAIN_PARENT_NOT_PREVIOUS_FIRST'):
            contract.validate_design(doc,freeze,plans)

    def test_a_order_must_cross(self):
        doc,_,freeze,plans=synthetic_design()
        for sid in ('dev1','dev2'):
            for rep in (1,2,3):
                selected=[t for t in plans['A']['slots'] if t['source_id']==sid and t['repeat_index']==rep]
                for t,candidate in zip(selected,('BASE','G','D')): t['candidate']=candidate
        with self.assertRaisesRegex(AssertionError,'A_ORDER_NOT_CROSSED'):
            contract.validate_design(doc,freeze,plans)

    def test_original_bytes_and_prompt_bytes_are_immutable(self):
        doc,_,freeze,plans=synthetic_design(); doc['sources'][0]['source']+=' '
        with self.assertRaisesRegex(AssertionError,'SOURCE_BYTE_SHA'):
            contract.validate_design(doc,freeze,plans)
        _,prompts,_,_=synthetic_design()
        with self.assertRaisesRegex(AssertionError,'LF_PROMPT_SHA'):
            contract.validate_prompts(prompts)

    def test_back_selection_is_technical_and_source_is_not_sent(self):
        task={'first_success_of':['A-001','A-002','A-003'],'source_id':'dev1','candidate':'BASE'}
        first=dict(good_result(),source_id='dev1',candidate='BASE',path='LF',stage='A',slot='A-001',quality='P0')
        later=dict(first,slot='A-002',quality='P2',display_text='Better output')
        picked=contract.choose_first_success(task,{'A-001':first,'A-002':later})
        self.assertIs(picked,first)
        payload=contract.build_payload(MODEL,'none','LB',contract.back_input(picked),{'LB':'Synthetic back instruction'})
        self.assertEqual(payload['input'],'Synthetic output')
        self.assertEqual(set(payload),{'model','reasoning','instructions','input','stream','store','max_output_tokens','service_tier'})
        self.assertNotIn('dev1',json.dumps(payload))
        self.assertIsNone(contract.back_input(dict(first,success=False)))
        self.assertIsNone(contract.back_input(dict(first,unknown=True)))

    def test_success_metadata_mismatch_stops(self):
        for key,value in [('actual_model','other-model'),('actual_service_tier','priority'),('response_id',None),('usage',None)]:
            result=good_result(); result[key]=value
            result=contract.validate_result_metadata(result)
            self.assertFalse(result['success']); self.assertIsNone(result['display_text'])
            self.assertEqual(result['partial_text'],'Synthetic output')

class RunnerTests(unittest.TestCase):
    def test_phase_success_has_exact_count_and_checkpoint_lock(self):
        store,control=fixture(); state,calls=run_fake(store,control)
        self.assertEqual(len(calls),18); self.assertEqual(state['reserved_total'],18)
        self.assertEqual(state['status'],'CHECKPOINT_LOCKED'); self.assertFalse(state['enabled'])
        self.assertEqual(state['max_new'],0); self.assertIn('locks/A.RELEASED.json',store.data)
        self.assertEqual(len([k for k in store.data if k.startswith('requests/')]),18)

    def test_committed_reservation_readback_failure_is_unknown_not_zero(self):
        store,control=fixture(); store.fail_after_create='budget/0001.json'
        state,calls=run_fake(store,control)
        self.assertEqual(calls,[]); self.assertEqual(state['attempted_this_run'],0)
        self.assertEqual(state['reserved_total'],1); self.assertEqual(state['unknown'],1)
        self.assertEqual(state['unused_locked'],79); self.assertEqual(state['status'],'PAUSED_LOCKED')
        self.assertIn('states/PAUSED_LOCKED.json',store.data)

    def test_committed_phase_lease_readback_failure_pauses_with_zero_calls(self):
        store,control=fixture(); store.fail_after_create='locks/A.json'
        with self.assertRaisesRegex(AssertionError,'SIMULATED_READBACK_FAILURE_AFTER_CREATE'):
            run_fake(store,control)
        state=json.loads(store.data['states/PAUSED_LOCKED.json'])
        self.assertEqual(state['attempted_this_run'],0); self.assertEqual(state['reserved_total'],0)
        self.assertFalse(any(k.startswith('budget/') for k in store.data))

    def test_response_saved_but_readback_failure_pauses_with_true_count(self):
        store,control=fixture(); store.fail_after_create='results/A-001.json'
        state,calls=run_fake(store,control)
        self.assertEqual(len(calls),1); self.assertEqual(state['reserved_total'],1)
        self.assertEqual(state['success'],1); self.assertEqual(state['unknown'],0)
        self.assertEqual(state['status'],'PAUSED_LOCKED')

    def test_unreadable_ledger_is_unresolved_and_cannot_close(self):
        store,control=fixture(); store.fail_after_create='budget/0001.json'; store.break_after_fault=True
        state,calls=run_fake(store,control)
        self.assertEqual(calls,[]); self.assertFalse(state['ledger_resolved'])
        self.assertIsNone(state['reserved_total']); self.assertEqual(state['status'],'PAUSED_LOCKED')
        self.assertNotIn('states/CLOSED_LOCKED.json',store.data)

    def test_one_http_failure_stops_without_retry_or_next_slot(self):
        store,control=fixture()
        def failure(): return {'success':False,'display_text':None,'partial_text':'','http_status':429,
                              'http_attempts':1,'terminal':None,'response_id':None,'usage':None}
        state,calls=run_fake(store,control,failure)
        self.assertEqual(len(calls),1); self.assertEqual(state['reserved_total'],1)
        self.assertEqual(state['failed'],1); self.assertEqual(state['status'],'PAUSED_LOCKED')

    def test_terminal_lock_blocks_all_new_generation(self):
        store,control=fixture(); store.data['states/PAUSED_LOCKED.json']=canon({'campaign':CAMPAIGN})
        with self.assertRaisesRegex(AssertionError,'TERMINAL_CAMPAIGN_LOCK'): run_fake(store,control)
        self.assertFalse(any(k.startswith('budget/') for k in store.data))

    def test_unverified_backup_stops_before_lease_and_generation(self):
        store,control=fixture(); gate=json.loads(store.data['gates/A.json']); gate['owner_only']=False
        store.data['gates/A.json']=canon(gate); control['backup_receipt_sha256']=sha(canon(gate))
        with self.assertRaisesRegex(AssertionError,'BACKUP_PROOF_INCOMPLETE'): run_fake(store,control)
        self.assertNotIn('locks/A.json',store.data)

class SenderTests(unittest.TestCase):
    def test_real_sender_has_one_post_on_429(self):
        requests=[]
        def handler(request):
            requests.append(request)
            return httpx.Response(429,json={'error':{'code':'rate_limit_exceeded','message':'Synthetic'}})
        async def run():
            async with http_sender.make_client(httpx.MockTransport(handler)) as client:
                return await http_sender.send(client,{'synthetic':True},'synthetic-key-not-real')
        result=asyncio.run(run())
        self.assertEqual(len(requests),1); self.assertEqual(requests[0].method,'POST')
        self.assertEqual(result['http_attempts'],1); self.assertEqual(result['http_status'],429)
        self.assertFalse(result['success'])

    def test_sse_done_mismatch_is_not_success(self):
        events=[{'type':'response.output_text.delta','delta':'one'},
                {'type':'response.completed','response':{'status':'completed','output':[{'content':[{'type':'output_text','text':'two'}]}]}}]
        result=contract.parse_events(events)
        self.assertFalse(result['success']); self.assertTrue(result['mismatch'])

if __name__=='__main__': unittest.main(verbosity=2)
