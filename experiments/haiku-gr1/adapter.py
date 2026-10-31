"""GR1: bounded, source-indexed grammatical interpretation options.
No bilingual examples, selected answer, source rewrite, word tokenization or HTTP.
"""
from pathlib import Path
import importlib.util,json,re
ROOT=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('gr1_frozen_lb1',ROOT.parent/'haiku-lb1/adapter.py');lb=importlib.util.module_from_spec(s);s.loader.exec_module(lb)
CARDS={
 'adverbial': 'ຫຼິ້ນ can modify another verb as a casual manner; distinguish that reading from a separate play event using context.',
 'condition': 'ຖ້າ may introduce a condition before or after its result; it can also be the verb wait. Choose scope across adjoining clauses before translating units, without forcing word-order adjacency.'
}
def cues(source):
    if len(source)>4000:return {'status':'NO_CUES_LENGTH_LIMIT','markers':[]}
    markers=[]
    for kind,pattern in [('adverbial',r'ຫຼິ້ນ|ຫລິ້ນ'),('condition',r'ຖ້າ')]:
        for m in re.finditer(pattern,source):markers.append({'kind':kind,'start':m.start(),'end':m.end(),'literal':m.group(),'interpretation':'UNSELECTED'})
    markers.sort(key=lambda x:x['start'])
    if len(markers)>8:return {'status':'NO_CUES_COUNT_LIMIT','markers':[]}
    return {'status':'CUE_OPTIONS' if markers else 'NO_MATCH','markers':markers}
def build_request(source,side,stage):
    payload=lb.prior.build_request(source,side,stage,'LA1');is_lao=(side=='L')==(stage=='first')
    receipt=cues(source) if is_lao else {'status':'UNCHANGED_KOREAN_INPUT','markers':[]}
    if receipt['markers']:
        kinds=sorted({m['kind'] for m in receipt['markers']})
        # Grammar knowledge is trusted context; offsets/literals remain user data.
        payload['system']+='\n<grammatical_options>'+ ' '.join(CARDS[k] for k in kinds)+' These are interpretation options, not an asserted parse. Preserve uncertainty. Return the unchanged LA1 output contract.</grammatical_options>'
        payload['messages'][0]['content']+='\n<source_construction_positions>'+json.dumps(receipt['markers'],ensure_ascii=False,separators=(',',':'))+'</source_construction_positions>'
    return {'payload':payload,'cues':receipt,'attempted':False,'semantic_quality':'UNVERIFIED'}
def prepare_back(response,side):
    # The shared validator sees the FIRST response only, never an earlier source.
    shared=lb.load('gr1_display_only',ROOT.parent/'relation-exemplars/adapter.py')
    out=shared.prepare_back(response,side,'H','BASELINE')
    if out['status']!='PREPARED_OFFLINE':return out
    obj=json.loads(''.join(x.get('text','') for x in response.get('content',[]) if x.get('type')=='text'),object_pairs_hook=lb.prior.unique_object)
    visible=''.join(x['target'] for x in obj['units'])
    return {'status':'PREPARED_OFFLINE',**build_request(visible,side,'back')}
def live(*args,**kwargs):raise PermissionError('GR1 not authorized for live generation')
