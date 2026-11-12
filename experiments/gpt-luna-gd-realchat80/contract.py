"""Immutable request, sample, dependency, and budget contract for REALCHAT80 only."""
import collections
import hashlib
import json

CAMPAIGN = 'GPT_LUNA_GD_REALCHAT80_20261112'
MODEL = 'gpt-6-luna'
PHASES = ('A', 'B', 'C', 'D')
CANDIDATES = ('BASE', 'G', 'D')
HARD_CAPS = {'A': 36, 'B': 12, 'C': 24, 'D': 8}
APPROVED_TOTAL = 80
EXPECTED_LF = {
    'BASE': 'b902a50dcaa0c19c4b2d3a0b26a7dc02c9dc0a8cc9a3d0536ff02f9605d8febd',
    'G': 'a754b9d2bebde1e166fd6e4233c3fb779eadc72e8c9cb58fbdf2127716a6fe72',
    'D': 'fa4b07e4057b565b763776ebed3c1adec732022c9e750519ec4442100779b880',
}
EXPECTED_BASE_OTHER = {
    'KF': '6c8302be24fb7adb31161c0c76d2dfc5190aefb4fbc66e05a66f6dd7f1c0e297',
    'KB': '9f850340ef4be99eb022cc52055f631e56835f502666e3104468d19830e6d1a8',
    'LB': '0337f538b89bfb9ccbddc2d4737751cda319b8366ce0a66a070521d20fc9e92c',
}

def canon(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode('utf-8')

def sha(value):
    return hashlib.sha256(value).hexdigest()

def require(condition, code):
    if not condition:
        raise AssertionError(code)

def validate_prompts(prompts):
    require(set(prompts) == set(CANDIDATES), 'PROMPT_CANDIDATE_SET')
    for candidate in CANDIDATES:
        require(set(prompts[candidate]) == {'LF', 'LB', 'KF', 'KB'}, 'PROMPT_PATH_SET')
        require(all(isinstance(v, str) for v in prompts[candidate].values()), 'PROMPT_NOT_STRING')
        require(sha(prompts[candidate]['LF'].encode()) == EXPECTED_LF[candidate], 'LF_PROMPT_SHA')
        for path, expected in EXPECTED_BASE_OTHER.items():
            require(prompts[candidate][path] == prompts['BASE'][path], 'NON_LF_CANDIDATE_CHANGE')
            require(sha(prompts[candidate][path].encode()) == expected, 'BASE_PROMPT_SHA')

def build_payload(model, effort, path, text, prompts):
    require(model == MODEL and effort == 'none', 'MODEL_OR_EFFORT_NOT_APPROVED')
    require(path in ('KF', 'KB', 'LF', 'LB') and isinstance(text, str) and bool(text.strip()), 'INVALID_REQUEST_TEXT')
    return dict(model=model, reasoning={'effort': effort}, instructions=prompts[path],
                input=text, stream=True, store=False, max_output_tokens=4096, service_tier='default')

def back_input(parent):
    if not parent or not parent.get('success') or parent.get('unknown'):
        return None
    value = parent.get('display_text')
    return value if isinstance(value, str) and value.strip() else None

def parse_events(events):
    # Same parser contract used by the previously verified streaming sender.
    deltas=[]; done=[]; response=None; refusal=False; terminal=None; usage=None
    for event in events:
        t=event.get('type')
        if t=='response.output_text.delta': deltas.append(event.get('delta',''))
        elif t=='response.output_text.done': done.append(event.get('text',''))
        elif t=='response.refusal.delta': refusal=True
        if t in ('response.completed','response.incomplete','response.failed'):
            terminal=t; response=event.get('response',{}); usage=response.get('usage')
    text=''.join(deltas); final=[]
    if response:
        for item in response.get('output',[]):
            for content in item.get('content',[]):
                if content.get('type')=='output_text': final.append(content['text'])
                if content.get('type')=='refusal': refusal=True
    completed=(terminal=='response.completed' and response.get('status')=='completed')
    mismatch=completed and (text!=''.join(final) or (done and text!=''.join(done)))
    ok=completed and not refusal and bool(text.strip()) and not mismatch
    return {'success':ok,'display_text':text if ok else None,'partial_text':text,
            'usage':usage,'terminal':terminal,'refusal':refusal,'mismatch':mismatch}

def validate_result_metadata(result):
    errors=[]
    if result.get('actual_model') != MODEL: errors.append('ACTUAL_MODEL_MISMATCH')
    if result.get('actual_service_tier') != 'default': errors.append('SERVICE_TIER_MISMATCH')
    if not isinstance(result.get('response_id'), str) or not result['response_id']: errors.append('RESPONSE_ID_MISSING')
    usage=result.get('usage')
    if not isinstance(usage, dict) or any(type(usage.get(k)) is not int or usage[k]<0 for k in ('input_tokens','output_tokens','total_tokens')):
        errors.append('USAGE_MISSING_OR_INVALID')
    elif usage['total_tokens'] != usage['input_tokens'] + usage['output_tokens']:
        errors.append('USAGE_TOTAL_MISMATCH')
    if result.get('http_attempts') != 1: errors.append('HTTP_ATTEMPT_CONTRACT')
    result['provider_parse_success'] = bool(result.get('success'))
    result['metadata_errors'] = errors
    result['success'] = bool(result.get('success')) and not errors
    result['unknown'] = bool(result.get('exception')) or (result.get('http_status') == 200 and result.get('terminal') is None)
    if not result['success']:
        result['display_text'] = None
    return result

def budget_guard(reservations, slot, phase, effective_caps):
    require(phase in PHASES, 'UNAPPROVED_PHASE')
    require(set(effective_caps) == set(PHASES), 'EFFECTIVE_CAP_KEYS')
    require(all(type(effective_caps[p]) is int and 0<=effective_caps[p]<=HARD_CAPS[p] for p in PHASES), 'EFFECTIVE_CAP_INCREASE')
    require(len(reservations) < APPROVED_TOTAL, 'CAMPAIGN_CAP')
    require(slot not in {r['slot'] for r in reservations}, 'DUPLICATE_SLOT')
    require(sum(r['stage']==phase for r in reservations) < effective_caps[phase], 'STAGE_CAP_NO_REALLOCATION')
    require(all(r['campaign']==CAMPAIGN and r['model']==MODEL for r in reservations), 'FOREIGN_RESERVATION')
    return {'campaign':CAMPAIGN,'model':MODEL,'slot':slot,'stage':phase,
            'ordinal':len(reservations)+1,'state':'RESERVED_TRANSMISSION_UNKNOWN'}

def validate_design(source_document, freeze, plans):
    require(source_document['campaign']==freeze['campaign']==CAMPAIGN, 'FOREIGN_FREEZE')
    require(freeze['approved_total']==APPROVED_TOTAL and set(plans)==set(PHASES), 'APPROVAL_OR_PLAN_SET')
    sources=source_document['sources']
    require(all(isinstance(s,dict) and isinstance(s.get('source'),str) and s['source'].strip() for s in sources), 'SOURCE_TYPE')
    by={s['source_id']:s for s in sources}
    require(len(by)==len(sources), 'DUPLICATE_SOURCE_ID')
    require(all(sha(s['source'].encode())==s['sha256'] for s in sources), 'SOURCE_BYTE_SHA')
    require(all(type(s.get('eligible')) is bool for s in sources), 'ELIGIBILITY_MISSING')
    groups={split:[s['source_id'] for s in sources if s['eligible'] and s['split']==split]
            for split in ('DEVELOPMENT','FINAL','SAFETY')}
    require(2<=len(groups['DEVELOPMENT'])<=4 and 2<=len(groups['FINAL'])<=4, 'INDEPENDENT_SAMPLE_MINIMUM')
    require(0<=len(groups['SAFETY'])<=4, 'SAFETY_SAMPLE_CAP')
    require(all(s['split'] in groups and s['direction']==('KF' if s['split']=='SAFETY' else 'LF') for s in sources), 'SOURCE_SPLIT_DIRECTION')
    require(len({s['sha256'] for s in sources if s['eligible']})==sum(map(len,groups.values())), 'DUPLICATE_ELIGIBLE_SOURCE_BYTES')
    effective={'A':len(groups['DEVELOPMENT'])*9,'B':len(groups['DEVELOPMENT'])*3,
               'C':len(groups['FINAL'])*6,'D':len(groups['SAFETY'])*2}
    require(freeze['stage_caps']==effective, 'EFFECTIVE_CAPS_VS_SAMPLES')
    require(all(effective[p]<=HARD_CAPS[p] for p in PHASES), 'HARD_CAP_EXCEEDED')
    all_ids=[]
    allowed_slot_keys={'slot','source_id','candidate','path','repeat_index','parent_first_id','first_success_of'}
    for phase in PHASES:
        p=plans[phase]
        require(p['campaign']==CAMPAIGN and p['phase']==phase, 'FOREIGN_OR_WRONG_PHASE_PLAN')
        require(len(p['slots'])==effective[phase], 'PLAN_COUNT_VS_CAP')
        require([t['slot'] for t in p['slots']]==[f'{phase}-{i:03d}' for i in range(1,len(p['slots'])+1)], 'NONCONTIGUOUS_SLOT_IDS')
        for t in p['slots']:
            require(set(t)<=allowed_slot_keys and {'slot','source_id','candidate','path','repeat_index'}<=set(t), 'SLOT_FIELD_CONTRACT')
            require(t['source_id'] in by and by[t['source_id']]['eligible'], 'INELIGIBLE_SOURCE_SLOT')
            require(t['candidate'] in CANDIDATES, 'UNAPPROVED_CANDIDATE')
            require(type(t['repeat_index']) is int, 'REPEAT_INDEX_TYPE')
            all_ids.append(t['slot'])
    require(len(set(all_ids))==len(all_ids), 'DUPLICATE_CROSS_PHASE_SLOT')
    a=plans['A']['slots']; b=plans['B']['slots']
    expected_a={(sid,c,'LF',r) for sid in groups['DEVELOPMENT'] for c in CANDIDATES for r in (1,2,3)}
    actual_a=[(t['source_id'],t['candidate'],t['path'],t['repeat_index']) for t in a]
    require(len(set(actual_a))==len(actual_a) and set(actual_a)==expected_a, 'A_FACTORIAL_REPEAT_CONTRACT')
    require(all('parent_first_id' not in t and 'first_success_of' not in t for t in a), 'A_DEPENDENCY_FORBIDDEN')
    for sid in groups['DEVELOPMENT']:
        orders=[]
        for rep in (1,2,3):
            order=tuple(t['candidate'] for t in a if t['source_id']==sid and t['repeat_index']==rep)
            require(set(order)==set(CANDIDATES) and len(order)==3, 'A_CANDIDATE_ORDER')
            orders.append(order)
        require(len(set(orders))>=2, 'A_ORDER_NOT_CROSSED')
        for candidate in CANDIDATES:
            require([t['repeat_index'] for t in a if t['source_id']==sid and t['candidate']==candidate]==[1,2,3], 'A_REPEAT_ORDER')
    expected_b={(sid,c,'LB',1) for sid in groups['DEVELOPMENT'] for c in CANDIDATES}
    actual_b=[(t['source_id'],t['candidate'],t['path'],t['repeat_index']) for t in b]
    require(len(set(actual_b))==len(actual_b) and set(actual_b)==expected_b, 'B_ONE_BACK_PER_CONDITION')
    for t in b:
        want=[u['slot'] for u in a if u['source_id']==t['source_id'] and u['candidate']==t['candidate']]
        require(t.get('first_success_of')==want and 'parent_first_id' not in t, 'B_FIRST_SUCCESS_ORDER_OR_COVERAGE')
    for phase,group,first,back,candidates in [('C','FINAL','LF','LB',CANDIDATES),('D','SAFETY','KF','KB',('BASE',))]:
        slots=plans[phase]['slots']; seen=[]
        for i in range(0,len(slots),2):
            f,r=slots[i:i+2]
            require(f['source_id']==r['source_id'] and f['candidate']==r['candidate'], 'CHAIN_SOURCE_OR_CANDIDATE_MISMATCH')
            require(f['path']==first and r['path']==back and f['repeat_index']==r['repeat_index']==1, 'CHAIN_PATH_OR_REPEAT')
            require('parent_first_id' not in f and 'first_success_of' not in f and 'first_success_of' not in r, 'CHAIN_UNEXPECTED_DEPENDENCY')
            require(r.get('parent_first_id')==f['slot'], 'CHAIN_PARENT_NOT_PREVIOUS_FIRST')
            seen.append((f['source_id'],f['candidate']))
        want={(sid,c) for sid in groups[group] for c in candidates}
        require(len(set(seen))==len(seen) and set(seen)==want, 'FINAL_OR_SAFETY_COVERAGE')
    return by, effective

def choose_first_success(task, results_by_slot):
    # Selection depends only on technical completion, never translation quality.
    for slot in task['first_success_of']:
        parent=results_by_slot.get(slot)
        if back_input(parent) is not None:
            require(parent['source_id']==task['source_id'] and parent['candidate']==task['candidate']
                    and parent['path']=='LF' and parent['stage']=='A', 'B_PARENT_IDENTITY')
            return parent
    return None
