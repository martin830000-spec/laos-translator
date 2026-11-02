"""Actual runner timings only, never mobile paint or invented token counts."""
import statistics,datetime
def distribution(xs):
 xs=sorted(xs)
 if not xs:return {'n':0}
 p=(len(xs)-1)*.95;i=int(p);p95=xs[i]+(xs[min(i+1,len(xs)-1)]-xs[i])*(p-i)
 return dict(n=len(xs),mean_ms=statistics.mean(xs),median_ms=statistics.median(xs),p95_ms=p95,max_ms=max(xs))
def summarize(r):
 xs=[x for x in r['slots']if x.get('attempted')];by={x['slot']:x for x in xs}
 success=sum(x['status']=='SUCCESS'for x in xs)
 out=dict(attempts=r['attempts'],success=success,failed=len(xs)-success,failure_rate=(len(xs)-success)/len(xs)if xs else None,skipped=sum(not x.get('attempted')for x in r['slots']),metrics={})
 for v in sorted({x['profile']for x in xs}):
  for side in ['K','L']:
   a=[x for x in xs if x['profile']==v and x['side']==side];pairs=[];pair_cost=[];pair_unknown=0
   for x in a:
    if x['stage']=='back'and x['status']=='SUCCESS'and x.get('depends_on')is not None:
     first=by[x['depends_on']]
     if first['status']=='SUCCESS':
      pairs.append((datetime.datetime.fromisoformat(x['sent_at_utc'])-datetime.datetime.fromisoformat(first['sent_at_utc'])).total_seconds()*1000+x['ready_ms'])
      if x.get('estimated_usd')is None or first.get('estimated_usd')is None:pair_unknown+=1
      else:pair_cost.append(x['estimated_usd']+first['estimated_usd'])
   if a:
    known=sum(x.get('estimated_usd')or 0 for x in a);unknown=sum(x.get('estimated_usd')is None for x in a)
    out['metrics'][v+'/'+side]={'first_api':distribution([x['api_ms']for x in a if x['stage']=='first'and x['status']=='SUCCESS']),'first_ready':distribution([x['ready_ms']for x in a if x['stage']=='first'and x['status']=='SUCCESS']),'back_api':distribution([x['api_ms']for x in a if x['stage']=='back'and x['status']=='SUCCESS']),'back_ready':distribution([x['ready_ms']for x in a if x['stage']=='back'and x['status']=='SUCCESS']),'roundtrip_wall':distribution(pairs),'usage':[x.get('usage')for x in a],'cost_known_usd':known,'cost_unknown_rows':unknown,'successful_pairs':len(pairs),'successful_pair_cost_unknown':pair_unknown,'translation_cost_per_1000_successful_pairs_usd':1000*statistics.mean(pair_cost)if pair_cost and not pair_unknown else None,'amortized_cost_per_1000_successful_pairs_usd':1000*known/len(pairs)if pairs and not unknown else None,'billing_verified':False}
 return out
