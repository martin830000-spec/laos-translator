import runner as r
s=r.Store();c=r.load_control()
assert not c['enabled'] and c['max_new']==0
rs=r.reservations(s);by=r.totals(s,rs)
state=r.json.loads(s.get('states/H4-finished.json'))
assert len(rs)==536==state['reserved_total'] and by==state['models']
assert by['gpt-6-luna']['reserved']==280 and by['gpt-6.1-terra']['reserved']==256
assert all(v['failed']==v['unknown']==0 for v in by.values())
assert state['finished'] and not state['enabled'] and state['max_new']==0
assert s.get('locks/H4.RELEASED.json') is not None
assert s.get('locks/FINAL.json',True) is None and s.get('locks/after-536.json',True) is None
print(r.json.dumps(dict(reserved=len(rs),models=by,final_lock_absent=True,prior_released=True,generation_calls=0)))
