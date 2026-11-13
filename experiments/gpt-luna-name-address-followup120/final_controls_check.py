"""Read-only FOLLOWUP120 terminal/ledger/freeze audit. No generation, writes, or key reads."""
import concurrent.futures
import copy
import hashlib
import json
import os
import pathlib

CAMPAIGN = 'GPT_LUNA_NAME_ADDRESS_FOLLOWUP120_20261114'
MODEL = 'gpt-6-luna'
ROOT = 'research/gemini-model-native500-20261107/'
PREFIX = ROOT + 'gpt-luna-name-address-followup120-20261114/'
PHASES = ('S', 'F', 'L')
HARD_CAPS = {'S': 72, 'F': 32, 'L': 16}
TOTAL = 120
COUNT_KEYS = ('reserved', 'success', 'failed', 'unknown', 'transmitted_recorded')
PREVIOUS = {
    'gpt-luna-p168a-transfer320-20261111': (288, 'fc34dfbb85dc46578ed9ca36c8881cea869b7727a4a88d200e0d42adfb8e6c31'),
    'gpt-luna-source-variant320-20261110': (290, '99bf3ffcf49186ef932b62c2089105b7bd0e3747accadc8bc53dc061e7b1068a'),
    'gpt-source-vs-prompt-factorial320-20261111': (264, '705e2a46c40305bc7c454b696d0803b503a469e8fecd754cfbf424ad1113d06f'),
    'gpt-luna-lf-variance320-20261110': (264, '926605041232b680d8011fffaba9b17effe0c308fd9fe7029ba5161dc2716663'),
    'gpt-luna-terra-mechanism1000-20261110': (776, '323c3e727c1aee812d23423ea1ed885db50a39dcf4203a4c1bf47810f366290e'),
}
RECENT = (
    ('gpt-luna-gd-scope-screen80-20261112', 'GPT_LUNA_GD_SCOPE_SCREEN80_20261112', 'PAUSED', 0, 80, 'old_screen_sha256', '8434a8e50989a3ffcc1854fb4ce12fe7289696fa208c17e853a3fc0adac048d1'),
    ('gpt-luna-gd-realchat80-20261112', 'GPT_LUNA_GD_REALCHAT80_20261112', 'CLOSED', 68, 12, 'old_realchat_sha256', 'd8b41bda835e084a965ff035f4a1e412ccb337c2a57629d325cdfad4c42b50a2'),
    ('gpt-luna-couple-tone-name-ab160-20261113', 'GPT_LUNA_COUPLE_TONE_NAME_AB160_20261113', 'CLOSED', 160, 0, 'old_ab160_sha256', '90215a127a3a2093dd94a8e3ca0dca4b50b4bf0f435160dd0a614d8c63d4150e'),
    ('gpt-luna-m1-gd-headtohead80-20261112', 'GPT_LUNA_M1_GD_HEADTOHEAD80_20261112', 'CLOSED', 72, 8, 'old_m1_headtohead_sha256', '424ffee4ce4a0753772061c1616817744edc6565be78f09a0d3bb143d6427430'),
)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def canon(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode()


def require(ok, code):
    if not ok:
        raise AssertionError(code)


def check_state(get, control):
    """get(full_object_name) returns bytes or None for NotFound only.

    A missing result after an existing reservation is charged UNKNOWN. Other read
    failures must propagate; they must never be converted into object absence.
    """
    from contract import build_payload, validate_design, validate_prompts, validate_result_metadata, valid_sha256, validate_fixed_lf_result, parse_events
    require(control.get('campaign') == CAMPAIGN and control.get('approved_total') == TOTAL
            and control.get('mode') == 'CLOSE' and control.get('enabled') is False
            and control.get('max_new') == 0, 'CLOSE_CONTROL')
    require(type(control.get('research_complete')) is bool, 'COMPLETE_FLAG_TYPE')
    cache = {}

    def raw(name, optional=False):
        if name not in cache:
            cache[name] = get(name)
        value = cache[name]
        require(value is None or isinstance(value, bytes), 'READBACK_NOT_BYTES')
        require(value is not None or optional, 'REQUIRED_OBJECT_MISSING')
        return value

    def own(name, optional=False):
        return raw(PREFIX + name, optional)

    def read(name):
        return json.loads(own(name))

    preflight_raw = own('preflight/PREFLIGHT.json')
    require(control.get('preflight_object') == 'preflight/PREFLIGHT.json'
            and sha(preflight_raw) == control['preflight_sha256'], 'PREFLIGHT_SHA_CHANGED')
    preflight = json.loads(preflight_raw)
    require(preflight['campaign'] == CAMPAIGN and preflight['generation_calls'] == 0
            and preflight['owner_token'] == control['owner_token'], 'PREFLIGHT_IDENTITY')
    old_ab_name = 'gpt-luna-couple-tone-name-ab160-20261113'
    require(set(preflight['old_closed']) == set(PREVIOUS) | {old_ab_name}, 'OLD_CAMPAIGN_SET')
    require(preflight['old_closed'][old_ab_name]['sha256'] == preflight['old_ab160_sha256']
            and preflight['old_closed'][old_ab_name]['reserved_total'] == 160
            and preflight.get('old_ab160_actual') == 160 and preflight.get('old_ab160_unused_locked') == 0,
            'OLD_AB160_PREFLIGHT_ENTRY')
    protected = {}
    for name, (count, digest) in PREVIOUS.items():
        data = raw(ROOT + name + '/states/CLOSED_LOCKED.json'); state = json.loads(data)
        require(sha(data) == digest == preflight['old_closed'][name]['sha256'], 'OLD_CLOSED_BYTES_CHANGED')
        require(state['status'] == 'CLOSED_LOCKED' and state['enabled'] is False
                and state['max_new'] == 0 and state['reserved_total'] == count, 'OLD_CLOSED_STATE')
        dual = None
        if name != 'gpt-luna-terra-mechanism1000-20261110':
            dual = raw(ROOT + name + '/controls/CLOSED/CLOSED_LOCKED.json') == data
            require(dual, 'OLD_DUAL_AUTHORITY')
        protected[name] = {'sha256': digest, 'status': state['status'], 'reserved_total': count,
                           'dual_authority_bytes_equal': dual, 'sha_equal_to_preflight': True}
    for name, campaign, status, count, unused, key, digest in RECENT:
        data = raw(ROOT + name + '/states/' + status + '_LOCKED.json'); state = json.loads(data)
        require(sha(data) == digest == preflight[key], 'PROTECTED_RECENT_BYTES_CHANGED')
        require(raw(ROOT + name + '/controls/' + status + '/' + status + '_LOCKED.json') == data, 'PROTECTED_RECENT_DUAL_AUTHORITY')
        require(state['campaign'] == campaign and state['status'] == status + '_LOCKED'
                and state['enabled'] is False and state['max_new'] == 0
                and state['reserved_total'] == count and state['unused_locked'] == unused, 'PROTECTED_RECENT_COUNTS')
        protected[name] = {'sha256': digest, 'status': state['status'], 'reserved_total': count,
                           'unused_locked': unused, 'enabled': False, 'max_new': 0,
                           'dual_authority_bytes_equal': True, 'sha_equal_to_preflight': True}

    source_raw = own('preparation/SOURCES.json'); prompts_raw = own('preparation/PROMPTS.json')
    freeze_raw = own('preparation/FREEZE.json')
    require(sha(source_raw) == control['source_sha256'], 'SOURCE_BYTES_CHANGED')
    require(sha(prompts_raw) == control['prompts_sha256'], 'PROMPT_BYTES_CHANGED')
    require(sha(freeze_raw) == control['freeze_sha256'], 'FREEZE_CHANGED')
    source_document = json.loads(source_raw); prompts = json.loads(prompts_raw); freeze = json.loads(freeze_raw)
    require(freeze['sources_sha256'] == sha(source_raw) and freeze['prompts_sha256'] == sha(prompts_raw), 'FREEZE_POINTERS_CHANGED')
    require(set(freeze['plan_sha256_by_phase']) == set(PHASES), 'FROZEN_PLAN_PHASE_SET')
    plans = {}; plan_hashes = {}
    for phase, digest in freeze['plan_sha256_by_phase'].items():
        require(valid_sha256(digest), 'INVALID_PLAN_SHA')
        data = own('plans/' + digest + '.json'); require(sha(data) == digest, 'PLAN_BYTES_CHANGED')
        plans[phase] = json.loads(data); plan_hashes[phase] = digest
    require('selected_candidate' not in plans['F'] and not plans['F'].get('slots'), 'INITIAL_FINAL_NOT_PENDING')
    metadata = freeze.get('metadata_sha256_by_object', {})
    require(isinstance(metadata, dict), 'METADATA_SHA_MAP')
    for name, digest in metadata.items():
        require(isinstance(name, str) and name.startswith('preparation/') and '..' not in name
                and name.endswith('.json') and valid_sha256(digest), 'METADATA_OBJECT_PATH_OR_SHA')
        require(sha(own(name)) == digest, 'FROZEN_METADATA_CHANGED')
    for name in freeze.get('additional_export_objects', []):
        if name.startswith('preparation/') and name not in ('preparation/SOURCES.json', 'preparation/PROMPTS.json', 'preparation/FREEZE.json'):
            require(name in metadata, 'METADATA_NOT_HASH_FROZEN')
    selection_raw = own('selection/FINAL_PLAN.json', True); selection_evidence = None
    if selection_raw is not None:
        selected = json.loads(selection_raw)
        evidence_raw = own('selection/FINAL_SELECTION.json')
        require(sha(evidence_raw) == selected['selection_evidence_sha256'], 'FINAL_SELECTION_EVIDENCE_SHA')
        selection_evidence = json.loads(evidence_raw)
        require(selection_evidence['campaign'] == CAMPAIGN
                and selection_evidence['sources_sha256'] == sha(source_raw)
                and selection_evidence['freeze_sha256'] == sha(freeze_raw)
                and selection_evidence['prior_reserved'] == len(plans['S']['slots'])
                and selection_evidence['selected_candidate'] == selected['selected_candidate'], 'FINAL_SELECTION_IDENTITY')
        require(selection_evidence.get('review_complete') is True
                and type(selection_evidence.get('generation_api_judge_calls')) is int
                and selection_evidence['generation_api_judge_calls'] == 0, 'FINAL_SELECTION_REVIEW_PROOF')
        if selected['selected_candidate'] is None or not selected.get('slots'):
            require(selection_evidence.get('omitted_reason') == selected.get('omitted_reason')
                    and bool(selection_evidence.get('omitted_reason')), 'OMITTED_FINAL_EVIDENCE')
        plans['F'] = selected; plan_hashes['F'] = sha(selection_raw)
    else:
        require(own('selection/FINAL_SELECTION.json', True) is None, 'ORPHAN_FINAL_SELECTION')
    sources, effective = validate_design(source_document, freeze, plans)
    validate_prompts(prompts)
    external_response_ids = set()
    for descriptor in source_document['fixed_lf_inputs']:
        result = validate_fixed_lf_result(descriptor, own(descriptor['origin_result_object']))
        sources[descriptor['input_id']] = dict(descriptor, _origin_result=result)
        external_response_ids.add(result['response_id'])
    require(control.get('phase') in PHASES and control['plan_sha256'] == plan_hashes[control['phase']], 'CLOSE_PLAN_POINTER')

    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as pool:
        budget_raw = list(pool.map(lambda i: own(f'budget/{i:04d}.json', True), range(1, TOTAL + 1)))
    records = [json.loads(value) for value in budget_raw if value is not None]
    total = len(records)
    require(all(value is not None for value in budget_raw[:total]) and all(value is None for value in budget_raw[total:]), 'NONCONTIGUOUS_LEDGER')
    require(total == control['prior_reserved'] and len({r['slot'] for r in records}) == total, 'RESERVATION_COUNT_OR_DUPLICATE')
    ordered_tasks = [task for phase in PHASES for task in plans[phase]['slots']]
    require([r['slot'] for r in records] == [task['slot'] for task in ordered_tasks[:total]], 'LEDGER_FROZEN_SLOT_ORDER')
    require(total <= len(ordered_tasks) <= TOTAL, 'LEDGER_EXCEEDS_FROZEN_PLAN')
    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as pool:
        result_raw = list(pool.map(lambda record: own('results/' + record['slot'] + '.json', True), records))
        request_raw = list(pool.map(lambda record: own('requests/' + record['slot'] + '.json'), records))
    results = {record['slot']: json.loads(data) for record, data in zip(records, result_raw) if data is not None}
    counts = {phase: {key: 0 for key in COUNT_KEYS} for phase in PHASES}
    response_ids = set()
    for ordinal, (record, task, req_raw, res_raw) in enumerate(zip(records, ordered_tasks, request_raw, result_raw), 1):
        phase = task['slot'][0]; sid = task['input_id'] if phase == 'L' else task['source_id']
        candidate = task['candidate']; path = task['path']; source = sources[sid]
        require(record['campaign'] == CAMPAIGN and record['model'] == MODEL
                and record['ordinal'] == ordinal and record['stage'] == phase, 'RESERVATION_IDENTITY')
        require(all(record[key] == task[key] for key in ('slot','candidate','path','repeat_index'))
                and record['source_id'] == sid, 'RESERVATION_TASK_MISMATCH')
        request = json.loads(req_raw); payload = request['request']
        if phase == 'L':
            parent = source['_origin_result']; text = source['display_text']
            require(record['input_id'] == sid and record['source_kind'] == 'FIXED_LF_OUTPUT'
                    and record['source_direction'] == 'LF' and record['raw_record_number'] == parent['raw_record_number'], 'FIXED_LF_RESERVATION_SOURCE')
            for key in ('origin_campaign','origin_slot','origin_result_sha256','origin_response_id','origin_source_id'):
                require(record[key] == source[key], 'FIXED_LF_RESERVATION_LINEAGE')
            require(record['origin_source_sha256'] == parent['source_sha256'], 'FIXED_LF_ORIGIN_SOURCE_SHA')
        else:
            require(record['source_kind'] == 'ORIGINAL_KF' and record['source_direction'] == 'KF'
                    and record['raw_record_number'] == source['raw_record_number'], 'RESERVATION_SOURCE_METADATA')
            if path == 'KF':
                text = source['source']; parent = None
            else:
                require(path == 'KB', 'FORBIDDEN_NEW_LF_PATH')
                parent = results.get(task['parent_first_id'])
                require(parent is not None and parent['success'] is True and parent['unknown'] is False
                        and parent['campaign'] == CAMPAIGN and parent['source_id'] == sid
                        and parent['candidate'] == candidate and parent['path'] == 'KF'
                        and parent['stage'] == phase, 'BACK_WITHOUT_MATCHING_FIRST')
                text = parent['display_text']
        require(record['source_sha256'] == source['sha256'], 'RESERVATION_SOURCE_SHA')
        expected_payload = build_payload(MODEL, 'none', path, text, prompts[candidate])
        require(payload == expected_payload, 'REQUEST_INPUT_PROMPT_OR_HIDDEN_CONTEXT')
        require(request['campaign'] == CAMPAIGN and request['slot'] == task['slot']
                and request['request_sha256'] == record['request_sha256'] == sha(canon(payload))
                and request['input_sha256'] == record['input_sha256'] == sha(text.encode())
                and record['prompt_sha256'] == sha(prompts[candidate][path].encode()), 'REQUEST_RESERVATION_SHA')
        row = counts[phase]; row['reserved'] += 1
        if res_raw is None:
            row['unknown'] += 1
            continue
        result = results[record['slot']]
        require(all(result.get(key) == record[key] for key in ('campaign', 'model', 'slot', 'stage', 'ordinal', 'source_id', 'candidate', 'path', 'repeat_index', 'source_sha256', 'source_direction', 'source_kind', 'raw_record_number', 'request_sha256', 'input_sha256')), 'RESULT_LEDGER_MISMATCH')
        require(result['request'] == payload and result.get('prompt_candidate') == candidate
                and result['prompt_sha256'] == record['prompt_sha256'], 'RESULT_REQUEST_OR_PROMPT')
        require(type(result.get('http_attempts')) is int and result['http_attempts'] == 1
                and result.get('send_invoked') is True, 'RESULT_SINGLE_TRANSMISSION')
        require(type(result.get('success')) is bool and type(result.get('unknown')) is bool
                and not (result['success'] and result['unknown']), 'RESULT_STATUS_FLAGS')
        recomputed = validate_result_metadata(copy.deepcopy(result))
        require(recomputed['success'] == result['success'] and recomputed['unknown'] == result['unknown'], 'RESULT_STATUS_METADATA_CONFLICT')
        if parent is not None:
            require(result.get('back_input_equals_displayed_first') is True
                    and result.get('displayed_first_sha256') == sha(text.encode()), 'BACK_DISPLAYED_INPUT_SHA')
            if phase == 'L':
                fields = ('input_id','origin_campaign','origin_slot','origin_result_sha256','origin_response_id','origin_source_id','origin_source_sha256')
                require(result.get('parent_first_id') is None and result.get('back_parent_kind') == 'EXTERNAL_FIXED_LF'
                        and result.get('external_first') == {key:record[key] for key in fields}
                        and all(result.get(key) == record[key] for key in fields), 'FIXED_LF_RESULT_LINEAGE')
            else:
                require(result.get('parent_first_id') == parent['slot']
                        and result.get('back_parent_kind') == 'NEW_CAMPAIGN_FIRST'
                        and 'external_first' not in result, 'BACK_PARENT_METADATA')
        else:
            require(result.get('parent_first_id') is None and result.get('back_parent_kind') is None
                    and 'external_first' not in result, 'FIRST_HAS_PARENT')
        if result['success']:
            response = result.get('response')
            require(result.get('http_status') == 200 and result.get('terminal') == 'response.completed'
                    and isinstance(response, dict) and response.get('status') == 'completed', 'SUCCESS_TERMINAL_METADATA')
            require(response.get('id') == result['response_id'] and response.get('model') == result['actual_model']
                    and response.get('service_tier') == result['actual_service_tier']
                    and response.get('usage') == result['usage'], 'RESPONSE_METADATA_MISMATCH')
            events = result.get('events')
            require(isinstance(events, list) and all(isinstance(e, dict) and isinstance(e.get('event'), dict) for e in events), 'SUCCESS_SSE_EVENTS_REQUIRED')
            parsed = parse_events([event['event'] for event in events])
            require(parsed['success'] and parsed['display_text'] == result['display_text']
                    and parsed['usage'] == result['usage'], 'SUCCESS_SSE_DISPLAY_MISMATCH')
            require(result['response_id'] not in response_ids and result['response_id'] not in external_response_ids,
                    'DUPLICATE_OR_HISTORICAL_RESPONSE_ID')
            response_ids.add(result['response_id'])
        row['transmitted_recorded'] += 1
        row['unknown' if result['unknown'] else 'success' if result['success'] else 'failed'] += 1
    totals = {key: sum(row[key] for row in counts.values()) for key in COUNT_KEYS}
    if selection_evidence is not None:
        expected_slots = {task['slot'] for task in plans['S']['slots']}
        require(set(selection_evidence['discovery_result_sha256_by_slot']) == expected_slots, 'FINAL_DISCOVERY_RESULT_SET')
        for slot, digest in selection_evidence['discovery_result_sha256_by_slot'].items():
            require(sha(own('results/' + slot + '.json')) == digest
                    and results.get(slot, {}).get('success') is True, 'FINAL_DISCOVERY_NOT_ALL_SUCCESS')
        require(counts['S']['success'] == effective['S'], 'FINAL_BEFORE_ALL_DISCOVERY_SUCCESS')

    closed_raw = own('states/CLOSED_LOCKED.json'); closed = json.loads(closed_raw)
    require(own('controls/CLOSED/CLOSED_LOCKED.json') == closed_raw, 'NEW_DUAL_AUTHORITY')
    complete = control['research_complete']
    require(closed['campaign'] == CAMPAIGN and closed['status'] == 'CLOSED_LOCKED'
            and closed['enabled'] is False and closed['max_new'] == 0 and closed['approved_total'] == TOTAL
            and closed['ledger_resolved'] is True and closed['research_complete'] is complete
            and closed['owner_token'] == preflight['owner_token'] and closed['next_new_authorization'] == 0
            and closed['generation_calls'] == 0, 'NEW_CLOSED_STATE')
    require(closed['reserved_total'] == total and closed['unused_locked'] == TOTAL - total
            and all(closed[key] == totals[key] for key in ('success', 'failed', 'unknown'))
            and closed['actual_api_attempts_recorded'] == totals['transmitted_recorded'], 'NEW_CLOSED_COUNTS')
    require(closed['stage_caps'] == effective and closed['hard_stage_caps'] == HARD_CAPS
            and closed['stage_counts'] == counts, 'NEW_STAGE_COUNTS')
    require(closed.get('selected_final_candidate') == plans['F'].get('selected_candidate')
            and closed.get('final_omitted_reason') == plans['F'].get('omitted_reason'), 'CLOSED_FINAL_SELECTION')
    if complete:
        require(selection_raw is not None and totals['failed'] == totals['unknown'] == 0
                and total == sum(effective.values()), 'INCOMPLETE_REPORTED_COMPLETE')
        for phase in PHASES:
            state = read('states/' + phase + '-finished.json')
            require(state['status'] == 'CHECKPOINT_LOCKED' and state['enabled'] is False and state['max_new'] == 0
                    and state['ledger_resolved'] is True and not state.get('skips')
                    and counts[phase]['reserved'] == counts[phase]['success'] == effective[phase], 'INCOMPLETE_PHASE')
            require(own('locks/' + phase + '.RELEASED.json') == own('locks/' + phase + '.json'), 'PHASE_RELEASE_BYTES')
    else:
        require(isinstance(closed.get('closure_reason'), str) and bool(closed['closure_reason'].strip())
                and closed['closure_reason'] == control.get('closure_reason'), 'PARTIAL_CLOSURE_REASON')
    gate_raw = own('gates/CLOSE.json'); gate = json.loads(gate_raw)
    require(control.get('backup_verified') is True and control.get('backup_receipt_object') == 'gates/CLOSE.json'
            and sha(gate_raw) == control['backup_receipt_sha256'], 'CLOSE_BACKUP_RECEIPT_SHA')
    require(gate['campaign'] == CAMPAIGN and gate['phase'] == 'CLOSE' and gate['prior_reserved'] == total
            and all(gate.get(key) is True for key in ('verified', 'drive_readback_verified', 'owner_only', 'sha256_verified', 'zip_crc_verified', 'manifest_verified')), 'CLOSE_BACKUP_NOT_VERIFIED')

    previous = control.get('previous_phase')
    require(previous in PHASES and gate.get('previous_phase') == previous, 'CLOSE_PREVIOUS_PHASE')
    if complete: require(previous == 'L', 'COMPLETE_CLOSE_PREVIOUS_NOT_L')
    previous_raw = own('states/' + previous + '-finished.json')
    previous_state = json.loads(previous_raw)
    require(sha(previous_raw) == gate['previous_state_sha256'] and previous_state['enabled'] is False
            and previous_state['max_new'] == 0 and previous_state['ledger_resolved'] is True
            and previous_state['reserved_total'] == total, 'CLOSE_PREVIOUS_STATE_SHA')
    require(own('locks/' + previous + '.RELEASED.json') == own('locks/' + previous + '.json'), 'CLOSE_PREVIOUS_LEASE')

    expected_root = {'campaign': CAMPAIGN, 'owner_token': preflight['owner_token'], 'status': 'PREFLIGHT_LOCKED',
                     'enabled': False, 'max_new': 0, 'approved_total': TOTAL, 'reserved_total': 0, 'actual': 0,
                     'success': 0, 'failed': 0, 'unknown': 0, 'unused_locked': TOTAL, 'generation_calls': 0}
    root_raw = own('CONTROL.json'); require(root_raw == canon(expected_root), 'ROOT_INITIAL_SNAPSHOT_CHANGED')
    expected_lock = {'campaign': CAMPAIGN, 'owner_token': preflight['owner_token'], 'created_run': preflight['run'],
                     'created_commit': preflight['commit'], 'enabled': False, 'approved_total': TOTAL, 'single_executor': True}
    require(own('LOCK.json') == canon(expected_lock), 'CAMPAIGN_INITIAL_LEASE_CHANGED')
    return {'campaign': CAMPAIGN, 'status': 'PASS', 'generation_calls': 0, 'gcs_writes': 0,
            'openai_requests': 0, 'api_key_reads': 0, 'objects_read': len(cache), 'previous_campaigns': protected,
            'new_campaign_authority': {'objects': [PREFIX + 'states/CLOSED_LOCKED.json', PREFIX + 'controls/CLOSED/CLOSED_LOCKED.json'],
                'sha256': sha(closed_raw), 'status': 'CLOSED_LOCKED', 'enabled': False, 'max_new': 0,
                'research_complete': complete, 'ledger_resolved': True, 'reserved_total': total,
                'success': totals['success'], 'failed': totals['failed'], 'unknown': totals['unknown'],
                'transmitted_attempts_recorded': totals['transmitted_recorded'], 'unused_locked': TOTAL - total,
                'next_new_authorization': 0, 'stage_caps': effective, 'stage_actual': {p: counts[p]['reserved'] for p in PHASES},
                'stage_counts': counts, 'selected_final_candidate': plans['F'].get('selected_candidate'),
                'unique_success_response_ids': len(response_ids), 'dual_authority_bytes_equal': True},
            'frozen_evidence': {'sources_sha256': sha(source_raw), 'prompts_sha256': sha(prompts_raw),
                'freeze_sha256': sha(freeze_raw), 'metadata_sha256_by_object': metadata, 'effective_plan_sha256_by_phase': plan_hashes},
            'historical_root_control': {'object': PREFIX + 'CONTROL.json', 'sha256': sha(root_raw),
                'status': 'PREFLIGHT_LOCKED', 'authority_status': 'HISTORICAL_INITIAL_SNAPSHOT_NOT_FINAL_COUNTS'}}


def main():
    require(os.environ.get('GITHUB_REF') == 'refs/heads/research/gemini-model-native500-20261107'
            and os.environ.get('GITHUB_RUN_ATTEMPT') == '1' and os.environ.get('GITHUB_ACTOR') == 'martin830000-spec', 'UNAUTHORIZED_OR_REPLAY')
    here = pathlib.Path(__file__).resolve().parent
    control = json.loads((here / 'CONTROL.json').read_bytes())
    require(set(control['code_sha256']) == {'runner.py', 'contract.py', 'http_sender.py'}, 'CODE_FREEZE_SET')
    for name, digest in control['code_sha256'].items():
        require(sha((here / name).read_bytes()) == digest, 'CODE_FREEZE_MISMATCH')
    from google.cloud import storage
    from google.api_core.exceptions import NotFound
    bucket = storage.Client(project='gen-lang-client-0422436907').bucket('lao-translator-src-460077888071')

    def get(name):
        try:
            return bucket.blob(name).download_as_bytes(timeout=30, retry=None)
        except NotFound:
            return None
    result = check_state(get, control)
    print('PROTECTED_STATE_RECHECK=' + json.dumps(result, sort_keys=True), flush=True)


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        value = str(error) if isinstance(error, AssertionError) else ''
        code = value if value and all(ch in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_' for ch in value) else type(error).__name__
        print('PROTECTED_STATE_RECHECK=' + json.dumps({'status': 'FAIL', 'generation_calls': 0, 'gcs_writes': 0, 'code': code}), flush=True)
        raise SystemExit(1)
