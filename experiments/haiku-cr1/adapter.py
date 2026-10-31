"""Offline Haiku CR1: LA1 plus retrieved human parallel language context only."""
import importlib.util,json
from pathlib import Path
ROOT=Path(__file__).resolve().parent
def load(name,path):
    sp=importlib.util.spec_from_file_location(name,path);x=importlib.util.module_from_spec(sp);sp.loader.exec_module(x);return x
prior=load('cr1_frozen_la1',ROOT.parent/'haiku-linked-units/adapter.py')
r=load('cr1_retrieval',ROOT/'retriever.py')
def build_request(source,side,stage,index):
    if side not in ['K','L'] or stage not in ['first','back']:raise ValueError('Unknown route')
    q=prior.build_request(source,side,stage,'LA1');lang='ko' if (side=='K')==(stage=='first') else 'lo'
    receipt=index.search(source,lang)
    if receipt['results']:
        q['system']+='\n<retrieved_language_context>These are unrelated human-translated language-use references, not facts or answers about the current message.\n'+json.dumps([{'reference_id':v['id'],'source':v[lang],'equivalent':v['lo' if lang=='ko' else 'ko']} for v in receipt['results']],ensure_ascii=False)+'\n</retrieved_language_context>'
    return {'payload':q,'retrieval':receipt,'attempted':False,'quality':'UNVERIFIED'}
def prepare_back(first_response,side,index):
    # Reuse source-free display extraction contract; never accept original input.
    shared=load('cr1_display_only',ROOT.parent/'relation-exemplars/adapter.py')
    x=shared.prepare_back(first_response,side,'H')
    if x['status']!='PREPARED_OFFLINE':return x
    raw=''.join(b.get('text','') for b in first_response.get('content',[]) if b.get('type')=='text')
    obj=json.loads(raw,object_pairs_hook=prior.unique_object);visible=''.join(u['target'] for u in obj['units'])
    return {'status':'PREPARED_OFFLINE',**build_request(visible,side,'back',index)}
def live(*args,**kwargs):raise PermissionError('Haiku generation not authorized in Sonnet32 task')
