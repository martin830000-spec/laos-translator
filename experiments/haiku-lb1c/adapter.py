"""LB1C: preserve non-Lao runs verbatim before local dictionary segmentation.
Engineering response to actual LB1 fallback when LaoNLP 1.3.0 drops '/'.
No translation quality claim. No generation transport. Frozen LB1 unchanged.
"""
import importlib.util,json,re,time
from pathlib import Path
ROOT=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('lb1c_frozen_lb1',ROOT.parent/'haiku-lb1/adapter.py');lb=importlib.util.module_from_spec(s);s.loader.exec_module(lb)
def preserve_runs(text,tokenize=None):
    if tokenize is None:
        from laonlp.tokenize import word_tokenize
        tokenize=word_tokenize
    tokens=[]
    for run in re.findall(r'[\u0e80-\u0eff]+|[^\u0e80-\u0eff]+',text):
        if '\u0e80'<=run[0]<='\u0eff':
            parts=tokenize(run)
            # Never attempt to infer or repair missing Lao characters.
            tokens.extend(parts if isinstance(parts,list) and all(isinstance(x,str) and x for x in parts) and ''.join(parts)==run else [run])
        else:tokens.append(run)
    assert ''.join(tokens)==text
    return tokens
def build_request(source,side,stage,tokenize=None):
    # Same wording/output/model as LB1, only the boundary producer differs.
    result=lb.build_request(source,side,stage,lambda text:preserve_runs(text,tokenize))
    result['candidate']='LB1C_NON_LAO_RUN_PRESERVATION'
    return result
def prepare_back(first_response,side,tokenize=None):
    result=lb.prepare_back(first_response,side,lambda text:preserve_runs(text,tokenize))
    result['candidate']='LB1C_NON_LAO_RUN_PRESERVATION'
    return result
def live(*args,**kwargs):raise PermissionError('LB1C has no paid generation authorization')
