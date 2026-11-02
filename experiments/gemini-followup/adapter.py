"""Controlled ablations. No network code; context accepted only by FIRST."""
from pathlib import Path
import importlib.util,json,copy
ROOT=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('real400legacy',ROOT/'legacy.py');old=importlib.util.module_from_spec(s);s.loader.exec_module(old)
MODELS=old.MODELS;digest=old.digest;usage_cost=old.usage_cost
CELLS={'38FA':(False,False),'38FB':(True,False),'38FC':(False,True),'38FD':(True,True)}
def _no_frames(q):
 q=copy.deepcopy(q);g=q['payload']['generationConfig'];g.pop('responseSchema',None);g.pop('responseMimeType',None)
 p=q['payload']['system_instruction']['parts'][0]['text'];cut=p.index(' Before translation, emit links:')
 q['payload']['system_instruction']['parts'][0]['text']=p[:cut]
 return q
def build_first(text,side,profile,context=None,turns=None):
 if side not in ('K','L')or not isinstance(text,str)or not text.strip():raise ValueError('message/direction')
 if turns is not None:raise ValueError('history-context hypothesis deferred: no unverified preceding-turn injection')
 if profile=='38SVC':return old.build(text,side,'first','38')
 if profile in CELLS:
  ctx,frames=CELLS[profile]
  if ctx and not isinstance(context,dict):raise ValueError('private FIRST context required')
  q=old.build(text,side,'first','38D')
  q['payload']['contents'][0]['parts'][0]['text']=json.dumps({'household_context':context if ctx else {},'message':text},ensure_ascii=False)
  if not frames:q=_no_frames(q)
 elif profile in ('31D','31L','31LL','35M','35ML'):
  original='31D'if profile.startswith('31')else'35T'
  if not isinstance(context,dict):raise ValueError('private FIRST context required')
  q=old.build(text,side,'first',original)
  q['payload']['contents'][0]['parts'][0]['text']=json.dumps({'household_context':context,'message':text},ensure_ascii=False)
  if profile in ('31L','31LL','35ML'):q=_no_frames(q)
  if profile.startswith('35'):q['payload']['generationConfig']['thinkingConfig']['thinkingLevel']='medium'
 else:raise ValueError('unregistered FIRST profile')
 q['prompt_variant']=profile
 return q
def build_back(first_text,side,profile):
 """API deliberately has no original/context/scaffold/history argument."""
 if side not in ('K','L')or not isinstance(first_text,str)or not first_text.strip():raise ValueError('actual FIRST required')

 if profile=='31TB':
  q=old.build(first_text,side,'back','31C')
  p=q['payload']['system_instruction']['parts'][0]['text']
  start=p.index(' First copy a short list');end=p.index(' Do not assign an omitted actor',start)
  p=p[:start]+' Before translation, copy only short explicitly present reference fragments into references. Mark each fragment as person_name, food_name, action, condition, symptom or quantity; do not invent a reference. A person name stays a name by sound rather than a spouse pronoun or an ordinary object. A local food name stays a food label by sound rather than a different familiar dish. Keep explicit action manner such as walking instead of reducing it to a broader activity. Translate the WHOLE current message, preserving these references and any expressed uncertainty. These categories are source evidence only, never extra message content.'+p[end:]
  q['payload']['system_instruction']['parts'][0]['text']=p.replace('The anchors are not shown','The references are not shown')
  refs={'type':'ARRAY','items':{'type':'OBJECT','properties':{'fragment':{'type':'STRING'},'kind':{'type':'STRING','enum':['person_name','food_name','action','condition','symptom','quantity']}},'required':['fragment','kind'],'propertyOrdering':['fragment','kind']}}
  q['payload']['generationConfig']['responseSchema']={'type':'OBJECT','properties':{'references':refs,'translation':{'type':'STRING'}},'required':['references','translation'],'propertyOrdering':['references','translation']}
  q['prompt_variant']=profile
  return q
 if profile in ('38P','38SVC','38FA','38FB','38FC','38FD'):
  return old.build(first_text,side,'back','38')
 if profile in ('31C','31D','31L'):return old.build(first_text,side,'back','31C')
 if profile in ('35M','35ML'):
  q=old.build(first_text,side,'back','35T');q['payload']['generationConfig']['thinkingConfig']['thinkingLevel']='medium';return q
 if profile=='31LL':
  q=old.build(first_text,side,'back','31C');g=q['payload']['generationConfig'];g.pop('responseSchema',None);g.pop('responseMimeType',None)
  p=q['payload']['system_instruction']['parts'][0]['text'];start=p.index(' First copy a short list');end=p.index(' Do not assign an omitted actor',start)
  p=p[:start]+p[end:];p=p.replace(' The anchors are not shown to the user; only translation is displayed.','')
  q['payload']['system_instruction']['parts'][0]['text']=p+' Output one finished translation only.';return q
 raise ValueError('unregistered BACK profile')
def inspect(raw,text,side,stage,profile):

 if profile=='31TB':
  try:
   candidate=raw.get('candidates',[{}])[0]
   visible=''.join(z.get('text','')for z in candidate.get('content',{}).get('parts',[])if z.get('thought')is not True)
   if candidate.get('finishReason')!='STOP':raise ValueError('NONSTOP')
   obj=json.loads(visible,object_pairs_hook=old.unique)
   if set(obj)!={'references','translation'}or type(obj['references'])is not list or type(obj['translation'])is not str or not obj['translation'].strip():raise ValueError('SCHEMA')
   for ref in obj['references']:
    if set(ref)!={'fragment','kind'}or type(ref['fragment'])is not str or ref['kind']not in ['person_name','food_name','action','condition','symptom','quantity']:raise ValueError('REFERENCE_SCHEMA')
   value=copy.deepcopy(raw);value['candidates'][0]['content']['parts']=[{'text':obj['translation']}]
   out=old.inspect_plain(value,text,side,stage,'31')
   out.update(raw_visible_text=visible,scaffold=obj,refs_verbatim=all(z['fragment']in text for z in obj['references']))
   return out
  except Exception as exc:return dict(status='FAILED',translation=None,failure_kind='TYPED_REFERENCE_PARSE',error_type=type(exc).__name__)
 # Reuse frozen display normalization; no automatic cleanup of foreign language.
 if stage=='back':
  v='38'if profile.startswith('38')else'35E'if profile.startswith('35')else'31C'
 elif profile in ('38FD','38FC'):v='38D'
 elif profile in ('31D',):v='31D'
 elif profile=='35M':v='35T'
 else:v='38'if profile.startswith('38')else'31'if profile.startswith('31')else'35E'
 if (profile=='31LL'and stage=='back')or (stage=='first'and profile in ('31L','31LL','35ML')):v=profile[:2]
 try:
  o=old.inspect_plain(raw,text,side,stage,profile[:2]) if ((stage=='first'and profile in ('31L','31LL','35ML'))or(stage=='back'and profile=='31LL')) else old.inspect(raw,text,side,stage,v)
  schema=(stage=='first'and profile in ('38FC','38FD','31D','35M'))
  if schema and o.get('status')=='SUCCESS':
   obj=o['scaffold'];assert set(obj)=={'links','states','translation'}
   for z in obj['links']:assert set(z)=={'condition','outcome'}and all(type(x)is str for x in z.values())
   for z in obj['states']:assert set(z)=={'event','state'}and type(z['event'])is str and z['state']in ['completed','ongoing','future','conditional','unspecified']
  if o.get('status')!='SUCCESS':o['failure_kind']='EMPTY_OR_NONSTOP'
  return o
 except Exception as exc:return dict(status='FAILED',translation=None,failure_kind='SCHEMA_OR_PARSE',error_type=type(exc).__name__)
