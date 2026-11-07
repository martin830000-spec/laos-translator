from pathlib import Path
import os,sys,json,time,hashlib,importlib.util,subprocess,http.client,datetime,zlib,base64
ROOT=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('cryptoonly',ROOT.parent/'s47-realuse16/run.py');b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b);b.PROTOCOL='gemini-multi1000-v1'
DEADLINE=1794014450 # 2026-11-07 01:20:50 UTC; overwritten by verified config below
cfg=b.read(ROOT/'config.json');DEADLINE=cfg['deadline_epoch']
def guard():
 b.check(os.environ.get('GITHUB_RUN_ATTEMPT')=='1'and cfg['enabled']and cfg['prior_actual']+cfg['max_new']<=1000 and time.time()<DEADLINE)
def prepare(state):
 guard();b.check(not state.exists());i=b.github('/repos/'+b.REPO+'/issues/'+str(cfg['issue_number']));b.check(i['state']=='open'and i['user']['login']==b.OWNER and i['title']==cfg['title']);init=json.loads(i['body']);b.check(init['phase']=='init'and init['protocol']==b.PROTOCOL);state.mkdir(mode=0o700);h=dict(protocol=b.PROTOCOL,nonce=init['nonce'],run_id=os.environ['GITHUB_RUN_ID'],issue_number=cfg['issue_number'],commit=os.environ['GITHUB_SHA'],input_public_key=b.keypair(state/'input-private.pem'),result_key_sha256=hashlib.sha256(init['result_public_key'].encode()).hexdigest());b.write(state/'init.json',init);b.write(state/'handshake.json',h)
def execute(state):
 guard();h=b.read(state/'handshake.json');init=b.read(state/'init.json');r=dict(campaign='GEMINI_MULTI1000_20261107',phase=cfg['phase'],prior_actual=cfg['prior_actual'],attempts=0,slots=[],execution=h|{'input_public_key':None},status='WAITING')
 def save(): b.write(state/'sealed-result.json',b.seal(r,init['result_public_key'],b.aad_for(h,'result')))
 save();w=None;conn=None
 try:
  until=min(time.time()+360,DEADLINE);plan=None
  while time.time()<until:
   i=b.github('/repos/'+b.REPO+'/issues/'+str(cfg['issue_number']));b.check(i['state']=='open'and i['title']==cfg['title']);body=json.loads(i['body']);b.check(body['nonce']==init['nonce']and body['result_public_key']==init['result_public_key'])
   if body['phase']=='sealed':
    data=b.unseal(body['envelope'],state/'input-private.pem',b.aad_for(h,'input'));plan=json.loads(zlib.decompress(base64.b64decode(data['compressed'])));break
   time.sleep(3)
  b.check(plan is not None and b.digest(plan)==cfg['plan_sha256']and plan['prior_actual']==cfg['prior_actual']and len(plan['tasks'])==cfg['max_new']);b.check(len({t['slot']for t in plan['tasks']})==len(plan['tasks']));
  b.github('/repos/'+b.REPO+'/git/refs',{'ref':'refs/tags/'+cfg['tag'],'sha':h['commit']})
  w=subprocess.Popen(['node',str(ROOT/'worker.cjs')],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True,encoding='utf8');key=os.environ['GEMINI_API_KEY'];done={};consecutive=0
  def worker(q):
   w.stdin.write(json.dumps(q,ensure_ascii=False)+'\n');w.stdin.flush();z=json.loads(w.stdout.readline());b.check(z['ok']);return z['value']
  for t in plan['tasks']:
   guard();b.check(r['attempts']<cfg['max_new']);x=dict(t,attempted=False);r['slots'].append(x);done[t['slot']]=x
   if t['path'].endswith('B')and'from_slot'in t:
    f=done[t['from_slot']];b.check(f['path']==t['path'][0]+'F'and f['case_id']==t['case_id'])
    if f.get('inspection',{}).get('status')!='SUCCESS':x['status']='SKIPPED_DEPENDENCY';save();continue
    inp=f['inspection']['displayed']
   else:inp=t['input']
   start=time.perf_counter_ns();q=worker(dict(mode='build',path=t['path'],variant=t['variant'],input=inp));built=time.perf_counter_ns();x.update(input=inp,request=q,sent_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),attempted=True);r['attempts']+=1
   with (state/'once.journal').open('a')as journal:journal.write(json.dumps({'slot':t['slot'],'request_sha256':b.digest(q),'ordinal':cfg['prior_actual']+r['attempts']})+'\n');journal.flush();os.fsync(journal.fileno())
   save();reused=conn is not None
   if conn is None:conn=http.client.HTTPSConnection('generativelanguage.googleapis.com',timeout=45)
   wire=json.dumps(q['payload'],ensure_ascii=False,separators=(',',':')).encode();ts=time.perf_counter_ns()
   try:
    conn.request('POST','/v1beta/models/'+q['model']+':generateContent',body=wire,headers={'x-goog-api-key':key,'Content-Type':'application/json'});sent=time.perf_counter_ns();response=conn.getresponse();headers=time.perf_counter_ns();rawbody=response.read().decode();bodytime=time.perf_counter_ns();raw=json.loads(rawbody.replace(key,'REDACTED'));parsed=time.perf_counter_ns();x.update(http_status=response.status,raw=raw,wire_request=wire.decode(),wire_response=rawbody.replace(key,'REDACTED'),usage=raw.get('usageMetadata'),returned_model_version=raw.get('modelVersion'));x['inspection']=worker(dict(mode='inspect',raw=raw,path=t['path'],variant=t['variant'],input=inp));ready=time.perf_counter_ns();x['timing']={'build_ms':(built-start)/1e6,'send_ms':(sent-ts)/1e6,'ttfb_ms':(headers-ts)/1e6,'body_ms':(bodytime-headers)/1e6,'parse_ms':(parsed-bodytime)/1e6,'api_ms':(bodytime-ts)/1e6,'ready_ms':((built-start)+(ready-ts))/1e6,'connection_reuse_attempted':reused,'dns_tcp_tls_separate':None,'mobile_render_ms':None};x['ready_epoch']=time.time();x['start_epoch']=x['ready_epoch']-(ready-start)/1e9
    if t['path'].endswith('B')and'from_slot'in t:x['pair_wall_ms']=(x['ready_epoch']-done[t['from_slot']]['start_epoch'])*1000
    if response.will_close:conn.close();conn=None
    if response.status in [401,403,429]or response.status>=500:r['status']='PROVIDER_STOP';save();break
    b.check(x['returned_model_version']and x['returned_model_version'].startswith(q['model']));consecutive=consecutive+1 if x['inspection']['status']=='FAILED'else 0
    if consecutive>=2:r['status']='CONSECUTIVE_OUTPUT_FAILURE';save();break
   except Exception as e:x['error_type']=type(e).__name__;r['status']='TRANSPORT_OR_VERSION_STOP';save();break
   save()
  else:r['status']='PHASE_COMPLETE_REVIEW_REQUIRED'
 except Exception as e:r['status']='GUARD_STOP';r['error_type']=type(e).__name__
 finally:
  if conn:conn.close()
  if w:w.terminate()
  r['sender_journal']=(state/'once.journal').read_text()if(state/'once.journal').exists()else'';save();print(json.dumps({'phase':cfg['phase'],'attempts':r['attempts'],'status':r['status']}))
if __name__=='__main__':
 try:(prepare if sys.argv[1]=='prepare'else execute)(Path(sys.argv[2]))
 except Exception as e:print('STOP '+type(e).__name__);sys.exit(2)
