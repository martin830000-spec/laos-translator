"""S1-ROLE-LITE: change only FIRST's couple_context block; BACK is byte-equivalent S1."""
from pathlib import Path
import importlib.util,hashlib,json
ROOT=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('role_lite_frozen_core',ROOT.parent/'claude-rd-core/core.py');core=importlib.util.module_from_spec(spec);spec.loader.exec_module(core)
ROLE={'K':'The speaker is a Korean husband messaging his Lao wife.','L':'The speaker is a Lao wife messaging her Korean husband.'}
def baseline_request(text,side,stage):return core.baseline(text,side,stage,'claude-sonnet-5-5')
def build_request(text,side,stage):
 q=baseline_request(text,side,stage)
 if stage=='first':
  old='<couple_context>'+core.PROMPTS['CLAUDE_SONNET55_S1_ROLE_'+side]+'</couple_context>'
  if q['system'].count(old)!=1:raise ValueError('Expected exactly one frozen role block')
  q['system']=q['system'].replace(old,'<couple_context>'+ROLE[side]+'</couple_context>',1)
 return q
inspect_response=core.inspect
def prepare_back(first_response,side):return core.prepare_back(first_response,side,build_request)
