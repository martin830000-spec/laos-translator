from pathlib import Path
import sys,json
sys.path.insert(0,str(Path(__file__).parent/'legacy-prompt320'))
import adapter
q=json.load(sys.stdin);p=q['path'];side=p[0];stage='first' if p.endswith('F') else 'back'
if q['mode']=='build':
 r=adapter.build(q['text'],side,stage,'31U');print(json.dumps(dict(model=r['model'],payload=r['payload']),ensure_ascii=False))
else:print(json.dumps(adapter.inspect(q['raw'],q['text'],side,stage,'31U'),ensure_ascii=False))
