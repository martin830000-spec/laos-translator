"""OB1: frozen S1 FIRST; remove route identity prior only from independent BACK."""
import importlib.util
from pathlib import Path
ROOT=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('opus_ob1_core',ROOT.parent/'claude-rd-core/core.py')
core=importlib.util.module_from_spec(spec);spec.loader.exec_module(core)
MODEL='claude-opus-5-5'

def build_request(source,side,stage):
    request=core.baseline(source,side,stage,MODEL)
    if stage=='back':
        block='<couple_context>'+core.PROMPTS['CLAUDE_SONNET55_S1_ROLE_'+side]+'</couple_context>\n'
        assert request['system'].count(block)==1
        request['system']=request['system'].replace(block,'',1)
    return request

def prepare_back(first_response,side):return core.prepare_back(first_response,side,build_request)
inspect_response=core.inspect
