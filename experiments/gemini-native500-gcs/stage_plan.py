"""Deterministic private plan staging. Public configuration contains hashes only."""
import hashlib,json,pathlib,sys
import build_plans as b
HERE=pathlib.Path(__file__).resolve().parent
def build(cfg,raw):
    assert hashlib.sha256(raw).hexdigest()==cfg['sample_sha256']
    rows=json.loads(raw); byhash={r['source_sha256']:r for r in rows}
    selected=[byhash[h] for h in cfg['selected_source_sha256']]
    if 'selected_record_sha256' in cfg:
        identities={hashlib.sha256((str(r['id'])+'|'+r['source_sha256']).encode()).hexdigest():r for r in rows}
        selected=[identities[h] for h in cfg['selected_record_sha256']]
        assert [r['source_sha256'] for r in selected]==cfg['selected_source_sha256']
    assert len(selected)==len(set(r['source_sha256'] for r in selected))
    result={}
    for model,settings in cfg['models'].items():
        tasks=[]
        for i,row in enumerate(selected,1):
            variants=settings['variants'];offset=(i-1)%len(variants)
            order=variants[offset:]+variants[:offset]
            if 'R36' in order:
                order=[v for v in order if v!='R36'];order.insert(order.index('BASE')+1,'R36')
            base_first=None
            for v in order:
                if v=='R36':
                    tasks.append({'slot':b.make_slot(cfg['phase'].lower(),i,row['side'],v,'b'),'case_id':str(row['id']),'path':row['side']+'B','variant':v,'first_variant':'BASE','from_slot':base_first})
                else:
                    slot=b.add_pair(tasks,row,i,v,cfg['phase'].lower())
                    if v=='BASE':base_first=slot
        plan=b.make_plan(model,cfg['phase'],settings['prior_actual'],tasks,selected,b.EXPECTED_MANIFEST_SHA)
        b.validate_plan(plan,model)
        payload=(json.dumps(plan,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode()
        result[model]=(payload,hashlib.sha256(payload).hexdigest())
    return result
def main():
    from google.cloud import storage
    from google.api_core.exceptions import PreconditionFailed
    cfg=json.loads((HERE/'stage_config.json').read_text());bucket=storage.Client(project='gen-lang-client-0422436907').bucket(b.BUCKET)
    raw=bucket.blob(f'{b.PREFIX}/samples/20261107_R2/'+cfg['sample_file']).download_as_bytes(timeout=30)
    result=build(cfg,raw)
    for model,(payload,sha) in result.items():
        # Frozen prior plans must all be finished and their actual calls match prior_actual.
        prior=0
        for previous_sha in cfg['models'][model]['prior_plans']:
            finish=json.loads(bucket.blob(f'{b.PREFIX}/{model}/results/{previous_sha}/RUN_FINISHED.json').download_as_bytes(timeout=30))
            assert finish['status'] in ('DONE','DONE_WITH_FAILURES')
            prior+=finish['attempted']
        assert prior==cfg['models'][model]['prior_actual']
        blob=bucket.blob(f'{b.PREFIX}/{model}/plans/{sha}.json')
        try:blob.upload_from_string(payload,content_type='application/json',if_generation_match=0,timeout=30)
        except PreconditionFailed:pass
        assert blob.download_as_bytes(timeout=30)==payload
        print(json.dumps({'model':model,'plan_sha256':sha,'calls':len(json.loads(payload)['tasks']),'prior_actual':prior,'paid_calls':0}))
if __name__=='__main__':main()
