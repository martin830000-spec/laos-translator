"""SOLO100_FOURPATH_MECHANISM320 immutable source/prompt, single-pass and budget contracts."""
import hashlib,json,math,re
CAMPAIGN='GPT_LUNA_SOLO100_FOURPATH_MECHANISM320_20261115'
MODEL='gpt-6-luna'
PHASES=('A','B','C','FINAL')
HARD_CAPS={'A':96,'B':32,'C':128,'FINAL':64}
APPROVED_TOTAL=320
BRANCH='refs/heads/research/gemini-model-native500-20261107'
def canon(value):return (json.dumps(value,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode()
def sha(value):return hashlib.sha256(value).hexdigest()
def require(ok,code):
 if not ok:raise AssertionError(code)
def back_input(parent):
 if not isinstance(parent,dict) or not parent.get('success') or parent.get('unknown'):return None
 value=parent.get('display_text');return value if isinstance(value,str) and value.strip() else None

def parse_events(events):
    """Return a failed parse, rather than lose raw evidence on malformed events.

    The displayed text is the exact concatenation of streamed output deltas.
    Completed final content and every output-text-done aggregate must agree.
    Partial, refused, incomplete, failed, or contradictory streams never feed BACK.
    """
    deltas = []; done = []; response = {}; refusal = False
    terminal = None; usage = None; errors = []; terminals = 0
    if not isinstance(events, (list, tuple)):
        events = []; errors.append('EVENT_LIST_INVALID')
    for event in events:
        if not isinstance(event, dict):
            errors.append('EVENT_NOT_OBJECT'); continue
        kind = event.get('type')
        if kind in ('response.output_text.delta', 'response.output_text.done'):
            field = 'delta' if kind.endswith('.delta') else 'text'
            value = event.get(field)
            if not isinstance(value, str):
                errors.append('OUTPUT_TEXT_NOT_STRING')
            else:
                (deltas if field == 'delta' else done).append(value)
        elif kind in ('response.refusal.delta', 'response.refusal.done'):
            refusal = True
        elif kind == 'error':
            errors.append('STREAM_ERROR_EVENT')
        if kind in ('response.completed', 'response.incomplete', 'response.failed'):
            terminals += 1; terminal = kind
            value = event.get('response')
            if not isinstance(value, dict):
                errors.append('TERMINAL_RESPONSE_NOT_OBJECT'); response = {}
            else:
                response = value; usage = response.get('usage')
    if terminals > 1:
        errors.append('MULTIPLE_TERMINAL_EVENTS')
    final = []
    output = response.get('output', [])
    if not isinstance(output, list):
        errors.append('RESPONSE_OUTPUT_NOT_LIST'); output = []
    for item in output:
        if not isinstance(item, dict):
            errors.append('OUTPUT_ITEM_NOT_OBJECT'); continue
        content = item.get('content', [])
        if not isinstance(content, list):
            errors.append('OUTPUT_CONTENT_NOT_LIST'); continue
        for part in content:
            if not isinstance(part, dict):
                errors.append('OUTPUT_CONTENT_NOT_OBJECT'); continue
            if part.get('type') == 'refusal':
                refusal = True
            elif part.get('type') == 'output_text':
                value = part.get('text')
                if not isinstance(value, str): errors.append('FINAL_TEXT_NOT_STRING')
                else: final.append(value)
    text = ''.join(deltas)
    completed = terminal == 'response.completed' and response.get('status') == 'completed'
    mismatch = bool(completed and (text != ''.join(final) or (done and text != ''.join(done))))
    success = completed and not refusal and bool(text.strip()) and not mismatch and not errors
    return {'success': bool(success), 'display_text': text if success else None,
            'partial_text': text, 'usage': usage, 'terminal': terminal, 'refusal': refusal,
            'mismatch': mismatch, 'parse_errors': list(dict.fromkeys(errors))}

def build_payload(path,text,prompt,tier):
 require(path in ('KF','KB','LF','LB') and isinstance(text,str) and bool(text.strip()),'REQUEST_INPUT')
 require(isinstance(prompt,str) and bool(prompt.strip()),'REQUEST_PROMPT')
 require(tier=='fast','UNAPPROVED_TIER')
 return dict(model=MODEL,reasoning={'effort':'none'},instructions=prompt,input=text,stream=True,store=False,max_output_tokens=4096,service_tier=tier)

def validate_result_metadata(r,requested_tier):
 errors=[];warnings=[];response=r.get('response');response=response if isinstance(response,dict) else {};usage=r.get('usage')
 if r.get('actual_model')!=MODEL:errors.append('ACTUAL_MODEL_MISMATCH')
 actual=r.get('actual_service_tier');normalized='fast' if actual in ('fast','priority') else actual
 r['normalized_service_tier']=normalized;r['requested_service_tier']=requested_tier
 r['tier_verified']=normalized==requested_tier
 if requested_tier=='default' and normalized!='default':errors.append('STANDARD_TIER_MISMATCH')
 if requested_tier=='fast' and normalized=='default':errors.append('FAST_DOWNGRADED_TO_DEFAULT')
 elif requested_tier=='fast' and normalized!='fast':errors.append('FAST_TIER_UNRECOGNIZED')
 for key in ('request_id','response_id'):
  if not isinstance(r.get(key),str) or not r[key].strip():errors.append(key.upper()+'_MISSING')
 effort=response.get('reasoning',{}).get('effort') if isinstance(response.get('reasoning'),dict) else None
 r['actual_reasoning_effort']=effort
 if effort is None:warnings.append('REASONING_EFFORT_NOT_REPORTED')
 elif effort!='none':errors.append('ACTUAL_EFFORT_MISMATCH')
 if not isinstance(usage,dict) or not all(type(usage.get(k)) is int and usage[k]>=0 for k in ('input_tokens','output_tokens','total_tokens')):errors.append('USAGE_INVALID')
 else:
  if usage['input_tokens']+usage['output_tokens']!=usage['total_tokens']:errors.append('USAGE_TOTAL_MISMATCH')
  for detail,key,total in [('input_tokens_details','cached_tokens','input_tokens'),('output_tokens_details','reasoning_tokens','output_tokens')]:
   details=usage.get(detail);value=details.get(key) if isinstance(details,dict) else None
   if details is not None and not isinstance(details,dict):errors.append('USAGE_DETAIL_TYPE_INVALID')
   r[key]=value
   if value is not None and (type(value) is not int or not 0<=value<=usage[total]):errors.append('USAGE_DETAIL_INVALID')
  if r.get('reasoning_tokens'):warnings.append('NONZERO_REASONING_TOKENS')
 if r.get('http_attempts')!=1:errors.append('HTTP_ATTEMPT_CONTRACT')
 if r.get('success'):
  keys=('t_first_text','t_first_displayable_text','t_response_done','t_display_extract_done');timings=[r.get(k) for k in keys]
  valid=lambda v:type(v) in (int,float) and math.isfinite(v) and v>=0
  if not all(valid(v) for v in timings):errors.append('REQUIRED_TIMING_INVALID')
  elif timings!=sorted(timings):errors.append('TIMING_ORDER_INVALID')
 r['unknown']=bool(r.get('exception') or r.get('http_status') is None or (r.get('http_status')==200 and r.get('terminal') is None))
 r['provider_parse_success']=bool(r.get('success'));r['metadata_errors']=errors;r['metadata_warnings']=warnings
 r['success']=bool(r.get('success')) and not errors and not r['unknown']
 if not r['success']:r['display_text']=None
 return r

BASELINE_SHA={'KF':'812804499856e31cd70bd4571d3791d3a2159f725b6f5f798069c78df1606194','KB':'4ecf671709652818bc0b432645210e8e498305b8fa8fb851eedcfd8dbed23300','LF':'b902a50dcaa0c19c4b2d3a0b26a7dc02c9dc0a8cc9a3d0536ff02f9605d8febd','LB':'0337f538b89bfb9ccbddc2d4737751cda319b8366ce0a66a070521d20fc9e92c'}
ORIGINAL_FILE_SHA='c9ebaca60b6c2290419cf6b819c07dad0392e76a307f20cc2c79401baa0ada4a'

def validate_sources(document):
 require(isinstance(document,dict) and isinstance(document.get('sources'),list),'SOURCE_SCHEMA');by={}
 for s in document['sources']:
  require(isinstance(s,dict) and isinstance(s.get('source'),str) and s['source'].strip(),'SOURCE_TEXT')
  require(isinstance(s.get('source_id'),str) and s['source_id'] not in by,'SOURCE_ID')
  require(s.get('direction') in ('KF','LF') and s.get('sha256')==sha(s['source'].encode()),'SOURCE_SHA_DIRECTION')
  require(s.get('split') in ('DISCOVERY','FINAL') and isinstance(s.get('event_cluster'),str) and s['event_cluster'],'SOURCE_SPLIT_CLUSTER')
  if s['split']=='FINAL':
   require(s.get('final_independence_verified') is True and s.get('used_for_candidate_development') is False,'FINAL_INDEPENDENCE')
   require(s.get('final_independence_scope') in ('campaign_internal','external_unexposed'),'FINAL_SCOPE')
   if s['final_independence_scope']=='external_unexposed':require(s.get('prior_exposure') is False,'EXTERNAL_FINAL_EXPOSED')
  by[s['source_id']]=s
 finals=[s for s in by.values() if s['split']=='FINAL'];discovery=[s for s in by.values() if s['split']=='DISCOVERY']
 require(not ({s['sha256'] for s in finals}&{s['sha256'] for s in discovery}),'FINAL_SOURCE_OVERLAP')
 require(not ({s['event_cluster'] for s in finals}&{s['event_cluster'] for s in discovery}),'FINAL_EVENT_OVERLAP')
 require(len({s['sha256'] for s in finals})==len(finals),'FINAL_DUPLICATE')
 for s in document.get('fixed_first_inputs',[]):
  require(isinstance(s,dict) and isinstance(s.get('input_id'),str) and s['input_id'] not in by and isinstance(s.get('display_text'),str) and s['display_text'].strip(),'FIXED_FIRST_ID_TEXT')
  require(s.get('sha256')==sha(s['display_text'].encode()) and s.get('route') in ('KB','LB'),'FIXED_FIRST_SHA_ROUTE')
  require(isinstance(s.get('origin_result_object'),str) and re.fullmatch('[0-9a-f]{64}',s.get('origin_result_sha256','')),'FIXED_FIRST_PROVENANCE')
  by[s['input_id']]=s
 return by

def validate_fixed_first(s,parent):
 require(isinstance(parent,dict) and back_input(parent)==s['display_text'],'FIXED_ORIGIN_FIRST')
 require(parent.get('actual_model')==MODEL and parent.get('path')==('KF' if s['route']=='KB' else 'LF'),'FIXED_ORIGIN_IDENTITY')
 require(parent.get('actual_service_tier') in ('fast','priority'),'FIXED_ORIGIN_TIER')
 require(parent.get('origin_file_sha256')==ORIGINAL_FILE_SHA and type(parent.get('record_number')) is int and 1<=parent['record_number']<=100,'FIXED_ORIGIN_RECORD')
 if 'record_number' in s:require(s['record_number']==parent['record_number'],'FIXED_ORIGIN_NUMBER')

def validate_prompts(prompts,freeze):
 require(set(prompts)=={'BASE','HLEX','HPROP','HBACK'},'PROMPT_CANDIDATES')
 require(set(freeze['prompt_sha256'])==set(prompts),'PROMPT_FREEZE_KEYS')
 for candidate,paths in prompts.items():
  required={'KF','KB','LF','LB'} if candidate=='BASE' else {'KB','LB'} if candidate=='HBACK' else {'KF','LF'}
  require(set(paths)==required and set(freeze['prompt_sha256'][candidate])==required,'PROMPT_PATHS')
  for path,text in paths.items():require(isinstance(text,str) and text and sha(text.encode())==freeze['prompt_sha256'][candidate][path],'PROMPT_SHA')
 for p,digest in BASELINE_SHA.items():require(sha(prompts['BASE'][p].encode())==digest,'BASELINE_PROMPT_CHANGED')
 require(all(prompts['HLEX'][p]!=prompts['HPROP'][p] and prompts['HLEX'][p]!=prompts['BASE'][p] and prompts['HPROP'][p]!=prompts['BASE'][p] for p in ('KF','LF')),'DUPLICATE_FIRST_MECHANISM')

def validate_configuration(config,prompts):
 require(isinstance(config,dict) and set(config)=={'KF','KB','LF','LB'},'CONFIG_FOUR_PATHS')
 for path,prompt_id in config.items():require(prompt_id in prompts and path in prompts[prompt_id],'CONFIG_PATH_PROMPT')

def validate_configuration_change(previous,selected,decision):
 changed={p for p in ('KF','KB','LF','LB') if previous[p]!=selected[p]}
 if changed:
  require(isinstance(decision.get('configuration_change_reason'),str) and decision['configuration_change_reason'].strip(),'FINAL_CONFIG_REASON')
  changes=decision.get('path_changes');require(isinstance(changes,dict) and set(changes)==changed,'FINAL_CONFIG_CHANGE_SET')
  for path in changed:
   item=changes[path];require(isinstance(item,dict) and item.get('from')==previous[path] and item.get('to')==selected[path] and isinstance(item.get('reason'),str) and item['reason'].strip(),'FINAL_CONFIG_CHANGE_DETAIL')
 else:require(not decision.get('path_changes'),'UNCHANGED_CONFIG_HAS_PATH_CHANGES')

def validate_plan(plan,sources,prompts):
 phase=plan['phase'];slots=plan['slots']
 require(plan['campaign']==CAMPAIGN and phase in PHASES and isinstance(slots,list) and len(slots)<=HARD_CAPS[phase],'PLAN_ID_CAP')
 require(len({t['slot'] for t in slots})==len(slots),'DUPLICATE_SLOT')
 if not slots:require(bool(plan.get('omitted_reason')),'EMPTY_PLAN_REASON')
 if phase in ('C','FINAL') and slots:validate_configuration(plan.get('selected_configuration'),prompts)
 by={};groups={}
 for i,t in enumerate(slots,1):
  require(t['slot']==f'{phase}-{i:03d}' and t['tier']=='fast','SLOT_SEQUENCE_TIER')
  path=t['path'];candidate=t['candidate'];prompt_id=t['prompt_id'];require(prompt_id in prompts and path in prompts[prompt_id],'PLAN_PATH_PROMPT')
  if phase=='B':
   require(path in ('KB','LB') and candidate in ('BASE','HBACK') and prompt_id==candidate and 'parent_first_id' not in t,'B_FIXED_ONLY')
   key=t['input_id'];require(key in sources and 'display_text' in sources[key] and sources[key]['route']==path,'B_INPUT')
  else:
   key=t['source_id'];require(key in sources and 'source' in sources[key],'SOURCE_ID_UNKNOWN');s=sources[key]
   require(s['split']==('FINAL' if phase=='FINAL' else 'DISCOVERY'),'WRONG_SOURCE_SPLIT')
   if path in ('KF','LF'):require(path==s['direction'] and 'parent_first_id' not in t,'FIRST_DIRECTION')
   else:
    parent=by.get(t.get('parent_first_id'));require(parent is not None,'BACK_PARENT_NOT_PRIOR')
    require(parent['path']==('KF' if path=='KB' else 'LF') and parent['source_id']==key and parent['candidate']==candidate,'BACK_PARENT_IDENTITY')
   if phase=='A':require(candidate in ('HLEX','HPROP') and prompt_id==(candidate if path in ('KF','LF') else 'BASE'),'A_CONSTANT_BASE_BACK')
   else:require(candidate in ('BASE','SELECTED') and prompt_id==('BASE' if candidate=='BASE' else plan['selected_configuration'][path]),'CONFIG_PROMPT_MISMATCH')
  groups.setdefault(key,[]).append(t);by[t['slot']]=t
 for direction in ('KF','LF'):
  cap={'A':12,'B':8,'C':16,'FINAL':8}[phase]
  require(sum((sources[k].get('direction')==direction if phase!='B' else sources[k]['route']==('KB' if direction=='KF' else 'LB')) for k in groups)<=cap,'DIRECTION_SOURCE_CAP')
 for key,group in groups.items():
  if phase=='B':require(len(group)==2 and {t['candidate'] for t in group}=={'BASE','HBACK'},'B_PAIRING')
  else:
   first=sources[key]['direction'];back='KB' if first=='KF' else 'LB';candidates={'HLEX','HPROP'} if phase=='A' else {'BASE','SELECTED'}
   require(len(group)==4 and {(t['candidate'],t['path']) for t in group}=={(c,p) for c in candidates for p in (first,back)},'FIRST_BACK_PAIRING')
 return by

def budget_guard(records,task):
 require(len(records)<APPROVED_TOTAL,'CAMPAIGN_CAP');require(task['slot'] not in {r['slot'] for r in records},'DUPLICATE_SLOT')
 phase=task['slot'].split('-')[0];require(phase in PHASES,'PHASE')
 require(sum(r['stage']==phase for r in records)<HARD_CAPS[phase],'STAGE_CAP')
 for i,r in enumerate(records,1):require(r['campaign']==CAMPAIGN and r['model']==MODEL and r['ordinal']==i,'FOREIGN_LEDGER')
 return {'campaign':CAMPAIGN,'model':MODEL,'ordinal':len(records)+1,'slot':task['slot'],'stage':phase,'state':'RESERVED_TRANSMISSION_UNKNOWN'}
