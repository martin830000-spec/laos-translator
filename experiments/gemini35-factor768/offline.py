from pathlib import Path
import json,subprocess,hashlib
n=0
for e,model in [('35','gemini-3.5-flash-lite'),('36','gemini-3.6-flash'),('38','gemini-3.8-flash')]:
 p=Path(f'experiments/gemini{e}-factor768');c=json.loads((p/'config.json').read_text());assert c['enabled'] is False and c['max_new']==0
 cfg=json.loads((p/'current-prompt-config.json').read_text());can={k:cfg[k]for k in ['schemaVersion','channel','promptRevision','forward','smart','back']};assert hashlib.sha256(json.dumps(can,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()==cfg['promptSha256']
 subprocess.run(['python3','-m','py_compile',str(p/'runner.py')],check=True)
 proc=subprocess.Popen(['node',str(p/'worker.cjs')],stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True)
 def build(path,v,src):
  proc.stdin.write(json.dumps(dict(mode='build',path=path,variant=v,input=src),ensure_ascii=False)+'\n');proc.stdin.flush();r=json.loads(proc.stdout.readline());assert r['ok'];return r['value']
 for path in ['KF','KB','LF','LB']:
  for src in (['나는 엄마와 얘기했어.','잘 자.']if path in ['KF','LB']else['ແມ່ບອກວ່າພັກຜ່ອນ.','ສະບາຍດີ']):
   q={v:build(path,v,src)for v in'ABCD'}
   for v,x in q.items():
    assert x['model']==model and x['payload']['contents']==[{'role':'user','parts':[{'text':src}]}]
    assert x['payload']['generationConfig']=={'maxOutputTokens':1024,'thinkingConfig':{'thinkingLevel':'low','includeThoughts':False}}
    assert 'SPEECH_ACT'not in x['smart']['attached_ids'];n+=1
   def prompt(v):return q[v]['payload']['system_instruction']['parts'][0]['text']
   assert prompt('A')==prompt('B')+q['A']['smart']['attachment'];assert prompt('C')==prompt('D')+q['C']['smart']['attachment'];assert q['A']['smart']['attachment']==q['C']['smart']['attachment']
   if path.endswith('B'):assert prompt('A')==prompt('B')and prompt('C')==prompt('D')and not q['A']['smart']['attached_ids']
   else:assert prompt('B')==cfg['forward']['k2l'if path=='KF'else'l2k']
 proc.terminate()
Path('factor768-free.json').write_text(json.dumps(dict(checks=n,passed=True,paid_calls=0,independent_cap_each=256,total_cap=768)))
print('PASS',n,'offline factorial requests; zero generation')
