"""H RE1 and S EX1: frozen, direction-matched contrastive parallel exemplars.
No source-specific trigger, inference call, facts ledger, rewrite or text repair.
"""
import importlib.util,json,copy
from pathlib import Path
ROOT=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('re1_ex1_frozen',ROOT.parent/'claude-real20-120/adapters.py')
prior=importlib.util.module_from_spec(spec);spec.loader.exec_module(prior)
CONFIG=json.loads((ROOT/'examples.json').read_text(encoding='utf-8'))
def examples(side,stage,engine):
    if side not in 'KL' or len(side)!=1 or stage not in ['first','back'] or engine not in ['H','S']:raise ValueError('Unknown route')
    group='K' if (side=='K')==(stage=='first') else 'L'
    src,dst=('ko','lo') if group=='K' else ('lo','ko')
    return [{'source':e[src],'translation':e[dst]} for e in CONFIG[engine] if e['group']==group]
def build_request(source,side,stage,engine,variant='EXEMPLARS'):
    if variant not in ['BASELINE','EXEMPLARS']:raise ValueError('Unknown variant')
    q=prior.build(source,side,stage,engine)
    if variant=='EXEMPLARS':
        q['system']+='\n<parallel_examples>\n'+json.dumps(examples(side,stage,engine),ensure_ascii=False)+'\n</parallel_examples>'
    return q
def inspect_response(response,source,side,stage,engine):
    if engine=='H':
        try:return prior.inspect(response,source,side,stage,'H')
        except Exception as exc:
            return {'status':'FAILED','translation':'','raw_visible_text':''.join(b.get('text','') for b in response.get('content',[]) if b.get('type')=='text'),'error_type':type(exc).__name__,'semantic_quality':'UNVERIFIED'}
    return prior.core.inspect(response)
def prepare_back(first_response,side,engine,variant='EXEMPLARS'):
    # No original-source argument. For LA1, display extraction uses target fields;
    # alignment remains a warning checked separately in the FIRST record.
    if engine=='H':
        try:
            if first_response.get('stop_reason')!='end_turn':raise ValueError('Incomplete')
            raw=''.join(b.get('text','') for b in first_response.get('content',[]) if b.get('type')=='text')
            obj=json.loads(raw,object_pairs_hook=prior.haiku.unique_object)
            if set(obj)!={'units'} or not isinstance(obj['units'],list) or not obj['units']:raise ValueError('Bad units')
            if any(not isinstance(x,dict) or set(x)!={'source','target'} or not isinstance(x['source'],str) or not isinstance(x['target'],str) for x in obj['units']):raise ValueError('Bad unit')
            visible=''.join(x['target'] for x in obj['units'])
            if not visible.strip():raise ValueError('Empty')
        except Exception as exc:return {'status':'SKIPPED_DEPENDENCY','attempted':False,'error_type':type(exc).__name__}
    else:
        result=prior.core.inspect(first_response)
        if result['status']!='SUCCESS':return {'status':'SKIPPED_DEPENDENCY','attempted':False,'visible_partial':result['translation']}
        visible=result['translation']
    return {'status':'PREPARED_OFFLINE','attempted':False,'payload':build_request(visible,side,'back',engine,variant)}
def live(*args,**kwargs):raise PermissionError('Haiku/Sonnet follow-up calls not approved')
