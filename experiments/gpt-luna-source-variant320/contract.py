import json,hashlib
MODEL='gpt-6-luna'
CAPS={'A':80,'B':40,'C':60,'D':60,'E':80}
def stage_root(stage):
 assert stage in ('A','B','C','D','E1','E2');return stage[0]
def budget_guard(reservations,slot,model,stage):
 assert model==MODEL,'MODEL_NOT_APPROVED'
 assert slot not in {r['slot'] for r in reservations},'DUPLICATE_SLOT'
 assert len(reservations)<320,'CAMPAIGN_CAP'
 root=stage_root(stage)
 assert sum(stage_root(r['stage'])==root for r in reservations)<CAPS[root],'STAGE_CAP_NO_ROLLOVER'
 return {'slot':slot,'model':model,'stage':stage,'state':'RESERVED_TRANSMISSION_UNKNOWN'}
def build_payload(model,effort,path,text,prompts):
 assert model==MODEL and effort=='none' and path in ('KF','KB','LF','LB') and isinstance(text,str)
 return dict(model=model,reasoning={'effort':effort},instructions=prompts[path],input=text,stream=True,store=False,max_output_tokens=4096,service_tier='default')
def back_input(parent):
 if not parent or not parent.get('success') or not isinstance(parent.get('display_text'),str) or not parent['display_text'].strip():return None
 return parent['display_text']
def assert_back_payload(payload,text,prompts,path):
 assert path in ('KB','LB') and payload==build_payload(MODEL,'none',path,text,prompts)
def repetition_guard(prior,task):
 fingerprint=task['condition_sha256'];n=sum(x['condition_sha256']==fingerprint for x in prior)
 assert n<5 and task['repeat_index']==n+1,'FIVE_TOTAL_NOT_FIVE_ADDITIONAL'

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
