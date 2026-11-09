"""PRACTICAL320 contracts; exact inherited BASE payload and parser."""
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
CAPS={'P1':96,'P2':64,'FINAL':160}
def budget_guard(reservations,slot,model,stage):
 assert model in MODELS
 assert stage in CAPS
 assert slot not in [r['slot'] for r in reservations], 'DUPLICATE_SLOT'
 assert len(reservations)<320, 'TOTAL_CAP'
 assert sum(r['stage']==stage for r in reservations)<CAPS[stage], 'STAGE_CAP'
 return {'slot':slot,'model':model,'stage':stage,'state':'RESERVED_TRANSMISSION_UNKNOWN'}

def shared_request_key(payload,parser_hash):
 return hashlib.sha256(json.dumps({'payload':payload,'parser':parser_hash},sort_keys=True,ensure_ascii=False).encode()).hexdigest()

def back_input(parent):
 if not parent or not parent.get('success') or not isinstance(parent.get('display_text'),str) or not parent['display_text'].strip():return None
 return parent['display_text']
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
