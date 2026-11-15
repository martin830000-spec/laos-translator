#!/usr/bin/env python3
"""Verify 21 inherited objects read-only, then create one SOLO320 receipt.

Run beside the frozen execution code, immediately before the CLOSE runner.
No paid sender or runner is imported. Expected private paths and digests are
read only from the SHA-pinned preparation/OLD_LOCK_EXPECTATIONS.json in GCS.
run_audit accepts callbacks so all safety checks can be tested offline.
"""
import argparse
import datetime
import hashlib
import json
import os
import pathlib
import re
import sys
import types

CAMPAIGN = 'GPT_LUNA_SOLO100_FOURPATH_MECHANISM320_20261115'
BRANCH = 'refs/heads/research/gemini-model-native500-20261107'
ACTOR = 'martin830000-spec'
ROOT = 'research/gemini-model-native500-20261107/'
PREFIX = ROOT + 'gpt-luna-solo100-fourpath-mechanism320-20261115'
CODE_FILES = frozenset(('runner.py', 'contract.py', 'http_sender.py', 'locked_objects.py'))
EXPECTATIONS_OBJECT = 'preparation/OLD_LOCK_EXPECTATIONS.json'
PREFLIGHT_OBJECT = 'preflight/PREFLIGHT.json'
FREEZE_OBJECT = 'preparation/FREEZE.json'
RECEIPT_OBJECT = 'evaluation/FINAL_OLD_LOCKS.json'
PROJECT = 'gen-lang-client-0422436907'
BUCKET = 'lao-translator-src-460077888071'


def require(ok, code):
    if not ok:
        raise AssertionError(code)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def canon(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode()


def parse_json(raw, code):
    require(isinstance(raw, bytes), code)
    try:
        value = json.loads(raw)
    except (ValueError, TypeError, UnicodeError):
        raise AssertionError(code) from None
    require(isinstance(value, dict), code)
    return value


def digest(value):
    return isinstance(value, str) and re.fullmatch(r'[0-9a-f]{64}', value) is not None


def validate_runtime(control, environment, code_bytes, helper_raw):
    """Pure validation; executable modules other than the pinned verifier stay unread as code."""
    require(isinstance(control, dict), 'CONTROL_JSON')
    require(control.get('campaign') == CAMPAIGN
            and type(control.get('approved_total')) is int
            and control['approved_total'] == 320, 'CONTROL_CAMPAIGN')
    require(control.get('mode') == 'CLOSE' and control.get('phase') == 'CLOSE'
            and control.get('enabled') is False
            and type(control.get('max_new')) is int and control['max_new'] == 0,
            'CLOSE_DISABLED_REQUIRED')
    require(environment.get('GITHUB_REF') == BRANCH
            and environment.get('GITHUB_ACTOR') == ACTOR
            and environment.get('GITHUB_RUN_ATTEMPT') == '1',
            'RUNTIME_BRANCH_ACTOR_ATTEMPT')
    require(re.fullmatch(r'[0-9a-f]{40}|[0-9a-f]{64}', environment.get('GITHUB_SHA', ''))
            is not None, 'RUNTIME_COMMIT')
    require(re.fullmatch(r'[1-9][0-9]*', environment.get('GITHUB_RUN_ID', ''))
            is not None, 'RUNTIME_RUN')
    require(isinstance(control.get('owner_token'), str) and bool(control['owner_token']),
            'CONTROL_OWNER')
    pinned = control.get('code_sha256')
    require(isinstance(pinned, dict) and set(pinned) == CODE_FILES
            and set(code_bytes) == CODE_FILES, 'CODE_FREEZE_SET')
    for name in sorted(CODE_FILES):
        require(isinstance(code_bytes[name], bytes) and digest(pinned[name])
                and sha(code_bytes[name]) == pinned[name], 'CODE_SHA')
    require(digest(control.get('old_locks_sha256')), 'OLD_EXPECTATIONS_SHA_FORMAT')
    require(digest(control.get('preflight_sha256')), 'PREFLIGHT_SHA_FORMAT')
    require(digest(control.get('freeze_sha256')), 'FREEZE_SHA_FORMAT')
    require(isinstance(helper_raw, bytes), 'HELPER_BYTES')
    if 'audit_helper_sha256' in control:
        require(digest(control['audit_helper_sha256'])
                and sha(helper_raw) == control['audit_helper_sha256'], 'HELPER_SHA')


def load_verifier(verified_raw):
    """Execute only the already SHA-checked locked_objects bytes, avoiding an import race."""
    module = types.ModuleType('_solo320_pinned_old_lock_verifier')
    exec(compile(verified_raw, 'locked_objects.py', 'exec'), module.__dict__)
    require(module.CAMPAIGN == CAMPAIGN and module.ROOT == ROOT and module.PREFIX == PREFIX,
            'LOCK_VERIFIER_SCOPE')
    require(callable(module.expectations) and callable(module.verify), 'LOCK_VERIFIER_API')
    return module


def verify_lease(raw, control, name):
    value = parse_json(raw, 'LEASE_JSON')
    require(value.get('campaign') == CAMPAIGN
            and value.get('owner_token') == control['owner_token']
            and type(value.get('approved_total')) is int and value['approved_total'] == 320
            and value.get('enabled') is False, 'CAMPAIGN_LEASE')
    if name == 'CONTROL.json':
        require(type(value.get('max_new')) is int and value['max_new'] == 0,
                'CAMPAIGN_CONTROL_DISABLED')


def run_audit(control, environment, code_bytes, helper_raw,
              read_new, fetch_old, create_new, observed_at_utc=None):
    """Callbacks: read_new(name, optional=False), fetch_old(full_path),
    create_new(name, raw, *, if_generation_match=0).

    Only RECEIPT_OBJECT is passed to create_new. An existing receipt is always
    refused, including an identical one. There is no retry or overwrite path.
    """
    validate_runtime(control, environment, code_bytes, helper_raw)
    verifier = load_verifier(code_bytes['locked_objects.py'])
    require(read_new(RECEIPT_OBJECT, optional=True) is None, 'FINAL_OLD_LOCKS_ALREADY_EXISTS')
    for terminal in ('states/CLOSED_LOCKED.json', 'controls/CLOSED/CLOSED_LOCKED.json'):
        require(read_new(terminal, optional=True) is None, 'CAMPAIGN_ALREADY_CLOSED')
    for name in ('CONTROL.json', 'LOCK.json'):
        verify_lease(read_new(name), control, name)
    freeze_raw = read_new(FREEZE_OBJECT)
    require(isinstance(freeze_raw, bytes) and sha(freeze_raw) == control['freeze_sha256'],
            'FREEZE_SHA')
    freeze = parse_json(freeze_raw, 'FREEZE_JSON')
    require(freeze.get('campaign') == CAMPAIGN
            and freeze.get('code_sha256') == control['code_sha256'], 'FROZEN_CODE_CHANGED')
    preflight_raw = read_new(PREFLIGHT_OBJECT)
    require(isinstance(preflight_raw, bytes)
            and sha(preflight_raw) == control['preflight_sha256'], 'PREFLIGHT_SHA')
    preflight = parse_json(preflight_raw, 'PREFLIGHT_JSON')
    require(preflight.get('campaign') == CAMPAIGN
            and preflight.get('owner_token') == control['owner_token']
            and type(preflight.get('generation_calls')) is int
            and preflight['generation_calls'] == 0, 'PREFLIGHT_IDENTITY')
    require(all(preflight.get(key) is True for key in
                ('input_decryption_verified', 'create_only_readback_verified',
                 'duplicate_create_rejected')), 'PREFLIGHT_NOT_VERIFIED')
    require(preflight.get('old_locks_sha256') == control['old_locks_sha256'],
            'PREFLIGHT_EXPECTATIONS_SHA')
    expectations_raw = read_new(EXPECTATIONS_OBJECT)
    expected = verifier.expectations(expectations_raw, control['old_locks_sha256'])
    initial = preflight.get('old_locks')
    require(isinstance(initial, dict) and initial.get('objects_read') == 21
            and initial.get('states_read') == 11 and initial.get('companions_read') == 10
            and initial.get('all_sha256_match') is True
            and initial.get('all_companion_bytes_match') is True
            and isinstance(initial.get('objects'), dict)
            and set(initial['objects']) == set(expected), 'PREFLIGHT_OLD_OBJECTS')
    observed = verifier.verify(expectations_raw, control['old_locks_sha256'], fetch_old)
    require(observed.get('objects_read') == 21 and observed.get('states_read') == 11
            and observed.get('companions_read') == 10
            and observed.get('old_object_mutations') == 0, 'OLD_READ_COUNTS')
    for path, value in observed['objects'].items():
        before = initial['objects'][path]
        require(isinstance(before, dict)
                and all(before.get(k) == value[k] for k in ('sha256', 'bytes', 'role'))
                and before.get('required_fields_match') is True, 'PREFLIGHT_OLD_BYTES_CHANGED')
        if value['role'] == 'companion':
            require(before.get('byte_equal_to_state') is True
                    and value.get('byte_equal_to_state') is True, 'PREFLIGHT_COMPANION_BYTES')
        else:
            # An authoritative state is equal to its own bytes by definition.
            value['byte_equal_to_state'] = True
    timestamp = observed_at_utc or datetime.datetime.now(datetime.timezone.utc).isoformat()
    receipt = dict(
        schema='SOLO320_FINAL_OLD_LOCKS_READBACK_V1', campaign=CAMPAIGN, status='PASS',
        observed_at_utc=timestamp, expectations_sha256=sha(expectations_raw),
        preflight_sha256=sha(preflight_raw), freeze_sha256=sha(freeze_raw),
        commit=environment['GITHUB_SHA'],
        run=environment['GITHUB_RUN_ID'], code_sha256=dict(control['code_sha256']),
        audit_helper_sha256=sha(helper_raw),
        audit_helper_sha256_pinned=('audit_helper_sha256' in control),
        objects=observed['objects'], objects_read=21, states_read=11, companions_read=10,
        all_sha256_match=True, all_companion_bytes_match=True,
        generation_api_calls=0, old_object_mutations=0, remote_mutations=1,
        remote_mutation_scope='One create-only receipt in the new campaign',
        new_campaign_receipt_object=PREFIX + '/' + RECEIPT_OBJECT)
    raw = canon(receipt)
    create_new(RECEIPT_OBJECT, raw, if_generation_match=0)
    require(read_new(RECEIPT_OBJECT) == raw, 'RECEIPT_READBACK_MISMATCH')
    return receipt, raw


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime-dir', type=pathlib.Path,
                        default=pathlib.Path(__file__).resolve().parent)
    args = parser.parse_args()
    runtime = args.runtime_dir.resolve()
    control = parse_json((runtime / 'CONTROL.json').read_bytes(), 'CONTROL_JSON')
    code_bytes = {}
    for name in sorted(CODE_FILES):
        path = runtime / name
        require(path.resolve().parent == runtime, 'CODE_PATH')
        code_bytes[name] = path.read_bytes()
    helper_raw = pathlib.Path(__file__).read_bytes()
    # Reject wrong context before credentials are discovered or any remote read occurs.
    validate_runtime(control, os.environ, code_bytes, helper_raw)
    from google.cloud import storage
    from google.api_core.exceptions import NotFound
    bucket = storage.Client(project=PROJECT).bucket(BUCKET)

    def read_new(name, optional=False):
        try:
            return bucket.blob(PREFIX + '/' + name).download_as_bytes(timeout=30, retry=None)
        except NotFound:
            if optional:
                return None
            raise

    def fetch_old(path):
        return bucket.blob(path).download_as_bytes(timeout=30, retry=None)

    def create_new(name, raw, *, if_generation_match):
        require(name == RECEIPT_OBJECT and type(if_generation_match) is int
                and if_generation_match == 0, 'RECEIPT_CREATE_ONLY_SCOPE')
        bucket.blob(PREFIX + '/' + name).upload_from_string(
            raw, if_generation_match=0, timeout=30, retry=None)

    receipt, raw = run_audit(control, os.environ, code_bytes, helper_raw,
                             read_new, fetch_old, create_new)
    # Public stdout intentionally contains only counts and the receipt digest.
    print('FINAL_OLD_LOCKS=' + json.dumps({
        'objects_read': receipt['objects_read'], 'states_read': receipt['states_read'],
        'companions_read': receipt['companions_read'], 'generation_api_calls': 0,
        'old_object_mutations': 0, 'remote_mutations': 1, 'receipt_sha256': sha(raw)},
        sort_keys=True), flush=True)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        value = str(exc) if isinstance(exc, AssertionError) else ''
        code = value if re.fullmatch(r'[A-Z0-9_]+', value) else type(exc).__name__
        print('FINAL_OLD_LOCKS_FAILED=' + json.dumps({
            'error': code, 'generation_api_calls': 0, 'old_object_mutations': 0}),
            file=sys.stderr, flush=True)
        raise SystemExit(1)
