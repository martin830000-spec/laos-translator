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

def make_plans(document):
    plans={phase:{'campaign':CAMPAIGN,'phase':phase,'slots':[]} for phase in PHASES}
    def add(phase,sid,candidate,path,**extra):
        slot={'slot':f'{phase}-{len(plans[phase]["slots"])+1:03d}','source_id':sid,
              'candidate':candidate,'path':path,'repeat_index':1,**extra}
        plans[phase]['slots'].append(slot)
        return slot['slot']
    for i,sid in enumerate(document['selection']['dev_order']):
        for c in contract.cyclic_candidates(i): add('A',sid,c,'LF')
    for first in plans['A']['slots']:
        add('B',first['source_id'],first['candidate'],'LB',first_success_of=[first['slot']])
    for i,sid in enumerate(document['selection']['final_order']):
        for c in contract.cyclic_candidates(i):
            parent=add('C',sid,c,'LF'); add('C',sid,c,'LB',parent_first_id=parent)
    return plans


def synthetic_design(full=False):
    dev=list(contract.DEV_ORDER[:6 if full else 4])
    final=list(contract.FINAL_PRIMARY_ORDER[:4 if full else 2])
    all_ids=contract.DEV_ORDER+contract.FINAL_PRIMARY_ORDER+contract.FINAL_RESERVE_ORDER
    selected=set(dev+final)
    sources=[]
    for sid in all_ids:
        value='Synthetic '+sid
        sources.append({'source_id':sid,'source':value,'sha256':sha(value.encode()),
                        'direction':'LF','split':'DEVELOPMENT' if sid in contract.DEV_ORDER else 'FINAL',
                        'eligible':sid in selected,'event_key':'synthetic-event-'+sid})
    rejected={sid:{'reason':'Synthetic prior exposure','evidence_sha256':'1'*64}
              for sid in all_ids if sid not in selected}
    document={'campaign':CAMPAIGN,'sources':sources,
              'selection':{'dev_order':dev,'final_order':final,'rejected':rejected}}
    plans=make_plans(document)
    prompts={c:{path:'Synthetic instruction '+c+' '+path for path in ['LF','LB']} for c in contract.CANDIDATES}
    for c in contract.CANDIDATES: prompts[c]['LB']=prompts['BASE']['LB']
    freeze={'campaign':CAMPAIGN,'approved_total':80,
            'order_rule':'Selected source order; cyclic BASE/M1/G/D; B same A order; C immediate LF/LB.',
            'stage_caps':{'A':len(dev)*4,'B':len(dev)*4,'C':len(final)*8},
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
    control={'campaign':CAMPAIGN,'approved_total':80,'mode':'EXECUTE','phase':'A','enabled':True,'max_new':16,
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
        self.assertEqual(caps,{'A':16,'B':16,'C':16}); self.assertEqual(sum(caps.values()),48)
        records=[{'campaign':CAMPAIGN,'model':MODEL,'stage':'A','slot':f'A-{i:03d}'} for i in range(1,17)]
        with self.assertRaisesRegex(AssertionError,'STAGE_CAP_NO_REALLOCATION'):
            contract.budget_guard(records,'A-017','A',caps)
        self.assertEqual(contract.budget_guard(records,'B-001','B',caps)['ordinal'],17)

    def test_full_design_exact_80_and_no_safety_calls(self):
        doc,_,freeze,plans=synthetic_design(full=True)
        _,caps=contract.validate_design(doc,freeze,plans)
        self.assertEqual(caps,{'A':24,'B':24,'C':32}); self.assertEqual(sum(caps.values()),80)
        self.assertEqual(set(plans),{'A','B','C'})
        self.assertEqual({t['path'] for p in plans.values() for t in p['slots']},{'LF','LB'})

    def test_total_cap_duplicate_and_foreign_reservation(self):
        r=[{'campaign':CAMPAIGN,'model':MODEL,'stage':'A','slot':f's{i}'} for i in range(80)]
        with self.assertRaisesRegex(AssertionError,'CAMPAIGN_CAP'): contract.budget_guard(r,'new','B',contract.HARD_CAPS)
        with self.assertRaisesRegex(AssertionError,'DUPLICATE_SLOT'): contract.budget_guard(r[:1],'s0','B',contract.HARD_CAPS)
        r[0]['campaign']='GPT_LUNA_GD_REALCHAT80_20261112'
        with self.assertRaisesRegex(AssertionError,'FOREIGN_RESERVATION'): contract.budget_guard(r[:1],'new','B',contract.HARD_CAPS)

    def test_b_requires_single_exact_first_in_a_order(self):
        for parents in ([],['A-002'],['A-001','A-002']):
            with self.subTest(parents=parents):
                doc,_,freeze,plans=synthetic_design(); plans['B']['slots'][0]['first_success_of']=parents
                with self.assertRaisesRegex(AssertionError,'B_SINGLE_PARENT_EXACT_A'): contract.validate_design(doc,freeze,plans)
        doc,_,freeze,plans=synthetic_design(); plans['B']['slots'][0]['candidate']='M1'
        with self.assertRaisesRegex(AssertionError,'B_ONE_BACK_A_ORDER'): contract.validate_design(doc,freeze,plans)

    def test_final_cannot_use_development_source(self):
        doc,_,freeze,plans=synthetic_design()
        plans['C']['slots'][0]['source_id']=plans['C']['slots'][1]['source_id']=contract.DEV_ORDER[0]
        with self.assertRaisesRegex(AssertionError,'C_FINAL_CYCLIC_ORDER'): contract.validate_design(doc,freeze,plans)

    def test_chain_cannot_point_to_another_first(self):
        doc,_,freeze,plans=synthetic_design(); plans['C']['slots'][1]['parent_first_id']='C-003'
        with self.assertRaisesRegex(AssertionError,'CHAIN_PARENT_NOT_PREVIOUS_FIRST'): contract.validate_design(doc,freeze,plans)

    def test_a_cyclic_order_and_single_attempt(self):
        doc,_,freeze,plans=synthetic_design()
        for task,candidate in zip(plans['A']['slots'][4:8],contract.CANDIDATES): task['candidate']=candidate
        with self.assertRaisesRegex(AssertionError,'A_SINGLE_FIRST_CYCLIC_ORDER'): contract.validate_design(doc,freeze,plans)
        doc,_,freeze,plans=synthetic_design(); plans['A']['slots'][0]['repeat_index']=2
        with self.assertRaisesRegex(AssertionError,'SINGLE_ATTEMPT_PER_CONDITION'): contract.validate_design(doc,freeze,plans)

    def test_source_minimum_and_event_independence(self):
        doc,_,freeze,plans=synthetic_design(); sid=contract.DEV_ORDER[3]
        doc['sources'][3]['eligible']=False; doc['selection']['dev_order'].remove(sid)
        doc['selection']['rejected'][sid]={'reason':'Synthetic overlap','evidence_sha256':'2'*64}
        with self.assertRaisesRegex(AssertionError,'INDEPENDENT_SAMPLE_MINIMUM'): contract.validate_design(doc,freeze,plans)
        doc,_,freeze,plans=synthetic_design(); doc['sources'][1]['event_key']=doc['sources'][0]['event_key']
        with self.assertRaisesRegex(AssertionError,'DUPLICATE_SELECTED_EVENT'): contract.validate_design(doc,freeze,plans)

    def test_reserve_replaces_rejected_primary_in_position(self):
        doc,_,freeze,_=synthetic_design(full=True); by={s['source_id']:s for s in doc['sources']}
        primary=contract.FINAL_PRIMARY_ORDER[1]; reserve=contract.FINAL_RESERVE_ORDER[0]
        by[primary]['eligible']=False; by[reserve]['eligible']=True
        doc['selection']['rejected'][primary]={'reason':'Preflight event overlap','evidence_sha256':'2'*64}
        del doc['selection']['rejected'][reserve]
        doc['selection']['final_order'][1]=reserve
        plans=make_plans(doc); contract.validate_design(doc,freeze,plans)
        doc['selection']['final_order'].remove(reserve); doc['selection']['final_order'].append(reserve)
        with self.assertRaisesRegex(AssertionError,'SELECTED_SOURCE_ORDER'): contract.validate_design(doc,freeze,plans)

    def test_reserve_skip_requires_evidence(self):
        doc,_,freeze,_=synthetic_design(full=True); by={s['source_id']:s for s in doc['sources']}
        primary=contract.FINAL_PRIMARY_ORDER[0]; earlier,later=contract.FINAL_RESERVE_ORDER[:2]
        by[primary]['eligible']=False; by[later]['eligible']=True
        doc['selection']['rejected'][primary]={'reason':'Synthetic overlap','evidence_sha256':'2'*64}
        del doc['selection']['rejected'][earlier]; del doc['selection']['rejected'][later]
        doc['selection']['final_order'][0]=later
        with self.assertRaisesRegex(AssertionError,'RESERVE_SKIP_UNDOCUMENTED'): contract.validate_design(doc,freeze,make_plans(doc))

    def test_rejection_proof_and_declared_order_required(self):
        doc,_,freeze,plans=synthetic_design(); del doc['selection']['rejected'][contract.DEV_ORDER[-1]]
        with self.assertRaisesRegex(AssertionError,'DEVELOPMENT_EXCLUSION_UNDOCUMENTED'): contract.validate_design(doc,freeze,plans)
        doc,_,freeze,plans=synthetic_design(); doc['selection']['rejected'][contract.DEV_ORDER[-1]]['evidence_sha256']='not-a-sha'
        with self.assertRaisesRegex(AssertionError,'REJECTION_EVIDENCE_MISSING'): contract.validate_design(doc,freeze,plans)
        doc,_,freeze,plans=synthetic_design(); doc['sources'][0],doc['sources'][1]=doc['sources'][1],doc['sources'][0]
        with self.assertRaisesRegex(AssertionError,'DECLARED_SOURCE_SET_OR_ORDER'): contract.validate_design(doc,freeze,plans)

    def test_original_and_prompt_bytes_immutable(self):
        doc,_,freeze,plans=synthetic_design(); doc['sources'][0]['source']+=' '
        with self.assertRaisesRegex(AssertionError,'SOURCE_BYTE_SHA'): contract.validate_design(doc,freeze,plans)
        _,prompts,_,_=synthetic_design()
        with self.assertRaisesRegex(AssertionError,'LF_PROMPT_SHA'): contract.validate_prompts(prompts)
        expected={c:sha(prompts[c]['LF'].encode()) for c in contract.CANDIDATES}
        with patch.object(contract,'EXPECTED_LF',expected),patch.object(contract,'EXPECTED_BASE_OTHER',{'LB':sha(prompts['BASE']['LB'].encode())}):
            contract.validate_prompts(prompts); prompts['M1']['LB']+=' changed'
            with self.assertRaisesRegex(AssertionError,'NON_LF_CANDIDATE_CHANGE'): contract.validate_prompts(prompts)

    def test_back_single_technical_success_only(self):
        task={'first_success_of':['A-001'],'source_id':contract.DEV_ORDER[0],'candidate':'M1'}
        first=dict(good_result(),source_id=contract.DEV_ORDER[0],candidate='M1',path='LF',stage='A',slot='A-001',quality='P0')
        picked=contract.choose_first_success(task,{'A-001':first}); self.assertIs(picked,first)
        payload=contract.build_payload(MODEL,'none','LB',contract.back_input(picked),{'LB':'Synthetic back instruction'})
        self.assertEqual(payload['input'],'Synthetic output')
        self.assertEqual(set(payload),{'model','reasoning','instructions','input','stream','store','max_output_tokens','service_tier'})
        self.assertNotIn(contract.DEV_ORDER[0],json.dumps(payload))
        self.assertIsNone(contract.choose_first_success(task,{'A-001':dict(first,success=False)}))
        self.assertIsNone(contract.choose_first_success(task,{'A-001':dict(first,unknown=True)}))
        with self.assertRaisesRegex(AssertionError,'B_PARENT_IDENTITY'): contract.choose_first_success(task,{'A-001':dict(first,candidate='BASE')})
        with self.assertRaisesRegex(AssertionError,'B_SINGLE_PARENT_REQUIRED'): contract.choose_first_success(dict(task,first_success_of=['A-001','A-002']),{'A-001':first})

    def test_kf_kb_and_old_phase_not_authorized(self):
        for path in ('KF','KB'):
            with self.assertRaisesRegex(AssertionError,'INVALID_REQUEST_TEXT'): contract.build_payload(MODEL,'none',path,'Synthetic',{path:'Synthetic'})
        with self.assertRaisesRegex(AssertionError,'UNAPPROVED_PHASE'): contract.budget_guard([],'D-001','D',contract.HARD_CAPS)

    def test_success_metadata_mismatch_stops(self):
        for key,value in [('actual_model','other-model'),('actual_service_tier','priority'),('response_id',None),('usage',None)]:
            result=good_result(); result[key]=value; result=contract.validate_result_metadata(result)
            self.assertFalse(result['success']); self.assertIsNone(result['display_text'])
            self.assertEqual(result['partial_text'],'Synthetic output')

class RunnerTests(unittest.TestCase):
    def test_abc_back_dependencies_and_close_after_verified_c(self):
        store,control=fixture(); all_calls=[]; output_number=0
        def distinct_result():
            nonlocal output_number
            output_number+=1
            result=good_result()
            result.update(display_text=f'Synthetic output {output_number}',
                          partial_text=f'Synthetic output {output_number}',
                          response_id=f'resp_synthetic_{output_number}')
            return result
        for index,phase in enumerate(PHASES):
            if index:
                previous=PHASES[index-1]
                prior_raw=store.data['states/'+previous+'-finished.json']
                prior=json.loads(prior_raw)
                gate={'campaign':CAMPAIGN,'phase':phase,'verified':True,
                      'prior_reserved':prior['reserved_total'],'previous_phase':previous,
                      'previous_state_sha256':sha(prior_raw),'drive_readback_verified':True,
                      'owner_only':True,'sha256_verified':True,'zip_crc_verified':True,'manifest_verified':True}
                store.data['gates/'+phase+'.json']=canon(gate)
                freeze=json.loads(store.data['preparation/FREEZE.json'])
                control.update(phase=phase,prior_reserved=prior['reserved_total'],previous_phase=previous,
                               max_new=freeze['stage_caps'][phase],plan_sha256=freeze['plan_sha256_by_phase'][phase],
                               backup_receipt_object='gates/'+phase+'.json',backup_receipt_sha256=sha(canon(gate)))
                store.data['controls/'+phase+'/STAGED_LOCKED.json']=canon({'campaign':CAMPAIGN,
                    'owner_token':control['owner_token'],'phase':phase,'status':'STAGED_LOCKED',
                    'enabled':False,'max_new':0,'reserved_total':prior['reserved_total'],
                    'plan_sha256':control['plan_sha256']})
            state,calls=run_fake(store,control,distinct_result); all_calls.extend(calls)
            self.assertEqual(state['status'],'CHECKPOINT_LOCKED')
            self.assertEqual(state['reserved_total'],(index+1)*16)
        prompts=json.loads(store.data['preparation/PROMPTS.json'])
        results={json.loads(raw)['slot']:json.loads(raw) for name,raw in store.data.items() if name.startswith('results/')}
        self.assertEqual(len(all_calls),48)
        for result in results.values():
            if result['path']=='LB':
                parent=results[result['parent_first_id']]
                self.assertEqual(result['request']['input'],parent['display_text'])
                self.assertEqual(result['request']['instructions'],prompts['BASE']['LB'])
                self.assertEqual(result['prompt_candidate'],'BASE')
                self.assertNotIn(result['source_id'],json.dumps(result['request']))
                self.assertEqual(parent['stage'],'A' if result['stage']=='B' else 'C')
        prior_raw=store.data['states/C-finished.json']
        gate={'campaign':CAMPAIGN,'phase':'CLOSE','verified':True,'prior_reserved':48,
              'previous_phase':'C','previous_state_sha256':sha(prior_raw),'drive_readback_verified':True,
              'owner_only':True,'sha256_verified':True,'zip_crc_verified':True,'manifest_verified':True}
        control.update(mode='CLOSE',phase='CLOSE',enabled=False,max_new=0,prior_reserved=48,
                       previous_phase='C',backup_receipt_object='gates/CLOSE.json',
                       backup_receipt_sha256=sha(canon(gate)))
        with patch.object(runner,'unpack_package',lambda *_:{'gates/CLOSE.json':canon(gate)}),\
             patch.object(runner,'validate_prompts',lambda _:None),\
             patch.dict(os.environ,{'GITHUB_RUN_ID':'1','GITHUB_SHA':'synthetic-commit'}),\
             contextlib.redirect_stdout(io.StringIO()):
            runner.ingest_close(store,control)
            closed=runner.close(store,control)
        self.assertEqual(closed['reserved_total'],48); self.assertEqual(closed['unused_locked'],32)
        self.assertEqual(closed['status'],'CLOSED_LOCKED'); self.assertFalse(closed['enabled'])
        self.assertEqual(closed['max_new'],0)
        self.assertEqual(store.data['states/CLOSED_LOCKED.json'],store.data['controls/CLOSED/CLOSED_LOCKED.json'])
        with self.assertRaisesRegex(AssertionError,'TERMINAL_CAMPAIGN_LOCK'):
            runner.require_no_terminal(store)

    def test_phase_success_has_exact_count_and_checkpoint_lock(self):
        store,control=fixture(); state,calls=run_fake(store,control)
        self.assertEqual(len(calls),16); self.assertEqual(state['reserved_total'],16)
        self.assertEqual(state['status'],'CHECKPOINT_LOCKED'); self.assertFalse(state['enabled'])
        self.assertEqual(state['max_new'],0); self.assertIn('locks/A.RELEASED.json',store.data)
        self.assertEqual(len([k for k in store.data if k.startswith('requests/')]),16)

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
