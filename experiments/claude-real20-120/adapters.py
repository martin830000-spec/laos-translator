"""Frozen Haiku LA1, Sonnet S1 and Opus OPT C, with their own display contracts."""
import importlib.util
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parent
def load(name,path):
    s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
haiku=load('real120_frozen_la1',ROOT.parent/'haiku-linked-units/adapter.py')
core=load('real120_frozen_s1',ROOT.parent/'claude-rd-core/core.py')
OPUS=json.loads((ROOT/'frozen-opus-c.json').read_text(encoding='utf-8'))
MODELS={'H':'claude-haiku-5-5','S':'claude-sonnet-5-5','O':'claude-opus-5-5'}

def build(source,side,stage,engine):
    if engine=='H':return haiku.build_request(source,side,stage,'LA1')
    q=core.baseline(source,side,stage,MODELS[engine])
    if engine=='O':
        p=OPUS['variant']['prompts']
        q['system']='<translation_task>'+p['CLAUDE_SONNET55_S1_COMMON']+'</translation_task>\n<couple_context>'+p['CLAUDE_SONNET55_S1_ROLE_'+side]+'</couple_context>\n<translation_stage>'+p['CLAUDE_SONNET55_S1_BACK' if stage=='back' else 'CLAUDE_SONNET55_S1_FORWARD']+'</translation_stage>'
        if OPUS['variant'].get('append'):q['system']+='\n'+OPUS['variant']['append']
    return q

def inspect(raw,source,side,stage,engine):
    if engine=='H':return dict(haiku.inspect_response(raw,source,side,stage,'LA1'),status='SUCCESS')
    out=core.inspect(raw)
    if engine=='O':
        out['raw_text']=out['translation']
        out['translation']=out['translation'].strip()  # existing OPT C display extraction
    return out

def cost(usage,engine):
    if not all(type(usage.get(k)) is int for k in ['input_tokens','output_tokens']):return None
    ip,op,read={'H':(.1,.5,.01),'S':(2,10,.1),'O':(4,20,.2)}[engine]
    cc=usage.get('cache_creation_input_tokens',0);hour=usage.get('cache_creation',{}).get('ephemeral_1h_input_tokens',0)
    return round((usage['input_tokens']*ip+usage['output_tokens']*op+max(0,cc-hour)*ip*1.25+hour*ip*2+usage.get('cache_read_input_tokens',0)*read)/1e6,9)
