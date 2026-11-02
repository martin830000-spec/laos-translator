"""Model-specific prompt hypotheses. Frozen P168A remains the A/B control."""
from pathlib import Path
import importlib.util,copy,json,hashlib
ROOT=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('p320baseline',ROOT/'baseline.py');b=importlib.util.module_from_spec(s);s.loader.exec_module(b)
MODELS=b.MODELS;digest=b.digest;usage_cost=b.usage_cost
def engine(variant,stage):return variant[:2]
COMMON='Translate the supplied message faithfully. Keep the same people and references, actions and objects, negation, condition, time and event state, certainty, amounts and units, names, symptoms, and emotional force. Use natural conversational grammar and preserve clear typos by intended meaning. Leave genuinely unspecified details unspecified. Keep questions, permission and plans distinct from statements, commands and completed events. Keep identity-bearing terms by name or sound when unsure. Return one finished translation only, without commentary, labels or alternatives.'
SPAN=' Follow each source clause in order: identify its expressed predicate and participants, translate that clause, then connect the translated clauses naturally. Each target action, concrete object and event must have evidence in that source clause. Keep a missing subject implicit rather than complete a plausible story. Keep broad states broad and distinct symptoms distinct. Preserve incomplete endings.'
LAO='??????????????????????? ??? ????????. ?????????????????????. ???????????? ???????? ?????? ??????????? ???? ?????????? ???????? ????? ??? ????????????????. ?????????????? ??????????????.'
def build(text,side,stage,variant):
 e=engine(variant,stage);q=b.build(text,side,stage,e)
 if len(variant)==2:return q
 lao=(side=='K')==(stage=='first'); target='Lao' if lao else 'Korean'
 speaker,listener=('husband','wife') if side=='K' else ('wife','husband')
 role=f' The message is from a {speaker} to their {listener}; explicit grammatical people override this setting. In direct address spouse terms refer to the listener.'
 independent=' Only the supplied translation is evidence. This is an independent back-translation: never reconstruct or repair an unseen original.' if stage=='back' else ''
 # A compact positive task, not the prior ever-growing P168 lock list.
 prompt=f'Translate into natural {target}.'+role+' '+COMMON+independent
 if e=='31':prompt+=SPAN
 if e=='35':
  prompt=(LAO+'\n' if lao else '�ڿ������� �ѱ��� ������ �ϳ��� ����ϼ���.\n')+prompt
  prompt+=' Use standard target-language spelling for ordinary words; retain proper names, numerals and emoji as needed.'
 if e=='38':
  prompt+=' Preserve supplied words rather than supplying an inferred cause, actor or symptom. Natural paraphrases and readable clause splitting are welcome when the practical meaning is unchanged.'
 if variant.endswith('R'):
  # Revision: lexical analysis in source language is silent, never a generated second pass.
  prompt+=' Read idiomatic source phrases as a whole before choosing target words. Distinguish an actual action from wanting/feeling like doing it; keep a quoted or reported proposition attached to its stated speaker. Do not translate familiar-looking fragments as a different object or place.'
 q['payload']['system_instruction']['parts'][0]['text']=prompt
 q['smart_ids']=[];q['prompt_variant']=variant
 return q
def inspect(raw,text,side,stage,variant):return b.inspect(raw,text,side,stage,engine(variant,stage))
