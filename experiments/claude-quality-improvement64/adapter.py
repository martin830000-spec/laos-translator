"""A: Sonnet native format only. B: Haiku FIRST exact-text+pixel view only."""
from pathlib import Path
import importlib.util,copy,json,base64,hashlib
R=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('quality64_frozen',R.parent/'claude-real20-120/adapters.py');f=importlib.util.module_from_spec(s);s.loader.exec_module(f)
SCHEMA={'type':'object','properties':{'translation':{'type':'string'}},'required':['translation'],'additionalProperties':False}
IMAGE_NOTICE='The image renders exactly the same current source message supplied below. They are two representations of ONE message, not separate events. Translate that one message once; the original text remains authoritative.\n'
def build(text,side,stage,study,variant,image=None):
 assert study in ('A','B') and variant in ('BASE','NEW')
 q=f.build(text,side,stage,'S' if study=='A' else 'H')
 if study=='A' and variant=='NEW':q['output_config']['format']={'type':'json_schema','schema':copy.deepcopy(SCHEMA)}
 if study=='B' and variant=='NEW' and stage=='first':
  assert image and image['source_sha256']==hashlib.sha256(text.encode()).hexdigest()
  png=base64.b64decode(image['image_b64'],validate=True)
  assert png.startswith(b'\x89PNG\r\n\x1a\n') and hashlib.sha256(png).hexdigest()==image['image_sha256']
  q['messages'][0]['content']=[{'type':'image','source':{'type':'base64','media_type':'image/png','data':image['image_b64']}},{'type':'text','text':IMAGE_NOTICE+q['messages'][0]['content']}]
 return q
def unique(pairs):
 d={}
 for k,v in pairs:
  if k in d:raise ValueError('Duplicate JSON key')
  d[k]=v
 return d
def inspect(raw,text,side,stage,study,variant):
 engine='S' if study=='A' else 'H'
 if study!='A' or variant!='NEW':return f.inspect(raw,text,side,stage,engine)
 visible=''.join(b.get('text','') for b in raw.get('content',[]) if b.get('type')=='text')
 if raw.get('stop_reason')!='end_turn':raise ValueError('Incomplete or refusal; no salvage')
 obj=json.loads(visible,object_pairs_hook=unique)
 if type(obj) is not dict or set(obj)!= {'translation'} or type(obj['translation']) is not str or not obj['translation'].strip():raise ValueError('Strict translation schema')
 # Deliberately preserve whitespace, drafts, English and tags INSIDE translation.
 return dict(translation=obj['translation'],raw_visible_text=visible,status='SUCCESS',schema_valid=True,semantic_quality='UNVERIFIED',stop_reason=raw['stop_reason'],warnings=[])
