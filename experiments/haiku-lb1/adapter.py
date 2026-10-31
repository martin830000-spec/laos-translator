"""LB1: lossless Lao source lexical-boundary hints; no translated examples/glosses.
LA1 model/output contract preserved. No HTTP, target rewrite or original in BACK.
"""
import importlib.util,json,re,time
from pathlib import Path
ROOT=Path(__file__).resolve().parent
def load(name,path):
    s=importlib.util.spec_from_file_location(name,path);x=importlib.util.module_from_spec(s);s.loader.exec_module(x);return x
prior=load('lb1_frozen_la1',ROOT.parent/'haiku-linked-units/adapter.py')
def lexical_hints(text,tokenize=None):
    started=time.perf_counter()
    if len(text)>4000:return {'status':'NO_HINT_LENGTH_LIMIT','tokens':[],'elapsed_ms':(time.perf_counter()-started)*1000}
    if tokenize is None:
        from laonlp.tokenize import word_tokenize
        tokenize=word_tokenize
    parts=tokenize(text)
    if not isinstance(parts,list) or any(not isinstance(x,str) or not x for x in parts) or ''.join(parts)!=text:
        return {'status':'NO_HINT_LOSSLESS_CHECK_FAILED','tokens':[],'elapsed_ms':(time.perf_counter()-started)*1000}
    spans=[];pos=0
    for part in parts:spans.append({'start':pos,'end':pos+len(part),'text':part});pos+=len(part)
    return {'status':'LOSSLESS_LEXICAL_HINTS','tokens':parts,'spans':spans,'elapsed_ms':(time.perf_counter()-started)*1000,'semantic_parse':False}
def build_request(source,side,stage,tokenize=None):
    q=prior.build_request(source,side,stage,'LA1');lang='ko' if (side=='K')==(stage=='first') else 'lo'
    receipt={'status':'UNCHANGED_KOREAN_INPUT','elapsed_ms':0,'semantic_parse':False}
    if lang=='lo':
        receipt=lexical_hints(source,tokenize)
        if receipt['status']=='LOSSLESS_LEXICAL_HINTS':
            q['messages'][0]['content']+='\n<source_lexical_boundaries>Approximate Lao word boundaries only. The original message remains authoritative; translate it as one whole message.\n'+json.dumps(receipt['tokens'],ensure_ascii=False)+'\n</source_lexical_boundaries>'
    return {'payload':q,'hints':receipt,'attempted':False,'semantic_quality':'UNVERIFIED'}
def prepare_back(first_response,side,tokenize=None):
    shared=load('lb1_source_free_extract',ROOT.parent/'relation-exemplars/adapter.py');out=shared.prepare_back(first_response,side,'H')
    if out['status']!='PREPARED_OFFLINE':return out
    obj=json.loads(''.join(b.get('text','') for b in first_response.get('content',[]) if b.get('type')=='text'),object_pairs_hook=prior.unique_object)
    visible=''.join(u['target'] for u in obj['units'])
    return {'status':'PREPARED_OFFLINE',**build_request(visible,side,'back',tokenize)}
def live(*args,**kwargs):raise PermissionError('LB1 not authorized for generation in Sonnet32 task')
