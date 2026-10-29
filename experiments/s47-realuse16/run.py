"""Approved private S47 sixteen-call controller. No monetary gate or retries.

Only public keys/nonces and authenticated ciphertext leave the local client or
runner. The original S47 adapter is imported unchanged. No plaintext input,
response, exception body or API key is printed or uploaded.
"""
import argparse
import base64
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import secrets
import sys
import time
import urllib.error
import urllib.request

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent
REPO = 'martin830000-spec/laos-translator'
OWNER = 'martin830000-spec'
TITLE = 'S47_REALUSE16_20261030_NO_MONEY_LIMIT'
PROTOCOL = 's47-private16-v1'
TAG = 's47-realuse16-20261030-consumed'
MODEL = 'claude-haiku-5-5'
MAX_CALLS = 16
EXPECTED = {
    386: ('K', '0367123b031d7e5e97ec443e4a8b6a12004a69b4c57827f1de96c7954051a73e'),
    333: ('K', 'b24ac72052362554e89c1d1d89919a9ea468dba0534131ed201351d66ebdff97'),
    258: ('L', '98bd5460856a8535a918f5786452aa9103a55bde1a8b1ca29189a54aa9fc7fa6'),
    123: ('L', '93f2bc4fc03ae77380a3aa5d050aa28c9123aa918938e4b0c452e60a64230287'),
}
ADAPTER_SHA = 'e85a3ff89f83aca7638f86b7b518aa1b1a5c6d060bc10ac9b436686138e15310'
CANDIDATE_SHA = '2805fdae658f7dee0c8744aa9a618c8045d61f58f652e7813d789a73e3f27330'


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True).encode('utf-8')


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def check(condition):
    if not condition:
        raise ValueError('Validation failed')


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(value, ensure_ascii=False, indent=2).encode('utf-8')
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_bytes(data)
    os.chmod(temporary, 0o600)
    temporary.replace(path)


def keypair(path):
    path = Path(path)
    with path.open('xb') as f:
        private = rsa.generate_private_key(public_exponent=65537, key_size=3072)
        f.write(private.private_bytes(serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    os.chmod(path, 0o600)
    return private.public_key().public_bytes(serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo).decode('ascii')


def public_key(pem):
    key = serialization.load_pem_public_key(pem.encode('ascii'))
    check(isinstance(key, rsa.RSAPublicKey) and key.key_size >= 3072)
    return key


def seal(value, pem, aad):
    key = AESGCM.generate_key(bit_length=256)
    nonce = secrets.token_bytes(12)
    wrapped = public_key(pem).encrypt(key, padding.OAEP(
        mgf=padding.MGF1(hashes.SHA256()), algorithm=hashes.SHA256(), label=None))
    ciphertext = AESGCM(key).encrypt(nonce, canonical(value), canonical(aad))
    return dict(protocol=PROTOCOL, aad=aad, wrapped_key=base64.b64encode(wrapped).decode(),
        iv=base64.b64encode(nonce).decode(), ciphertext=base64.b64encode(ciphertext).decode())


def unseal(envelope, private_path, aad):
    check(envelope['protocol'] == PROTOCOL and envelope['aad'] == aad)
    private = serialization.load_pem_private_key(Path(private_path).read_bytes(), password=None)
    key = private.decrypt(base64.b64decode(envelope['wrapped_key'], validate=True),
        padding.OAEP(mgf=padding.MGF1(hashes.SHA256()), algorithm=hashes.SHA256(), label=None))
    data = AESGCM(key).decrypt(base64.b64decode(envelope['iv'], validate=True),
        base64.b64decode(envelope['ciphertext'], validate=True), canonical(aad))
    return json.loads(data)


def aad_for(h, purpose):
    return dict(protocol=PROTOCOL, nonce=h['nonce'], run_id=str(h['run_id']),
        issue_number=int(h['issue_number']), purpose=purpose)


def load_adapter():
    p = ROOT.parent / 'haiku-50-steps' / 'adapter.py'
    check(hashlib.sha256(p.read_bytes()).hexdigest() == ADAPTER_SHA)
    spec = importlib.util.spec_from_file_location('s47_original_adapter', p)
    adapter = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(adapter)
    check(digest(adapter.CANDIDATE) == CANDIDATE_SHA)
    return adapter


def validate_cases(cases):
    check(len(cases) == 4 and [int(c['id']) for c in cases] == list(EXPECTED))
    for c in cases:
        side, sha = EXPECTED[int(c['id'])]
        check(c['side'] == side and hashlib.sha256(c['source'].encode()).hexdigest() == sha)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError('Redirect forbidden')


def request_json(url, headers, data=None, timeout=60):
    req = urllib.request.Request(url, headers=headers,
        data=None if data is None else json.dumps(data, ensure_ascii=False).encode())
    with urllib.request.build_opener(NoRedirect).open(req, timeout=timeout) as response:
        return json.loads(response.read())


def github(path, data=None):
    check(path.startswith('/repos/' + REPO + '/'))
    return request_json('https://api.github.com' + path,
        {'Authorization': 'Bearer ' + os.environ['GITHUB_TOKEN'],
         'Accept': 'application/vnd.github+json', 'Content-Type': 'application/json',
         'X-GitHub-Api-Version': '2022-11-28'}, data)


def initial_issue(event):
    check(os.environ['GITHUB_REPOSITORY'] == REPO and os.environ['GITHUB_RUN_ATTEMPT'] == '1')
    issue = event['issue']
    check(issue['title'] == TITLE and issue['user']['login'] == OWNER)
    init = json.loads(issue['body'])
    check(init['protocol'] == PROTOCOL and init['phase'] == 'init')
    check(len(init['nonce']) == 64 and all(c in '0123456789abcdef' for c in init['nonce']))
    public_key(init['result_public_key'])
    return issue, init


def prepare(state):
    check(not state.exists())
    load_adapter()
    issue, init = initial_issue(read(os.environ['GITHUB_EVENT_PATH']))
    state.mkdir(mode=0o700, parents=True)
    pem = keypair(state/'input-private.pem')
    h = dict(protocol=PROTOCOL, nonce=init['nonce'], run_id=os.environ['GITHUB_RUN_ID'],
        issue_number=issue['number'], commit=os.environ['GITHUB_SHA'], input_public_key=pem,
        result_key_sha256=hashlib.sha256(init['result_public_key'].encode()).hexdigest())
    write(state/'init.json', init)
    write(state/'handshake.json', h)
    print('Public handshake prepared; model calls 0', flush=True)


def cost(usage):
    i = int(usage.get('input_tokens', 0))
    o = int(usage.get('output_tokens', 0))
    ci = int(usage.get('cache_creation_input_tokens', 0))
    cr = int(usage.get('cache_read_input_tokens', 0))
    factor = 5 if i + ci + cr > 100000 else 1
    return round(factor*(i*.10 + o*.50 + ci*.125 + cr*.01)/1000000, 9)


class Controller:
    def __init__(self, cases, persist):
        validate_cases(cases)
        self.adapter = load_adapter()
        self.persist = persist
        self.data = dict(status='RUNNING', model=MODEL, candidate='S47', candidate_sha256=CANDIDATE_SHA,
            adapter_sha256=ADAPTER_SHA, cases=cases, attempts=0, responses=0, first_attempts=0,
            back_attempts=0, retries=0, records=[], estimated_usd=0.0, money_limit=None,
            actual_invoice='UNKNOWN', native_lao_review=False)

    def call(self, case, repeat, stage, visible, transport):
        d = self.data
        field = 'first_attempts' if stage == 'first' else 'back_attempts'
        check(d['attempts'] < MAX_CALLS and d[field] < 8)
        q = self.adapter.build_request(visible, case['side'], stage)
        check(q['model'] == MODEL and q['max_tokens'] == 2048)
        d['attempts'] += 1
        d[field] += 1
        record = dict(attempt=d['attempts'], record_id=case['id'], repeat=repeat,
            path=case['side']+'_'+stage, input=visible, payload=q,
            payload_sha256=digest(q), status='SENT_OR_UNKNOWN', usage=None)
        d['records'].append(record)
        self.persist(d)  # encrypted pre-send journal; uncertain attempts are never replayed
        started = time.perf_counter()
        try:
            raw = transport(q)
            record['response'] = raw
            d['responses'] += 1
            record['usage'] = raw.get('usage', {})
            record['estimated_usd'] = cost(record['usage'])
            d['estimated_usd'] += record['estimated_usd']
            text = self.adapter.extract_translation(raw)
            record['translation'] = text
            record['status'] = 'SUCCESS'
            return text
        except Exception as e:
            record['error_type'] = type(e).__name__
            record['status'] = 'STOP_TECHNICAL_OR_UNKNOWN'
            d['status'] = 'HOLD_TECHNICAL_OR_UNKNOWN'
            raise
        finally:
            record['ms'] = round((time.perf_counter()-started)*1000)
            self.persist(d)

    def run(self, transport):
        try:
            for case in self.data['cases']:
                for repeat in (1, 2):
                    first = self.call(case, repeat, 'first', case['source'], transport)
                    self.call(case, repeat, 'back', first, transport)
            self.data['status'] = 'HOLD_FOUR_PATH_SEMANTIC_REVIEW'
        finally:
            self.persist(self.data)


def live(q):
    try:
        return request_json('https://api.anthropic.com/v1/messages',
            {'x-api-key': os.environ['ANTHROPIC_API_KEY'], 'anthropic-version': '2023-06-01',
             'Content-Type': 'application/json'}, q, timeout=90)
    except urllib.error.HTTPError as e:
        return dict(stop_reason='http_error', http_status=e.code,
            error_body=e.read(65536).decode('utf-8', errors='replace'))


def execute(state):
    h, init = read(state/'handshake.json'), read(state/'init.json')
    check(str(h['run_id']) == os.environ['GITHUB_RUN_ID'])
    check(os.environ['GITHUB_RUN_ATTEMPT'] == '1' and os.environ['GITHUB_SHA'] == h['commit'])
    adapter = load_adapter()
    del adapter
    until = time.monotonic() + 900
    cases = None
    while time.monotonic() < until:
        issue = github('/repos/'+REPO+'/issues/'+str(h['issue_number']))
        check(issue['user']['login'] == OWNER and issue['title'] == TITLE and issue['state'] == 'open')
        body = json.loads(issue['body'])
        check(body['nonce'] == init['nonce'] and body['result_public_key'] == init['result_public_key'])
        if body['phase'] == 'sealed':
            cases = unseal(body['envelope'], state/'input-private.pem', aad_for(h, 'input'))['cases']
            validate_cases(cases)
            break
        check(body['phase'] == 'init')
        time.sleep(10)  # control-channel polling, never a model retry
    check(cases is not None)
    persist = lambda d: write(state/'sealed-result.json', seal(d, init['result_public_key'], aad_for(h, 'result')))
    try:
        check(bool(os.environ.get('ANTHROPIC_API_KEY')))
        metadata = request_json('https://api.anthropic.com/v1/models/'+MODEL,
            {'x-api-key': os.environ['ANTHROPIC_API_KEY'], 'anthropic-version': '2023-06-01'}, timeout=30)
        check(metadata['id'] == MODEL)
        # Independent persistent lock, never touch old128. Existing tag -> fail closed.
        github('/repos/'+REPO+'/git/refs', {'ref':'refs/tags/'+TAG,'sha':h['commit']})
        with (state/'started.lock').open('x') as f:
            f.write(str(h['run_id']))
        controller = Controller(cases, persist)
        controller.data['model_metadata'] = metadata
        controller.data['github'] = {k:h[k] for k in ['run_id','issue_number','commit']}
        try:
            controller.run(live)
        finally:
            print('S47 status='+controller.data['status']+' attempts='+str(controller.data['attempts'])+
                ' responses='+str(controller.data['responses'])+' estimated_usd='+str(round(controller.data['estimated_usd'],9)), flush=True)
    except Exception as e:
        if not (state/'sealed-result.json').exists():
            persist(dict(status='HOLD_PREFLIGHT', attempts=0, responses=0, error_type=type(e).__name__))
        raise


def client_init(state):
    check(not state.exists())
    state.mkdir(mode=0o700, parents=True)
    pem = keypair(state/'result-private.pem')
    write(state/'init.json', dict(protocol=PROTOCOL, phase='init', nonce=secrets.token_hex(32), result_public_key=pem))
    print('Local private result recipient prepared; no model calls')


def client_seal(args):
    state = args.state
    init, h = read(state/'init.json'), read(args.handshake)
    check(h['nonce'] == init['nonce'] and str(h['run_id']) == args.run_id and h['issue_number'] == args.issue_number)
    check(h['result_key_sha256'] == hashlib.sha256(init['result_public_key'].encode()).hexdigest())
    check(h['commit'] == args.commit)
    rows = read(args.records)
    cases = [dict(id=rid, side=side, source=next(r for r in rows if r['id']==rid)['source'])
        for rid,(side,sha) in EXPECTED.items()]
    validate_cases(cases)
    body = dict(init, phase='sealed', envelope=seal({'cases':cases}, h['input_public_key'], aad_for(h, 'input')))
    write(state/'handshake.json', h)
    write(state/'sealed-issue-body.json', body)
    print('Encrypted approved four-source envelope prepared; no model calls')


def main():
    p = argparse.ArgumentParser()
    p.add_argument('mode', choices=['prepare','execute','client-init','client-seal','client-decrypt'])
    p.add_argument('--state', required=True, type=Path)
    p.add_argument('--handshake', type=Path)
    p.add_argument('--records', type=Path)
    p.add_argument('--sealed', type=Path)
    p.add_argument('--run-id')
    p.add_argument('--issue-number', type=int)
    p.add_argument('--commit')
    args = p.parse_args()
    if args.mode == 'prepare': prepare(args.state)
    elif args.mode == 'execute': execute(args.state)
    elif args.mode == 'client-init': client_init(args.state)
    elif args.mode == 'client-seal': client_seal(args)
    else:
        h = read(args.state/'handshake.json')
        result = unseal(read(args.sealed), args.state/'result-private.pem', aad_for(h,'result'))
        write(args.state/'decrypted-result.json', result)
        print('Private result decrypted locally; no model calls')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        # Exceptions may originate from private payloads or API bodies; never print their text.
        print('S47 HOLD error_type='+type(exc).__name__, flush=True)
        sys.exit(2)
