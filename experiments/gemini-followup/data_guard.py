"""Metadata-only reservation. Opening FINAL requires verified frozen files and reviews."""
import hashlib,json
from pathlib import Path
def sha_file(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def verify_freeze(freeze,code_root,winner_path,review_root):
 if not freeze or freeze.get('candidate_frozen')is not True or freeze.get('P1_P4_review_complete')is not True:raise PermissionError('FINAL_STILL_SEALED')
 for key,root in [('code_files',code_root),('review_files',review_root)]:
  entries=freeze.get(key,{})
  if not entries or (key=='review_files'and set(entries)!={'P1.json','P2.json','P3.json','P4.json'}):raise PermissionError('MISSING_FREEZE_EVIDENCE')
  for name,expected in entries.items():
   base=Path(root).resolve();p=(base/name).resolve()
   if not p.is_relative_to(base)or sha_file(p)!=expected:raise PermissionError('FREEZE_CHANGED')
 if sha_file(winner_path)!=freeze.get('winner_config_sha256'):raise PermissionError('WINNER_CHANGED')
 return True
def pick_final(metadata,k=8,l=8):
 groups={}
 for x in metadata:groups.setdefault(x['cluster'],[]).append(x)
 keys=sorted(groups)
 def solve(i,nk,nl,out):
  if nk==k and nl==l:return out
  if i==len(keys)or len(keys)-i<k+l-nk-nl:return None
  for side,allowed in [('K',nk<k),('L',nl<l)]:
   opts=[x for x in groups[keys[i]]if x['side']==side]
   if allowed and opts:
    a=solve(i+1,nk+(side=='K'),nl+(side=='L'),out+[sorted(opts,key=lambda x:x['source_sha256'])[0]])
    if a:return a
  return solve(i+1,nk,nl,out)
 out=solve(0,0,0,[])
 if not out:raise ValueError('not enough unexposed independent clusters')
 return out
def bind_final(rows,metadata,freeze,*,code_root=None,winner_path=None,review_root=None):
 if not freeze or freeze.get('candidate_frozen')is not True:raise PermissionError('FINAL_STILL_SEALED')
 if None in (code_root,winner_path,review_root):raise PermissionError('FREEZE_PATHS_REQUIRED')
 verify_freeze(freeze,code_root,winner_path,review_root)
 chosen=pick_final(metadata);lookup={x['id']:x for x in rows};out=[]
 for m in chosen:
  r=lookup[m['id']]
  if hashlib.sha256(r['source'].encode()).hexdigest()!=m['source_sha256']:raise PermissionError('SOURCE_CHANGED')
  out.append(r)
 return out
