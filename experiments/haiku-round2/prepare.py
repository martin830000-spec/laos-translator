"""Offline evidence reuse and deterministic candidate preparation. No network."""
import csv, hashlib, json, sys
from pathlib import Path
ROOT = Path(__file__).parent
def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
def sha(data):
    return hashlib.sha256(data).hexdigest()
def prepare(prior):
    data = json.loads((prior/'claude50-experiments.json').read_text(encoding='utf-8'))
    assert len(data)==11 and sum(r['attempts'] for r in data)==488
    variants={v['id']:v for r in data for v in r['steps']}
    assert all(f'S{i:02}' in variants for i in range(1,51))
    rows=[]
    for run in data:
        for r in run['results']:
            for stage in ('first','back'):
                o=r.get(stage)
                if o is None: continue
                rows.append(dict(round=run['round'],step=r['step'],case=r['id'],path=r['side']+'_'+stage,
                    source=r['source'],input=r['source'] if stage=='first' else r['first']['text'],
                    translation=o['text'],status=o['status'],payload_sha256=o['payload_sha256'],
                    severity='UNREVIEWED',regression='UNREVIEWED',ms=o['ms'],estimated_usd=o['estimated_usd']))
    assert len(rows)==488
    with (ROOT/'prior-index.csv').open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=rows[0]); w.writeheader();w.writerows(rows)
    dump(ROOT/'prior-manifest.json',{'source_zip':'https://drive.google.com/file/d/1GWZtbFCVwd4Ak2p8HQNijDvW0XoUV9I8/view',
        'files':{p.name:sha(p.read_bytes()) for p in sorted(prior.iterdir()) if p.is_file()},
        'runs':11,'attempts':488,'new_paid_calls':0,'historical_quality_labels':'not automatically inferred',
        'test_head':'fe85e58e2c18387f3c4b7c3b473593c8c0b91d3e',
        'wife_head':'e24c5a9298c8f8324ba88e4aea08721010c89886',
        'general_head':'f7ef97cbdaa79674350811c55a1e8f9c15619961'})
    a=json.loads(json.dumps(variants['S47']))
    a['id']='R2A';a['hypothesis']='Scope neutral-sibling instruction symmetrically; preserve explicit gender and ownership instead of suppressing them.'
    a['sense_groups'][1]['note']='Preserve the full kinship expression: retain explicitly stated gender, relative age and ownership. Use a neutral sibling expression only when those attributes are unspecified in the visible source. Do not add missing attributes or erase stated ones.'
    b=json.loads(json.dumps(a)); b['id']='R2B';b['schema']='translation'
    b['hypothesis']='Same scoped instruction as R2A, but translation-only JSON: test whether generated fact fields introduce unsupported commitments. Prior S43 failure remains a regression risk, not evidence this works.'
    dump(ROOT/'candidates.json',[variants['S38'],variants['S47'],a,b])
    dump(ROOT/'candidate-freeze.json',{'sha256':sha((ROOT/'candidates.json').read_bytes()),'status':'FROZEN_BEFORE_NEW_HOLDOUT','quality':'UNTESTED'})
    old={r['source'] for run in data for r in run['results']}
    dump(ROOT/'prior-sources.json',sorted(old))
    dump(ROOT/'regression22.json',[{'id':r['id'],'side':r['side'],'source':r['source']} for r in data[-1]['results'] if r['step']=='S47'])
    print('488 historical responses indexed; 4 frozen arms; paid calls 0')
if __name__=='__main__': prepare(Path(sys.argv[1]))
