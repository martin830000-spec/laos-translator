"""Local, network-free boundary tests; no API keys, clients, or generation calls."""
import copy
import json
import pathlib
import unittest

import contract
from contract import (APPROVED_TOTAL, BACK_PATH, CAMPAIGN, CANDIDATES, HARD_CAPS,
                      MODEL, PATHS, PHASES, back_input, budget_guard, build_payload,
                      final_selection, parse_events, sha, validate_design,
                      validate_prompts, validate_result_metadata)


def fixture(selected=None):
    """Synthetic metadata only; these sentences must never become paid samples."""
    sources = []; discovery = []; final = []
    for split, count, order in (('DISCOVERY', 8, discovery), ('FINAL', 4, final)):
        for index in range(count):
            for direction in ('KF', 'LF'):
                sid = f'SYNTHETIC_{split}_{direction}_{index + 1:02d}'
                text = 'SYNTHETIC_NOT_REAL_CHAT_' + sid
                sources.append({'source_id': sid, 'source': text, 'sha256': sha(text.encode()),
                                'direction': direction, 'split': split,
                                'raw_record_number': len(sources) + 1, 'class': 'test_only',
                                'duplicate_group': 'group_' + sid, 'prior_exposure': False,
                                'audit_case': False, 'luna_test': False})
                order.append(sid)
    by = {s['source_id']: s for s in sources}
    # Choose noninitial sources, so D must preserve discovery-global rotation.
    smoke = [discovery[4], discovery[9]]
    source = {'campaign': CAMPAIGN, 'sources': sources,
              'selection': {'discovery_order': discovery, 'smoke_order': smoke, 'final_order': final}}
    freeze = {'campaign': CAMPAIGN, 'approved_total': APPROVED_TOTAL,
              'stage_caps': dict(HARD_CAPS),
              'order_rule': 'DISCOVERY original index cyclic4; FINAL direction-local alternating2'}
    plans = {phase: {'campaign': CAMPAIGN, 'phase': phase, 'slots': []} for phase in PHASES}

    def pair(phase, sid, candidate):
        slots = plans[phase]['slots']; path = by[sid]['direction']
        first = {'slot': f'{phase}-{len(slots) + 1:03d}', 'source_id': sid,
                 'candidate': candidate, 'path': path, 'repeat_index': 1}
        back = {'slot': f'{phase}-{len(slots) + 2:03d}', 'source_id': sid,
                'candidate': candidate, 'path': BACK_PATH[path], 'repeat_index': 1,
                'parent_first_id': first['slot']}
        slots.extend((first, back))

    for phase, order in (('S', smoke), ('D', [sid for sid in discovery if sid not in smoke])):
        for sid in order:
            rotation = discovery.index(sid) % 4
            for candidate in CANDIDATES[rotation:] + CANDIDATES[:rotation]:
                pair(phase, sid, candidate)
    if selected is not None:
        plans['F']['selected_candidates'] = selected.copy()
        plans['F']['selection_evidence_sha256'] = sha(b'synthetic immutable selection evidence')
        seen = {'KF': 0, 'LF': 0}
        for sid in final:
            direction = by[sid]['direction']; index = seen[direction]; seen[direction] += 1
            candidate = selected[direction]
            if candidate is None: continue
            order = ('BASE', candidate) if index % 2 == 0 else (candidate, 'BASE')
            for item in order: pair('F', sid, item)
    return source, freeze, plans


def good_result():
    return {'success': True, 'display_text': 'synthetic output', 'actual_model': MODEL,
            'actual_service_tier': 'default', 'request_id': 'req_synthetic',
            'response_id': 'resp_synthetic', 'http_status': 200,
            'terminal': 'response.completed', 'http_attempts': 1,
            't_first_text': 0.2, 't_first_displayable_text': 0.2,
            't_text_done': 0.9, 't_response_done': 1.0, 't_display_extract_done': 1.01,
            'usage': {'input_tokens': 10, 'output_tokens': 5, 'total_tokens': 15,
                      'input_tokens_details': {'cached_tokens': 0},
                      'output_tokens_details': {'reasoning_tokens': 0}}}


def stream(text='synthetic text'):
    return [{'type': 'response.output_text.delta', 'delta': text},
            {'type': 'response.output_text.done', 'text': text},
            {'type': 'response.completed', 'response': {'status': 'completed',
             'usage': good_result()['usage'], 'output': [{'type': 'message',
             'content': [{'type': 'output_text', 'text': text}]}]}}]


def ledger(s=0, d=0, f=0):
    records = []
    for phase, count in (('S', s), ('D', d), ('F', f)):
        for index in range(1, count + 1):
            records.append({'campaign': CAMPAIGN, 'model': MODEL, 'stage': phase,
                            'slot': f'{phase}-{index:03d}', 'ordinal': len(records) + 1,
                            'state': 'RESERVED_TRANSMISSION_UNKNOWN'})
    return records


class DesignTests(unittest.TestCase):
    def test_pending_final_has_no_generation_but_fixed_capacity(self):
        source, freeze, plans = fixture()
        by, effective = validate_design(source, freeze, plans)
        self.assertEqual(len(by), 24)
        self.assertEqual(effective, {'S': 16, 'D': 112, 'F': 0})
        self.assertEqual(freeze['stage_caps'], {'S': 16, 'D': 112, 'F': 32})
        self.assertIsNone(final_selection(plans['F']))

    def test_all_directional_final_choices_and_skip_sizes(self):
        for kf in (None, 'TONE', 'NAME', 'TONE_NAME'):
            for lf in (None, 'TONE', 'NAME', 'TONE_NAME'):
                with self.subTest(kf=kf, lf=lf):
                    source, freeze, plans = fixture({'KF': kf, 'LF': lf})
                    _, effective = validate_design(source, freeze, plans)
                    self.assertEqual(effective['F'], 16 * ((kf is not None) + (lf is not None)))
                    self.assertIsNotNone(final_selection(plans['F']))

    def test_final_order_alternates_within_each_direction(self):
        source, freeze, plans = fixture({'KF': 'TONE', 'LF': 'NAME'})
        validate_design(source, freeze, plans)
        by = {s['source_id']: s for s in source['sources']}
        first_candidates = {'KF': [], 'LF': []}
        for index in range(0, 32, 4):
            task = plans['F']['slots'][index]
            first_candidates[by[task['source_id']]['direction']].append(task['candidate'])
        self.assertEqual(first_candidates['KF'], ['BASE', 'TONE', 'BASE', 'TONE'])
        self.assertEqual(first_candidates['LF'], ['BASE', 'NAME', 'BASE', 'NAME'])

    def test_smoke_requires_one_original_in_each_direction(self):
        source, freeze, plans = fixture()
        source['selection']['smoke_order'].reverse()
        with self.assertRaisesRegex(AssertionError, 'SMOKE_DIRECTION_ORDER'):
            validate_design(source, freeze, plans)

    def test_d_rotation_cannot_restart_after_smoke_removal(self):
        source, freeze, plans = fixture()
        slots = plans['D']['slots']
        # D source index4 was discovery index5: local rotation0 is wrong.
        block = slots[32:40]
        block = block[-2:] + block[:-2]
        for index, task in enumerate(block, 33):
            task['slot'] = f'D-{index:03d}'
            if task['path'].endswith('B'): task['parent_first_id'] = f'D-{index - 1:03d}'
        slots[32:40] = block
        with self.assertRaisesRegex(AssertionError, 'D_EXACT_FROZEN_SOURCE_CANDIDATE_ORDER'):
            validate_design(source, freeze, plans)

    def test_smoke_sources_cannot_be_repeated_in_d(self):
        source, freeze, plans = fixture()
        for task in plans['D']['slots'][:8]:
            task['source_id'] = source['selection']['smoke_order'][0]
        with self.assertRaisesRegex(AssertionError, 'D_EXACT_FROZEN_SOURCE_CANDIDATE_ORDER'):
            validate_design(source, freeze, plans)

    def test_parent_must_be_exact_previous_first_not_other_candidate(self):
        for phase in PHASES:
            source, freeze, plans = fixture({'KF': 'TONE', 'LF': 'NAME'})
            plans[phase]['slots'][1]['parent_first_id'] = plans[phase]['slots'][2]['slot']
            with self.subTest(phase=phase), self.assertRaisesRegex(AssertionError, 'CHAIN_PARENT_NOT_PREVIOUS_FIRST'):
                validate_design(source, freeze, plans)

    def test_cross_language_back_path_is_rejected(self):
        source, freeze, plans = fixture()
        plans['S']['slots'][1]['path'] = 'LB'
        with self.assertRaisesRegex(AssertionError, 'CHAIN_PATH_MISMATCH'):
            validate_design(source, freeze, plans)

    def test_source_candidate_and_extra_context_mismatches_rejected(self):
        for change in ('candidate', 'source_id', 'original_text', 'first_success_of'):
            source, freeze, plans = fixture()
            back = plans['S']['slots'][1]
            if change == 'candidate': back[change] = 'TONE_NAME'
            elif change == 'source_id': back[change] = source['selection']['discovery_order'][0]
            elif change == 'first_success_of': back[change] = ['S-001']
            else: back[change] = 'hidden original must not enter BACK'
            with self.subTest(change=change), self.assertRaises(AssertionError):
                validate_design(source, freeze, plans)

    def test_repeat_slot_and_old_campaign_forbidden(self):
        for change in ('repeat', 'slot', 'campaign'):
            source, freeze, plans = fixture()
            if change == 'repeat': plans['S']['slots'][0]['repeat_index'] = 2
            elif change == 'slot': plans['S']['slots'][1]['slot'] = 'S-001'
            else: plans['S']['campaign'] = 'GPT_LUNA_M1_GD_HEADTOHEAD80_20261112'
            with self.subTest(change=change), self.assertRaises(AssertionError):
                validate_design(source, freeze, plans)

    def test_raw_source_byte_change_and_record_bounds_rejected(self):
        for change in ('source', 'raw_zero', 'raw_501', 'raw_bool'):
            source, freeze, plans = fixture()
            row = source['sources'][0]
            if change == 'source': row['source'] += ' '
            else: row['raw_record_number'] = {'raw_zero': 0, 'raw_501': 501, 'raw_bool': True}[change]
            with self.subTest(change=change), self.assertRaises(AssertionError):
                validate_design(source, freeze, plans)

    def test_final_exposed_duplicate_or_luna_test_rejected(self):
        for change in ('prior_exposure', 'audit_case', 'luna_test', 'duplicate_group', 'sha256', 'raw_record_number'):
            source, freeze, plans = fixture()
            row = source['sources'][16]; prior = source['sources'][0]
            if change in ('prior_exposure', 'audit_case', 'luna_test'):
                row[change] = True; row['prior_exposure'] = True
            elif change == 'sha256': row['source'] = prior['source']; row['sha256'] = prior['sha256']
            else: row[change] = prior[change]
            with self.subTest(change=change), self.assertRaises(AssertionError):
                validate_design(source, freeze, plans)

    def test_discovery_requires_at_least_twelve_unaudited_unexposed(self):
        for key in ('prior_exposure', 'audit_case'):
            source, freeze, plans = fixture()
            for row in source['sources'][:5]:
                row[key] = True; row['prior_exposure'] = True
            with self.subTest(key=key), self.assertRaises(AssertionError):
                validate_design(source, freeze, plans)

    def test_missing_sample_or_wrong_direction_quota_rejected(self):
        source, freeze, plans = fixture()
        source['sources'].pop()
        with self.assertRaisesRegex(AssertionError, 'SOURCE_COUNT_24_REQUIRED'):
            validate_design(source, freeze, plans)
        source, freeze, plans = fixture()
        source['sources'][0]['direction'] = 'LF'
        with self.assertRaisesRegex(AssertionError, 'SOURCE_DIRECTION_QUOTA'):
            validate_design(source, freeze, plans)

    def test_final_needs_nonbase_selection_and_real_evidence_sha(self):
        for change in ('base', 'evidence', 'missing_direction', 'pending_with_slots'):
            source, freeze, plans = fixture({'KF': 'TONE', 'LF': 'NAME'})
            if change == 'base': plans['F']['selected_candidates']['KF'] = 'BASE'
            elif change == 'evidence': plans['F']['selection_evidence_sha256'] = 'unverified'
            elif change == 'missing_direction': del plans['F']['selected_candidates']['LF']
            else: del plans['F']['selected_candidates']
            with self.subTest(change=change), self.assertRaises(AssertionError):
                validate_design(source, freeze, plans)

    def test_skipped_final_direction_cannot_consume_its_budget_elsewhere(self):
        source, freeze, plans = fixture({'KF': 'TONE', 'LF': None})
        freeze['stage_caps'] = {'S': 16, 'D': 128, 'F': 16}
        with self.assertRaisesRegex(AssertionError, 'FIXED_HARD_STAGE_CAPS'):
            validate_design(source, freeze, plans)


class PayloadAndPromptTests(unittest.TestCase):
    def test_all_sixteen_actual_packet_prompt_hashes_and_mutations(self):
        packet = pathlib.Path(__file__).resolve().parent.parent / 'couple_tone_name_inputs' / 'packet'
        if not packet.is_dir(): self.skipTest('Private prompt packet absent; no substitute prompt gold')
        prompts = {candidate: json.loads((packet / ('PROMPTS_' + candidate + '.json')).read_bytes())['prompts']
                   for candidate in CANDIDATES}
        validate_prompts(prompts)
        for candidate in CANDIDATES:
            for path in PATHS:
                damaged = copy.deepcopy(prompts); damaged[candidate][path] += ' '
                with self.subTest(candidate=candidate, path=path), self.assertRaisesRegex(AssertionError, 'PROMPT_BYTE_SHA'):
                    validate_prompts(damaged)

    def test_candidate_back_prompts_cannot_be_replaced_with_base(self):
        packet = pathlib.Path(__file__).resolve().parent.parent / 'couple_tone_name_inputs' / 'packet'
        if not packet.is_dir(): self.skipTest('Private prompt packet absent')
        prompts = {candidate: json.loads((packet / ('PROMPTS_' + candidate + '.json')).read_bytes())['prompts']
                   for candidate in CANDIDATES}
        for candidate in CANDIDATES[1:]:
            for path in ('KB', 'LB'):
                damaged = copy.deepcopy(prompts); damaged[candidate][path] = damaged['BASE'][path]
                with self.subTest(candidate=candidate, path=path), self.assertRaisesRegex(AssertionError, 'PROMPT_BYTE_SHA'):
                    validate_prompts(damaged)

    def test_four_paths_have_exact_request_keys_and_exact_input(self):
        text = '  synthetic actual FIRST\nsecond line🙂\n'
        prompts = {path: 'Synthetic prompt for ' + path for path in PATHS}
        for path in PATHS:
            payload = build_payload(MODEL, 'none', path, text, prompts)
            self.assertEqual(payload['input'], text)
            self.assertEqual(payload['instructions'], prompts[path])
            self.assertEqual(set(payload), {'model', 'reasoning', 'instructions', 'input', 'stream', 'store', 'max_output_tokens', 'service_tier'})
            self.assertEqual(payload['reasoning'], {'effort': 'none'})
            self.assertTrue(payload['stream']); self.assertFalse(payload['store'])

    def test_other_model_effort_and_empty_request_rejected(self):
        for model, effort, path, text in ((MODEL, 'low', 'KF', 'x'), ('other', 'none', 'KF', 'x'),
                                           (MODEL, 'none', 'KF', '  '), (MODEL, 'none', 'OLD', 'x')):
            with self.subTest(model=model, effort=effort, path=path), self.assertRaises(AssertionError):
                build_payload(model, effort, path, text, {key: 'synthetic' for key in PATHS})

    def test_back_accepts_actual_complete_text_without_semantic_repair(self):
        text = '\nSynthetic mistranslation must remain the BACK input.  '
        self.assertEqual(back_input({'success': True, 'unknown': False, 'display_text': text}), text)
        for parent in (None, {'success': False, 'display_text': text},
                       {'success': True, 'unknown': True, 'display_text': text},
                       {'success': True, 'display_text': '   '}):
            self.assertIsNone(back_input(parent))


class AccountingTests(unittest.TestCase):
    def test_exact160_boundary_with_unknown_reservations(self):
        records = ledger(16, 112, 31)
        record = budget_guard(records, 'F-032', 'F', HARD_CAPS)
        self.assertEqual(record['ordinal'], 160)
        self.assertEqual(record['state'], 'RESERVED_TRANSMISSION_UNKNOWN')
        with self.assertRaisesRegex(AssertionError, 'CAMPAIGN_CAP'):
            budget_guard(records + [record], 'F-033', 'F', HARD_CAPS)

    def test_no_stage_or_skipped_direction_reallocation(self):
        with self.assertRaisesRegex(AssertionError, 'STAGE_CAP_NO_REALLOCATION'):
            budget_guard(ledger(16, 112), 'F-001', 'F', {'S': 16, 'D': 112, 'F': 0})
        with self.assertRaisesRegex(AssertionError, 'STAGE_CAP_NO_REALLOCATION'):
            budget_guard(ledger(16, 112, 16), 'F-017', 'F', {'S': 16, 'D': 112, 'F': 16})
        with self.assertRaisesRegex(AssertionError, 'STAGE_CAP_NO_REALLOCATION'):
            budget_guard([], 'D-001', 'D', {'S': 0, 'D': 128, 'F': 32})

    def test_duplicate_foreign_and_noncontiguous_ledger_rejected(self):
        with self.assertRaisesRegex(AssertionError, 'DUPLICATE_SLOT'):
            budget_guard(ledger(1), 'S-001', 'S', HARD_CAPS)
        for change in ('campaign', 'ordinal'):
            records = ledger(1); records[0][change] = 'old' if change == 'campaign' else 2
            with self.subTest(change=change), self.assertRaisesRegex(AssertionError, 'FOREIGN_OR_INVALID_RESERVATION'):
                budget_guard(records, 'S-002', 'S', HARD_CAPS)


class MetadataAndStreamTests(unittest.TestCase):
    def test_reasoning_tokens_are_recorded_inside_output_not_added(self):
        result = good_result(); result['usage']['output_tokens_details']['reasoning_tokens'] = 2
        checked = validate_result_metadata(result)
        self.assertTrue(checked['success']); self.assertEqual(checked['reasoning_tokens'], 2)
        self.assertEqual(checked['usage']['total_tokens'], 15)
        self.assertIn('NONZERO_REASONING_TOKENS_WITH_REQUESTED_NONE', checked['metadata_warnings'])

    def test_missing_or_invalid_reasoning_tokens_cannot_pass_smoke(self):
        for value in (None, -1, 6, True, '0'):
            result = good_result(); result['usage']['output_tokens_details']['reasoning_tokens'] = value
            checked = validate_result_metadata(result)
            with self.subTest(value=value):
                self.assertFalse(checked['success'])
                self.assertIn('REASONING_TOKENS_MISSING_OR_INVALID', checked['metadata_errors'])

    def test_missing_cache_count_is_unknown_not_fabricated_zero(self):
        result = good_result(); del result['usage']['input_tokens_details']
        checked = validate_result_metadata(result)
        self.assertTrue(checked['success']); self.assertIsNone(checked['cached_input_tokens'])
        self.assertIn('CACHED_TOKENS_NOT_REPORTED', checked['metadata_warnings'])

    def test_request_response_model_tier_and_usage_required(self):
        for key in ('request_id', 'response_id', 'actual_model', 'actual_service_tier', 'http_attempts', 'usage'):
            result = good_result(); result.pop(key)
            with self.subTest(key=key): self.assertFalse(validate_result_metadata(result)['success'])
        result = good_result(); result['usage']['total_tokens'] = 17
        self.assertIn('USAGE_TOTAL_MISMATCH', validate_result_metadata(result)['metadata_errors'])

    def test_missing_nonfinite_or_reversed_timings_cannot_pass_smoke(self):
        for key, value in (('t_first_text', None), ('t_first_displayable_text', float('nan')),
                           ('t_response_done', float('inf')), ('t_display_extract_done', 0.5),
                           ('t_text_done', 2.0)):
            result = good_result(); result[key] = value
            with self.subTest(key=key, value=value):
                self.assertFalse(validate_result_metadata(result)['success'])

    def test_unknown_and_known_failures_are_distinct(self):
        for changes, expected in (({'exception': 'TIMEOUT'}, True),
                                  ({'http_status': None}, True),
                                  ({'terminal': None}, True),
                                  ({'success': False, 'http_status': 429, 'terminal': None}, False),
                                  ({'success': False, 'terminal': 'response.incomplete'}, False)):
            result = good_result(); result.update(changes)
            with self.subTest(changes=changes):
                checked = validate_result_metadata(result)
                self.assertEqual(checked['unknown'], expected)
                if expected: self.assertFalse(checked['success'])

    def test_completed_stream_preserves_exact_text(self):
        text = '  Lao-like unicode ທີ່ຮັກ\nKorean text🙂\n'
        result = parse_events(stream(text))
        self.assertTrue(result['success']); self.assertEqual(result['display_text'], text)

    def test_done_final_mismatch_refusal_incomplete_and_error_rejected(self):
        for change in ('done', 'final', 'refusal', 'incomplete', 'error', 'double_terminal'):
            events = stream()
            if change == 'done': events[1]['text'] += ' changed'
            elif change == 'final': events[-1]['response']['output'][0]['content'][0]['text'] += ' changed'
            elif change == 'refusal': events.insert(0, {'type': 'response.refusal.delta', 'delta': 'no'})
            elif change == 'incomplete': events[-1]['type'] = 'response.incomplete'; events[-1]['response']['status'] = 'incomplete'
            elif change == 'error': events.append({'type': 'error', 'message': 'synthetic'})
            else: events.append(copy.deepcopy(events[-1]))
            with self.subTest(change=change):
                self.assertFalse(parse_events(events)['success'])
                self.assertIsNone(parse_events(events)['display_text'])

    def test_malformed_stream_returns_failed_parse_without_losing_raw_control(self):
        for change in ('delta', 'response', 'item', 'content', 'text', 'event'):
            events = stream()
            if change == 'delta': events[0]['delta'] = ['invalid']
            elif change == 'response': events[-1]['response'] = None
            elif change == 'item': events[-1]['response']['output'] = [None]
            elif change == 'content': events[-1]['response']['output'][0]['content'] = 'invalid'
            elif change == 'text': events[-1]['response']['output'][0]['content'][0]['text'] = 7
            else: events.insert(0, None)
            with self.subTest(change=change):
                result = parse_events(events)
                self.assertFalse(result['success']); self.assertTrue(result['parse_errors'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
