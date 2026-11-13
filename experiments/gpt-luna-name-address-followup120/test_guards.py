"""Offline FOLLOWUP120 boundary tests. Synthetic text, memory store, mock HTTP only."""
import asyncio
import base64
import copy
import json
import os
import pathlib
import tempfile
import time
import unittest
from unittest import mock

import contract as c
import runner as r
import final_controls_check as check
import http_sender


PROMPTS = {n: {'KF': 'Synthetic forward '+n, 'KB': 'Synthetic common back'} for n in ('N0','N1','N2')}
PROMPTS.update({n: {'LF': 'Synthetic historical forward', 'LB': 'Synthetic controlled back '+n} for n in ('L0','L1')})


def good_result(text='Synthetic response', response_id='resp-synthetic', request_id='req-synthetic'):
    usage={'input_tokens':3,'output_tokens':5,'total_tokens':8,
           'input_tokens_details':{'cached_tokens':0},'output_tokens_details':{'reasoning_tokens':0}}
    response={'id':response_id,'model':c.MODEL,'service_tier':'default','reasoning':{'effort':'none'},'status':'completed',
              'usage':usage,'output':[{'type':'message','content':[{'type':'output_text','text':text}]}]}
    events=[{'type':'response.output_text.delta','delta':text},
            {'type':'response.output_text.done','text':text},
            {'type':'response.completed','response':response}]
    wire=''.join('data: '+json.dumps(event)+'\n\n' for event in events).encode()
    return {'success':True,'unknown':False,'http_status':200,'http_attempts':1,
            'request_id':request_id,'response_id':response_id,'actual_model':c.MODEL,
            'actual_service_tier':'default','terminal':'response.completed','usage':usage,
            'response':response,'display_text':text,'partial_text':text,
            'events':[{'elapsed':.1+i*.1,'raw_data':json.dumps(event),'event':event} for i,event in enumerate(events)],
            'raw_chunks_base64':[{'elapsed':.3,'bytes_b64':base64.b64encode(wire).decode()}],
            't_first_text':.1,'t_first_displayable_text':.1,'t_text_done':.2,
            't_response_done':.3,'t_display_extract_done':.4}


def fixture(ns=12,nf=8,nl=8):
    document={'campaign':c.CAMPAIGN,'sources':[],
              'selection':{'discovery_order':[],'final_order':[]},
              'fixed_lf_inputs':[],'fixed_lf_order':[],
              'sample_shortage_reason':'Synthetic fixture uses frozen effective sample sizes.',
              'fixed_lf_shortage_reason':'Synthetic fixture uses frozen historical input count.'}
    for i in range(ns+nf):
        sid='K'+str(i+1); final=i>=ns; text='Synthetic Korean-source fixture '+str(i+1)
        document['sources'].append({'source_id':sid,'source':text,'sha256':c.sha(text.encode()),
            'direction':'KF','split':'FINAL' if final else 'DISCOVERY','raw_record_number':i+1,
            'class':'synthetic','duplicate_group':'dup'+sid,'event_cluster':'event'+sid,
            'prior_exposure':False,'final_independence_verified':final,'selection_reason':'Synthetic offline guard fixture.'})
        document['selection']['final_order' if final else 'discovery_order'].append(sid)
    historical={}
    for i in range(nl):
        slot=f'D-{i+1:03d}'; iid='OLD_'+str(i+1); text='Synthetic fixed LF output '+str(i+1)
        payload={'model':c.MODEL,'reasoning':{'effort':'none'},'instructions':PROMPTS['L0']['LF'],
                 'input':'Synthetic old original '+str(i+1),'stream':True,'store':False,'max_output_tokens':4096,'service_tier':'default'}
        result=good_result(text,'resp-historical-'+str(i+1),'req-historical-'+str(i+1))
        result.update(campaign=c.OLD_AB160,model=c.MODEL,slot=slot,stage='D',source_id='OLD_SOURCE_'+str(i+1),
            candidate='TONE_NAME',path='LF',raw_record_number=100+i,source_direction='LF',
            source_sha256=c.sha(payload['input'].encode()),input_sha256=c.sha(payload['input'].encode()),
            request=payload,request_sha256=c.sha(c.canon(payload)),send_invoked=True)
        raw=c.canon(result); name='preparation/fixed_lf_results/'+slot+'.json'; historical[name]=raw
        document['fixed_lf_inputs'].append({'input_id':iid,'display_text':text,'sha256':c.sha(text.encode()),
            'origin_campaign':c.OLD_AB160,'origin_slot':slot,'origin_result_sha256':c.sha(raw),
            'origin_response_id':result['response_id'],'origin_request_id':result['request_id'],
            'origin_source_id':result['source_id'],'origin_source_sha256':result['source_sha256'],
            'origin_candidate':'TONE_NAME','origin_path':'LF','origin_result_object':name})
        document['fixed_lf_order'].append(iid)
    plans={p:{'campaign':c.CAMPAIGN,'phase':p,'slots':[]} for p in c.PHASES}
    def chain(phase,sid,candidate):
        first=f'{phase}-{len(plans[phase]["slots"])+1:03d}'
        plans[phase]['slots'].append({'slot':first,'source_id':sid,'candidate':candidate,'path':'KF','repeat_index':1})
        plans[phase]['slots'].append({'slot':f'{phase}-{len(plans[phase]["slots"])+1:03d}',
            'source_id':sid,'candidate':candidate,'path':'KB','repeat_index':1,'parent_first_id':first})
    for i,sid in enumerate(document['selection']['discovery_order']):
        for candidate in c.cyclic_candidates(i):chain('S',sid,candidate)
    for i,iid in enumerate(document['fixed_lf_order']):
        for candidate in (('L0','L1') if i%2==0 else ('L1','L0')):
            plans['L']['slots'].append({'slot':f'L-{len(plans["L"]["slots"])+1:03d}',
                'input_id':iid,'candidate':candidate,'path':'LB','repeat_index':1})
    freeze={'campaign':c.CAMPAIGN,'approved_total':120,'stage_caps':dict(c.HARD_CAPS),
            'order_rule':'Synthetic sources in fixed order; cyclic N0/N1/N2; alternating pairs.',
            'sources_sha256':c.sha(c.canon(document)),'prompts_sha256':c.sha(c.canon(PROMPTS)),
            'plan_sha256_by_phase':{p:c.sha(c.canon(plan)) for p,plan in plans.items()},
            'metadata_sha256_by_object':{name:c.sha(raw) for name,raw in historical.items()},
            'additional_export_objects':list(historical)}
    return document,freeze,plans,historical


def final_plan(document,selected='N1',evidence_sha='a'*64):
    plan={'campaign':c.CAMPAIGN,'phase':'F','slots':[],
          'selected_candidate':selected,'selection_evidence_sha256':evidence_sha}
    if selected is not None:
        for i,sid in enumerate(document['selection']['final_order']):
            for candidate in (('N0',selected) if i%2==0 else (selected,'N0')):
                first=f'F-{len(plan["slots"])+1:03d}'
                plan['slots'].append({'slot':first,'source_id':sid,'candidate':candidate,'path':'KF','repeat_index':1})
                plan['slots'].append({'slot':f'F-{len(plan["slots"])+1:03d}','source_id':sid,'candidate':candidate,
                    'path':'KB','repeat_index':1,'parent_first_id':first})
    if not plan['slots']:plan['omitted_reason']='NO_CONFIRMED_IMPROVEMENT' if selected is None else 'NO_ELIGIBLE_FINAL'
    return plan


class MemoryStore:
    class PreconditionFailed(Exception):pass
    def __init__(self):self.data={};self.fail_after_write=None
    def get(self,name,optional=False):
        if name not in self.data and not optional:raise KeyError(name)
        return self.data.get(name)
    def create(self,name,data):
        if name in self.data:raise self.PreconditionFailed(name)
        self.data[name]=data
        if name==self.fail_after_write:
            self.fail_after_write=None;raise OSError('synthetic readback failure after commit')
    def put_same(self,name,data):
        if name in self.data:c.require(self.data[name]==data,'IMMUTABLE_OBJECT_MISMATCH')
        else:self.create(name,data)


class DummyClient:
    async def __aenter__(self):return self
    async def __aexit__(self,*args):pass


class Guards(unittest.TestCase):
    def setUp(self):
        self.real_prompt_shas=copy.deepcopy(c.EXPECTED_PROMPT_SHA256)
        test_shas={k:{p:c.sha(t.encode()) for p,t in paths.items()} for k,paths in PROMPTS.items()}
        self.enterContext(mock.patch.object(c,'EXPECTED_PROMPT_SHA256',test_shas))
        self.enterContext(mock.patch.object(r,'metadata_log'))
        self.enterContext(mock.patch.dict(os.environ,{'OPENAI_API_KEY':'synthetic-key-not-a-secret','GITHUB_RUN_ID':'offline-run',
            'GITHUB_SHA':'c'*40,'GITHUB_REF':'refs/heads/research/gemini-model-native500-20261107',
            'GITHUB_RUN_ATTEMPT':'1','GITHUB_ACTOR':'martin830000-spec'}))
        self.calls=[]

    async def sender(self,client,payload,key):
        self.calls.append(copy.deepcopy(payload));i=len(self.calls)
        return good_result('Synthetic new output '+str(i),'resp-new-'+str(i),'req-new-'+str(i))

    def initialize(self,ns=12,nf=8,nl=8):
        self.document,self.freeze,self.plans,historical=fixture(ns,nf,nl)
        self.store=MemoryStore();self.old={};previous={};recent=[];old_closed={};receipt_keys={}
        for name,(count,_) in check.PREVIOUS.items():
            state={'status':'CLOSED_LOCKED','enabled':False,'max_new':0,'reserved_total':count}
            raw=c.canon(state);digest=c.sha(raw);previous[name]=(count,digest);old_closed[name]={'sha256':digest}
            self.old[check.ROOT+name+'/states/CLOSED_LOCKED.json']=raw
            if 'mechanism1000' not in name:self.old[check.ROOT+name+'/controls/CLOSED/CLOSED_LOCKED.json']=raw
        for name,campaign,status,count,unused,key,_ in check.RECENT:
            state={'campaign':campaign,'status':status+'_LOCKED','enabled':False,'max_new':0,'reserved_total':count,'unused_locked':unused}
            raw=c.canon(state);digest=c.sha(raw);recent.append((name,campaign,status,count,unused,key,digest));receipt_keys[key]=digest
            if name=='gpt-luna-couple-tone-name-ab160-20261113':old_closed[name]={'sha256':digest,'reserved_total':160}
            self.old[check.ROOT+name+'/states/'+status+'_LOCKED.json']=raw
            self.old[check.ROOT+name+'/controls/'+status+'/'+status+'_LOCKED.json']=raw
        self.enterContext(mock.patch.object(check,'PREVIOUS',previous));self.enterContext(mock.patch.object(check,'RECENT',tuple(recent)))
        self.enterContext(mock.patch.object(r,'OLD_AB160_CLOSED_SHA256',receipt_keys['old_ab160_sha256']))
        self.preflight={'campaign':c.CAMPAIGN,'owner_token':'offline-owner','generation_calls':0,
            'model_access':{'luna':{'allowed':True,'http_status':200}},'create_only_readback_verified':True,
            'duplicate_create_rejected':True,'old_closed':old_closed,'old_ab160_actual':160,'old_ab160_unused_locked':0,
            'run':'preflight-run','commit':'a'*40,**receipt_keys}
        root={'campaign':c.CAMPAIGN,'owner_token':'offline-owner','status':'PREFLIGHT_LOCKED','enabled':False,'max_new':0,
              'approved_total':120,'reserved_total':0,'actual':0,'success':0,'failed':0,'unknown':0,'unused_locked':120,'generation_calls':0}
        lock={'campaign':c.CAMPAIGN,'owner_token':'offline-owner','created_run':'preflight-run','created_commit':'a'*40,
              'enabled':False,'approved_total':120,'single_executor':True}
        self.store.data.update({'CONTROL.json':c.canon(root),'LOCK.json':c.canon(lock),
            'preflight/PREFLIGHT.json':c.canon(self.preflight),'preparation/SOURCES.json':c.canon(self.document),
            'preparation/PROMPTS.json':c.canon(PROMPTS),'preparation/FREEZE.json':c.canon(self.freeze),**historical})
        for phase,plan in self.plans.items():self.store.data['plans/'+self.freeze['plan_sha256_by_phase'][phase]+'.json']=c.canon(plan)

    def control(self,phase,previous=None,closing=False,complete=True):
        total=len(r.reservations(self.store));gate_phase='CLOSE' if closing else phase
        gate={'campaign':c.CAMPAIGN,'phase':gate_phase,'prior_reserved':total,'previous_phase':previous,
              'previous_state_sha256':c.sha(self.store.get('states/'+previous+'-finished.json')) if previous else None,
              **{key:True for key in ('verified','drive_readback_verified','owner_only','sha256_verified','zip_crc_verified','manifest_verified')}}
        self.store.put_same('gates/'+gate_phase+'.json',c.canon(gate))
        planraw=self.store.get('selection/FINAL_PLAN.json',True) if phase=='F' else None
        plan_sha=c.sha(planraw) if planraw is not None else self.freeze['plan_sha256_by_phase'][phase]
        plan=json.loads(planraw) if planraw is not None else self.plans[phase]
        return {'campaign':c.CAMPAIGN,'approved_total':120,'mode':'CLOSE' if closing else 'EXECUTE','phase':phase,
            'enabled':not closing,'max_new':0 if closing else len(plan['slots']),'prior_reserved':total,'owner_token':'offline-owner',
            'deadline_epoch':time.time()+600,'plan_sha256':plan_sha,'source_sha256':c.sha(c.canon(self.document)),
            'prompts_sha256':c.sha(c.canon(PROMPTS)),'freeze_sha256':c.sha(c.canon(self.freeze)),
            'preflight_object':'preflight/PREFLIGHT.json','preflight_sha256':c.sha(c.canon(self.preflight)),
            'backup_verified':True,'backup_receipt_object':'gates/'+gate_phase+'.json','backup_receipt_sha256':c.sha(c.canon(gate)),
            'previous_phase':previous,'package_sha256':c.sha(c.canon(gate)),'research_complete':complete,
            'closure_reason':'NORMAL_PROTOCOL_COMPLETE' if complete else 'SYNTHETIC_PARTIAL_STOP'}

    def run_phase(self,phase,previous=None,sender=None):
        control=self.control(phase,previous)
        self.last_control=control
        with mock.patch.object(r,'unpack_package',return_value={control['backup_receipt_object']:self.store.get(control['backup_receipt_object'])}):
            r.stage(self.store,control)
        return asyncio.run(r.execute(self.store,control,sender=sender or self.sender,client_factory=DummyClient))

    def select(self,candidate='N1'):
        plan=final_plan(self.document,candidate)
        evidence={'campaign':c.CAMPAIGN,'sources_sha256':c.sha(c.canon(self.document)),
                  'freeze_sha256':c.sha(c.canon(self.freeze)),'prior_reserved':len(self.plans['S']['slots']),
                  'selected_candidate':candidate,'review_complete':True,'generation_api_judge_calls':0,
                  'discovery_result_sha256_by_slot':{task['slot']:c.sha(self.store.get('results/'+task['slot']+'.json')) for task in self.plans['S']['slots']}}
        if 'omitted_reason' in plan:evidence['omitted_reason']=plan['omitted_reason']
        plan['selection_evidence_sha256']=c.sha(c.canon(evidence))
        self.store.create('selection/FINAL_SELECTION.json',c.canon(evidence));self.store.create('selection/FINAL_PLAN.json',c.canon(plan))

    def close(self,previous='L',complete=True):
        control=self.control(previous,previous,closing=True,complete=complete)
        with mock.patch.object(r,'unpack_package',return_value={'gates/CLOSE.json':self.store.get('gates/CLOSE.json')}):r.ingest_close(self.store,control)
        state=r.close(self.store,control)
        def get(name):return self.store.data.get(name[len(r.PREFIX)+1:]) if name.startswith(r.PREFIX+'/') else self.old.get(name)
        report=check.check_state(get,control)
        return state,report,control,get

    def test_maximum_frozen_design(self):
        document,freeze,plans,_=fixture();plans['F']=final_plan(document)
        self.assertEqual(c.validate_design(document,freeze,plans)[1],{'S':72,'F':32,'L':16})

    def test_partial_final_quota_and_reason(self):
        document,freeze,plans,_=fixture(12,6,8);plans['F']=final_plan(document)
        self.assertEqual(c.validate_design(document,freeze,plans)[1],{'S':72,'F':24,'L':16})
        del document['sample_shortage_reason']
        with self.assertRaises(AssertionError):c.validate_design(document,freeze,plans)

    def test_pending_and_omitted_final_distinguished(self):
        document,freeze,plans,_=fixture();self.assertEqual(c.validate_design(document,freeze,plans)[1]['F'],0)
        plans['F']=final_plan(document,None);self.assertEqual(c.validate_design(document,freeze,plans)[1]['F'],0)
        del plans['F']['omitted_reason']
        with self.assertRaises(AssertionError):c.validate_design(document,freeze,plans)

    def test_final_exposure_and_cluster_rejected(self):
        for mutation in ('prior_exposure','final_independence_verified','event_cluster'):
            document,freeze,plans,_=fixture();row=document['sources'][-1]
            row[mutation]=True if mutation=='prior_exposure' else False if mutation=='final_independence_verified' else document['sources'][0]['event_cluster']
            with self.assertRaises(AssertionError):c.validate_design(document,freeze,plans)

    def test_source_sha_and_fixed_pointer_rejected(self):
        document,freeze,plans,_=fixture();document['sources'][0]['source']+=' changed'
        with self.assertRaises(AssertionError):c.validate_design(document,freeze,plans)

    def test_discovery_shared_event_allowed_but_final_isolated(self):
        document,freeze,plans,_=fixture();document['sources'][1]['event_cluster']=document['sources'][0]['event_cluster']
        self.assertEqual(c.validate_design(document,freeze,plans)[1]['S'],72)
        document['sources'][-1]['event_cluster']=document['sources'][-2]['event_cluster']
        with self.assertRaises(AssertionError):c.validate_design(document,freeze,plans)
        document,freeze,plans,_=fixture();freeze['additional_export_objects']=[]
        with self.assertRaises(AssertionError):c.validate_design(document,freeze,plans)

    def test_common_kb_and_prompt_sha(self):
        c.validate_prompts(PROMPTS);bad=copy.deepcopy(PROMPTS);bad['N2']['KB']+=' extra'
        with self.assertRaises(AssertionError):c.validate_prompts(bad)

    def test_actual_packet_prompt_shas_when_available(self):
        path=pathlib.Path(__file__).resolve().parent.parent/'name_address_followup_inputs/design_packet/KF_NAME_ADDRESS_CANDIDATES_AND_LB_SAFETY.json'
        if not path.exists():self.skipTest('Private preparation packet is deliberately absent from public CI.')
        packet=json.loads(path.read_bytes());prompts=dict(zip(('N0','N1','N2'),packet['conditions'].values()));prompts.update(zip(('L0','L1'),packet['lb_safety_ablation'].values()))
        with mock.patch.object(c,'EXPECTED_PROMPT_SHA256',self.real_prompt_shas):c.validate_prompts(prompts)

    def test_new_lf_call_forbidden(self):
        with self.assertRaises(AssertionError):c.build_payload(c.MODEL,'none','LF','synthetic',PROMPTS['L0'])

    def test_old_actual_first_lineage_and_wrapper_events(self):
        document,_,_,historical=fixture();row=document['fixed_lf_inputs'][0];raw=historical[row['origin_result_object']]
        self.assertEqual(c.validate_fixed_lf_result(row,raw)['display_text'],row['display_text'])
        with self.assertRaises(AssertionError):c.validate_fixed_lf_result(row,raw+b' ')
        bad=copy.deepcopy(row);bad['origin_response_id']='different'
        with self.assertRaises(AssertionError):c.validate_fixed_lf_result(bad,raw)

    def test_misleading_legacy_display_rejected(self):
        document,_,_,historical=fixture();row=document['fixed_lf_inputs'][0];result=json.loads(historical[row['origin_result_object']])
        result['events'][0]['event']['delta']='different actual streamed text';raw=c.canon(result);row['origin_result_sha256']=c.sha(raw)
        with self.assertRaises(AssertionError):c.validate_fixed_lf_result(row,raw)

    def test_l_pair_and_no_hidden_parent(self):
        document,freeze,plans,_=fixture();plans['L']['slots'][1]['input_id']=document['fixed_lf_order'][1]
        with self.assertRaises(AssertionError):c.validate_design(document,freeze,plans)
        document,freeze,plans,_=fixture();plans['L']['slots'][0]['parent_first_id']='S-001'
        with self.assertRaises(AssertionError):c.validate_design(document,freeze,plans)

    def test_wrong_common_back_parent_rejected(self):
        task={'slot':'S-002','source_id':'K1','candidate':'N0','path':'KB','parent_first_id':'S-001'}
        parent={'campaign':c.CAMPAIGN,'source_id':'K1','candidate':'N1','path':'KF','stage':'S','success':True,'unknown':False,'display_text':'synthetic'}
        with self.assertRaises(AssertionError):r.resolve_input(task,{}, {'S-001':parent})

    def test_budget_no_reallocation_or_skipped_stage(self):
        with self.assertRaises(AssertionError):c.validate_effective_caps({'S':78,'F':26,'L':16})
        with self.assertRaises(AssertionError):c.budget_guard([],'F-001','F',dict(c.HARD_CAPS))
        record=c.budget_guard([],'S-001','S',dict(c.HARD_CAPS))
        with self.assertRaises(AssertionError):c.budget_guard([record],'S-003','S',dict(c.HARD_CAPS))
        with self.assertRaises(AssertionError):c.budget_guard([record],'S-001','S',dict(c.HARD_CAPS))

    def test_121st_reservation_rejected(self):
        records=[]
        for phase in c.PHASES:
            for i in range(c.HARD_CAPS[phase]):records.append(c.budget_guard(records,f'{phase}-{i+1:03d}',phase,dict(c.HARD_CAPS)))
        self.assertEqual(len(records),120)
        with self.assertRaises(AssertionError):c.budget_guard(records,'L-017','L',dict(c.HARD_CAPS))

    def test_full_120_memory_pipeline_and_readonly_checker(self):
        self.initialize();self.run_phase('S');self.select('N1');self.run_phase('F','S');self.run_phase('L','F')
        state,report,_,_=self.close();self.assertEqual((len(self.calls),state['success'],state['unused_locked']),(120,120,0))
        self.assertEqual(report['status'],'PASS');self.assertEqual(len(report['previous_campaigns']),9)
        for i,iid in enumerate(self.document['fixed_lf_order']):
            expected=self.document['fixed_lf_inputs'][i]['display_text']
            self.assertEqual([request['input'] for request in self.calls[104+2*i:106+2*i]],[expected,expected])

    def test_s72_f0_l16_close_ordinal_lease(self):
        self.initialize();self.run_phase('S');self.select(None);self.run_phase('F','S')
        self.assertNotIn('locks/after-72.json',self.store.data)
        self.run_phase('L','F');state,report,_,_=self.close()
        self.assertEqual((len(self.calls),state['reserved_total'],state['unused_locked']),(88,88,32))
        self.assertEqual(json.loads(self.store.get('locks/after-72.json'))['phase'],'L')
        self.assertEqual(report['new_campaign_authority']['stage_actual'],{'S':72,'F':0,'L':16})

    def test_s72_f16_l16_shortage_is_locked(self):
        self.initialize(12,4,8);self.run_phase('S');self.select('N2');self.run_phase('F','S');self.run_phase('L','F')
        state,_,_,_=self.close();self.assertEqual((len(self.calls),state['reserved_total'],state['unused_locked']),(104,104,16))

    def test_reservation_readback_failure_charged_unknown_no_post(self):
        self.initialize();self.store.fail_after_write='budget/0001.json';state=self.run_phase('S')
        self.assertEqual((len(self.calls),state['reserved_total'],state['unknown']),(0,1,1))
        self.assertEqual(state['status'],'PAUSED_LOCKED')
        with self.assertRaisesRegex(AssertionError,'TERMINAL_CAMPAIGN_LOCK'):
            asyncio.run(r.execute(self.store,self.last_control,self.sender,DummyClient))
        closed,report,_,_=self.close('S',False)
        self.assertEqual((closed['unknown'],closed['unused_locked'],closed['research_complete']),(1,119,False))
        self.assertEqual(report['status'],'PASS')

    def test_failure_single_post_no_retry(self):
        self.initialize()
        async def fail(client,payload,key):
            self.calls.append(payload);result=good_result();result.update(success=False,http_status=500,terminal=None,display_text=None);return result
        state=self.run_phase('S',sender=fail)
        self.assertEqual(len(self.calls),1);self.assertEqual(state['reserved_total'],1);self.assertEqual(state['status'],'PAUSED_LOCKED')

    def test_backup_gate_unverified_blocks_post(self):
        self.initialize();control=self.control('S');gate=json.loads(self.store.get('gates/S.json'));gate['owner_only']=False
        self.store.data['gates/S.json']=c.canon(gate);control['backup_receipt_sha256']=c.sha(c.canon(gate))
        with self.assertRaises(AssertionError):asyncio.run(r.execute(self.store,control,self.sender,DummyClient))
        self.assertEqual(len(self.calls),0)

    def test_wrong_actor_and_replay_block_before_control_read(self):
        for key,value in (('GITHUB_ACTOR','other'),('GITHUB_RUN_ATTEMPT','2'),('GITHUB_REF','refs/heads/main')):
            with mock.patch.dict(os.environ,{key:value}),self.assertRaises(AssertionError):r.runtime_control()

    def test_final_checker_rejects_old_lock_mutation(self):
        self.initialize(1,1,1);self.run_phase('S');self.select(None);self.run_phase('F','S');self.run_phase('L','F');_,_,control,get=self.close()
        name=next(iter(self.old));self.old[name]+=b' '
        with self.assertRaises(AssertionError):check.check_state(get,control)

    def test_final_checker_rejects_external_input_context(self):
        self.initialize(1,1,1);self.run_phase('S');self.select(None);self.run_phase('F','S');self.run_phase('L','F');_,_,control,get=self.close()
        value=json.loads(self.store.get('requests/L-001.json'));value['request']['previous_response_id']='hidden-history'
        self.store.data['requests/L-001.json']=c.canon(value)
        with self.assertRaises(AssertionError):check.check_state(get,control)

    def test_final_checker_read_errors_are_not_absence(self):
        self.initialize(1,1,1);self.run_phase('S');self.select(None);self.run_phase('F','S');self.run_phase('L','F');_,_,control,get=self.close()
        def failed_get(name):
            if name.endswith('budget/0120.json'):raise OSError('synthetic unavailable read')
            return get(name)
        with self.assertRaises(OSError):check.check_state(failed_get,control)

    def test_sender_http500_is_one_mock_request(self):
        import httpx
        seen=[]
        async def handler(request):seen.append(request);return httpx.Response(500,json={'error':{'message':'synthetic error'}})
        async def run():
            async with http_sender.make_client(httpx.MockTransport(handler)) as client:
                return await http_sender.send(client,c.build_payload(c.MODEL,'none','KF','synthetic',PROMPTS['N0']),'synthetic-key-not-a-secret')
        result=asyncio.run(run());self.assertEqual(len(seen),1);self.assertEqual(result['http_attempts'],1);self.assertFalse(result['success'])

    def test_required_metadata_and_timing_reject(self):
        for key,value in (('actual_model','other-model'),('actual_service_tier','flex'),('request_id',None),('response_id',None),('usage',None),('t_first_text',float('nan'))):
            result=good_result();result[key]=value;self.assertFalse(c.validate_result_metadata(result)['success'])

    def test_actual_reasoning_effort_explicit_mismatch_stops(self):
        for effort in ('low','medium',None):
            result=good_result();result['response']['reasoning']['effort']=effort
            checked=c.validate_result_metadata(result)
            self.assertFalse(checked['success']);self.assertIsNone(checked['display_text'])
            self.assertIn('ACTUAL_REASONING_EFFORT_MISMATCH',checked['metadata_errors'])
            self.assertTrue(checked['raw_chunks_base64'])
        result=good_result();del result['response']['reasoning']
        checked=c.validate_result_metadata(result)
        self.assertTrue(checked['success']);self.assertIn('ACTUAL_REASONING_EFFORT_NOT_REPORTED',checked['metadata_warnings'])
        self.assertTrue(c.validate_result_metadata(good_result())['success'])

    def test_runtime_effort_mismatch_pauses_after_one_post(self):
        self.initialize()
        async def mismatch(client,payload,key):
            self.calls.append(payload);result=good_result();result['response']['reasoning']['effort']='low';return result
        state=self.run_phase('S',sender=mismatch)
        self.assertEqual((len(self.calls),state['reserved_total'],state['failed']),(1,1,1))
        self.assertEqual(state['status'],'PAUSED_LOCKED')
        result=json.loads(self.store.get('results/S-001.json'))
        self.assertIn('ACTUAL_REASONING_EFFORT_MISMATCH',result['metadata_errors'])
        self.assertTrue(result['raw_chunks_base64'])


if __name__=='__main__':unittest.main()
