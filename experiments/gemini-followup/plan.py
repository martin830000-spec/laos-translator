"""Deterministic counterbalancing and same-FIRST dependency schedules."""
from campaign import ID
def pairs(cases,profiles,prefix,context):
 tasks=[]
 for i,case in enumerate(cases):
  variants=profiles[i%len(profiles):]+profiles[:i%len(profiles)]
  for profile in variants:
   first=len(tasks)+1
   tasks.append(dict(slot=first,case_id=case['id'],side=case['side'],stage='first',profile=profile,input=case['source']))
   tasks.append(dict(slot=len(tasks)+1,case_id=case['id'],side=case['side'],stage='back',profile=profile,depends_on=first))
 return dict(campaign_id=ID,phase=prefix,prior_new_attempts=0,recommended_only=True,context=context,tasks=tasks)
def fixed_backs(cases,profiles=('31C','38P')):
 tasks=[];ordinal={'K':0,'L':0}
 for case in cases:
  i=ordinal[case['side']];ordinal[case['side']]+=1
  variants=list(profiles);shift=i%len(variants);variants=variants[shift:]+variants[:shift]
  for v in variants:tasks.append(dict(slot=len(tasks)+1,case_id=case['id'],side=case['side'],stage='back',profile=v,depends_on=None,fixed_first=case['fixed_first']))
 return dict(campaign_id=ID,phase='P3_FIXED_BACK',prior_new_attempts=0,recommended_only=True,tasks=tasks)
