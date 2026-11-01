"""New bounded two-engine comparison, frozen prompts and private transport."""
from pathlib import Path
import base64,copy,hashlib,importlib.util,json,os,re,sys,time,urllib.request,urllib.error,zlib
ROOT=Path(__file__).resolve().parent
def load(n,p):
 s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
b=load('new8_crypto',ROOT.parent/'s47-realuse16/run.py')
a=load('new8_frozen',ROOT.parent/'claude-real20-120/adapters.py')
stream=load('new8_existing_stream',ROOT.parent/'opus-c-stream/adapter.py')
C=json.loads((ROOT/'config.json').read_text())
b.PROTOCOL='sonnet-opus-new8-20261101-v1'
b.TITLE='WORK_SONNET_OPUS_NEW8_STAGE'+str(C['phase'])+'_20261101_APPROVED_V1'
b.TAG='sonnet-opus-new8-stage'+str(C['phase'])+'-16-20261101-consumed-v1'
def sh(x):return hashlib.sha256(x).hexdigest()
def validate(m):
 assert sh(b.canonical(m))==C['manifest_canonical_sha256']
 assert m['phase']==C['phase'] and m['maximum_new_attempts']==16 and m['whole_task_maximum']==32
 assert m['retries']==0 and m['extra_models']==0 and m['transport']=='SAME_STREAM_TRUE'
 assert len(m['sources'])==4 and sum(x['side']=='K' for x in m['sources'])==2
 assert len(set(x['id'] for x in m['sources']))==4
 for x in m['sources']:assert x['development_allowed'] and sh(x['source'].encode())==x['source_sha256']
 for n,h in m['frozen_file_sha256'].items():assert sh((ROOT.parent/n).read_bytes())==h
 for e in ['S','O']:
  for side in ['K','L']:
   for stage in ['first','back']:
    q=a.build('offline-contract',side,stage,e)
    assert q['model']==a.MODELS[e] and q['max_tokens']==2048 and q['output_config']=={'effort':'low'}
    assert q['thinking']=={'type':'between_tools' if e=='S' else 'adaptive'}
 return m
def synthetic_test():
 # Exercise the same decoder for both exact models, split UTF-8, end_turn,
 # raw whitespace retention for S1, and incomplete FIRST rejection.
 for model in ['claude-sonnet-5-5','claude-opus-5-5']:
  stream.MODEL=model;d=stream.Decoder()
  for x in [{'type':'message_start','message':{'model':model,'usage':{'input_tokens':3}}},{'type':'content_block_start','index':0,'content_block':{'type':'text','text':''}},{'type':'content_block_delta','index':0,'delta':{'type':'text_delta','text':' \u0e81\u0ec8\u0ead\u0e99. '}},{'type':'content_block_stop','index':0},{'type':'message_delta','delta':{'stop_reason':'end_turn'},'usage':{'output_tokens':4}},{'type':'message_stop'}]:
   wire=('data: '+json.dumps(x,ensure_ascii=False)+'\n\n').encode()
   for v in wire:d.feed(bytes([v]))
  o=d.finish();assert o['status']=='SUCCESS' and o['raw_text']==' \u0e81\u0ec8\u0ead\u0e99. ' and o['response']['usage']['output_tokens']==4
  assert stream.Decoder().finish()['status']=='FAILED'
 return True
def live(q):
 stream.MODEL=q['model'];d=stream.Decoder();started=time.perf_counter();wire=[];first_sentence=None
 req=urllib.request.Request('https://api.anthropic.com/v1/messages',data=json.dumps(q,ensure_ascii=False).encode(),headers={'x-api-key':os.environ['ANTHROPIC_API_KEY'],'anthropic-version':'2023-06-01','Content-Type':'application/json'})
 try:
  with urllib.request.build_opener(b.NoRedirect).open(req,timeout=90) as response:
   while True:
    chunk=response.read1(4096)
    if not chunk:break
    ms=(time.perf_counter()-started)*1000;wire.append({'ms':ms,'bytes_b64':base64.b64encode(chunk).decode()})
    snap=d.feed(chunk)
    if first_sentence is None and re.search(r'[.!?\u3002\uff01\uff1f](?:\s|$)',snap['raw_text']):first_sentence=ms
    if d.done:break
   snap=d.finish()
   return {'http_status':response.status,'response':snap['response'],'stream_snapshot':snap,'events':d.events,'wire':wire,'first_sentence_terminator_ms':first_sentence,'total_ms':(time.perf_counter()-started)*1000}
 except urllib.error.HTTPError as exc:
  return {'http_status':exc.code,'error_body':exc.read(65536).decode(errors='replace'),'total_ms':(time.perf_counter()-started)*1000}
def run(m,state,persist,transport=live):
 validate(m);data={'experiment_id':m['experiment_id'],'phase':m['phase'],'status':'RUNNING','attempts':0,'retries':0,'per_engine':{'S':0,'O':0},'slots':[]}
 with (state/'once.journal').open('x') as f:f.write('0\n')
 persist(data)
 for i,case in enumerate(m['sources']):
  for engine in m['first_engine_order'][i]:
   first=None
   for stage in ['first','back']:
    x={'slot':len(data['slots'])+1,'case_id':case['id'],'side':case['side'],'engine':engine,'stage':stage,'attempted':False};data['slots'].append(x)
    if stage=='back' and first is None:x['status']='SKIPPED_DEPENDENCY';persist(data);continue
    text=case['source'] if stage=='first' else first
    q=a.build(text,case['side'],stage,engine);q['stream']=True
    assert data['attempts']<16 and data['per_engine'][engine]<8
    data['attempts']+=1;data['per_engine'][engine]+=1
    x.update(attempted=True,attempt=data['attempts'],status='SENT_OR_UNKNOWN',input=text,input_sha256=sh(text.encode()),payload=q,payload_sha256=b.digest(q))
    with (state/'once.journal').open('a') as f:f.write(json.dumps({'attempt':data['attempts'],'payload_sha256':x['payload_sha256']})+'\n')
    persist(data) # encrypted write before every send; uncertain attempts never replayed
    try:
     r=transport(q);x.update(r);raw=r.get('response') or {};x['response_sha256']=b.digest(raw)
     x['usage']=raw.get('usage',{});x['estimated_usd']=a.cost(x['usage'],engine)
     out=a.inspect(raw,text,case['side'],stage,engine);x.update(out)
     if r.get('http_status')!=200 or r.get('stream_snapshot',{}).get('status')!='SUCCESS':x['status']='FAILED'
     if raw and raw.get('model')!=q['model']:x['status']='FAILED';raise RuntimeError('MODEL_MISMATCH')
     if r.get('http_status') in [401,403]:raise RuntimeError('GLOBAL_AUTH_FAILURE')
     if stage=='first' and x['status']=='SUCCESS':first=x['translation']
    except RuntimeError:
     data['status']='GLOBAL_SAFETY_STOP';persist(data);raise
    except Exception as exc:x.update(status='FAILED',error_type=type(exc).__name__)
    finally:persist(data)
 data['status']='PHASE_COMPLETE_QUALITY_REVIEW_REQUIRED';persist(data);return data
def prepare(state):
 assert not state.exists();synthetic_test()
 issue=b.github('/repos/'+b.REPO+'/issues/'+str(C['issue_number']))
 assert issue['title']==b.TITLE and issue['user']['login']==b.OWNER and issue['state']=='open'
 init=json.loads(issue['body']);assert init['protocol']==b.PROTOCOL and init['phase']=='init'
 b.public_key(init['result_public_key']);assert len(init['nonce'])==64
 state.mkdir(parents=True,mode=0o700);pub=b.keypair(state/'input-private.pem')
 h={'protocol':b.PROTOCOL,'nonce':init['nonce'],'run_id':os.environ['GITHUB_RUN_ID'],'issue_number':C['issue_number'],'commit':os.environ['GITHUB_SHA'],'input_public_key':pub,'result_key_sha256':sh(init['result_public_key'].encode())}
 b.write(state/'handshake.json',h);b.write(state/'init.json',init)
 print('Public handshake ready. New model attempts 0.',flush=True)
def execute(state):
 assert os.environ['GITHUB_RUN_ATTEMPT']=='1'
 h=b.read(state/'handshake.json');init=b.read(state/'init.json')
 assert h['commit']==os.environ['GITHUB_SHA']
 persist=lambda d:b.write(state/'sealed-result.json',b.seal(dict(d,execution=h),init['result_public_key'],b.aad_for(h,'result')))
 until=time.monotonic()+900;m=None
 try:
  while time.monotonic()<until:
   issue=b.github('/repos/'+b.REPO+'/issues/'+str(C['issue_number']));body=json.loads(issue['body'])
   assert issue['state']=='open' and issue['title']==b.TITLE and issue['user']['login']==b.OWNER
   assert body['nonce']==init['nonce'] and body['result_public_key']==init['result_public_key']
   if body['phase']=='sealed':
    v=b.unseal(body['envelope'],state/'input-private.pem',b.aad_for(h,'input'))
    m=json.loads(zlib.decompress(base64.b64decode(v['zlib_manifest_b64'])));validate(m);break
   assert body['phase']=='init';time.sleep(5)
  assert m is not None
  if C['phase']==2:
   assert C['stage1_gate']=='PROCEED_STAGE2'
   b.github('/repos/'+b.REPO+'/git/ref/tags/sonnet-opus-new8-stage1-16-20261101-consumed-v1')
  b.github('/repos/'+b.REPO+'/git/refs',{'ref':'refs/tags/'+b.TAG,'sha':h['commit']})
  d=run(m,state,persist);print(json.dumps({k:d[k] for k in ['phase','attempts','per_engine','status']}),flush=True)
 except Exception:
  if not (state/'sealed-result.json').exists():persist({'status':'PREFLIGHT_STOP','attempts':0})
  raise
def client(state,mode):
 if mode=='client-init':
  assert not state.exists();state.mkdir(parents=True,mode=0o700)
  pub=b.keypair(state/'result-private.pem');b.write(state/'init.json',{'protocol':b.PROTOCOL,'phase':'init','nonce':os.urandom(32).hex(),'result_public_key':pub})
 elif mode=='client-seal':
  h=b.read(state/'handshake.json');init=b.read(state/'init.json');m=b.read(state/'manifest.json');validate(m)
  assert h['nonce']==init['nonce'] and h['result_key_sha256']==sh(init['result_public_key'].encode())
  assert str(h['issue_number'])==str(C['issue_number']) and h['commit']==C['execution_commit'] and str(h['run_id'])==str(C['run_id'])
  packed={'zlib_manifest_b64':base64.b64encode(zlib.compress(b.canonical(m),9)).decode()}
  body=dict(init,phase='sealed',envelope=b.seal(packed,h['input_public_key'],b.aad_for(h,'input')));assert len(json.dumps(body))<64000
  b.write(state/'sealed-issue-body.json',body)
 elif mode=='client-decrypt':
  h=b.read(state/'handshake.json');d=b.unseal(b.read(state/'sealed-result.json'),state/'result-private.pem',b.aad_for(h,'result'));b.write(state/'actual-private.json',d)
if __name__=='__main__':
 try:
  mode=sys.argv[1];state=Path(sys.argv[2])
  if mode=='prepare':prepare(state)
  elif mode=='execute':execute(state)
  elif mode=='selftest':synthetic_test();print('SSE contract checks passed; calls 0')
  else:client(state,mode)
 except Exception as exc:
  print('NEW8 STOP '+type(exc).__name__,flush=True);sys.exit(2)
