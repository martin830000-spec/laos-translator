"""FOLLOWUP120 fixed prompt, budget, source-independence and external-FIRST guards.
No network or model calls. Historical LF outputs are evidence, not new attempts.
"""
import hashlib
import json
import math
import re

CAMPAIGN = 'GPT_LUNA_NAME_ADDRESS_FOLLOWUP120_20261114'
OLD_AB160 = 'GPT_LUNA_COUPLE_TONE_NAME_AB160_20261113'
OLD_AB160_CLOSED_SHA256 = '90215a127a3a2093dd94a8e3ca0dca4b50b4bf0f435160dd0a614d8c63d4150e'
MODEL = 'gpt-6-luna'
PHASES = ('S', 'F', 'L')
N_CANDIDATES = ('N0', 'N1', 'N2')
L_CANDIDATES = ('L0', 'L1')
CANDIDATES = N_CANDIDATES + L_CANDIDATES
PATHS = ('KF', 'KB', 'LB')
HARD_CAPS = {'S': 72, 'F': 32, 'L': 16}
APPROVED_TOTAL = 120

EXPECTED_PROMPT_SHA256 = {'N0': {'KF': '812804499856e31cd70bd4571d3791d3a2159f725b6f5f798069c78df1606194', 'KB': '4ecf671709652818bc0b432645210e8e498305b8fa8fb851eedcfd8dbed23300'}, 'N1': {'KF': 'a0e2e6fa55b4579521dd90258c8660f4bdf38a744ea38c41036e0a64e39fcfae', 'KB': '4ecf671709652818bc0b432645210e8e498305b8fa8fb851eedcfd8dbed23300'}, 'N2': {'KF': '487b65c6f5b6d9f190596bf90222752bddd8ca3401b37612107e9f85193e2e3f', 'KB': '4ecf671709652818bc0b432645210e8e498305b8fa8fb851eedcfd8dbed23300'}, 'L0': {'LF': '4398966a9339ba3a7bf075f5c26f4b8636fc03194e56942b56bd0a81ae3eaa3f', 'LB': '24f0b00ba4f6a73e148f14d0cfa02b575f5344d07f8d8403f4f0416b778c1f1a'}, 'L1': {'LF': '4398966a9339ba3a7bf075f5c26f4b8636fc03194e56942b56bd0a81ae3eaa3f', 'LB': '397586e2f3bc4361d7ca46e2d314914159a52b00ac9c7962648375f02753fb87'}}

def canon(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode('utf-8')

def sha(value):
    return hashlib.sha256(value).hexdigest()

def require(condition, code):
    if not condition:
        raise AssertionError(code)

def valid_sha256(value):
    return isinstance(value, str) and re.fullmatch(r'[0-9a-f]{64}', value) is not None

def back_input(parent):
    if not isinstance(parent, dict) or not parent.get('success') or parent.get('unknown'):
        return None
    value = parent.get('display_text')
    return value if isinstance(value, str) and value.strip() else None

def parse_events(events):
    """Return a failed parse, rather than lose raw evidence on malformed events.

    The displayed text is the exact concatenation of streamed output deltas.
    Completed final content and every output-text-done aggregate must agree.
    Partial, refused, incomplete, failed, or contradictory streams never feed BACK.
    """
    deltas = []; done = []; response = {}; refusal = False
    terminal = None; usage = None; errors = []; terminals = 0
    if not isinstance(events, (list, tuple)):
        events = []; errors.append('EVENT_LIST_INVALID')
    for event in events:
        if not isinstance(event, dict):
            errors.append('EVENT_NOT_OBJECT'); continue
        kind = event.get('type')
        if kind in ('response.output_text.delta', 'response.output_text.done'):
            field = 'delta' if kind.endswith('.delta') else 'text'
            value = event.get(field)
            if not isinstance(value, str):
                errors.append('OUTPUT_TEXT_NOT_STRING')
            else:
                (deltas if field == 'delta' else done).append(value)
        elif kind in ('response.refusal.delta', 'response.refusal.done'):
            refusal = True
        elif kind == 'error':
            errors.append('STREAM_ERROR_EVENT')
        if kind in ('response.completed', 'response.incomplete', 'response.failed'):
            terminals += 1; terminal = kind
            value = event.get('response')
            if not isinstance(value, dict):
                errors.append('TERMINAL_RESPONSE_NOT_OBJECT'); response = {}
            else:
                response = value; usage = response.get('usage')
    if terminals > 1:
        errors.append('MULTIPLE_TERMINAL_EVENTS')
    final = []
    output = response.get('output', [])
    if not isinstance(output, list):
        errors.append('RESPONSE_OUTPUT_NOT_LIST'); output = []
    for item in output:
        if not isinstance(item, dict):
            errors.append('OUTPUT_ITEM_NOT_OBJECT'); continue
        content = item.get('content', [])
        if not isinstance(content, list):
            errors.append('OUTPUT_CONTENT_NOT_LIST'); continue
        for part in content:
            if not isinstance(part, dict):
                errors.append('OUTPUT_CONTENT_NOT_OBJECT'); continue
            if part.get('type') == 'refusal':
                refusal = True
            elif part.get('type') == 'output_text':
                value = part.get('text')
                if not isinstance(value, str): errors.append('FINAL_TEXT_NOT_STRING')
                else: final.append(value)
    text = ''.join(deltas)
    completed = terminal == 'response.completed' and response.get('status') == 'completed'
    mismatch = bool(completed and (text != ''.join(final) or (done and text != ''.join(done))))
    success = completed and not refusal and bool(text.strip()) and not mismatch and not errors
    return {'success': bool(success), 'display_text': text if success else None,
            'partial_text': text, 'usage': usage, 'terminal': terminal, 'refusal': refusal,
            'mismatch': mismatch, 'parse_errors': list(dict.fromkeys(errors))}

def validate_result_metadata(result):
    errors = []; warnings = []
    if result.get('actual_model') != MODEL: errors.append('ACTUAL_MODEL_MISMATCH')
    if result.get('actual_service_tier') != 'default': errors.append('SERVICE_TIER_MISMATCH')
    response = result.get('response')
    reasoning = response.get('reasoning') if isinstance(response, dict) else None
    if isinstance(reasoning, dict) and 'effort' in reasoning:
        result['actual_reasoning_effort'] = reasoning['effort']
        if reasoning['effort'] != 'none': errors.append('ACTUAL_REASONING_EFFORT_MISMATCH')
    else:
        result['actual_reasoning_effort'] = None
        warnings.append('ACTUAL_REASONING_EFFORT_NOT_REPORTED')
    for key in ('request_id', 'response_id'):
        if not isinstance(result.get(key), str) or not result[key].strip():
            errors.append(key.upper() + '_MISSING')
    usage = result.get('usage')
    usage_valid = isinstance(usage, dict) and all(
        type(usage.get(k)) is int and usage[k] >= 0 for k in ('input_tokens', 'output_tokens', 'total_tokens'))
    reasoning_tokens = None; cached_tokens = None
    if not usage_valid:
        errors.append('USAGE_MISSING_OR_INVALID')
    else:
        if usage['total_tokens'] != usage['input_tokens'] + usage['output_tokens']:
            errors.append('USAGE_TOTAL_MISMATCH')
        details = usage.get('output_tokens_details')
        reasoning_tokens = details.get('reasoning_tokens') if isinstance(details, dict) else None
        if type(reasoning_tokens) is not int or not 0 <= reasoning_tokens <= usage['output_tokens']:
            errors.append('REASONING_TOKENS_MISSING_OR_INVALID')
            reasoning_tokens = None
        elif reasoning_tokens:
            warnings.append('NONZERO_REASONING_TOKENS_WITH_REQUESTED_NONE')
        details = usage.get('input_tokens_details')
        if isinstance(details, dict) and 'cached_tokens' in details:
            cached_tokens = details['cached_tokens']
            if type(cached_tokens) is not int or not 0 <= cached_tokens <= usage['input_tokens']:
                errors.append('CACHED_TOKENS_INVALID'); cached_tokens = None
        else:
            warnings.append('CACHED_TOKENS_NOT_REPORTED')
    if type(result.get('http_attempts')) is not int or result['http_attempts'] != 1:
        errors.append('HTTP_ATTEMPT_CONTRACT')
    if result.get('success'):
        if result.get('http_status') != 200 or result.get('terminal') != 'response.completed':
            errors.append('SUCCESS_TERMINAL_HTTP_MISMATCH')
        timing_keys = ('t_first_text', 't_first_displayable_text', 't_response_done', 't_display_extract_done')
        timings = [result.get(key) for key in timing_keys]
        valid_number = lambda value: type(value) in (int, float) and math.isfinite(value) and value >= 0
        if not all(valid_number(value) for value in timings):
            errors.append('REQUIRED_TIMING_MISSING_OR_INVALID')
        elif timings != sorted(timings):
            errors.append('TIMING_ORDER_INVALID')
        text_done = result.get('t_text_done')
        if text_done is not None and (not valid_number(text_done)
                or not valid_number(timings[0]) or not valid_number(timings[2])
                or not timings[0] <= text_done <= timings[2]):
            errors.append('TEXT_DONE_TIMING_INVALID')
    result['provider_parse_success'] = bool(result.get('success'))
    result['metadata_errors'] = errors
    result['metadata_warnings'] = warnings
    result['reasoning_tokens'] = reasoning_tokens
    result['cached_input_tokens'] = cached_tokens
    result['unknown'] = (bool(result.get('exception')) or result.get('http_status') is None
                         or (result.get('http_status') == 200 and result.get('terminal') is None))
    result['success'] = bool(result.get('success')) and not errors and not result['unknown']
    if not result['success']:
        result['display_text'] = None
    return result


def validate_prompts(prompts):
    require(isinstance(prompts, dict) and set(prompts) == set(CANDIDATES), 'PROMPT_CANDIDATE_SET')
    for candidate in CANDIDATES:
        required_paths = {'KF', 'KB'} if candidate in N_CANDIDATES else {'LF', 'LB'}
        require(isinstance(prompts[candidate], dict) and set(prompts[candidate]) == required_paths, 'PROMPT_PATH_SET')
        for path, value in prompts[candidate].items():
            require(isinstance(value, str) and sha(value.encode()) == EXPECTED_PROMPT_SHA256[candidate][path], 'PROMPT_BYTE_SHA')
    require(prompts['N0']['KB'] == prompts['N1']['KB'] == prompts['N2']['KB'], 'COMMON_NAME_KB_REQUIRED')
    require(prompts['L0']['LF'] == prompts['L1']['LF'], 'HISTORICAL_LF_PROMPT_NOT_FROZEN')


def build_payload(model, effort, path, text, prompts):
    require(model == MODEL and effort == 'none', 'MODEL_OR_EFFORT_NOT_APPROVED')
    require(path in PATHS and isinstance(text, str) and bool(text.strip()), 'INVALID_REQUEST_TEXT_OR_FORBIDDEN_LF')
    require(isinstance(prompts, dict) and isinstance(prompts.get(path), str), 'PATH_PROMPT_MISSING')
    return dict(model=model, reasoning={'effort': effort}, instructions=prompts[path],
                input=text, stream=True, store=False, max_output_tokens=4096, service_tier='default')


def validate_effective_caps(caps):
    require(isinstance(caps, dict) and set(caps) == set(PHASES), 'EFFECTIVE_CAP_KEYS')
    for phase, unit in (('S', 6), ('F', 4), ('L', 2)):
        require(type(caps[phase]) is int and 0 <= caps[phase] <= HARD_CAPS[phase]
                and caps[phase] % unit == 0, 'STAGE_CAP_NO_REALLOCATION')


def budget_guard(reservations, slot, phase, effective_caps):
    require(phase in PHASES, 'UNAPPROVED_PHASE')
    validate_effective_caps(effective_caps)
    require(isinstance(reservations, list) and len(reservations) < APPROVED_TOTAL, 'CAMPAIGN_CAP')
    require(isinstance(slot, str) and re.fullmatch(phase + r'-[0-9]{3}', slot) is not None
            and 1 <= int(slot[2:]) <= HARD_CAPS[phase], 'INVALID_SLOT')
    counts = {p: 0 for p in PHASES}; previous = -1
    for ordinal, record in enumerate(reservations, 1):
        require(isinstance(record, dict) and record.get('campaign') == CAMPAIGN
                and record.get('model') == MODEL and record.get('stage') in PHASES
                and type(record.get('ordinal')) is int and record['ordinal'] == ordinal, 'FOREIGN_OR_INVALID_RESERVATION')
        p = record['stage']; index = PHASES.index(p)
        require(index >= previous, 'RESERVATION_PHASE_ORDER'); previous = index
        counts[p] += 1
        require(record.get('slot') == f'{p}-{counts[p]:03d}', 'NONCONTIGUOUS_STAGE_RESERVATION')
    require(len({r['slot'] for r in reservations}) == len(reservations), 'DUPLICATE_EXISTING_RESERVATION')
    require(slot not in {r['slot'] for r in reservations}, 'DUPLICATE_SLOT')
    for p in PHASES:
        require(counts[p] <= effective_caps[p], 'EXISTING_STAGE_CAP_EXCEEDED')
        if PHASES.index(p) < PHASES.index(phase):
            require(counts[p] == effective_caps[p], 'PREVIOUS_STAGE_NOT_COMPLETE')
        elif PHASES.index(p) > PHASES.index(phase):
            require(counts[p] == 0, 'LATER_STAGE_ALREADY_RESERVED')
    require(counts[phase] < effective_caps[phase] and slot == f'{phase}-{counts[phase]+1:03d}', 'STAGE_CAP_OR_NEXT_SLOT')
    return {'campaign': CAMPAIGN, 'model': MODEL, 'slot': slot, 'stage': phase,
            'ordinal': len(reservations) + 1, 'state': 'RESERVED_TRANSMISSION_UNKNOWN'}


def cyclic_candidates(index):
    offset = index % len(N_CANDIDATES)
    return N_CANDIDATES[offset:] + N_CANDIDATES[:offset]


def selected_source_order(document):
    sources = document.get('sources')
    require(isinstance(sources, list) and len(sources) <= 20, 'SOURCE_COUNT_CAP')
    required = {'source_id', 'source', 'sha256', 'direction', 'split', 'raw_record_number',
                'class', 'duplicate_group', 'event_cluster', 'prior_exposure',
                'final_independence_verified', 'selection_reason'}
    for source in sources:
        require(isinstance(source, dict) and required <= set(source), 'SOURCE_FIELD_CONTRACT')
        require(all(isinstance(source[k], str) and bool(source[k].strip()) for k in
                    ('source_id', 'source', 'class', 'duplicate_group', 'event_cluster', 'selection_reason')), 'SOURCE_STRING_FIELD')
        require(valid_sha256(source['sha256']) and sha(source['source'].encode()) == source['sha256'], 'SOURCE_BYTE_SHA')
        require(source['direction'] == 'KF' and source['split'] in ('DISCOVERY', 'FINAL'), 'SOURCE_SPLIT_DIRECTION')
        require(type(source['raw_record_number']) is int and 1 <= source['raw_record_number'] <= 500, 'RAW_RECORD_NUMBER')
        require(type(source['prior_exposure']) is bool and type(source['final_independence_verified']) is bool, 'SOURCE_EXPOSURE_FLAG_TYPE')
        for key in ('audit_case', 'luna_test'):
            if key in source:
                require(type(source[key]) is bool and (not source[key] or source['prior_exposure']), 'SOURCE_OPTIONAL_EXPOSURE_FLAG')
        if source['split'] == 'FINAL':
            require(not source['prior_exposure'] and source['final_independence_verified']
                    and not source.get('audit_case', False) and not source.get('luna_test', False), 'FINAL_INDEPENDENCE_REQUIRED')
    by = {s['source_id']: s for s in sources}
    require(len(by) == len(sources), 'DUPLICATE_SOURCE_ID')
    for key in ('sha256', 'duplicate_group', 'raw_record_number'):
        require(len({s[key] for s in sources}) == len(sources), 'DUPLICATE_SELECTED_SOURCE_OR_EVENT')
    selection = document.get('selection')
    require(isinstance(selection, dict) and set(selection) == {'discovery_order', 'final_order'}, 'SELECTION_SCHEMA')
    discovery = selection['discovery_order']; final = selection['final_order']
    for order, cap in ((discovery, 12), (final, 8)):
        require(isinstance(order, list) and len(order) <= cap and all(isinstance(sid, str) for sid in order)
                and len(set(order)) == len(order) and set(order) <= set(by), 'SELECTION_COUNT_OR_IDS')
    require(set(discovery).isdisjoint(final) and set(discovery + final) == set(by), 'SOURCE_SELECTION_PARTITION')
    require(all(by[sid]['split'] == 'DISCOVERY' for sid in discovery)
            and all(by[sid]['split'] == 'FINAL' for sid in final), 'SELECTION_SPLIT_MISMATCH')
    final_events = [by[sid]['event_cluster'] for sid in final]
    discovery_events = {by[sid]['event_cluster'] for sid in discovery}
    require(len(set(final_events)) == len(final_events) and set(final_events).isdisjoint(discovery_events),
            'FINAL_EVENT_CLUSTER_NOT_INDEPENDENT')
    if len(discovery) < 12 or len(final) < 8:
        require(isinstance(document.get('sample_shortage_reason'), str)
                and bool(document['sample_shortage_reason'].strip()), 'FROZEN_SAMPLE_SHORTAGE_REASON_REQUIRED')
    return by, discovery, final


def fixed_lf_order(document):
    rows = document.get('fixed_lf_inputs'); order = document.get('fixed_lf_order')
    require(isinstance(rows, list) and len(rows) <= 8 and isinstance(order, list), 'FIXED_LF_COUNT_CAP')
    required = {'input_id', 'display_text', 'sha256', 'origin_campaign', 'origin_slot',
                'origin_result_sha256', 'origin_response_id', 'origin_source_id',
                'origin_candidate', 'origin_path', 'origin_result_object'}
    for row in rows:
        require(isinstance(row, dict) and required <= set(row), 'FIXED_LF_FIELD_CONTRACT')
        require(all(isinstance(row[k], str) and bool(row[k].strip()) for k in
                    ('input_id', 'display_text', 'origin_slot', 'origin_response_id', 'origin_source_id')), 'FIXED_LF_STRING_FIELD')
        require(valid_sha256(row['sha256']) and sha(row['display_text'].encode()) == row['sha256']
                and valid_sha256(row['origin_result_sha256']), 'FIXED_LF_BYTE_SHA')
        require(row['origin_campaign'] == OLD_AB160 and row['origin_candidate'] == 'TONE_NAME'
                and row['origin_path'] == 'LF' and re.fullmatch(r'[SDF]-[0-9]{3}', row['origin_slot']) is not None,
                'FIXED_LF_ORIGIN_IDENTITY')
        require(row['origin_result_object'] == 'preparation/fixed_lf_results/' + row['origin_slot'] + '.json', 'FIXED_LF_OBJECT_PATH')
    by = {row['input_id']: row for row in rows}
    require(len(by) == len(rows) and len(order) == len(rows) and len(set(order)) == len(order)
            and set(order) == set(by), 'FIXED_LF_ORDER_IDS')
    require(set(by).isdisjoint(s['source_id'] for s in document['sources']), 'FIXED_LF_SOURCE_ID_COLLISION')
    for key in ('sha256', 'origin_slot', 'origin_response_id', 'origin_source_id', 'origin_result_object'):
        require(len({row[key] for row in rows}) == len(rows), 'DUPLICATE_FIXED_LF_ORIGIN')
    if len(rows) < 8:
        require(isinstance(document.get('fixed_lf_shortage_reason'), str)
                and bool(document['fixed_lf_shortage_reason'].strip()), 'FIXED_LF_SHORTAGE_REASON_REQUIRED')
    return by, order


def validate_fixed_lf_result(descriptor, raw):
    require(isinstance(raw, bytes) and sha(raw) == descriptor['origin_result_sha256'], 'FIXED_LF_RESULT_BYTE_SHA')
    result = json.loads(raw)
    require(isinstance(result, dict), 'FIXED_LF_RESULT_SCHEMA')
    mapping = {'campaign': 'origin_campaign', 'slot': 'origin_slot', 'response_id': 'origin_response_id',
               'source_id': 'origin_source_id', 'candidate': 'origin_candidate', 'path': 'origin_path'}
    require(all(result.get(key) == descriptor[value] for key, value in mapping.items()), 'FIXED_LF_RESULT_IDENTITY')
    require(result.get('success') is True and result.get('unknown') is False and result.get('send_invoked') is True
            and result.get('display_text') == descriptor['display_text'], 'FIXED_LF_NOT_ACTUAL_SUCCESS')
    checked = validate_result_metadata(dict(result))
    require(checked['success'] is True and not checked['metadata_errors'], 'FIXED_LF_TECHNICAL_METADATA')
    events = result.get('events')
    require(isinstance(events, list) and events and all(isinstance(e, dict) and isinstance(e.get('event'), dict) for e in events), 'FIXED_LF_EVENT_WRAPPERS')
    parsed = parse_events([e['event'] for e in events])
    require(parsed['success'] and parsed['display_text'] == descriptor['display_text']
            and parsed['usage'] == result['usage'], 'FIXED_LF_SSE_DISPLAY_MISMATCH')
    require(isinstance(result.get('raw_chunks_base64'), list) and result['raw_chunks_base64'], 'FIXED_LF_RAW_STREAM_REQUIRED')
    request = result.get('request')
    require(isinstance(request, dict) and set(request) == {'model','reasoning','instructions','input','stream','store','max_output_tokens','service_tier'}, 'FIXED_LF_REQUEST_SHAPE')
    require(request['model'] == MODEL and request['reasoning'] == {'effort':'none'}
            and request['stream'] is True and request['store'] is False and request['max_output_tokens'] == 4096
            and request['service_tier'] == 'default', 'FIXED_LF_REQUEST_MODEL_CONFIG')
    require(isinstance(request['input'], str) and isinstance(request['instructions'], str)
            and sha(request['instructions'].encode()) == EXPECTED_PROMPT_SHA256['L0']['LF'], 'FIXED_LF_PROMPT_SHA')
    require(sha(canon(request)) == result.get('request_sha256') and sha(request['input'].encode()) == result.get('input_sha256')
            and result.get('source_sha256') == result['input_sha256'], 'FIXED_LF_REQUEST_SHA')
    for field, target in (('origin_request_id','request_id'), ('origin_source_sha256','source_sha256')):
        if field in descriptor: require(descriptor[field] == result.get(target), 'FIXED_LF_EXTRA_LINEAGE_MISMATCH')
    require(type(result.get('raw_record_number')) is int and 1 <= result['raw_record_number'] <= 500, 'FIXED_LF_RAW_RECORD')
    return result


def final_selection(plan):
    if 'selected_candidate' not in plan:
        require(not plan.get('slots') and 'selection_evidence_sha256' not in plan, 'PENDING_FINAL_HAS_EXECUTABLE_PLAN')
        return False, None
    candidate = plan['selected_candidate']
    require(candidate is None or candidate in ('N1', 'N2'), 'FINAL_SELECTION_NOT_NONBASE')
    require(valid_sha256(plan.get('selection_evidence_sha256')), 'FINAL_SELECTION_EVIDENCE_SHA')
    if candidate is None or not plan.get('slots'):
        require(isinstance(plan.get('omitted_reason'), str) and bool(plan['omitted_reason'].strip()), 'OMITTED_FINAL_REASON_REQUIRED')
    return True, candidate


def validate_design(document, freeze, plans):
    require(document.get('campaign') == freeze.get('campaign') == CAMPAIGN, 'FOREIGN_FREEZE')
    require(type(freeze.get('approved_total')) is int and freeze['approved_total'] == APPROVED_TOTAL, 'APPROVED_TOTAL_MISMATCH')
    require(isinstance(plans, dict) and set(plans) == set(PHASES), 'PLAN_PHASE_SET')
    require(freeze.get('stage_caps') == HARD_CAPS and all(type(v) is int for v in freeze['stage_caps'].values()), 'FIXED_HARD_STAGE_CAPS')
    require(isinstance(freeze.get('order_rule'), str) and bool(freeze['order_rule'].strip()), 'ORDER_RULE_NOT_DOCUMENTED')
    by, discovery, final = selected_source_order(document)
    external, external_order = fixed_lf_order(document)
    metadata = freeze.get('metadata_sha256_by_object', {})
    exports = freeze.get('additional_export_objects', [])
    for row in external.values():
        require(metadata.get(row['origin_result_object']) == row['origin_result_sha256']
                and row['origin_result_object'] in exports, 'FIXED_LF_FROZEN_EXPORT_POINTER')
    for phase in PHASES:
        plan = plans[phase]
        require(isinstance(plan, dict) and plan.get('campaign') == CAMPAIGN and plan.get('phase') == phase
                and isinstance(plan.get('slots'), list), 'FOREIGN_OR_WRONG_PHASE_PLAN')
        if phase != 'F':
            require('selected_candidate' not in plan and 'selection_evidence_sha256' not in plan, 'NONFINAL_SELECTION_FIELDS')
    decided, selected = final_selection(plans['F'])
    require(selected is None or bool(discovery), 'FINAL_WITHOUT_DISCOVERY')
    effective = {'S': 6*len(discovery), 'F': 4*len(final) if decided and selected is not None else 0,
                 'L': 2*len(external_order)}
    validate_effective_caps(effective)
    all_ids = []
    for phase in PHASES:
        slots = plans[phase]['slots']
        require(len(slots) == effective[phase], 'PLAN_COUNT_VS_CAP')
        require([task.get('slot') for task in slots] == [f'{phase}-{i:03d}' for i in range(1,len(slots)+1)], 'NONCONTIGUOUS_SLOT_IDS')
        for task in slots:
            common = {'slot','candidate','path','repeat_index'}
            required = common | ({'input_id'} if phase == 'L' else {'source_id'})
            allowed = required if phase == 'L' else required | {'parent_first_id'}
            require(isinstance(task, dict) and required <= set(task) <= allowed, 'SLOT_FIELD_CONTRACT')
            require(type(task['repeat_index']) is int and task['repeat_index'] == 1, 'SINGLE_ATTEMPT_PER_CONDITION')
            all_ids.append(task['slot'])
        seen = []
        for index in range(0,len(slots),2):
            first, back = slots[index:index+2]
            if phase == 'L':
                require(first['input_id'] == back['input_id'] and first['input_id'] in external
                        and first['path'] == back['path'] == 'LB', 'FIXED_LB_PAIR_INPUT_PATH')
                seen.extend((row['input_id'],row['candidate']) for row in (first,back))
            else:
                require(first['source_id'] == back['source_id'] and first['source_id'] in by
                        and first['candidate'] == back['candidate'] and first['candidate'] in N_CANDIDATES, 'CHAIN_SOURCE_OR_CANDIDATE_MISMATCH')
                require(first['path'] == 'KF' and back['path'] == 'KB' and 'parent_first_id' not in first
                        and back.get('parent_first_id') == first['slot'], 'CHAIN_PARENT_NOT_PREVIOUS_FIRST')
                seen.append((first['source_id'],first['candidate']))
        if phase == 'S':
            expected = [(sid,candidate) for i,sid in enumerate(discovery) for candidate in cyclic_candidates(i)]
        elif phase == 'F':
            expected = [] if not decided or selected is None else [(sid,candidate) for i,sid in enumerate(final)
                       for candidate in (('N0',selected) if i%2==0 else (selected,'N0'))]
        else:
            expected = [(sid,candidate) for i,sid in enumerate(external_order)
                        for candidate in (L_CANDIDATES if i%2==0 else tuple(reversed(L_CANDIDATES)))]
        require(seen == expected, phase + '_EXACT_FROZEN_SOURCE_CANDIDATE_ORDER')
    require(len(set(all_ids)) == len(all_ids), 'DUPLICATE_CROSS_PHASE_SLOT')
    return dict(by, **external), effective
