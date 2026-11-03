"""Iterative general candidates; no network and no private context literals."""
from pathlib import Path
import importlib.util,copy,json
ROOT=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('followup272_adapter',ROOT.parent/'gemini-followup/adapter.py');base=importlib.util.module_from_spec(s);s.loader.exec_module(base)
MODELS=base.MODELS;usage_cost=base.usage_cost
CLOCK=' Preserve the meaning, unit and scope of every number. Read an hour together with its daypart as one time point and express it once in a consistent target-language clock convention. An equivalent24-hour rendering is allowed; do not add a conflicting local-clock alternative. Preserve before/after, not yet, bounds, dates, durations, ages, frequency, money and condition-result attachment. Correct clear typos only when the intended meaning is clear; do not invent a time, number or event.'
SCOPE=' Use household_context only to disambiguate explicitly mentioned references. A similar sound alone does not establish an alias. Local grammar, money units and ordinary noun predicates override nickname expectations. Do not add a baby, pregnancy, diagnosis, relationship or event that the current message does not express.'
BIND=' Copy short reference spans from the CURRENT message only. Bind each span to its expressed predicate with relation actor, target, address, label or modifier. Keep a title plus a name as one reference when the grammar establishes one. Cover expressed names, food labels and specific action manners. Address terms do not become extra participants in the described event. Preserve the number and scope of referents. If a label is unfamiliar, retain it by sound instead of guessing a familiar replacement. These bindings are evidence from the supplied text, not extra facts. Then translate the WHOLE current message.'
UNCERTAIN=' Preserve expressed uncertainty, causal direction and referent count. If this supplied message contains contradictory alternatives, show that same inconsistency; never repair an unseen original or silently choose a preferred time. Do not change empathy into new advice or broaden a named referent into extra people.'
DIGITAL=' For an explicitly specified clock time with a daypart, express that same time once using unambiguous 24-hour HH:MM notation. Do not also add a local or Thai-style counted evening hour. Preserve the scope of before, after and not yet. This applies to clock times only; retain the meaning and units of dates, durations, money and other quantities.'
SUBJECT=' When the source states an event without identifying its subject, keep a natural subjectless target clause. Do not add first-person ownership, attendance, intention or a family role to fill that gap. A vocative identifies the addressee, not the actor of every clause.'
COMPARISON=' Keep a comparison of a feeling or sensation as a comparison. Saying that something feels as if an event happened does not assert that the event happened or caused it. Preserve the comparison and its uncertainty without adding a real event or a guessed cause. Resolve a clear typo conservatively, retaining any uncertainty that affects this distinction.'
EVENT_RELATIONS=' Preserve the event graph expressed by the CURRENT source, rather than filling it in from a plausible story: a realized event in a causal clause remains a fact even if its emotional consequence is anticipated; a factual cause (-아서/-어서/-기 때문에) is not a hypothetical condition (-면/if). In motion and waiting clauses track each person\'s location, origin, destination and whether return was actually asserted: coming to a place is not returning from it and arrival is not departure. Do not turn figurative arrival, announcement or expectation into an already-completed birth or other irreversible event. Keep the exact actor, tense, cause and destination for each clause while rewriting naturally and warmly in Lao. Never add a gloss or explanation.'
SPEAKER_SCOPE=' Preserve the grammatical subject of each main action and utterance. A possessor in a noun phrase is not automatically the actor who asked, sent, moved or reported. In nested requests and reported speech track exactly who asked whom to ask whom, who could not be reached, and whose phone or documents are discussed. Resolve omitted subjects only from explicit local grammar, not the closest named person. Keep uncertainty, questions and the exact strength of a symptom. Do not add implied agents or change present pain into already recovered pain.'
SYMPTOM_EVENT=' Preserve whether the current source actually asserts vomiting, merely feeling nauseated or wanting to vomit, retching, or just a comparison. These are not interchangeable completed events. Likewise keep symptom occurrence versus anticipated possibility, severity and time references unchanged. Translate naturally without diagnosis or medical advice, and preserve the rest of the message instead of focusing on symptoms.'
DISCOURSE_ACCURACY=' Keep the exact predicate and speech act of each question or statement: do not replace a question about one event or state with a related earlier or later event. Preserve the head activity and purpose inside compound nouns and notices instead of broadening to a generic trip, action or object. Maintain kinship relations without guessing unspecified gender, and do not output slash-separated gender alternatives or translator notes. Respect nested request attribution, time, and realized versus hypothetical events. Retain counterfactual regret rather than weakening it to a present wish. Translate naturally without editorializing.'
CHAT_REGISTER=' Preserve the interpersonal register signaled by the CURRENT message: informal affectionate chat should read as natural casual Korean, not stiff formal polite speech, while formal or institutional messages remain formal. Keep affectionate vocatives only when expressed; do not insert extra participants, advice, emotions or relationship facts. Preserve the original sequence and concise spoken rhythm, without compromising tense, symptom severity or factual content.'
LEXEME_REFERENCE=' Recover normal lexical word units from obvious syllable-by-syllable spacing or STT segmentation before choosing a meaning; do not translate only a familiar suffix of a segmented word. Keep every expressed named referent attached to its own clause. A completed event explaining an emotion must remain its cause; do not replace it with a future condition or substitute a nearby address term for its actor or object.'
def append(q,text):
 q=copy.deepcopy(q);q['payload']['system_instruction']['parts'][0]['text']+=text;return q
def build_first(text,side,profile,context=None,turns=None):
 if turns is not None:raise ValueError('history not authorized')
 if profile in ('31T4','31T5','31T6','31T7','31T8','31T9'):
  q=append(base.build_first(text,side,'31L',context),DIGITAL+(SUBJECT if profile in ('31T5','31T6','31T7','31T8','31T9')else'')+(LEXEME_REFERENCE if profile=='31T6'else'')+(EVENT_RELATIONS if profile in ('31T7','31T8','31T9')else'')+(SPEAKER_SCOPE if profile=='31T8'else'')+(DISCOURSE_ACCURACY if profile=='31T9'else''));q['prompt_variant']=profile;return q
 if profile in ('38CF','38CG','38CH'):
  q=append(build_first(text,side,'38CA',context),COMPARISON+(SYMPTOM_EVENT if profile in ('38CG','38CH') else '')+(CHAT_REGISTER if profile=='38CH' else ''));q['prompt_variant']=profile;return q
 if profile in ('31T1','31T2','31T3'):
  q=base.build_first(text,side,'31D'if profile=='31T3'else'31L',context)
  if profile!='31T2':q=append(q,CLOCK)
  else:
   q=append(q,' Before translation, copy short numeric/time/condition fragments into facts. role is time_point, duration, amount, quantity, age, frequency, condition or event_state. scope is the exact source fragment identifying its governed event or bound; keep it empty when unspecified. Do not compute a second clock representation. Translate the whole message while preserving these expressed relations.')
   item={'type':'OBJECT','properties':{'span':{'type':'STRING'},'role':{'type':'STRING','enum':['time_point','duration','amount','quantity','age','frequency','condition','event_state']},'scope':{'type':'STRING'}},'required':['span','role','scope'],'propertyOrdering':['span','role','scope']}
   q['payload']['generationConfig'].update(responseMimeType='application/json',responseSchema={'type':'OBJECT','properties':{'facts':{'type':'ARRAY','items':item},'translation':{'type':'STRING'}},'required':['facts','translation'],'propertyOrdering':['facts','translation']})
  q['prompt_variant']=profile;return q
 if profile in ('38CS','38CA'):
  ctx=context
  if profile=='38CA':
   if not isinstance(context,dict)or not isinstance(context.get('aliases'),list):raise ValueError('private aliases required')
   ctx={'aliases':copy.deepcopy(context['aliases']),'interpretation':'Listed expressions can be personal nicknames when the current grammar denotes a person. Ordinary financial/noun meanings override aliases. Do not infer any unexpressed event.'}
  q=base.build_first(text,side,'38FB',ctx)
  if profile=='38CS':q=append(q,SCOPE)
  q['prompt_variant']=profile;return q
 return base.build_first(text,side,profile,context,turns)
def build_back(first_text,side,profile):
 if profile=='31RB':
  q=base.build_back(first_text,side,'31C');p=q['payload']['system_instruction']['parts'][0]['text']
  start=p.index(' First copy a short list');end=p.index(' Do not assign an omitted actor',start)
  q['payload']['system_instruction']['parts'][0]['text']=p[:start]+' '+BIND+p[end:].replace('The anchors are not shown','The bindings are not shown')
  item={'type':'OBJECT','properties':{'span':{'type':'STRING'},'predicate':{'type':'STRING'},'relation':{'type':'STRING','enum':['actor','target','address','label','modifier']}},'required':['span','predicate','relation'],'propertyOrdering':['span','predicate','relation']}
  q['payload']['generationConfig']['responseSchema']={'type':'OBJECT','properties':{'bindings':{'type':'ARRAY','items':item},'translation':{'type':'STRING'}},'required':['bindings','translation'],'propertyOrdering':['bindings','translation']}
  q['prompt_variant']=profile;return q
 if profile=='38CB':return append(base.build_back(first_text,side,'38P'),UNCERTAIN)
 return base.build_back(first_text,side,profile)
def inspect(raw,text,side,stage,profile):
 special=(stage=='first'and profile=='31T2')or(stage=='back'and profile=='31RB')
 if not special:
  mapped={'31T1':'31L','31T3':'31D','31T4':'31L','31T5':'31L','31T6':'31L','31T7':'31L','31T8':'31L','31T9':'31L','38CG':'38FB','38CH':'38FB','38CS':'38FB','38CA':'38FB','38CF':'38FB','38CB':'38P'}.get(profile,profile)
  return base.inspect(raw,text,side,stage,mapped)
 try:
  cand=raw.get('candidates',[{}])[0]
  if cand.get('finishReason')!='STOP':raise ValueError('NONSTOP')
  visible=''.join(z.get('text','')for z in cand.get('content',{}).get('parts',[])if z.get('thought')is not True)
  obj=json.loads(visible,object_pairs_hook=base.old.unique);key='facts'if profile=='31T2'else'bindings'
  if set(obj)!={key,'translation'}or type(obj[key])is not list or type(obj['translation'])is not str or not obj['translation'].strip():raise ValueError('SCHEMA')
  for z in obj[key]:
   if profile=='31T2':
    if set(z)!={'span','role','scope'}or z['role']not in ['time_point','duration','amount','quantity','age','frequency','condition','event_state']:raise ValueError('FACT')
   elif set(z)!={'span','predicate','relation'}or z['relation']not in ['actor','target','address','label','modifier']:raise ValueError('BINDING')
   if any(type(v)is not str for v in z.values()):raise ValueError('FIELD_TYPE')
  value=copy.deepcopy(raw);value['candidates'][0]['content']['parts']=[{'text':obj['translation']}]
  out=base.old.inspect_plain(value,text,side,stage,'31');out.update(scaffold=obj,raw_visible_text=visible,span_verbatim=all(z['span']in text for z in obj[key]))
  return out
 except Exception as exc:return dict(status='FAILED',translation=None,failure_kind='SCHEMA_OR_PARSE',error_type=type(exc).__name__)
