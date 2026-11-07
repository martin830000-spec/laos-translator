import json,pathlib,subprocess,os,sys,hashlib
HERE=pathlib.Path(__file__).resolve().parent;ROOT=HERE.parents[1];sys.path.insert(0,str(HERE));import runner
checks=0
for m in ('35','36'):
 old=json.loads((ROOT/f'experiments/gemini{m}-native500/config.json').read_text());assert old['enabled']is False and old['max_new']==0
 for path in ('KF','KB','LF','LB'):
  variants=['BASE','NP8']+(['FWD','FWD8']if path.endswith('B')else[])
  built={}
  for v in variants:
   r=subprocess.run(['node',str(HERE/'worker.cjs'),m],input=json.dumps({'mode':'build','path':path,'variant':v,'input':'BOUNDARY_SENTINEL_123'})+'\n',capture_output=True,text=True,check=True)
   q=json.loads(r.stdout);assert q['ok'];q=q['value'];built[v]=q
   assert q['model']==runner.MODELS[m]
   assert q['payload']['contents']==[{'role':'user','parts':[{'text':'BOUNDARY_SENTINEL_123'}]}]
   assert q['payload']['generationConfig']['maxOutputTokens']==1024;checks+=3
  x=json.loads(json.dumps(built['NP8']['payload']));del x['generationConfig']['topP'];assert x==built['BASE']['payload'];checks+=1
  if path.endswith('B'):
   s=json.dumps(built['FWD']['payload'].get('system_instruction',built['FWD']['payload'].get('systemInstruction')),ensure_ascii=False)
   assert 'ROLE LOCK:'not in s and 'husband=speaker'not in s and 'wife=speaker'not in s and '부부 사이'not in s
   assert 'Back-translate'not in s and 'presumed original'not in s;checks+=2
for config in (HERE/'35/config.json',HERE/'36/config.json'):
 c=json.loads(config.read_text());assert c['prior_actual']+c['max_new']<=320;checks+=1
print(json.dumps({'checks':checks,'status':'PASS','paid_calls':0}))
