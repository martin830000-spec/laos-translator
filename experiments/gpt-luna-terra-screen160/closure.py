"""Free append-only closure; no generation functions imported or called."""
import json,pathlib,datetime,os,hashlib,concurrent.futures
from runner import Store,config,reservations,totals,canon,CAMPAIGN
c=config();cfg=json.loads((pathlib.Path(__file__).parent/'config.json').read_bytes())
assert c['mode']=='CLOSE' and cfg['enabled'] is False and cfg['max_new']==0
s=Store();rs=reservations(s);assert len(rs)==c['expected_actual']
by=totals(s,rs)
fidelity_ledger=json.loads(pathlib.Path('experiments/gemini35-fidelity240/35/ledger.json').read_bytes())
expected=['83e99ebf8d650b43cf57ae2875a932893b41278db56726f68e3b600fe5a35310','5219a9cb75cf0bef3ba6cfbee35457294c99288f7fb7ebc85473785ff9b58cfb','3068ed964aa39cda4831b2245b951e69f01eec0ea3cfdf4120ab84b2cd5c795f']
fidelity=[]
for p in fidelity_ledger['phases']:
 raw=s.bucket.blob('research/gemini-model-native500-20261107/fidelity240-20261108/35/results/'+p['plan_sha256']+'/RUN_FINISHED.json').download_as_bytes(timeout=30)
 d=json.loads(raw);fidelity.append({'attempted':d['attempted'],'sha256':hashlib.sha256(raw).hexdigest()})
assert [d['sha256'] for d in fidelity]==expected and sum(d['attempted'] for d in fidelity)==224
s.put('closure/FIDELITY240_UNCHANGED.json',canon({'attempted':224,'unused_locked':16,'runs':fidelity,'unchanged_from_start':True}))
with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
 raw=list(pool.map(lambda i:s.get(f'skips/S{i:03d}.json',True),range(1,161)))
skips=[json.loads(x) for x in raw if x]
state={**cfg,'campaign':CAMPAIGN,'enabled':False,'max_new':0,'status':'CLOSED_LOCKED','cumulative_actual':len(rs),'unused_locked':160-len(rs),'models_ledger':by,'skips':skips,'closed_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'closure_run':os.environ['GITHUB_RUN_ID'],'latest_state_object':'states/CLOSED.json'}
for model,d in by.items():assert d['attempted']<=80 and sum(d[x] for x in ['success','failed','unknown'])==d['attempted']
assert len(rs)<=160
s.put('states/CLOSED.json',canon(state));assert s.get('states/CLOSED.json')==canon(state)
receipt={'state_sha256':hashlib.sha256(canon(state)).hexdigest(),'readback_exact':True,'actual':len(rs),'models':by,'enabled':False,'max_new':0,'status':'CLOSED_LOCKED'}
s.put('closure/READBACK.json',canon(receipt));print(json.dumps(receipt))
