"""RR1: deterministic repeated full user input; unchanged frozen LA1 decoder contract."""
from pathlib import Path
import importlib.util
s=importlib.util.spec_from_file_location('rr1_frozen_la1',Path(__file__).resolve().parent.parent/'haiku-linked-units/adapter.py');la1=importlib.util.module_from_spec(s);s.loader.exec_module(la1)
REREAD='\nInput presentation RR1: The identical user translation request is provided twice for rereading. These are two views of ONE current message, not two messages or two events. Produce the usual single units array for ONE copy; do not repeat the translation. No extra interpretation, selection, explanation or correction field.'
def build_request(text,side,stage):
 q=la1.build_request(text,side,stage,'LA1')
 q['system']+=REREAD
 u=q['messages'][0]['content'];q['messages'][0]['content']=u+'\n\n'+u
 return q
def inspect_response(raw,text,side,stage):return la1.inspect_response(raw,text,side,stage,'LA1')
