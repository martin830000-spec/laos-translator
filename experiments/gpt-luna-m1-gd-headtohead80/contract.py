"""Immutable request, sample, dependency, and budget contract for M1_HEADTOHEAD80 only."""
import hashlib
import json

CAMPAIGN = 'GPT_LUNA_M1_GD_HEADTOHEAD80_20261112'
MODEL = 'gpt-6-luna'
PHASES = ('A', 'B', 'C')
CANDIDATES = ('BASE', 'M1', 'G', 'D')
HARD_CAPS = {'A': 24, 'B': 24, 'C': 32}
APPROVED_TOTAL = 80
EXPECTED_LF = {
    'BASE': 'b902a50dcaa0c19c4b2d3a0b26a7dc02c9dc0a8cc9a3d0536ff02f9605d8febd',
    'M1': '9778fa396400c056d4c3c0e0b817304948f68b54311ab8631094737050b4520e',
    'G': 'a754b9d2bebde1e166fd6e4233c3fb779eadc72e8c9cb58fbdf2127716a6fe72',
    'D': 'fa4b07e4057b565b763776ebed3c1adec732022c9e750519ec4442100779b880',
}
EXPECTED_BASE_OTHER = {
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
        require(set(prompts[candidate]) == {'LF', 'LB'}, 'PROMPT_PATH_SET')
        require(all(isinstance(v, str) for v in prompts[candidate].values()), 'PROMPT_NOT_STRING')
        require(sha(prompts[candidate]['LF'].encode()) == EXPECTED_LF[candidate], 'LF_PROMPT_SHA')
        for path, expected in EXPECTED_BASE_OTHER.items():
            require(prompts[candidate][path] == prompts['BASE'][path], 'NON_LF_CANDIDATE_CHANGE')
            require(sha(prompts[candidate][path].encode()) == expected, 'BASE_PROMPT_SHA')

def build_payload(model, effort, path, text, prompts):
    require(model == MODEL and effort == 'none', 'MODEL_OR_EFFORT_NOT_APPROVED')
    require(path in ('LF', 'LB') and isinstance(text, str) and bool(text.strip()), 'INVALID_REQUEST_TEXT')
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

# These source IDs and declared orders are metadata from the unmodified private
# packet. No original messages or prompt text is embedded in the public code.
DEV_ORDER = (
    'R20261112L0020', 'R20261112L0163', 'R20261112L0276',
    'R20261112L0194', 'R20261112L0121', 'R20261112L0054',
)
FINAL_PRIMARY_ORDER = (
    'R20261112L0001', 'R20261112L0190', 'R20261112L0250', 'R20261112L0378',
)
FINAL_RESERVE_ORDER = (
    'R20261112L0340', 'R20261112L0321', 'R20261112L0239', 'R20261112L0362',
)


def valid_sha256(value):
    return isinstance(value, str) and len(value) == 64 and all(c in '0123456789abcdef' for c in value)


def selected_source_order(source_document):
    """Resolve the complete preflight selection without looking at any outputs.

    DEVELOPMENT keeps the packet's declared order. For FINAL, walk the fixed
    primary order; replace a rejected primary in its original position with the
    next eligible reserve in the predeclared reserve order. Every skipped source
    encountered while filling a required position needs immutable audit evidence.
    Unused reserves after four FINAL positions are filled need no rejection.
    """
    sources = source_document['sources']
    declared = DEV_ORDER + FINAL_PRIMARY_ORDER + FINAL_RESERVE_ORDER
    require([s['source_id'] for s in sources] == list(declared), 'DECLARED_SOURCE_SET_OR_ORDER')
    by = {s['source_id']: s for s in sources}
    selection = source_document.get('selection')
    require(isinstance(selection, dict) and set(selection) == {'dev_order', 'final_order', 'rejected'}, 'SELECTION_SCHEMA')
    rejected = selection['rejected']
    require(isinstance(rejected, dict) and set(rejected) <= set(declared), 'REJECTION_SOURCE_SET')
    for sid, evidence in rejected.items():
        require(not by[sid]['eligible'], 'ELIGIBLE_SOURCE_REJECTED')
        require(isinstance(evidence, dict) and isinstance(evidence.get('reason'), str)
                and bool(evidence['reason'].strip()) and valid_sha256(evidence.get('evidence_sha256')), 'REJECTION_EVIDENCE_MISSING')
    dev = []
    for sid in DEV_ORDER:
        if by[sid]['eligible']:
            dev.append(sid)
        else:
            require(sid in rejected, 'DEVELOPMENT_EXCLUSION_UNDOCUMENTED')
    final = []
    reserve_index = 0
    for sid in FINAL_PRIMARY_ORDER:
        if by[sid]['eligible']:
            final.append(sid)
            continue
        require(sid in rejected, 'PRIMARY_EXCLUSION_UNDOCUMENTED')
        while reserve_index < len(FINAL_RESERVE_ORDER):
            reserve = FINAL_RESERVE_ORDER[reserve_index]
            reserve_index += 1
            if by[reserve]['eligible']:
                final.append(reserve)
                break
            require(reserve in rejected, 'RESERVE_SKIP_UNDOCUMENTED')
    selected = dev + final
    require({s['source_id'] for s in sources if s['eligible']} == set(selected), 'UNUSED_ELIGIBLE_SOURCE')
    require(selection['dev_order'] == dev and selection['final_order'] == final, 'SELECTED_SOURCE_ORDER')
    require(4 <= len(dev) <= 6 and 2 <= len(final) <= 4, 'INDEPENDENT_SAMPLE_MINIMUM')
    event_keys = [by[sid].get('event_key') for sid in selected]
    require(all(isinstance(k, str) and bool(k.strip()) for k in event_keys), 'SELECTED_EVENT_KEY_MISSING')
    require(len(set(event_keys)) == len(event_keys), 'DUPLICATE_SELECTED_EVENT')
    return by, dev, final


def cyclic_candidates(source_index):
    offset = source_index % len(CANDIDATES)
    return CANDIDATES[offset:] + CANDIDATES[:offset]


def validate_design(source_document, freeze, plans):
    require(source_document['campaign'] == freeze['campaign'] == CAMPAIGN, 'FOREIGN_FREEZE')
    require(freeze['approved_total'] == APPROVED_TOTAL and set(plans) == set(PHASES), 'APPROVAL_OR_PLAN_SET')
    require(isinstance(freeze.get('order_rule'), str) and bool(freeze['order_rule'].strip()), 'ORDER_RULE_NOT_DOCUMENTED')
    sources = source_document['sources']
    require(isinstance(sources, list) and all(isinstance(s, dict) and isinstance(s.get('source'), str)
            and bool(s['source'].strip()) for s in sources), 'SOURCE_TYPE')
    require(all(isinstance(s.get('source_id'), str) for s in sources), 'SOURCE_ID_TYPE')
    require(len({s['source_id'] for s in sources}) == len(sources), 'DUPLICATE_SOURCE_ID')
    require(all(sha(s['source'].encode()) == s['sha256'] for s in sources), 'SOURCE_BYTE_SHA')
    require(all(type(s.get('eligible')) is bool for s in sources), 'ELIGIBILITY_MISSING')
    require(all(s['direction'] == 'LF' and s['split'] == ('DEVELOPMENT' if s['source_id'] in DEV_ORDER else 'FINAL')
                for s in sources), 'SOURCE_SPLIT_DIRECTION')
    by, dev, final = selected_source_order(source_document)
    require(len({s['sha256'] for s in sources if s['eligible']}) == len(dev) + len(final), 'DUPLICATE_ELIGIBLE_SOURCE_BYTES')
    effective = {'A': len(dev) * 4, 'B': len(dev) * 4, 'C': len(final) * 8}
    require(freeze['stage_caps'] == effective and all(type(v) is int for v in freeze['stage_caps'].values()), 'EFFECTIVE_CAPS_VS_SAMPLES')
    require(all(effective[p] <= HARD_CAPS[p] for p in PHASES) and sum(effective.values()) <= APPROVED_TOTAL, 'HARD_CAP_EXCEEDED')
    all_ids = []
    required_slot_keys = {'slot', 'source_id', 'candidate', 'path', 'repeat_index'}
    allowed_slot_keys = required_slot_keys | {'parent_first_id', 'first_success_of'}
    for phase in PHASES:
        plan = plans[phase]
        require(plan['campaign'] == CAMPAIGN and plan['phase'] == phase, 'FOREIGN_OR_WRONG_PHASE_PLAN')
        require(len(plan['slots']) == effective[phase], 'PLAN_COUNT_VS_CAP')
        require([t['slot'] for t in plan['slots']] == [f'{phase}-{i:03d}' for i in range(1, len(plan['slots']) + 1)], 'NONCONTIGUOUS_SLOT_IDS')
        for task in plan['slots']:
            require(required_slot_keys <= set(task) <= allowed_slot_keys, 'SLOT_FIELD_CONTRACT')
            require(task['source_id'] in by and by[task['source_id']]['eligible'], 'INELIGIBLE_SOURCE_SLOT')
            require(task['candidate'] in CANDIDATES and task['path'] in ('LF', 'LB'), 'UNAPPROVED_CANDIDATE_OR_PATH')
            require(type(task['repeat_index']) is int and task['repeat_index'] == 1, 'SINGLE_ATTEMPT_PER_CONDITION')
            all_ids.append(task['slot'])
    require(len(set(all_ids)) == len(all_ids), 'DUPLICATE_CROSS_PHASE_SLOT')
    a = plans['A']['slots']; b = plans['B']['slots']; c = plans['C']['slots']
    expected_a = [(sid, candidate, 'LF', 1) for i, sid in enumerate(dev) for candidate in cyclic_candidates(i)]
    actual_a = [(t['source_id'], t['candidate'], t['path'], t['repeat_index']) for t in a]
    require(actual_a == expected_a, 'A_SINGLE_FIRST_CYCLIC_ORDER')
    require(all('parent_first_id' not in t and 'first_success_of' not in t for t in a), 'A_DEPENDENCY_FORBIDDEN')
    for first, back in zip(a, b):
        require((back['source_id'], back['candidate'], back['path'], back['repeat_index'])
                == (first['source_id'], first['candidate'], 'LB', 1), 'B_ONE_BACK_A_ORDER')
        require(back.get('first_success_of') == [first['slot']] and 'parent_first_id' not in back, 'B_SINGLE_PARENT_EXACT_A')
    seen = []
    for i in range(0, len(c), 2):
        first, back = c[i:i+2]
        require(first['source_id'] == back['source_id'] and first['candidate'] == back['candidate'], 'CHAIN_SOURCE_OR_CANDIDATE_MISMATCH')
        require(first['path'] == 'LF' and back['path'] == 'LB', 'CHAIN_PATH_OR_REPEAT')
        require('parent_first_id' not in first and 'first_success_of' not in first and 'first_success_of' not in back, 'CHAIN_UNEXPECTED_DEPENDENCY')
        require(back.get('parent_first_id') == first['slot'], 'CHAIN_PARENT_NOT_PREVIOUS_FIRST')
        seen.append((first['source_id'], first['candidate']))
    expected_c = [(sid, candidate) for i, sid in enumerate(final) for candidate in cyclic_candidates(i)]
    require(seen == expected_c, 'C_FINAL_CYCLIC_ORDER')
    return by, effective

def choose_first_success(task, results_by_slot):
    # A condition has exactly one FIRST. Never select or regenerate by quality.
    require(isinstance(task.get('first_success_of'), list) and len(task['first_success_of']) == 1, 'B_SINGLE_PARENT_REQUIRED')
    for slot in task['first_success_of']:
        parent=results_by_slot.get(slot)
        if back_input(parent) is not None:
            require(parent['source_id']==task['source_id'] and parent['candidate']==task['candidate']
                    and parent['path']=='LF' and parent['stage']=='A' and parent.get('slot')==slot, 'B_PARENT_IDENTITY')
            return parent
    return None
