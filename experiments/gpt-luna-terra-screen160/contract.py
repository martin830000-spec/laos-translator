"""Offline SCREEN160 contracts only. No HTTP transport or paid runner."""
import hashlib,json,pathlib
MODELS=('gpt-6-luna','gpt-6.1-terra')
def build_payload(model,effort,path,display_text,prompts):
 assert model in MODELS and effort in ('none','low')
 assert path in ('KF','LF','KB','LB') and isinstance(display_text,str)
 return {'model':model,'reasoning':{'effort':effort},'instructions':prompts[path],'input':display_text,'stream':True,'store':False,'max_output_tokens':4096,'service_tier':'default'}
def assert_back_payload(payload,displayed_first,prompts,path):
 assert path in ('KB','LB')
 expected=build_payload(payload['model'],payload['reasoning']['effort'],path,displayed_first,prompts)
 assert payload==expected
 assert hashlib.sha256(payload['input'].encode()).digest()==hashlib.sha256(displayed_first.encode()).digest()
def budget_guard(reservations,slot,model):
 assert model in MODELS
 assert slot not in [r['slot'] for r in reservations], 'DUPLICATE_SLOT'
 assert len(reservations)<160, 'TOTAL_CAP'
 assert sum(r['model']==model for r in reservations)<80, 'MODEL_CAP'
 return {'slot':slot,'model':model,'state':'RESERVED_TRANSMISSION_UNKNOWN'}
def parse_events(events):
 deltas=[];done=[];response=None;refusal=False;terminal=None;usage=None
 for event in events:
  t=event.get('type')
  if t=='response.output_text.delta':deltas.append(event.get('delta',''))
  elif t=='response.output_text.done':done.append(event.get('text',''))
  elif t=='response.refusal.delta':refusal=True
  if t in ('response.completed','response.incomplete','response.failed'):
   terminal=t;response=event.get('response',{});usage=response.get('usage')
 text=''.join(deltas)
 final=[]
 if response:
  for item in response.get('output',[]):
   for content in item.get('content',[]):
    if content.get('type')=='output_text':final.append(content['text'])
    if content.get('type')=='refusal':refusal=True
 completed=(terminal=='response.completed' and response.get('status')=='completed')
 mismatch=completed and (text!=''.join(final) or (done and text!=''.join(done)))
 ok=completed and not refusal and bool(text.strip()) and not mismatch
 return {'success':ok,'display_text':text if ok else None,'partial_text':text,'usage':usage,'terminal':terminal,'refusal':refusal,'mismatch':mismatch}
