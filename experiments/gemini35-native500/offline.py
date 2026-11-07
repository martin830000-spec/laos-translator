from pathlib import Path
import json,subprocess
n=0
for e,vs in [('35',['BASE','N35','S35','S35_LOW']),('36',['BASE','R36','S36','S36_MINIMAL'])]:
 p=Path(f'experiments/gemini{e}-native500');c=json.load(open(p/'config.json'));assert c['enabled']is False and c['max_new']==0
 w=subprocess.Popen(['node',str(p/'worker.cjs')],stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True)
 for path in ['KF','KB','LF','LB']:
  for v in vs:
   inp='나 이제 쉬어. 내일 보자.'if path in ['KF','LB']else'ຂ້ອຍຈະພັກຜ່ອນ.';w.stdin.write(json.dumps(dict(mode='build',path=path,variant=v,input=inp))+'\n');w.stdin.flush();o=json.loads(w.stdout.readline());assert o['ok'];q=o['value'];assert q['model']==c['model'];assert q['payload']['contents']==[{'role':'user','parts':[{'text':inp}]}];assert q['payload']['generationConfig']['maxOutputTokens']==1024
   if path.endswith('B'):assert not q.get('smart',{}).get('attached_ids')
   n+=1
 w.terminate()
Path('native500-free.json').write_text(json.dumps(dict(checks=n,paid_calls=0,status='PASS')));print('PASS',n,'offline contracts; zero generation')
