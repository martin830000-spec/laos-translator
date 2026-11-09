import hashlib,json
MODELS=('gpt-6-luna','gpt-6.1-terra')
def build_payload(model,effort,path,text,prompts):
 assert model in MODELS and effort in ('none','low') and path in ('KF','KB','LF','LB') and isinstance(text,str)
 return dict(model=model,reasoning={'effort':effort},instructions=prompts[path],input=text,stream=True,store=False,max_output_tokens=4096,service_tier='default')
def assert_back_payload(payload,text,prompts,path):
 assert path in ('KB','LB') and payload==build_payload(payload['model'],payload['reasoning']['effort'],path,text,prompts)
def budget_guard(rs,slot,model,stage):
 assert model in MODELS and slot not in [r['slot'] for r in rs],'DUPLICATE_OR_MODEL'
 assert len(rs)<1000 and sum(r['model']==model for r in rs)<500,'MODEL_CAP'
 if stage!='FINAL':assert sum(r['model']==model and r['stage']!='FINAL' for r in rs)<340,'RESERVE_FINAL160'
 return dict(slot=slot,model=model,stage=stage,state='RESERVED_TRANSMISSION_UNKNOWN')
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
