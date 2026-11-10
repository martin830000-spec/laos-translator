import runner as r
s=r.Store();split=r.json.loads(s.get('preparation/SOURCE_SPLIT.json'));rows=[x for x in split['selected'] if x['stage']=='FINAL'];schedule=[]
for i,x in enumerate(rows):
 if x['side']=='K':schedule.append({'source_id':x['id'],'arm':'SHARED_BASE','paths':['KF','KB']})
 else:
  for arm in (['BASE','CANDIDATE'] if i%2==0 else ['CANDIDATE','BASE']):schedule.append({'source_id':x['id'],'arm':arm,'paths':['LF','LB']})
obj={'campaign':r.CAMPAIGN,'rows':schedule,'candidate_prompt':'to_be_frozen_after_C_before_D','source_split_sha256':r.sha(r.canon(split))}
expected=r.json.loads((r.HERE/'FINAL_SCHEDULE_HASH.json').read_bytes())['sha256'];assert r.sha(r.canon(obj))==expected
s.put('preparation/FINAL_SCHEDULE.json',r.canon(obj));print('FINAL_SCHEDULE_FROZEN_SHA256='+expected)
