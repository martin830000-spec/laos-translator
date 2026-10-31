"""LA1 linked source/target units. No HTTP, secrets, correction or hidden call."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parent
CONFIG=json.loads((ROOT/'candidate.json').read_text(encoding='utf-8'))

def canonical(value):
    return json.dumps(value,ensure_ascii=False,sort_keys=True).encode('utf-8')

def digest(value): return hashlib.sha256(canonical(value)).hexdigest()

def load_baseline():
    path=ROOT.parent/'haiku-50-steps/adapter.py'
    if hashlib.sha256(path.read_bytes()).hexdigest()!=CONFIG['baseline_adapter_sha256']:
        raise ValueError('Frozen S47 adapter mismatch')
    spec=importlib.util.spec_from_file_location('frozen_s47_for_la1',path)
    obj=importlib.util.module_from_spec(spec)
    old=sys.dont_write_bytecode;sys.dont_write_bytecode=True
    try:spec.loader.exec_module(obj)
    finally:sys.dont_write_bytecode=old
    if digest(obj.CANDIDATE)!=CONFIG['baseline_candidate_canonical_sha256']:
        raise ValueError('Frozen S47 configuration mismatch')
    return obj

BASELINE=load_baseline()

class SafetyStop(Exception):
    """Only a global authentication/model-integrity problem, never ordinary output failure."""

# Fixed schema: never embed names, quotations or private facts in cached grammar.
SCHEMA={
    'type':'object',
    'properties':{
        'units':{
            'type':'array',
            'items':{
                'type':'object',
                'properties':{
                    'source':{'type':'string','description':'Exact consecutive source substring, including its whitespace and punctuation.'},
                    'target':{'type':'string','description':'Natural target-language fragment for the adjacent source chunk, including spaces needed for direct concatenation.'}
                },
                'required':['source','target'],
                'additionalProperties':False
            }
        }
    },
    'required':['units'],
    'additionalProperties':False
}

CONTRACT=(
    '\nOutput contract LA1: return one JSON object with an ordered units array. '
    'For each unit, copy a consecutive source chunk verbatim into source, then translate that chunk into target. '
    'The concatenated source fields reproduce the entire current visible message exactly, including whitespace and punctuation. '
    'Choose coherent phrases or clauses, not individual words; use one unit when a short message needs no split. '
    'Read the whole current message for grammar and context. Keep flexible word order inside a unit. '
    'The target fields, concatenated exactly without extra separators, are the single finished message the recipient reads; '
    'include any needed spaces or line breaks in those fields. '
    'There is no separate people/events paraphrase and no separate global translation to rewrite the unit translations. '
    'Do not include an explanation of the task, intermediate draft, alternatives, labels or correction attempts in target.'
)

def target_language(side,stage):
    if side not in ('K','L') or stage not in ('first','back'):
        raise ValueError('side K/L; stage first/back')
    return 'Lao' if (side=='K')==(stage=='first') else 'Korean'

def build_request(visible_text,side,stage,variant='LA1'):
    target_language(side,stage)
    if not isinstance(visible_text,str) or not visible_text.strip():raise ValueError('Nonempty visible text required')
    if variant not in ('S47','LA1'):raise ValueError('variant S47/LA1')
    q=copy.deepcopy(BASELINE.build_request(visible_text,side,stage))
    if variant=='LA1':
        q['system']+=CONTRACT
        q['output_config']['format']['schema']=copy.deepcopy(SCHEMA)
    return q

def unique_object(pairs):
    result={}
    for key,value in pairs:
        if key in result:raise ValueError('Duplicate JSON key')
        result[key]=value
    return result

def inspect_response(response,visible_text,side,stage,variant='LA1'):
    target_language(side,stage)
    if variant=='S47':
        return {'translation':BASELINE.extract_translation(response),'warnings':[],
                'alignment_checked':False,'alignment_ok':None}
    if variant!='LA1':raise ValueError('variant S47/LA1')
    if response.get('stop_reason')!='end_turn':raise ValueError('Incomplete response; no retry or partial JSON salvage')
    raw=''.join(b.get('text','') for b in response.get('content',[]) if b.get('type')=='text')
    obj=json.loads(raw,object_pairs_hook=unique_object)
    if not isinstance(obj,dict) or set(obj)!={'units'} or not isinstance(obj['units'],list) or not obj['units']:
        raise ValueError('Invalid units schema')
    for unit in obj['units']:
        if not isinstance(unit,dict) or set(unit)!={'source','target'} or any(not isinstance(unit[k],str) for k in ('source','target')):
            raise ValueError('Invalid source/target unit')
    # This is the declared wire representation, not a rewrite of a model translation.
    rendered=''.join(u['target'] for u in obj['units'])
    if not rendered.strip():raise ValueError('Empty visible translation')
    reconstructed=''.join(u['source'] for u in obj['units'])
    aligned=reconstructed==visible_text
    warnings=[] if aligned else ['SOURCE_RECONSTRUCTION_MISMATCH']
    if any(not u['source'] for u in obj['units']):warnings.append('EMPTY_SOURCE_UNIT')
    # Advisory only. Keep every model-authored target character even on mismatch.
    return {'translation':rendered,'units':obj['units'],'warnings':warnings,
            'alignment_checked':True,'alignment_ok':aligned,'unit_count':len(obj['units']),
            'reconstructed_source_sha256':hashlib.sha256(reconstructed.encode()).hexdigest()}

def failure_reason(response,exc):
    if response.get('stop_reason')=='max_tokens':return 'MAX_TOKENS'
    if response.get('http_status'):return 'HTTP_'+str(response['http_status'])
    if isinstance(exc,json.JSONDecodeError):return 'WHOLE_JSON_'+exc.msg+'_POSITION_'+str(exc.pos)
    if response and response.get('stop_reason')!='end_turn':return 'INCOMPLETE_'+str(response.get('stop_reason'))
    return type(exc).__name__

def estimated_cost_usd(usage):
    if not isinstance(usage.get('input_tokens'),int) or not isinstance(usage.get('output_tokens'),int):return None
    i,o=usage['input_tokens'],usage['output_tokens']
    cc=usage.get('cache_creation_input_tokens',0);cr=usage.get('cache_read_input_tokens',0)
    one_hour=usage.get('cache_creation',{}).get('ephemeral_1h_input_tokens',0)
    five_minute=max(0,cc-one_hour)
    factor=5 if i+cc+cr>100000 else 1
    return round(factor*(i*.10+o*.50+five_minute*.125+one_hour*.20+cr*.01)/1000000,9)

class SinglePassSession:
    """One-use two-call interface, with errors/skips recorded, no built-in transport."""
    def __init__(self,side,variant='LA1'):
        target_language(side,'first')
        if variant not in ('S47','LA1'):raise ValueError('variant S47/LA1')
        self.side=side;self.variant=variant;self.used=False

    def run(self,source,transport,persist=lambda record:None):
        import time
        if self.used:raise RuntimeError('Single-pass session consumed')
        self.used=True
        stages=[]
        for stage in ('first','back'):
            if stage=='back' and stages[0]['status']!='SUCCESS':
                item={'stage':stage,'status':'SKIPPED_DEPENDENCY','attempted':False};stages.append(item);persist(copy.deepcopy(item));break
            visible=source if stage=='first' else stages[0]['translation']
            q=build_request(visible,self.side,stage,self.variant)
            item={'stage':stage,'status':'SENT_OR_UNKNOWN','attempted':True,'input':visible,
                  'payload':q,'payload_sha256':digest(q)}
            stages.append(item);persist(copy.deepcopy(item))
            start=time.perf_counter();raw={}
            try:
                raw=transport(q)
                item['api_ms']=(time.perf_counter()-start)*1000
                item['response']=raw
                item['usage']=raw.get('usage',{})
                item['stop_reason']=raw.get('stop_reason')
                item['http_status']=raw.get('http_status',200 if raw.get('type')=='message' else None)
                item['response_sha256']=digest(raw)
                item['response_id']=raw.get('id')
                item['estimated_usd']=estimated_cost_usd(item['usage'])
                if raw.get('http_status') in (401,403):raise SafetyStop('GLOBAL_AUTHENTICATION_FAILURE')
                if raw.get('model') not in (None,CONFIG['model']):raise SafetyStop('MODEL_ID_MISMATCH')
                item.update(inspect_response(raw,visible,self.side,stage,self.variant))
                item['status']='SUCCESS'
            except SafetyStop as exc:
                item.update(status='FAILED',reason=str(exc),exception_type=type(exc).__name__)
                raise
            except Exception as exc:
                item.update(status='FAILED',reason=failure_reason(raw,exc),exception_type=type(exc).__name__)
            finally:
                item.setdefault('estimated_usd',None)
                item.setdefault('api_ms',(time.perf_counter()-start)*1000);persist(copy.deepcopy(item))
        return {'stages':stages,'attempts':sum(s['attempted'] for s in stages),'retries':0}
