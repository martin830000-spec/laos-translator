"""CP1: competing whole-source readings BEFORE one target rendering. No HTTP."""
from pathlib import Path
import importlib.util,copy,json
ROOT=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('cp1_frozen_la1',ROOT.parent/'haiku-linked-units/adapter.py');la1=importlib.util.module_from_spec(s);s.loader.exec_module(la1)
CONTRACT=('\nWhole-message interpretation contract CP1: before writing any target translation, '
 'form one or two possible readings of the current whole message in its SOURCE language. '
 'If there is a material ambiguity in an action or relation, use two genuinely competing readings; '
 'otherwise use one and do not invent a competing fact. A reading is a coherent semantic paraphrase, '
 'not a copied evidence list, not a target-language translation and not a translation draft. '
 'Compare any competing readings against the grammar and compatibility of the ENTIRE current message. '
 'Choose the supported reading, retaining any uncertainty the message does not resolve. '
 'In selection_reason briefly state why that reading fits better, or why uncertainty remains. '
 'Only after this source-interpretation comparison, generate translation ONCE as one natural finished '
 'target-language message. Do not translate both readings, do not revise an earlier translation, '
 'and put no planning, alternatives, commentary or correction attempts inside translation. '
 'The source readings and selection describe only the current visible message, including during BACK; '
 'they must never reconstruct an unseen earlier original.')
SCHEMA={'type':'object','properties':{
 'source_readings':{'type':'array','minItems':1,'items':{'type':'string'},'description':'One or two competing whole-message readings in the current source language, before any target translation.'},
 'chosen_reading':{'type':'integer','enum':[0,1],'description':'Zero-based selected source-reading index.'},
 'selection_reason':{'type':'string','description':'Why the whole current message supports the selected reading, or what remains uncertain. Not a target translation.'},
 'translation':{'type':'string','description':'The single finished natural target message, generated once after source-reading selection.'}},'required':['source_readings','chosen_reading','selection_reason','translation'],'additionalProperties':False}
def build_request(text,side,stage):
 q=la1.build_request(text,side,stage,'LA1');assert q['system'].endswith(la1.CONTRACT)
 q['system']=q['system'][:-len(la1.CONTRACT)]+CONTRACT
 q['output_config']['format']['schema']=copy.deepcopy(SCHEMA)
 return q
def inspect_response(raw,text,side,stage):
 visible=''.join(b.get('text','') for b in raw.get('content',[]) if b.get('type')=='text')
 out={'raw_visible_text':visible,'translation':'','status':'FAILED','warnings':[],'stop_reason':raw.get('stop_reason')}
 if raw.get('stop_reason')!='end_turn':return out
 obj=json.loads(visible,object_pairs_hook=la1.unique_object)
 if not isinstance(obj,dict) or set(obj)!=set(SCHEMA['required']):raise ValueError('CP1 schema')
 if not isinstance(obj['source_readings'],list) or not 1<=len(obj['source_readings'])<=2 or any(not isinstance(x,str) or not x.strip() for x in obj['source_readings']):raise ValueError('CP1 readings')
 if type(obj['chosen_reading']) is not int or not 0<=obj['chosen_reading']<len(obj['source_readings']):raise ValueError('CP1 selection')
 if not isinstance(obj['selection_reason'],str) or not isinstance(obj['translation'],str) or not obj['translation'].strip():raise ValueError('CP1 output')
 out.update(obj,status='SUCCESS',schema_valid=True,reading_count=len(obj['source_readings']))
 return out
