import json,pathlib,subprocess,hashlib,runpy
R=pathlib.Path(__file__).resolve().parents[2];count=0
def test(x):
 global count
 assert x;count+=1
for m in ['35','36']:
 p=subprocess.Popen(['node',str(R/f'experiments/gemini{m}-native500/worker.cjs')],stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True)
 def call(q):
  p.stdin.write(json.dumps(q,ensure_ascii=False)+'\n');p.stdin.flush();r=json.loads(p.stdout.readline());assert r['ok'];return r['value']
 for path in ['KF','KB','LF','LB']:
  text='오늘은 집에서 쉴게 😊' if path in ['KF','LB']else'ມື້ນີ້ຂ້ອຍຈະພັກຢູ່ເຮືອນ 😊'
  base=call(dict(mode='build',path=path,variant='BASE',input=text))
  for v in ['A','B']:
   q=call(dict(mode='build',path=path,variant=v,input=text));test(q['payload']['generationConfig']==base['payload']['generationConfig']);test(q['payload']['contents']==[{'role':'user','parts':[{'text':text}]}]);test(q['model']==base['model']);test(q['payload']['generationConfig']['maxOutputTokens']==1024)
   field='senses'if v=='A'else'frames';raw={'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':json.dumps({field:[], 'translation':text})}]}}]}
   out=call(dict(mode='inspect',path=path,variant=v,raw=raw));test(out['status']=='SUCCESS'and out['displayed']==text and out['retry']==0)
   raw['candidates'][0]['content']['parts'][0]['text']='{"translation":"truncated'
   out=call(dict(mode='inspect',path=path,variant=v,raw=raw));test(out['status']=='FAILED'and out['displayed']is None)
 p.terminate()
mod=runpy.run_path(str(R/'experiments/gemini-native500-gcs/runner.py'))
for m in ['35','36']:
 cfg=json.loads((R/f'experiments/gemini{m}-native500/config.json').read_text());test(cfg['turn_cap']==160);test(cfg['turn_initial_actual']=={'35':316,'36':304}[m]);test(cfg['prior_actual']+cfg['max_new']<=cfg['turn_initial_actual']+160)
print(json.dumps({'checks':count,'status':'PASS','generation_calls':0}))
