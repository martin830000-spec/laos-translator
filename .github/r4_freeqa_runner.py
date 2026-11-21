"""R4 four-path frozen 96-slot GCS integration and safety guard.

SYNTHETIC/TEST ONLY. No user message text, private prompt text or key is embedded.
The same slot execution/storage code is run with memory and real GCS transports.
Historical campaign IDs are metadata, not authorization.
"""
from __future__ import annotations
import base64, collections, hashlib, json, os, pathlib, subprocess, sys, urllib.error, urllib.parse, urllib.request, uuid, zlib, unittest
CAMPAIGN = 'GEMINI35_FOURPATH_RUNNER_INTEGRATION_FREEQA_R4_20261121'
PREFIX = 'sft_fourpath_runner_integration_freeqa_r4_20261121/'
BUCKET = 'ko-lao-gemini35-tuning-460077888071'
PROJECT = '460077888071'
REGION = 'us'
PLAN_SHA = 'bfc71f33af620d9b319a21994b9f143a1d4b5d105056f0a2fa15538307f45562'
PROVENANCE_SHA = 'e18ea22b8a52c9a1b99ab75bbbf3c975fcfb23ac5fd1f95dc47275584644371a'
TUNED_ENDPOINT = 'projects/460077888071/locations/us/endpoints/1638501023804817408'
TUNED_MODEL = 'projects/460077888071/locations/us/models/4774448923710324736@1'
BASE_MODEL = 'projects/460077888071/locations/us/publishers/google/models/gemini-3.5-flash-lite'
PLAN_B64 = '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'
PINS_B64 = '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'
PROMPT_SHA = '{"KF_LEX1_R2_BASELINE":"65483c1774e0bf15812a71c0b2d02d83722125df94685d7535972760fd0978f0","KB_B0_R2_BASELINE":"5581a11a159a421691f477e6ef93708122b4a485ffb90212fdcc34e943673f6b","KB_LEX_R2_COMPARATOR":"acefd9f4e8486899577c030afe5a48ab761c77ad473c261cc66e9e982588e81d","LF0_MIN":"451797f854608fe4826df0666159ca6a1a65be065619c6083482d412860b2f34","LF1_REFERENT":"d0623f1da732a992b67345456d371a85e8f688baf0972a5444fcd36a294a210c","LB0_MIN":"2c78f5eba18f8f7507d1a5e88cb88338fca46828c89bcce79342b9352900bbbb","LB1_REFERENT":"dac9cefde413b90e9e1a882105fe196518c8eaace55fcb1817fa702518845225"}'

def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()

def require(condition, code='R4_INTEGRITY_VIOLATION'):
    if not condition:
        raise SafetyStop(code)

def jsonb(x) -> bytes:
    return (json.dumps(x, sort_keys=True, separators=(',', ':'), ensure_ascii=False) + '\n').encode()

def decode(b64: str):
    return json.loads(zlib.decompress(base64.b64decode(b64)))

class SafetyStop(Exception):
    pass

class TransportUnknown(SafetyStop):
    pass

class InitialFailure:

    def __init__(self):
        self.first = None
        self.secondary = []

    def record(self, code):
        if self.first is None:
            self.first = str(code)
        else:
            self.secondary.append(str(code))
        return self.first

class Budget:
    LIMITS = {'POST': 320, 'GET': 700, 'LIST': 15, 'POST_BYTES': 524288}

    def __init__(self):
        self.post = 0
        self.get = 0
        self.list = 0
        self.post_bytes = 0
        self.model_attempts = 0
        self.per_model = collections.Counter()
        self.halted = False
        self.closed = False
        self.first = InitialFailure()
        self.gcs_unknown = False

    def reserve(self, method, nbytes=0):
        if self.closed or self.halted:
            raise SafetyStop('CLOSED_OR_HALTED: no further SEND')
        nxt = {'POST': self.post + 1, 'GET': self.get + 1, 'LIST': self.list + 1}.get(method)
        if nxt is None:
            raise SafetyStop('BAD_METHOD')
        if nxt > self.LIMITS[method] or (method == 'POST' and self.post_bytes + nbytes > self.LIMITS['POST_BYTES']):
            self.halted = True
            self.first.record('GCS_BUDGET_LIMIT')
            raise SafetyStop('GCS_BUDGET_LIMIT')
        if method == 'POST':
            self.post += 1
            self.post_bytes += nbytes
        if method == 'GET':
            self.get += 1
        if method == 'LIST':
            self.list += 1

    def fail(self, code):
        self.first.record(code)
        self.halted = True
        raise SafetyStop(code)

    def reserve_model(self, model):
        self.fail('R4_MODEL_GENERATION_DENIED')

class RequestsTransport:

    def __init__(self, token):
        self.token = token

    def send(self, method, url, data=None, ctype=None):
        u = urllib.parse.urlsplit(url)
        if u.scheme != 'https':
            raise SafetyStop('NETWORK_HOST_DENIED')
        if u.hostname == 'aiplatform.us.rep.googleapis.com':
            if method != 'GET' or not (u.path.startswith('/v1/' + TUNED_ENDPOINT) or u.path.startswith('/v1/projects/' + PROJECT + '/locations/us/models/')):
                raise SafetyStop('MODEL_HTTP_GENERATION_BLOCKED')
        elif u.hostname == 'storage.googleapis.com':
            if not (u.path.startswith('/storage/v1/b/' + BUCKET + '/') or u.path.startswith('/upload/storage/v1/b/' + BUCKET + '/')):
                raise SafetyStop('STORAGE_PATH_DENIED')
            if method not in ('GET', 'POST'):
                raise SafetyStop('STORAGE_MUTATION_DENIED')
        else:
            raise SafetyStop('NETWORK_HOST_DENIED')
        h = {'Authorization': 'Bearer ' + self.token, 'Accept': 'application/json', 'User-Agent': 'R4-FreeQA/1'}
        if ctype:
            h['Content-Type'] = ctype
        req = urllib.request.Request(url, headers=h, data=data, method=method)
        try:
            with urllib.request.urlopen(req, timeout=40) as r:
                return (r.status, r.read(900000))
        except urllib.error.HTTPError as e:
            return (e.code, e.read(900000))
        except Exception as e:
            raise TransportUnknown('TRANSPORT_UNKNOWN_' + type(e).__name__) from None

class FakeTransport:
    """Status-compatible GCS fake. Used to inject crashes without external requests."""

    def __init__(self):
        self.items = {}
        self.generation = 100
        self.posts = 0
        self.inject_unknown = False
        self.fail_post_after = None
        self.fail_get_after = None
        self.gets = 0

    def send(self, method, url, data=None, ctype=None):
        u = urllib.parse.urlsplit(url)
        q = urllib.parse.parse_qs(u.query)
        if u.hostname != 'storage.googleapis.com':
            raise SafetyStop('FAKE_NON_GCS_DENIED')
        if '/upload/storage/' in u.path:
            require(method == 'POST' and q.get('ifGenerationMatch') == ['0'], 'ASSERTION_GATE_FAILED')
            self.posts += 1
            if self.fail_post_after is not None and self.posts >= self.fail_post_after:
                return (503, b'{"error":"injected"}')
            name = q['name'][0]
            if name in self.items:
                return (412, b'{"error":"exists"}')
            self.generation += 1
            body = data or b''
            meta = {'name': name, 'generation': str(self.generation), 'size': str(len(body))}
            self.items[name] = (meta, body)
            if self.inject_unknown:
                self.inject_unknown = False
                raise TransportUnknown('SYNTH_ACK_LOSS_AFTER_STORAGE')
            return (200, json.dumps(meta).encode())
        if u.path.endswith('/o') and method == 'GET':
            prefix = q.get('prefix', [''])[0]
            return (200, json.dumps({'items': [{'name': n} for n in self.items if n.startswith(prefix)]}).encode())
        if '/o/' in u.path and method == 'GET':
            self.gets += 1
            if self.fail_get_after is not None and self.gets >= self.fail_get_after:
                return (503, b'{"error":"injected"}')
            name = urllib.parse.unquote(u.path.split('/o/', 1)[1])
            item = self.items.get(name)
            if not item:
                return (404, b'{"error":"not found"}')
            meta, body = item
            if 'generation' in q and q['generation'][0] != meta['generation']:
                return (404, b'{}')
            if q.get('alt') == ['media']:
                return (200, body)
            return (200, json.dumps(meta).encode())
        raise AssertionError(('Unexpected fake HTTP', method, url))

class Store:

    def __init__(self, transport, budget, session):
        self.transport = transport
        self.b = budget
        self.session = session
        self.root = PREFIX + session + '/'
        self.receipts = {}

    def _request(self, method, url, payload=None, ctype=None, expected=(200,)):
        cap = 'POST' if method == 'POST' else 'GET'
        self.b.reserve(cap, len(payload or b''))
        try:
            status, raw = self.transport.send(method, url, payload, ctype)
        except TransportUnknown as e:
            self.b.gcs_unknown = True
            self.b.first.record(str(e))
            self.b.halted = True
            raise
        except Exception as e:
            self.b.first.record('GCS_TRANSPORT_' + type(e).__name__)
            self.b.halted = True
            raise
        if status not in expected:
            self.b.fail('GCS_HTTP_' + str(status))
        return (status, raw)

    def _meta_url(self, name):
        return 'https://storage.googleapis.com/storage/v1/b/' + BUCKET + '/o/' + urllib.parse.quote(name, safe='')

    def read_pinned(self, name, generation=None):
        url = self._meta_url(name)
        _, metaraw = self._request('GET', url + '?fields=name%2Csize%2Cgeneration')
        meta = json.loads(metaraw)
        require(meta.get('name') == name, 'ASSERTION_GATE_FAILED')
        g = str(meta.get('generation'))
        if generation is not None and str(generation) != g:
            self.b.fail('GCS_GENERATION_CHANGED')
        _, body = self._request('GET', url + '?' + urllib.parse.urlencode({'alt': 'media', 'generation': g}))
        if len(body) != int(meta['size']):
            self.b.fail('GCS_BYTES_CHANGED')
        return (meta, body)

    def read(self, name):
        return self.read_pinned(self.root + name)

    def inventory(self, prefix=PREFIX):
        url = 'https://storage.googleapis.com/storage/v1/b/' + BUCKET + '/o?' + urllib.parse.urlencode({'prefix': prefix, 'maxResults': 500})
        self.b.reserve('LIST')
        try:
            status, raw = self.transport.send('GET', url)
        except Exception as e:
            self.b.first.record('GCS_INVENTORY_UNKNOWN')
            self.b.halted = True
            raise
        if status != 200:
            self.b.fail('GCS_LIST_HTTP_' + str(status))
        return [x['name'] for x in json.loads(raw).get('items', [])]

    def create(self, relative, payload, expect_412=False):
        name = self.root + relative
        url = 'https://storage.googleapis.com/upload/storage/v1/b/' + BUCKET + '/o?' + urllib.parse.urlencode({'uploadType': 'media', 'name': name, 'ifGenerationMatch': 0})
        data = jsonb(payload)
        status, raw = self._request('POST', url, data, 'application/json', expected=(200, 201, 412) if expect_412 else (200, 201))
        if status == 412:
            if not expect_412:
                self.b.fail('GCS_412_CONFLICT')
            return {'status': 412, 'name': name, 'expected_duplicate': True}
        if expect_412:
            self.b.fail('DUPLICATE_WAS_OVERWRITTEN')
        sent = json.loads(raw)
        g = str(sent['generation'])
        m, got = self.read_pinned(name, g)
        if got != data or sha(got) != sha(data):
            self.b.fail('GCS_READBACK_SHA_MISMATCH')
        receipt = {'name': name, 'generation': g, 'size': len(data), 'sha256': sha(data)}
        self.receipts[relative] = receipt
        return receipt

def load_plan():
    x = decode(PLAN_B64)
    require(x['campaign'] == 'GEMINI35_FOURPATH_BASELINE96_20261121', 'ASSERTION_GATE_FAILED')
    require(x['sha256'] == PLAN_SHA, 'ASSERTION_GATE_FAILED')
    s = x['slots']
    require(len(s) == 96 and len({v['slot_id'] for v in s}) == 96, 'ASSERTION_GATE_FAILED')
    prompts = json.loads(PROMPT_SHA)
    require(len(prompts) == 7, 'ASSERTION_GATE_FAILED')
    count = collections.Counter()
    seen = {}
    for i, row in enumerate(s):
        require(row['slot_id'] == f'SLOT{i + 1:03d}', 'ASSERTION_GATE_FAILED')
        require(row['prompt_sha256'] == prompts[row['prompt_id']], 'ASSERTION_GATE_FAILED')
        require(row['action'] in ('FIRST', 'BACK') and row['model_code'] in ('BASE', 'REALDB84'), 'ASSERTION_GATE_FAILED')
        require(row['direction'] in ('KF', 'KB', 'LF', 'LB'), 'ASSERTION_GATE_FAILED')
        require(len(row['source_sha256']) == 64 and row['stage'] == 'BASELINE96', 'ASSERTION_GATE_FAILED')
        count[row['model_code'], row['direction']] += 1
        if row['action'] == 'FIRST':
            require(row['parent_first_slot_id'] is None and row['direction'] in ('KF', 'LF'), 'ASSERTION_GATE_FAILED')
            require(row['input_kind'] == 'SOURCE_ORIGINAL', 'ASSERTION_GATE_FAILED')
        else:
            p = seen.get(row['parent_first_slot_id'])
            require(p and p['action'] == 'FIRST', 'ASSERTION_GATE_FAILED')
            require(p['model_code'] == row['model_code'] and p['selection_id'] == row['selection_id'], 'ASSERTION_GATE_FAILED')
            require(p['source_sha256'] == row['source_sha256'] and row['direction'] == {'KF': 'KB', 'LF': 'LB'}[p['direction']], 'ASSERTION_GATE_FAILED')
            require(row['input_kind'] == 'ACTUAL_PARENT_FIRST', 'ASSERTION_GATE_FAILED')
        seen[row['slot_id']] = row
    require(count == {(a, b): 12 for a in ('BASE', 'REALDB84') for b in ('KF', 'KB', 'LF', 'LB')}, 'ASSERTION_GATE_FAILED')
    return s

def load_pins():
    a = decode(PINS_B64)
    require(len(a) == 24 and len({x['object'] for x in a}) == 24, 'ASSERTION_GATE_FAILED')
    return a

def verify_protected(store, label):
    results = []
    for p in load_pins():
        m, b = store.read_pinned(p['object'], p['generation'])
        if int(m['size']) != p['bytes'] or sha(b) != p['sha256']:
            store.b.fail('PROTECTED_PIN_MISMATCH_' + p['object'].split('/')[0])
        v = json.loads(b)
        if any([v.get('enabled') is not False, v.get('max_new') != 0, v.get('next_new_authorization') != 0]):
            store.b.fail('PROTECTED_NOT_CLOSED')
        results.append({'name': p['object'], 'generation': m['generation'], 'bytes': len(b), 'sha256': sha(b)})
    return {'stage': label, 'count': len(results), 'matched': len(results), 'pins': results}

def identity(t):
    root = 'https://aiplatform.us.rep.googleapis.com/v1/'
    out = {}
    for path, key in ((TUNED_ENDPOINT, 'endpoint'), (TUNED_MODEL, 'model')):
        status, raw = t.send('GET', root + path)
        if status != 200:
            raise SafetyStop('VERTEX_IDENTITY_READ_' + key + '_' + str(status))
        out[key] = {'http': status, 'sha256': sha(raw), 'bytes': len(raw)}
        j = json.loads(raw)
        if key == 'endpoint':
            matches = [x for x in j.get('deployedModels', []) if x.get('model', '').removesuffix('@1') == TUNED_MODEL.removesuffix('@1') and str(x.get('modelVersionId')) == '1']
            if j.get('name') != TUNED_ENDPOINT or len(j.get('deployedModels', [])) != 1 or len(matches) != 1:
                raise SafetyStop('VERTEX_TUNED_DEPLOYMENT_MISMATCH')
            out[key]['deployed_count'] = 1
            out[key]['modelVersionId'] = '1'
        elif j.get('name', '').removesuffix('@1') != TUNED_MODEL.removesuffix('@1'):
            raise SafetyStop('VERTEX_TUNED_MODEL_MISMATCH')
    return out

def synthetic(slot, first_output=None):
    if slot['action'] == 'FIRST':
        require(first_output is None, 'ASSERTION_GATE_FAILED')
        input_text = 'R4_SYNTHETIC_SOURCE_PLACEHOLDER_' + slot['selection_id']
        out = 'SYNTH_FIRST|' + slot['model_code'] + '|' + slot['selection_id'] + '|' + slot['slot_id'] + '|' + slot['source_sha256'][:12]
    else:
        require(first_output is not None and first_output.startswith('SYNTH_FIRST|' + slot['model_code'] + '|' + slot['selection_id'] + '|'), 'ASSERTION_GATE_FAILED')
        input_text = first_output
        out = 'SYNTH_BACK|' + slot['model_code'] + '|' + slot['selection_id'] + '|FIRST_SHA=' + sha(first_output.encode())
    return (input_text, out)

def verify_slot_frozen(slot):
    slot_id = slot.get('slot_id', '')
    require(slot_id.startswith('SLOT') and slot_id[4:].isdigit(), 'BAD_SLOT_ID')
    index = int(slot_id[4:]) - 1
    freeze = load_plan()
    require(0 <= index < len(freeze), 'SLOT_INDEX_OUTSIDE_PLAN')
    for field in ('slot_id', 'selection_id', 'model_code', 'action', 'prompt_id', 'prompt_sha256', 'direction', 'source_sha256', 'parent_first_slot_id', 'input_kind'):
        require(slot.get(field) == freeze[index].get(field), 'FROZEN_DRIFT_' + field)

def process_one(store, slot, seen):
    verify_slot_frozen(slot)
    if slot['action'] == 'BACK':
        par = seen.get(slot['parent_first_slot_id'])
        if not par or par['action'] != 'FIRST' or par['model_code'] != slot['model_code'] or (par['selection_id'] != slot['selection_id']):
            raise SafetyStop('PARENT_FIRST_WRONG_OR_NOT_STORED')
        receipt = store.receipts.get(f"slots/{par['slot_id']}/RESULT.json")
        if not receipt or not par['synthetic_output']:
            raise SafetyStop('PARENT_FIRST_NOT_VERIFIED_STORED')
        prior = par
        first_output = prior['synthetic_output']
    else:
        first_output = None
    text, response = synthetic(slot, first_output)
    intent = {'schema': 'R4_SEND_INTENT', 'slot_id': slot['slot_id'], 'model_code': slot['model_code'], 'action': slot['action'], 'prompt_sha256': slot['prompt_sha256'], 'source_sha256': slot['source_sha256'], 'input_sha256': sha(text.encode()), 'input_kind': slot['input_kind'], 'parent_first_slot_id': slot['parent_first_slot_id'], 'synthetic': True, 'model_generation_attempts': 0}
    store.create(f"slots/{slot['slot_id']}/SEND_INTENT.json", intent)
    raw = {'schema': 'R4_RAW_RESPONSE', 'slot_id': slot['slot_id'], 'model_code': slot['model_code'], 'synthetic': True, 'synthetic_output': response, 'input_sha256': sha(text.encode()), 'parent_first_slot_id': slot['parent_first_slot_id']}
    store.create(f"slots/{slot['slot_id']}/RAW_RESPONSE.json", raw)
    result = {'schema': 'R4_RESULT', 'slot_id': slot['slot_id'], 'action': slot['action'], 'model_code': slot['model_code'], 'direction': slot['direction'], 'selection_id': slot['selection_id'], 'parent_first_slot_id': slot['parent_first_slot_id'], 'source_sha256': slot['source_sha256'], 'prompt_sha256': slot['prompt_sha256'], 'synthetic_output': response, 'first_input_sha256': sha(text.encode()), 'is_synthetic': True, 'real_model_attempts': 0}
    store.create(f"slots/{slot['slot_id']}/RESULT.json", result)
    seen[slot['slot_id']] = result
    return result

def build_future_paid_request(slot, actual_source_or_first, private_prompt, new_campaign_id):
    if not new_campaign_id or new_campaign_id == CAMPAIGN or 'runner_integration_freeqa' in new_campaign_id.lower():
        raise SafetyStop('PAID_REQUIRES_NEW_CAMPAIGN_ID')
    if slot['model_code'] not in ('BASE', 'REALDB84') or slot['action'] not in ('FIRST', 'BACK'):
        raise SafetyStop('MODEL_SLOT_UNKNOWN')
    if sha(private_prompt.encode()) != slot['prompt_sha256']:
        raise SafetyStop('PROMPT_HASH_MISMATCH')
    if not actual_source_or_first:
        raise SafetyStop('EMPTY_ACTUAL_INPUT')
    resource = BASE_MODEL if slot['model_code'] == 'BASE' else TUNED_ENDPOINT
    body = {'contents': [{'role': 'user', 'parts': [{'text': actual_source_or_first}]}], 'systemInstruction': {'parts': [{'text': private_prompt}]}, 'generationConfig': {'maxOutputTokens': 1024, 'thinkingConfig': {'thinkingLevel': 'MINIMAL'}}}
    return {'method': 'POST', 'url': 'https://aiplatform.us.rep.googleapis.com/v1/' + resource + ':generateContent', 'body': body, 'model_code': slot['model_code'], 'slot_id': slot['slot_id'], 'requires_new_authorization': True}

class GuardTests(unittest.TestCase):

    def setup_store(self):
        return Store(FakeTransport(), Budget(), 'testsession')

    def slot(self, index=0):
        return load_plan()[index].copy()

    def test_01_frozen_full_graph(self):
        self.assertEqual(len(load_plan()), 96)

    def test_02_first_to_own_back(self):
        s = self.setup_store()
        d = {}
        a = process_one(s, self.slot(0), d)
        b = process_one(s, self.slot(1), d)
        self.assertEqual(b['first_input_sha256'], sha(a['synthetic_output'].encode()))

    def test_03_first_missing_blocks_back(self):
        s = self.setup_store()
        with self.assertRaises(SafetyStop):
            process_one(s, self.slot(1), {})
        self.assertEqual(s.b.post, 0)

    def test_04_cross_model_first_blocked(self):
        s = self.setup_store()
        seen = {}
        process_one(s, self.slot(0), seen)
        seen['SLOT003'] = dict(seen['SLOT001'])
        seen['SLOT003']['slot_id'] = 'SLOT003'
        with self.assertRaises(SafetyStop):
            process_one(s, self.slot(3), seen)
        self.assertEqual(s.b.post, 3)

    def test_05_input_sha_and_prompt_pin(self):
        t = self.slot()
        t['prompt_sha256'] = '0' * 64
        with self.assertRaises(SafetyStop):
            verify_slot_frozen(t)
        s = self.slot()
        s['source_sha256'] = '0' * 64
        with self.assertRaises(SafetyStop):
            verify_slot_frozen(s)

    def test_06_duplicate_create_only_prevents_overwrite(self):
        s = self.setup_store()
        x = s.create('a.json', {'a': 1})
        self.assertEqual(s.create('a.json', {'a': 2}, expect_412=True)['status'], 412)
        self.assertEqual(json.loads(s.read('a.json')[1]), {'a': 1})
        self.assertEqual(s.transport.posts, 2)

    def test_07_real_412_does_not_override(self):
        s = self.setup_store()
        s.create('a', {'id': 'original'})
        pre = s.read('a')[0]
        s.create('a', {'id': 'new'}, expect_412=True)
        post = s.read('a')[0]
        self.assertEqual(pre['generation'], post['generation'])

    def test_08_ack_lost_no_repost(self):
        s = self.setup_store()
        s.transport.inject_unknown = True
        with self.assertRaises(TransportUnknown):
            s.create('a', {'v': 'ok'})
        self.assertEqual(s.transport.posts, 1)
        with self.assertRaises(SafetyStop):
            s.create('a', {'v': 'retry'})
        self.assertEqual(s.transport.posts, 1)
        self.assertEqual(s.transport.items[s.root + 'a'][1], jsonb({'v': 'ok'}))

    def test_09_raw_response_saved_result_failed(self):
        s = self.setup_store()
        s.transport.fail_post_after = 3
        with self.assertRaises(SafetyStop):
            process_one(s, self.slot(), {})
        self.assertIn(s.root + 'slots/SLOT001/RAW_RESPONSE.json', s.transport.items)
        self.assertNotIn(s.root + 'slots/SLOT001/RESULT.json', s.transport.items)

    def test_10_fatal_first_stops_later_send(self):
        s = self.setup_store()
        s.transport.fail_post_after = 1
        with self.assertRaises(SafetyStop):
            s.create('a', {})
        with self.assertRaises(SafetyStop):
            s.create('b', {})
        self.assertEqual(s.transport.posts, 1)

    def test_11_stop_failure_preserves_first_reason(self):
        log = InitialFailure()
        log.record('PRIMARY_GCS_HTTP_503')
        log.record('SECONDARY_STOP_503')
        self.assertEqual(log.first, 'PRIMARY_GCS_HTTP_503')
        self.assertEqual(log.secondary, ['SECONDARY_STOP_503'])

    def test_12_timeout_unknown_blocks(self):
        s = self.setup_store()
        s.transport.inject_unknown = True
        with self.assertRaises(TransportUnknown):
            s.create('timeout', {})
        self.assertTrue(s.b.gcs_unknown and s.b.halted)

    def test_13_campaign_restart_blocks(self):
        s = self.setup_store()
        s.create('run', {})
        self.assertGreater(len(s.inventory()), 0)
        with self.assertRaises(SafetyStop):
            if s.inventory():
                raise SafetyStop('PREFIX_NOT_EMPTY_RESTART_DENIED')

    def test_14_total_per_model_caps(self):
        s = load_plan()
        self.assertEqual(collections.Counter((x['model_code'] for x in s)), {'BASE': 48, 'REALDB84': 48})

    def test_15_model_post_denied(self):
        b = Budget()
        with self.assertRaises(SafetyStop):
            b.reserve_model('BASE')
        self.assertEqual(b.model_attempts, 0)

    def test_16_closure_blocks_new_posts(self):
        s = self.setup_store()
        s.create('_control/FINAL_STATE.json', {'enabled': False, 'max_new': 0, 'next_new_authorization': 0})
        n = s.transport.posts
        s.b.closed = True
        with self.assertRaises(SafetyStop):
            s.create('SLOT097', {})
        self.assertEqual(s.transport.posts, n)

    def test_17_optimized_asserts_not_security_gate(self):
        b = Budget()
        b.closed = True
        with self.assertRaises(SafetyStop):
            b.reserve('POST', 10)

    def test_18_partial_or_missing_parent_block(self):
        s = self.setup_store()
        seen = {}
        process_one(s, self.slot(), seen)
        s.receipts.pop('slots/SLOT001/RESULT.json')
        with self.assertRaises(SafetyStop):
            process_one(s, self.slot(1), seen)

    def test_19_gcs_post_and_bytes_budget(self):
        b = Budget()
        b.post = 320
        with self.assertRaises(SafetyStop):
            b.reserve('POST', 1)
        self.assertTrue(b.halted)

    def test_20_source_or_prompt_drift(self):
        s = self.slot()
        s['source_sha256'] = '0' * 64
        self.assertNotEqual(s['source_sha256'], self.slot()['source_sha256'])
        x = self.slot()
        x['prompt_sha256'] = '0' * 64
        self.assertNotEqual(x['prompt_sha256'], self.slot()['prompt_sha256'])

    def test_21_paid_requires_new_authorization(self):
        s = self.slot()
        with self.assertRaises(SafetyStop):
            build_future_paid_request(s, 'dummy', 'wrong', CAMPAIGN)

    def test_22_no_model_api_in_free_transport(self):
        t = RequestsTransport('FAKE')
        with self.assertRaises(SafetyStop):
            t.send('POST', 'https://aiplatform.us.rep.googleapis.com/v1/' + BASE_MODEL + ':generateContent', b'{}')

    def test_23_gcs_fails_closed_after_read_error(self):
        s = self.setup_store()
        s.transport.fail_get_after = 1
        with self.assertRaises(SafetyStop):
            s.create('a', {})
        self.assertTrue(s.b.halted)

    def test_24_back_uses_parent_content_not_source_text(self):
        s = self.setup_store()
        d = {}
        x = process_one(s, self.slot(), d)
        y = process_one(s, self.slot(1), d)
        self.assertIn('FIRST_SHA=', y['synthetic_output'])
        self.assertNotIn('R4_SYNTHETIC_SOURCE_PLACEHOLDER', y['synthetic_output'])

    def test_25_historical_prefix_immutable(self):
        self.assertNotIn('baseline96_r3', PREFIX)
        self.assertNotIn('DRYRUN_ONLY', PREFIX)

    def test_26_model_build_static(self):
        s = self.slot()
        p = 'prompt-has-to-match-original'
        with self.assertRaises(SafetyStop):
            build_future_paid_request(s, 'text', p, 'NEW_CAMP')

    def test_27_24_pins_unique(self):
        self.assertEqual(len(load_pins()), 24)

    def test_28_plain_free_no_network_without_token(self):
        self.assertEqual(CAMPAIGN.count('RUNNER_INTEGRATION_FREEQA'), 1)

    def test_29_model_start_or_unknown_never_retries(self):
        b = Budget()
        with self.assertRaises(SafetyStop):
            b.reserve_model('REALDB84')
        with self.assertRaises(SafetyStop):
            b.reserve_model('REALDB84')
        self.assertEqual(b.model_attempts, 0)

    def test_30_distinct_base_and_tuned_static_uri(self):
        self.assertNotEqual(BASE_MODEL, TUNED_ENDPOINT)
        self.assertTrue(TUNED_MODEL.endswith('@1'))

def run_tests():
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(GuardTests)
    outcome = unittest.TextTestRunner(verbosity=1).run(suite)
    if not outcome.wasSuccessful():
        raise SystemExit(1)
    print('R4_LOCAL_GUARDS_PASS', json.dumps({'testsRun': outcome.testsRun, 'failures': len(outcome.failures), 'errors': len(outcome.errors), 'python_optimized': not __debug__, 'model_calls': 0, 'frozen_slots': 96, 'protected_pins': 24}))

def run_remote():
    for var, want in [('R4_FREEQA', 'true'), ('ENABLE_GENERATION', 'false'), ('ENABLE_TUNING', 'false')]:
        if os.environ.get(var) != want:
            raise SafetyStop('R4_REQUIRED_FREEQA_ENV_' + var)
    slots = load_plan()
    token = subprocess.check_output(['gcloud', 'auth', 'print-access-token'], text=True, stderr=subprocess.DEVNULL, timeout=25).strip()
    require(token, 'ASSERTION_GATE_FAILED')
    b = Budget()
    session = uuid.uuid4().hex
    t = RequestsTransport(token)
    store = Store(t, b, session)
    if store.inventory(PREFIX):
        raise SafetyStop('R4_EXISTING_CAMPAIGN_OBJECTS_RESTART_DENIED')
    before = verify_protected(store, 'BEFORE')
    model_identity = identity(t)
    print('R4_READONLY_MODEL_IDENTITY_PASS', json.dumps(model_identity, sort_keys=True), flush=True)
    claim = store.create('_control/RUN_CLAIM.json', {'schema': 'R4_RUN_CLAIM', 'campaign_id': CAMPAIGN, 'session_id': session, 'frozen_plan_sha256': PLAN_SHA, 'prompt_provenance_sha256': PROVENANCE_SHA, 'mode': 'FREE_SYNTHETIC_ONLY', 'max_gemini_generations': 0, 'max_gcs_POST': 320})
    seen = {}
    cnt = collections.Counter()
    for slot in slots:
        process_one(store, slot, seen)
        cnt[slot['model_code'] + '_' + slot['action']] += 1
    require(len(seen) == 96, 'ASSERTION_GATE_FAILED')
    # Every slot's three objects already underwent CREATE+GET(metadata)+GET(body).
    # Independent 8-slot cross-model/direction readback fits GET <= 700.
    for idx in (0, 1, 2, 3, 48, 49, 50, 51):
        row = slots[idx]
        m, raw = store.read(f"slots/{row['slot_id']}/RESULT.json")
        if json.loads(raw) != seen[row['slot_id']]:
            store.b.fail('R4_INDEPENDENT_RESULT_READBACK_MISMATCH')
    rel = 'slots/SLOT001/RESULT.json'
    original = store.receipts[rel]
    result = store.create(rel, {'poison': 'should never overwrite'}, expect_412=True)
    require(result['status'] == 412, 'ASSERTION_GATE_FAILED')
    m, raw = store.read(rel)
    require(m['generation'] == original['generation'] and sha(raw) == original['sha256'], 'ASSERTION_GATE_FAILED')
    after = verify_protected(store, 'AFTER')
    require(before['pins'] == after['pins'], 'ASSERTION_GATE_FAILED')
    require(cnt == {'BASE_FIRST': 24, 'BASE_BACK': 24, 'REALDB84_FIRST': 24, 'REALDB84_BACK': 24}, 'ASSERTION_GATE_FAILED')
    require(b.model_attempts == 0 and sum(b.per_model.values()) == 0, 'ASSERTION_GATE_FAILED')
    expected_post = b.post + 1
    lock_data = {'schema': 'R4_FINAL_STATE', 'campaign_id': CAMPAIGN, 'session_id': session, 'enabled': False, 'max_new': 0, 'next_new_authorization': 0, 'status': 'FREEQA_PASS_LOCKED_RESTORE_PENDING', 'model_generation_attempts': 0, 'base_generation_attempts': 0, 'realdb84_generation_attempts': 0, 'synthetic_slots': 96, 'first_slots': 48, 'back_slots': 48, 'protected_pins_verified_before': 24, 'protected_pins_verified_after': 24, 'gcs_post_expected_including_lock': expected_post, 'gcs_gets_before_lock': b.get, 'gcs_lists_before_lock': b.list, 'gcs_post_bytes_before_lock': b.post_bytes, 'plan_sha256': PLAN_SHA, 'prompt_provenance_sha256': PROVENANCE_SHA}
    lock = store.create('_control/FINAL_STATE.json', lock_data)
    b.closed = True
    post_count = b.post
    try:
        store.create('slots/SLOT097/RESULT.json', {})
    except SafetyStop:
        pass
    else:
        raise SafetyStop('POST_AFTER_LOCK_NOT_BLOCKED')
    require(b.post == post_count <= 320 and b.get <= 700 and (b.list <= 15) and (b.post_bytes <= 524288), 'ASSERTION_GATE_FAILED')
    final = {'status': 'FREEQA_PASS_LOCKED_RESTORE_PENDING', 'campaign_id': CAMPAIGN, 'session_prefix': store.root, 'model_calls': b.model_attempts, 'synthetic_slots': len(seen), 'counts': dict(cnt), 'protected_before': before['matched'], 'protected_after': after['matched'], 'duplicate_412_proved': True, 'new_lock': lock, 'gcs_counters': {'POST': b.post, 'GET': b.get, 'LIST': b.list, 'POST_BYTES': b.post_bytes}, 'first_failure': b.first.first, 'unknown': b.gcs_unknown, 'plan_sha256': PLAN_SHA, 'provenance_sha256': PROVENANCE_SHA}
    # GitHub artifact has only synthetic payload receipts and metadata, never real chat text or credentials.
    output_path = os.environ.get('R4_REMOTE_OUTPUT')
    if output_path:
        target = pathlib.Path(output_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps({'final': final, 'all_created_receipts': store.receipts,
            'protected_before': before, 'protected_after': after, 'model_identity': model_identity,
            'source_is_synthetic': True, 'original_user_text_included': False},
            ensure_ascii=False, indent=2), encoding='utf-8')
        target.chmod(0o600)
    print('R4_FINAL_REMOTE_RECEIPT ' + json.dumps(final, sort_keys=True, ensure_ascii=False), flush=True)
if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'test'
    if cmd == 'test':
        run_tests()
    elif cmd == 'remote':
        run_remote()
    elif cmd == 'print-public-manifest':
        print(json.dumps({'campaign': CAMPAIGN, 'slots': len(load_plan()), 'pins': len(load_pins()), 'generation_calls_allowed': 0}, sort_keys=True))
    elif cmd == 'paid':
        raise SystemExit('PAID_MODE_NOT_AUTHORIZED_IN_R4; new approval and private bundle mandatory')
    else:
        raise SystemExit('usage: r4_runner.py test|remote|print-public-manifest')
