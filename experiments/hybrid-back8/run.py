"""Approved fixed S47 FIRST8 -> Gemini BACK8. Reuses private16 crypto/channel."""
import importlib.util,json,os,sys,time,hashlib
from pathlib import Path
p=Path(__file__).resolve().parents[1]/'s47-realuse16'/'run.py'
s=importlib.util.spec_from_file_location('private16',p);b=importlib.util.module_from_spec(s);s.loader.exec_module(b)
b.TITLE='WORK_HYBRID_BACK8_20261031_APPROVED';b.PROTOCOL='work-hybrid-back8-v1'
TAG='work-hybrid-back8-20261031-consumed';MODEL='gemini-3.8-flash'
HASHES=['b7900ee7924caf24e8a96e7ec396d14b672ffb48fb80c64c81325008917525f4','66d574e28e0b469fabf0a98e5112fbb37e0cbee553c10b242a608aaa5629e8cd','030c417bfb67deb2cc411bc728a8fbb864c355ee799126aead47be20e84f8e3d','62361a04de3bd3d4e655b718ef59a7829ce6695aa36add992bad45f8b9d32c06','7e3b9b2115a350472e0420d04452552e5f4434afae76cc47b281569e30ceee0a','57b5849513c71f442a4d80b113cc1960d53594b8fd0fae599eecdb8106e979c8','031cd98b4be0ddc6246d3e141df681e81a16948ec33e2b02e32d34d69a917ce9','12f373e47fdbbe524a6a0c71bcba9c860567c45578a7f423a11bd4e3df5a3dc6']
PROMPT_HASH='cc9369f17494cff4d2f2557b5f53bdf20ebee5cde7192fc706bef5df4209ee59'
def validate(v):
 b.check(set(v)=={'cases','prompts'} and b.digest(v['prompts'])==PROMPT_HASH)
 b.check(len(v['cases'])==8)
 for i,c in enumerate(v['cases']):
  b.check(set(c)=={'id','repeat','side','text'} and c['id']==[386,386,333,333,258,258,123,123][i] and c['repeat']==i%2+1 and c['side']==('K' if i<4 else 'L'))
  b.check(hashlib.sha256(c['text'].encode()).hexdigest()==HASHES[i])
def payload(c,prompts):
 return {'systemInstruction':{'parts':[{'text':prompts['husband' if c['side']=='K' else 'wife']}]},'contents':[{'role':'user','parts':[{'text':c['text']}]}],'generationConfig':{'maxOutputTokens':2048,'thinkingConfig':{'thinkingLevel':'low','includeThoughts':False}}}
def endpoint(method,q):
 return b.request_json('https://generativelanguage.googleapis.com/v1beta/models/'+MODEL+':'+method,{'x-goog-api-key':os.environ['GEMINI_API_KEY'],'Content-Type':'application/json'},q,timeout=90)
def run(v,send,count,persist):
 validate(v);d={'status':'PREFLIGHT','model':MODEL,'attempts':0,'responses':0,'count_token_requests':0,'claude_calls':0,'first_calls':0,'retries':0,'estimated_usd':0,'max_usd':.12,'records':[],'prompt_sha256':PROMPT_HASH};persist(d)
 try:
  qs=[payload(c,v['prompts']) for c in v['cases']]
  counts=[]
  for q in qs:
   d['count_token_requests']+=1;persist(d)
   n=count({'generateContentRequest':dict(q,model='models/'+MODEL)})['totalTokens'];b.check(isinstance(n,int) and 0<n<=8192);counts.append(n)
  b.check(sum((n+32)*.75+2048*3.75 for n in counts)/1e6<=.12)
  for c,q,n in zip(v['cases'],qs,counts):
   b.check(d['attempts']<8 and d['estimated_usd']+((n+32)*.75+2048*3.75)/1e6<=.12)
   rec={'id':c['id'],'repeat':c['repeat'],'side':c['side'],'input':c['text'],'input_sha256':hashlib.sha256(c['text'].encode()).hexdigest(),'payload':q,'counted_input_tokens':n,'status':'SENT_OR_UNKNOWN'}
   d['attempts']+=1;d['records'].append(rec);persist(d);start=time.perf_counter()
   try:
    raw=send(q);rec['response']=raw;d['responses']+=1
    u=raw['usageMetadata'];rec['usage']=u;b.check(u['promptTokenCount']<=8192 and u['totalTokenCount']>=u['promptTokenCount']);output_tokens=u['totalTokenCount']-u['promptTokenCount'];b.check(output_tokens<=2048)
    rec['estimated_usd']=(u['promptTokenCount']*.75+output_tokens*3.75)/1e6;d['estimated_usd']+=rec['estimated_usd']
    a=raw['candidates'];b.check(len(a)==1 and a[0]['finishReason']=='STOP');parts=a[0]['content']['parts'];text=''.join(x.get('text','') for x in parts if not x.get('thought'));b.check(bool(text.strip()));rec['translation']=text;rec['status']='SUCCESS'
   finally:rec['ms']=round((time.perf_counter()-start)*1000);persist(d)
  d['status']='COMPLETE_REVIEW_REQUIRED'
 except Exception as e:d['status']='HOLD_NO_RETRY';d['error_type']=type(e).__name__
 persist(d);return d
def execute(state):
 h,init=b.read(state/'handshake.json'),b.read(state/'init.json');b.check(os.environ['GITHUB_RUN_ATTEMPT']=='1' and h['commit']==os.environ['GITHUB_SHA'])
 until=time.monotonic()+600;v=None
 while time.monotonic()<until:
  issue=b.github('/repos/'+b.REPO+'/issues/'+str(h['issue_number']));body=json.loads(issue['body']);b.check(issue['title']==b.TITLE and issue['user']['login']==b.OWNER and issue['state']=='open' and body['nonce']==init['nonce'] and body['result_public_key']==init['result_public_key'])
  if body['phase']=='sealed':v=b.unseal(body['envelope'],state/'input-private.pem',b.aad_for(h,'input'));break
  b.check(body['phase']=='init');time.sleep(5)
 b.check(v is not None);validate(v)
 persist=lambda d:b.write(state/'sealed-result.json',b.seal(dict(d,github={k:h[k] for k in ['run_id','issue_number','commit']}),init['result_public_key'],b.aad_for(h,'result')))
 b.github('/repos/'+b.REPO+'/git/refs',{'ref':'refs/tags/'+TAG,'sha':h['commit']})
 with (state/'started.lock').open('x') as f:f.write(str(h['run_id']))
 d=run(v,lambda q:endpoint('generateContent',q),lambda q:endpoint('countTokens',q),persist)
 print(json.dumps({k:d[k] for k in ['status','attempts','responses','count_token_requests','estimated_usd','claude_calls','first_calls','retries']}),flush=True)
 b.check(d['status']=='COMPLETE_REVIEW_REQUIRED')
if __name__=='__main__':
 try:
  mode=sys.argv[1];state=Path(sys.argv[2])
  if mode=='prepare':b.prepare(state)
  elif mode=='execute':execute(state)
  else:raise ValueError()
 except Exception as e:print('Hybrid HOLD '+type(e).__name__,flush=True);sys.exit(2)

