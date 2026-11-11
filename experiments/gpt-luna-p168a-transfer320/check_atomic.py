import runner as r
from google.api_core.exceptions import PreconditionFailed
s=r.Store();c=r.load_control();assert c['mode']=='EXECUTE';name='checks/atomic-'+r.os.environ['GITHUB_RUN_ID']+'.json';data=r.canon({'offline_contract_probe':True,'generation_calls':0});s.create(name,data)
try:s.create(name,b'conflict')
except PreconditionFailed:pass
else:raise AssertionError('ATOMIC_DUPLICATE_ACCEPTED')
assert s.get(name)==data
assert len(r.reservations(s))==c['prior_reserved']
print('ATOMIC_CREATE_DUPLICATE_DENIAL_READBACK_PASS generation_calls=0')
