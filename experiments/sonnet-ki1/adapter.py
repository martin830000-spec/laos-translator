"""KI1: Korean task-instruction localization, no examples or semantic hints."""
import importlib.util,json
from pathlib import Path
ROOT=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('ki1_frozen_core',ROOT.parent/'claude-rd-core/core.py');core=importlib.util.module_from_spec(s);s.loader.exec_module(core)
P=json.loads((ROOT/'prompts-ko.json').read_text(encoding='utf-8'))
def baseline_request(text,side,stage):return core.baseline(text,side,stage,'claude-sonnet-5-5')
def build_request(text,side,stage):
 q=baseline_request(text,side,stage)
 q['system']='<translation_task>'+P['COMMON']+'</translation_task>\n<couple_context>'+P['ROLE_'+side]+'</couple_context>\n<translation_stage>'+P['BACK' if stage=='back' else 'FORWARD']+'</translation_stage>'
 src,dst=('한국어','라오어') if side=='K' else ('라오어','한국어')
 if stage=='back':src,dst=dst,src
 q['messages']=[{'role':'user','content':'다음 메시지를 '+src+'에서 '+dst+'로 번역하세요.\n<source>\n'+text+'\n</source>'}]
 return q
def inspect_response(raw):return core.inspect(raw)
