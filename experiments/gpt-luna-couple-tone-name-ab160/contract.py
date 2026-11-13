"""Immutable, network-free contract for COUPLE_TONE_NAME_AB160 only.

Original messages and generated translations do not belong in this public code.
The private source document is separately frozen by SHA before the first request.
FINAL source selection is immutable; only its directional candidate decision is
appended after DISCOVERY. A pending FINAL and an intentionally empty FINAL are
different states and must remain distinguishable to the runner.
"""
import hashlib
import json
import math
import re

CAMPAIGN = 'GPT_LUNA_COUPLE_TONE_NAME_AB160_20261113'
MODEL = 'gpt-6-luna'
PHASES = ('S', 'D', 'F')
CANDIDATES = ('BASE', 'TONE', 'NAME', 'TONE_NAME')
PATHS = ('KF', 'KB', 'LF', 'LB')
FIRST_PATHS = ('KF', 'LF')
BACK_PATH = {'KF': 'KB', 'LF': 'LB'}
HARD_CAPS = {'S': 16, 'D': 112, 'F': 32}
APPROVED_TOTAL = 160

EXPECTED_PROMPT_SHA256 = {
    'BASE': {
        'KF': '6c8302be24fb7adb31161c0c76d2dfc5190aefb4fbc66e05a66f6dd7f1c0e297',
        'KB': '9f850340ef4be99eb022cc52055f631e56835f502666e3104468d19830e6d1a8',
        'LF': 'b902a50dcaa0c19c4b2d3a0b26a7dc02c9dc0a8cc9a3d0536ff02f9605d8febd',
        'LB': '0337f538b89bfb9ccbddc2d4737751cda319b8366ce0a66a070521d20fc9e92c',
    },
    'TONE': {
        'KF': 'f19a19ce1f6beddd0cd01b64786384c4a9a109e06f5f2234d0dda5f79a271331',
        'KB': 'd0c572a60e334e255a883e6836841a830ff966e64e1970371a1dc151570d03da',
        'LF': 'b0c37520ae78e565aefa754fa34ce64c9969f5259bb680fc8afc8ac78010b679',
        'LB': '79bcf723eab1b188c73bd9558e7f7e566d5227d5ae1acb1d545143f5874164ba',
    },
    'NAME': {
        'KF': '812804499856e31cd70bd4571d3791d3a2159f725b6f5f798069c78df1606194',
        'KB': '4ecf671709652818bc0b432645210e8e498305b8fa8fb851eedcfd8dbed23300',
        'LF': '7326ba1bfa92af0ceedc625fa967e15ed26deaf907120ad54ba4b820ecc30d1f',
        'LB': 'e886d786989168d2b8a9b343ec2d6886ef759aeddfdbacda8d82beaaf5440968',
    },
    'TONE_NAME': {
        'KF': '127c41170be95c9256f3c0436f5c6bc45a365ed3793f7ae2168bf9b979655a07',
        'KB': '65a28bf4b6d3d1d27090f198396c88805caf4b98a00e2c296dee87d17de86121',
        'LF': '4398966a9339ba3a7bf075f5c26f4b8636fc03194e56942b56bd0a81ae3eaa3f',
        'LB': '24f0b00ba4f6a73e148f14d0cfa02b575f5344d07f8d8403f4f0416b778c1f1a',
    },
}


def canon(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode('utf-8')


def sha(value):
    return hashlib.sha256(value).hexdigest()


def require(condition, code):
    if not condition:
        raise AssertionError(code)


def valid_sha256(value):
    return isinstance(value, str) and re.fullmatch(r'[0-9a-f]{64}', value) is not None


def validate_prompts(prompts):
    require(isinstance(prompts, dict) and set(prompts) == set(CANDIDATES), 'PROMPT_CANDIDATE_SET')
    for candidate in CANDIDATES:
        require(isinstance(prompts[candidate], dict) and set(prompts[candidate]) == set(PATHS), 'PROMPT_PATH_SET')
        for path in PATHS:
            value = prompts[candidate][path]
            require(isinstance(value, str), 'PROMPT_NOT_STRING')
            require(sha(value.encode('utf-8')) == EXPECTED_PROMPT_SHA256[candidate][path], 'PROMPT_BYTE_SHA')


def build_payload(model, effort, path, text, prompts):
    require(model == MODEL and effort == 'none', 'MODEL_OR_EFFORT_NOT_APPROVED')
    require(path in PATHS and isinstance(text, str) and bool(text.strip()), 'INVALID_REQUEST_TEXT')
    require(isinstance(prompts, dict) and isinstance(prompts.get(path), str), 'PATH_PROMPT_MISSING')
    return dict(model=model, reasoning={'effort': effort}, instructions=prompts[path],
                input=text, stream=True, store=False, max_output_tokens=4096, service_tier='default')


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


def validate_effective_caps(effective_caps):
    require(isinstance(effective_caps, dict) and set(effective_caps) == set(PHASES), 'EFFECTIVE_CAP_KEYS')
    require(all(type(effective_caps[p]) is int for p in PHASES), 'EFFECTIVE_CAP_TYPE')
    require(effective_caps['S'] == 16 and effective_caps['D'] == 112
            and effective_caps['F'] in (0, 16, 32), 'STAGE_CAP_NO_REALLOCATION')


def budget_guard(reservations, slot, phase, effective_caps):
    require(phase in PHASES, 'UNAPPROVED_PHASE')
    validate_effective_caps(effective_caps)
    require(isinstance(reservations, list), 'RESERVATION_LIST')
    require(len(reservations) < APPROVED_TOTAL, 'CAMPAIGN_CAP')
    require(isinstance(slot, str) and re.fullmatch(phase + r'-[0-9]{3}', slot) is not None
            and 1 <= int(slot[2:]) <= HARD_CAPS[phase], 'INVALID_SLOT')
    for ordinal, record in enumerate(reservations, 1):
        require(isinstance(record, dict) and record.get('campaign') == CAMPAIGN
                and record.get('model') == MODEL and record.get('stage') in PHASES
                and record.get('ordinal') == ordinal, 'FOREIGN_OR_INVALID_RESERVATION')
    require(len({r['slot'] for r in reservations}) == len(reservations), 'DUPLICATE_EXISTING_RESERVATION')
    require(slot not in {r['slot'] for r in reservations}, 'DUPLICATE_SLOT')
    for stage in PHASES:
        count = sum(r['stage'] == stage for r in reservations)
        require(count <= effective_caps[stage], 'EXISTING_STAGE_CAP_EXCEEDED')
    require(sum(r['stage'] == phase for r in reservations) < effective_caps[phase], 'STAGE_CAP_NO_REALLOCATION')
    return {'campaign': CAMPAIGN, 'model': MODEL, 'slot': slot, 'stage': phase,
            'ordinal': len(reservations) + 1, 'state': 'RESERVED_TRANSMISSION_UNKNOWN'}


def cyclic_candidates(source_index):
    offset = source_index % len(CANDIDATES)
    return CANDIDATES[offset:] + CANDIDATES[:offset]


def selected_source_order(source_document):
    sources = source_document.get('sources')
    require(isinstance(sources, list) and len(sources) == 24, 'SOURCE_COUNT_24_REQUIRED')
    required = {'source_id', 'source', 'sha256', 'direction', 'split', 'raw_record_number',
                'class', 'duplicate_group', 'prior_exposure', 'audit_case', 'luna_test'}
    for source in sources:
        require(isinstance(source, dict) and required <= set(source), 'SOURCE_FIELD_CONTRACT')
        require(all(isinstance(source[k], str) and bool(source[k].strip())
                    for k in ('source_id', 'source', 'class', 'duplicate_group')), 'SOURCE_STRING_FIELD')
        require(valid_sha256(source['sha256']) and sha(source['source'].encode('utf-8')) == source['sha256'], 'SOURCE_BYTE_SHA')
        require(source['direction'] in FIRST_PATHS and source['split'] in ('DISCOVERY', 'FINAL'), 'SOURCE_SPLIT_DIRECTION')
        require(type(source['raw_record_number']) is int and 1 <= source['raw_record_number'] <= 500, 'RAW_RECORD_NUMBER')
        require(all(type(source[k]) is bool for k in ('prior_exposure', 'audit_case', 'luna_test')), 'EXPOSURE_FLAG_TYPE')
        require(not (source['audit_case'] or source['luna_test']) or source['prior_exposure'], 'EXPOSURE_FLAG_INCONSISTENT')
    by = {s['source_id']: s for s in sources}
    require(len(by) == len(sources), 'DUPLICATE_SOURCE_ID')
    for key, code in (('sha256', 'DUPLICATE_SOURCE_BYTES'),
                      ('duplicate_group', 'DUPLICATE_SELECTED_EVENT'),
                      ('raw_record_number', 'DUPLICATE_RAW_RECORD')):
        require(len({s[key] for s in sources}) == len(sources), code)
    selection = source_document.get('selection')
    require(isinstance(selection, dict) and set(selection) == {'discovery_order', 'smoke_order', 'final_order'}, 'SELECTION_SCHEMA')
    discovery = selection['discovery_order']; smoke = selection['smoke_order']; final = selection['final_order']
    for order, size in ((discovery, 16), (smoke, 2), (final, 8)):
        require(isinstance(order, list) and len(order) == size
                and all(isinstance(sid, str) for sid in order) and len(set(order)) == size
                and set(order) <= set(by), 'SELECTION_COUNT_OR_IDS')
    require(set(discovery).isdisjoint(final) and set(discovery + final) == set(by), 'SOURCE_SELECTION_PARTITION')
    require(all(by[sid]['split'] == 'DISCOVERY' for sid in discovery)
            and all(by[sid]['split'] == 'FINAL' for sid in final), 'SELECTION_SPLIT_MISMATCH')
    for direction in FIRST_PATHS:
        require(sum(by[sid]['direction'] == direction for sid in discovery) == 8
                and sum(by[sid]['direction'] == direction for sid in final) == 4, 'SOURCE_DIRECTION_QUOTA')
    require(set(smoke) <= set(discovery) and [by[sid]['direction'] for sid in smoke] == ['KF', 'LF'], 'SMOKE_DIRECTION_ORDER')
    require(sum(by[sid]['audit_case'] for sid in discovery) <= 4, 'DISCOVERY_AUDIT_EXPOSURE_CAP')
    require(sum(by[sid]['prior_exposure'] for sid in discovery) <= 4, 'DISCOVERY_PRIOR_EXPOSURE_CAP')
    require(all(not any(by[sid][key] for key in ('prior_exposure', 'audit_case', 'luna_test'))
                for sid in final), 'FINAL_EXPOSURE_FORBIDDEN')
    return by, discovery, smoke, final


def final_selection(plan):
    """None means pending; a two-key dict, including two nulls, means selected."""
    if 'selected_candidates' not in plan:
        require(not plan.get('slots') and 'selection_evidence_sha256' not in plan, 'PENDING_FINAL_HAS_EXECUTABLE_PLAN')
        return None
    selected = plan['selected_candidates']
    require(isinstance(selected, dict) and set(selected) == set(FIRST_PATHS), 'FINAL_SELECTION_DIRECTION_KEYS')
    require(all(value is None or value in CANDIDATES[1:] for value in selected.values()), 'FINAL_SELECTION_NOT_NONBASE')
    require(valid_sha256(plan.get('selection_evidence_sha256')), 'FINAL_SELECTION_EVIDENCE_SHA')
    return selected


def validate_design(source_document, freeze, plans):
    require(source_document.get('campaign') == freeze.get('campaign') == CAMPAIGN, 'FOREIGN_FREEZE')
    require(type(freeze.get('approved_total')) is int and freeze['approved_total'] == APPROVED_TOTAL, 'APPROVED_TOTAL_MISMATCH')
    require(isinstance(plans, dict) and set(plans) == set(PHASES), 'PLAN_PHASE_SET')
    require(freeze.get('stage_caps') == HARD_CAPS
            and all(type(v) is int for v in freeze['stage_caps'].values()), 'FIXED_HARD_STAGE_CAPS')
    require(isinstance(freeze.get('order_rule'), str) and bool(freeze['order_rule'].strip()), 'ORDER_RULE_NOT_DOCUMENTED')
    by, discovery, smoke, final = selected_source_order(source_document)
    for phase in PHASES:
        plan = plans[phase]
        require(isinstance(plan, dict) and plan.get('campaign') == CAMPAIGN and plan.get('phase') == phase, 'FOREIGN_OR_WRONG_PHASE_PLAN')
        require(isinstance(plan.get('slots'), list), 'PLAN_SLOTS_TYPE')
        if phase != 'F':
            require('selected_candidates' not in plan and 'selection_evidence_sha256' not in plan, 'NONFINAL_SELECTION_FIELDS')
    selected = final_selection(plans['F'])
    effective = {'S': 16, 'D': 112, 'F': 0 if selected is None else 16 * sum(value is not None for value in selected.values())}
    validate_effective_caps(effective)
    all_ids = []
    required_slot_keys = {'slot', 'source_id', 'candidate', 'path', 'repeat_index'}
    allowed_slot_keys = required_slot_keys | {'parent_first_id'}
    for phase in PHASES:
        slots = plans[phase]['slots']
        require(len(slots) == effective[phase], 'PLAN_COUNT_VS_CAP')
        require(all(isinstance(task, dict) and required_slot_keys <= set(task) <= allowed_slot_keys for task in slots), 'SLOT_FIELD_CONTRACT')
        require([task['slot'] for task in slots] == [f'{phase}-{i:03d}' for i in range(1, len(slots) + 1)], 'NONCONTIGUOUS_SLOT_IDS')
        for task in slots:
            require(task['source_id'] in by and task['candidate'] in CANDIDATES and task['path'] in PATHS, 'UNAPPROVED_SLOT_IDENTITY')
            require(type(task['repeat_index']) is int and task['repeat_index'] == 1, 'SINGLE_ATTEMPT_PER_CONDITION')
            all_ids.append(task['slot'])
        seen = []
        for index in range(0, len(slots), 2):
            first, back = slots[index:index + 2]
            require(first['source_id'] == back['source_id'] and first['candidate'] == back['candidate'], 'CHAIN_SOURCE_OR_CANDIDATE_MISMATCH')
            require(first['path'] == by[first['source_id']]['direction']
                    and first['path'] in FIRST_PATHS and back['path'] == BACK_PATH[first['path']], 'CHAIN_PATH_MISMATCH')
            require('parent_first_id' not in first and back.get('parent_first_id') == first['slot'], 'CHAIN_PARENT_NOT_PREVIOUS_FIRST')
            seen.append((first['source_id'], first['candidate']))
        if phase in ('S', 'D'):
            order = smoke if phase == 'S' else [sid for sid in discovery if sid not in smoke]
            expected = [(sid, candidate) for sid in order for candidate in cyclic_candidates(discovery.index(sid))]
        else:
            expected = []
            if selected is not None:
                direction_index = {direction: 0 for direction in FIRST_PATHS}
                for sid in final:
                    direction = by[sid]['direction']
                    source_index = direction_index[direction]
                    direction_index[direction] += 1
                    candidate = selected[direction]
                    if candidate is None: continue
                    pair = ('BASE', candidate) if source_index % 2 == 0 else (candidate, 'BASE')
                    expected.extend((sid, item) for item in pair)
        require(seen == expected, phase + '_EXACT_FROZEN_SOURCE_CANDIDATE_ORDER')
    require(len(set(all_ids)) == len(all_ids), 'DUPLICATE_CROSS_PHASE_SLOT')
    return by, effective
