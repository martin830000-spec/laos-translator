"""Model-specific prompt hypotheses. Frozen P168A remains the A/B control."""
from pathlib import Path
import importlib.util,copy,json,hashlib
ROOT=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('p320baseline',ROOT/'baseline.py');b=importlib.util.module_from_spec(s);s.loader.exec_module(b)
MODELS=b.MODELS;digest=b.digest;usage_cost=b.usage_cost
def engine(variant,stage):return variant[:2]
COMMON='Translate the supplied message faithfully. Keep the same people and references, actions and objects, negation, condition, time and event state, certainty, amounts and units, names, symptoms, and emotional force. Use natural conversational grammar and preserve clear typos by intended meaning. Leave genuinely unspecified details unspecified. Keep questions, permission and plans distinct from statements, commands and completed events. Keep identity-bearing terms by name or sound when unsure. Return one finished translation only, without commentary, labels or alternatives.'
SPAN=' Follow each source clause in order: identify its expressed predicate and participants, translate that clause, then connect the translated clauses naturally. Each target action, concrete object and event must have evidence in that source clause. Keep a missing subject implicit rather than complete a plausible story. Keep broad states broad and distinct symptoms distinct. Preserve incomplete endings.'
LAO='ແປເປັນພາສາລາວທີ່ທຳມະຊາດ ແລະ ອ່ານງ່າຍ. ຂຽນຄຳລາວດ້ວຍອັກສອນລາວ. ຮັກສາຄວາມໝາຍ ຜູ້ເວົ້າ ຜູ້ຟັງ ບຸກຄົນທີສາມ ເວລາ ການປະຕິເສດ ເງື່ອນໄຂ ຈຳນວນ ແລະ ນ້ຳສຽງຂອງຂໍ້ຄວາມ. ສົ່ງພຽງຄຳແປດຽວ ບໍ່ຕ້ອງອະທິບາຍ.'
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
  prompt=(LAO+'\n' if lao else '자연스러운 한국어 번역문 하나만 출력하세요.\n')+prompt
  prompt+=' Use standard target-language spelling for ordinary words; retain proper names, numerals and emoji as needed.'
 if e=='38':
  prompt+=' Preserve supplied words rather than supplying an inferred cause, actor or symptom. Natural paraphrases and readable clause splitting are welcome when the practical meaning is unchanged.'
 if variant.endswith('R'):
  # Revision: lexical analysis in source language is silent, never a generated second pass.
  prompt+=' Read idiomatic source phrases as a whole before choosing target words. Distinguish an actual action from wanting/feeling like doing it; keep a quoted or reported proposition attached to its stated speaker. Do not translate familiar-looking fragments as a different object or place.'
 if variant=='35R':
  if lao:
   prompt=LAO+' ຂໍ້ຄວາມນີ້ແມ່ນຄຳເວົ້າລະຫວ່າງຜົວເມຍ. ຢ່າປ່ຽນຜູ້ເຮັດ ຫຼື ຜູ້ຮັບການກະທຳ. ຢ່າເພີ່ມສິ່ງຂອງ ເຫດການ ຫຼື ອາການທີ່ບໍ່ມີໃນຂໍ້ຄວາມ. ຮັກສາຊື່ຄົນ ສະຖານທີ່ ແລະ ສິ່ງຂອງ. ແຍກການກະທຳທີ່ແລ້ວ ທີ່ກຳລັງເຮັດ ແລະ ທີ່ຈະເຮັດ. ຖ້າບໍ່ຊັດເຈນ ຢ່າເດົາເພີ່ມ. ຮັກສາຄຳຖາມ ຄວາມປາຖະໜາ ແລະ ຄວາມຮູ້ສຶກ. ຂຽນພຽງຄຳແປເປັນພາສາລາວ.'
   if stage=='back':prompt+=' ໃຊ້ພຽງຂໍ້ຄວາມເກົາຫຼີທີ່ໃຫ້ມາເປັນຫຼັກຖານ. ຢ່າເດົາຫຼືແກ້ໄຂຕາມຕົ້ນສະບັບທີ່ບໍ່ໄດ້ເຫັນ.'
  else:
   prompt='주어진 라오어 메시지만 자연스럽고 읽기 쉬운 한국어로 번역하세요. 부부 사이의 대화입니다. 명시된 화자·청자·제삼자, 행동의 주체와 대상, 부정·조건·시점·예정과 완료·확실성·수치·단위·이름·증상·감정을 그대로 전달하세요. 없는 물건이나 사건·증상을 덧붙이지 마세요. 모호한 부분은 모호하게 남기고 문법만 자연스럽게 정리하세요. 친근한 말은 자연스러운 반말로, 공손한 말은 자연스러운 존댓말로 옮기세요. 해설·대안·라벨 없이 완성된 한국어 번역문 하나만 출력하세요.'
   if stage=='back':prompt+=' 주어진 번역문만 근거로 삼으세요. 보이지 않는 최초 원문을 추측하거나 복원·수정하지 마세요.'
 if variant=='31U':
  prompt+=(' Produce JSON units in source order. Each unit has source: an exact contiguous phrase from the current supplied message, and target: its natural '+target+' translation. Cover the whole message once, with no duplication or gaps; keep names and meaningful phrases together. A short message may use one unit. Joining target strings in order must produce the one finished translation. Do not produce an analysis, checklist, paraphrase of the source, alternatives or corrections. The source fields contain only the current supplied message, never an unseen original.')
  q['payload']['generationConfig'].update(responseMimeType='application/json',responseSchema={'type':'OBJECT','properties':{'units':{'type':'ARRAY','items':{'type':'OBJECT','properties':{'source':{'type':'STRING'},'target':{'type':'STRING'}},'required':['source','target'],'propertyOrdering':['source','target']}}},'required':['units'],'propertyOrdering':['units']})
 if variant=='38G':
  # Restore selected proven P168A components removed by the compact ablation.
  # No sample-specific vocabulary or reference translation is added.
  conf=json.loads((ROOT/'prompt-config.json').read_text(encoding='utf-8'))
  old=conf['forward']['k2l' if side=='K' else 'l2k'] if stage=='first' else conf['back']['husband' if side=='K' else 'wife']
  import re
  labels=['SEMANTIC-BREADTH/IDENTITY LOCK','INCOMPLETE INPUT','STATE-BREADTH LOCK'] if stage=='first' else ['STATE-BREADTH']
  restored=[]
  for label in labels:
   match=re.search(re.escape(label)+r':.*?(?= [A-Z][A-Z/-]*(?: [A-Z/-]+)*:|$)',old)
   if match:restored.append(match.group(0))
  prompt+=' '+' '.join(restored)
  prompt+=' If an expression is misspelled or unfamiliar, use the closest supported source reading, not a plausible follow-up message or an instruction to the listener. Retain an uncertain name by sound; do not identify a different familiar species, product, action or person from a phonetic resemblance.'
 q['payload']['system_instruction']['parts'][0]['text']=prompt
 q['smart_ids']=[];q['prompt_variant']=variant
 return q
def inspect(raw,text,side,stage,variant):
 if variant!='31U':return b.inspect(raw,text,side,stage,engine(variant,stage))
 c=raw.get('candidates',[{}])[0];visible=''.join(x.get('text','') for x in c.get('content',{}).get('parts',[]) if x.get('thought') is not True)
 if c.get('finishReason')!='STOP':return dict(status='FAILED',stop_reason=c.get('finishReason'),raw_text=visible,translation=None)
 obj=json.loads(visible,object_pairs_hook=b.unique);assert set(obj)=={'units'} and type(obj['units']) is list and obj['units']
 for u in obj['units']:assert set(u)=={'source','target'} and all(type(v)is str and v.strip() for v in u.values())
 value=copy.deepcopy(raw);value['candidates'][0]['content']['parts']=[{'text':' '.join(u['target'] for u in obj['units'])}];out=b.inspect(value,text,side,stage,'31');out.update(raw_text=visible,units=obj['units'],source_coverage_exact=''.join(u['source'] for u in obj['units'])==text)
 return out
