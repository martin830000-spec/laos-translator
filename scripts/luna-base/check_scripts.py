from pathlib import Path
import re,html,subprocess,sys,tempfile
p=Path(sys.argv[1]);s=(p/'index.html').read_text(); sources=[('outer',s)]
for mode in ('husband','wife'):
 m=re.search(r'<textarea[^>]*id="payload-'+mode+r'"[^>]*>(.*?)</textarea>',s,re.S);assert m
 sources.append((mode,html.unescape(m.group(1))))
n=0
with tempfile.TemporaryDirectory() as d:
 for name,src in sources:
  for i,m in enumerate(re.finditer(r'<script([^>]*)>(.*?)</script>',src,re.S)):
   if 'src=' in m[1] or not m[2].strip() or 'application/json' in m[1]:continue
   f=Path(d)/f'{name}-{i}.js';f.write_text(m[2]);subprocess.run(['node','--check',str(f)],check=True,capture_output=True);n+=1
 for f in p.glob('luna*.js'):subprocess.run(['node','--check',str(f)],check=True);n+=1
print('JavaScript syntax PASS:',n)
