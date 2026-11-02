"""New mechanisms, not renamed compact or target-only prompts. One API per stage."""
from pathlib import Path
import importlib.util,copy,json
ROOT=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('prior320',ROOT/'prior_adapter.py');p=importlib.util.module_from_spec(s);s.loader.exec_module(p)
b=p.b;MODELS=b.MODELS;digest=b.digest;usage_cost=b.usage_cost
def engine(v,stage):return v[:2]
def structured(q,props):
 q['payload']['generationConfig'].update(maxOutputTokens=2048,responseMimeType='application/json',responseSchema=dict(type='OBJECT',properties=props,required=list(props),propertyOrdering=list(props)))
 return q
def build(text,side,stage,v):
 if v in ('38','31U','35R'):return p.build(text,side,stage,v)
 if v=='35Q':
  q=build(text,side,stage,'35E');q['payload']['generationConfig']['thinkingConfig']['thinkingLevel']='low';q['prompt_variant']=v
  return q
 if v=='31C':
  q=build(text,side,stage,'31I')
  q['payload']['system_instruction']['parts'][0]['text']+=' Preserve causal links: waking because of pain is different from noticing pain after waking. Resolve relative time against the expressed event state: a completed night of sleep followed by morning waking refers to the most recent night, not an upcoming night. Names and family address terms remain names or address terms when the predicate refers to a person. A completed report must not become a request to relay a message. Symptom terminology: Korean 배가 아프다 / 배 아픈 것은 corresponds to Lao ເຈັບທ້ອງ (abdominal pain), not ທ້ອງເສຍ (diarrhea); only explicit 설사 supports diarrhea. Nausea is ປວດຮາກ or ພະອືດພະອົມ, not merely fullness. Use this terminology only when that symptom is actually present in the supplied message.'
  q['prompt_variant']=v;return q
 if v=='38S':
  q=b.build(text,side,stage,'38');target='Lao' if (side=='K')==(stage=='first') else 'Korean'
  q['payload']['system_instruction']['parts'][0]['text']+=' In this single response emit repairs, then translation. repairs is a short list of ONLY evident misspelled fragments with source and reading in the supplied language; use an empty list when no evident repair is needed. Never repair an unfamiliar name into a common noun, infer absent facts or rewrite whole clauses. Translate the whole supplied message into '+target+', preserving event state and causes; the list is not a summary or extra user message. Only translation is displayed.'
  structured(q,{'repairs':{'type':'ARRAY','items':{'type':'OBJECT','properties':{'source':{'type':'STRING'},'reading':{'type':'STRING'}},'required':['source','reading'],'propertyOrdering':['source','reading']}},'translation':{'type':'STRING'}});q['prompt_variant']=v;return q
 q=b.build(text,side,stage,engine(v,stage));lao=(side=='K')==(stage=='first');target='Lao' if lao else 'Korean'
 base=q['payload']['system_instruction']['parts'][0]['text']
 independent=' Use ONLY the supplied message, never an unseen original or an inferred conversation.' if stage=='back' else ''
 if v=='31I':
  base='Translate this spouse message into natural '+target+'. '+p.COMMON+independent
  base+=' First copy a short list of evidence anchors from the supplied message: clauses containing actions, negation, time/aspect, symptoms or quantities. Copy rather than explain. These are source evidence, not new facts. Then produce translation of the WHOLE supplied message. Do not assign an omitted actor unless the current grammar establishes one. A statement about the speaker\'s state stays a statement; do not turn it into advice. Unknown names stay names by sound. The anchors are not shown to the user; only translation is displayed.'
  structured(q,{'anchors':{'type':'ARRAY','items':{'type':'STRING'}},'translation':{'type':'STRING'}})
 elif v=='38F':
  base+=' In this single response, first provide reading: the supplied message in its OWN language, with ONLY evident typo/spacing repairs. Preserve names, quantities, negation, time and unknown expressions; do not expand missing participants or supply a cause. Then translate that reading into '+target+'. Reading is not a paraphrase, summary, answer or correction of an unseen original. When more than one reading is possible keep the ambiguity. Only translation is displayed.'+independent
  structured(q,{'reading':{'type':'STRING'},'translation':{'type':'STRING'}})
 elif v=='35E':
  base='Translate spouse messages into natural '+target+'. '+p.COMMON+independent
  base+=' The examples demonstrate output language and preserved event state. They are unrelated examples; never borrow their people, objects, facts or vocabulary for a new message. Output only the translation of the final user message.'
  examples=[('아직 안 보냈어. 내일 보낼게.','ຍັງບໍ່ໄດ້ສົ່ງເທື່ອ. ມື້ອື່ນຈະສົ່ງໃຫ້.'),('ເມື່ອຍແຕ່ບໍ່ໄດ້ເຈັບຫົວ','피곤하지만 머리가 아픈 건 아니야.')]
  pair=examples[0] if lao else examples[1]
  q['payload']['contents']=[{'role':'user','parts':[{'text':pair[0]}]},{'role':'model','parts':[{'text':pair[1]}]},{'role':'user','parts':[{'text':text}]}]
 else:raise ValueError('Unregistered hypothesis '+v)
 q['payload']['system_instruction']['parts'][0]['text']=base;q['prompt_variant']=v
 return q
def inspect(raw,text,side,stage,v):
 if v in ('38','31U','35R'):return p.inspect(raw,text,side,stage,v)
 if v in ('35E','35Q'):return b.inspect(raw,text,side,stage,'35')
 c=raw.get('candidates',[{}])[0];visible=''.join(x.get('text','') for x in c.get('content',{}).get('parts',[]) if x.get('thought') is not True)
 if c.get('finishReason')!='STOP':return dict(status='FAILED',raw_text=visible,translation=None,stop_reason=c.get('finishReason'))
 obj=json.loads(visible,object_pairs_hook=b.unique);expected={'anchors','translation'} if v in ('31I','31C') else {'repairs','translation'} if v=='38S' else {'reading','translation'}
 assert set(obj)==expected and type(obj['translation'])is str and obj['translation'].strip()
 if v in ('31I','31C'):assert type(obj['anchors'])is list and all(type(x)is str for x in obj['anchors'])
 elif v=='38S':assert type(obj['repairs'])is list
 else:assert type(obj['reading'])is str
 value=copy.deepcopy(raw);value['candidates'][0]['content']['parts']=[{'text':obj['translation']}];out=b.inspect(value,text,side,stage,engine(v,stage));out.update(raw_text=visible,scaffold=obj)
 if v in ('31I','31C'):out['anchor_verbatim']=all(x in text for x in obj['anchors'])
 return out
