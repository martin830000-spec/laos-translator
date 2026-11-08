"""SCREEN160 free readiness only. No generation request exists in this file."""
import os,json,hashlib,platform,concurrent.futures,urllib.request,urllib.error
from google.cloud import storage
from google.api_core.exceptions import NotFound
CAMPAIGN='GPT_LUNA_TERRA_SCREEN160_20261109'
PREFIX='research/gemini-model-native500-20261107/gpt-luna-terra-screen160-20261109'
def main():
 assert os.environ['GITHUB_REF']=='refs/heads/research/gemini-model-native500-20261107'
 assert os.environ['GITHUB_RUN_ATTEMPT']=='1'
 report={'campaign':CAMPAIGN,'generation_attempts':0,'openai_key_present':bool(os.environ.get('OPENAI_API_KEY')),'python':platform.python_version(),'run_id':os.environ['GITHUB_RUN_ID'],'commit':os.environ['GITHUB_SHA']}
 # Only a single read-only model-list request; never a hello/completion.
 if report['openai_key_present']:
  req=urllib.request.Request('https://api.openai.com/v1/models',headers={'Authorization':'Bearer '+os.environ['OPENAI_API_KEY']})
  try:
   with urllib.request.urlopen(req,timeout=20) as r:
    data=json.load(r);ids={x['id'] for x in data['data']};report['model_metadata']={'http_status':r.status,'models':{m:m in ids for m in ['gpt-6-luna','gpt-6.1-terra']}}
  except urllib.error.HTTPError as e:
   try:code=json.loads(e.read()).get('error',{}).get('code')
   except Exception:code='UNPARSEABLE_ERROR'
   report['model_metadata']={'http_status':e.code,'error_code':code}
  except Exception as e:report['model_metadata']={'exception_type':type(e).__name__}
 b=storage.Client(project='gen-lang-client-0422436907').bucket('lao-translator-src-460077888071')
 try:
  old='research/gemini-model-native500-20261107/fidelity240-20261108/35'
  ledger=json.load(open('experiments/gemini35-fidelity240/35/ledger.json'))
  done=[]
  for p in ledger['phases']:
   raw=b.blob(old+'/results/'+p['plan_sha256']+'/RUN_FINISHED.json').download_as_bytes(timeout=20)
   d=json.loads(raw);done.append({'attempted':d['attempted'],'failed':d['failed'],'sha256':hashlib.sha256(raw).hexdigest()})
  report['fidelity240']={'attempted':sum(x['attempted'] for x in done),'runs':done,'repo_ledger_attempted':ledger['attempted']}
  assert report['fidelity240']['attempted']==224
  paths=[f'{PREFIX}/budget/{i:04d}.json' for i in range(1,161)]+[f'{PREFIX}/STATE.json',f'{PREFIX}/LOCK.json']
  with concurrent.futures.ThreadPoolExecutor(max_workers=8) as p:
   present=list(p.map(lambda n:b.blob(n).exists(timeout=20),paths))
  report['existing_campaign_objects']=[n for n,yes in zip(paths,present) if yes]
  assert not any(present),'EXISTING_CAMPAIGN_REQUIRES_RESUME'
  raw=json.dumps({'kind':'FREE_SYNTHETIC','text':'Test 한국어 ລາວ 123','generation_calls':0},ensure_ascii=False,sort_keys=True).encode()
  obj=b.blob(PREFIX+'/readiness/synthetic.json');obj.upload_from_string(raw,if_generation_match=0,timeout=20)
  actual=obj.download_as_bytes(timeout=20);assert actual==raw
  report['gcs_roundtrip']={'pass':True,'sha256':hashlib.sha256(actual).hexdigest()}
 except Exception as e:report['gcs_error']={'exception_type':type(e).__name__,'code':getattr(e,'code',None)}
 print('SCREEN160_READINESS='+json.dumps(report,sort_keys=True))
 out=os.path.join(os.environ['RUNNER_TEMP'],'screen160-readiness.json')
 with open(out,'w') as f:json.dump(report,f,indent=2)
if __name__=='__main__':main()
