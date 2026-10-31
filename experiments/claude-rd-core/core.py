"""Offline request preparation and response inspection; intentionally no transport."""
import copy
import hashlib
import json
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parent
PROMPTS=json.loads((ROOT/'s1-prompts.json').read_text(encoding='utf-8'))

def digest(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True).encode()).hexdigest()

def baseline(source, side, stage, model):
    if side not in ('K','L') or stage not in ('first','back'):
        raise ValueError('Unknown route')
    if model not in ('claude-sonnet-5-5','claude-opus-5-5'):
        raise ValueError('Unknown single engine')
    if not isinstance(source,str) or not source.strip():
        raise ValueError('Nonempty visible source required')
    src,dst=('Korean','Lao') if side=='K' else ('Lao','Korean')
    if stage=='back':src,dst=dst,src
    p=PROMPTS
    system=('<translation_task>'+p['CLAUDE_SONNET55_S1_COMMON']+'</translation_task>\n'
        '<couple_context>'+p['CLAUDE_SONNET55_S1_ROLE_'+side]+'</couple_context>\n'
        '<translation_stage>'+p['CLAUDE_SONNET55_S1_BACK' if stage=='back' else 'CLAUDE_SONNET55_S1_FORWARD']+'</translation_stage>')
    return {'model':model,'max_tokens':2048,
        'thinking':{'type':'between_tools' if model=='claude-sonnet-5-5' else 'adaptive'},
        'output_config':{'effort':'low'},'system':system,
        'messages':[{'role':'user','content':'Translate the following message from '+src+' into '+dst+'.\n<source>\n'+source+'\n</source>'}]}

def inspect(response):
    # Preserve every text character. Warnings neither delete nor replace output.
    texts=[b.get('text','') for b in response.get('content',[]) if b.get('type')=='text']
    visible=''.join(texts)
    warnings=[]
    if re.search(r'[\u0e00-\u0e7f]',visible):warnings.append('THAI_SCRIPT_REVIEW')
    if re.search(r'Wait\s*[—-]|I need to correct|Correct version:',visible,re.I):warnings.append('DRAFT_OR_COMMENTARY_REVIEW')
    complete=response.get('stop_reason')=='end_turn' and bool(visible.strip())
    return {'translation':visible,'status':'SUCCESS' if complete else 'FAILED',
        'stop_reason':response.get('stop_reason'),'warnings':warnings,
        'usage':copy.deepcopy(response.get('usage',{})),
        'semantic_quality':'UNVERIFIED','response_sha256':digest(response)}

def prepare_back(first_response, side, builder):
    first=inspect(first_response)
    if first['status']!='SUCCESS':
        return {'status':'SKIPPED_DEPENDENCY','attempted':False,'visible_partial':first['translation']}
    # This interface cannot receive original source, facts, history, or another result.
    return {'status':'PREPARED_OFFLINE','attempted':False,
            'payload':builder(first['translation'],side,'back')}

def read_exact(path):
    with Path(path).open('r',encoding='utf-8',newline='') as f:return f.read()

def live(*args,**kwargs):
    raise PermissionError('Research authorization is zero calls; no live transport installed')
