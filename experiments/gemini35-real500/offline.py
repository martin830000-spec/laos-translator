from pathlib import Path
import json,subprocess
n=0
for e,model in [('35','gemini-3.5-flash-lite'),('36','gemini-3.6-flash')]:
 p=Path(f'experiments/gemini{e}-real500');c=json.loads((p/'config.json').read_text());assert c['enabled'] is False and c['max_new']==0
 subprocess.run(['python3','-m','py_compile',str(p/'runner.py')],check=True);subprocess.run(['node','--check',str(p/'worker.cjs')],check=True)
 for v in ['BASE','COMPUTE','WINDOW']:
  for path in ['KF','KB','LF','LB']:
   src='자기야, 오늘은 쉬자.'if path in ['KF','LB']else'ທີ່ຮັກ ພັກຜ່ອນ.'
   s=subprocess.run(['node',str(p/'worker.cjs')],input=json.dumps(dict(mode='build',variant=v,path=path,input=src),ensure_ascii=False)+'\n',text=True,capture_output=True,check=True);q=json.loads(s.stdout);assert q['ok'];q=q['value'];assert q['model']==model
   content=q['payload']['contents'][0]['parts'][0]['text']
   if v=='WINDOW' and path.endswith('F') and content!=src:
    wrapped=json.loads(content);assert wrapped['message']==src and all(w['text'] in src for w in wrapped['source_windows'])
   else:assert content==src
   system=json.dumps(q['payload'].get('systemInstruction',q['payload'].get('system_instruction')),ensure_ascii=False)
   if path.endswith('B'):assert 'ROLE LOCK'not in system and 'REGISTER_TARGET'not in system
   n+=1
Path('real500-free.json').write_text(json.dumps(dict(checks=n,passed=True,paid_calls=0,independent_cap_each=500,old_campaign_actual=616)))
print('PASS',n,'offline requests; zero generation')
