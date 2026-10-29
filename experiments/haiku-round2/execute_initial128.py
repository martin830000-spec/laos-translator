"""Approved initial128 only. No retries. Run behind persistent GitHub tag lock."""
import json, os, urllib.request
from pathlib import Path
import runner

ROOT=Path(__file__).parent
TITLE='HAIKU_ROUND2_INITIAL128_APPROVED_20261029'
def main():
    runner.check(os.getenv('GITHUB_RUN_ATTEMPT')=='1','rerun forbidden')
    runner.check(os.getenv('ROUND2_APPROVAL')==TITLE,'wrong approval scope')
    event=json.loads(Path(os.environ['GITHUB_EVENT_PATH']).read_text())
    runner.check(event['issue']['title']==TITLE and event['issue']['user']['login']=='martin830000-spec','wrong trigger')
    variants=json.loads((ROOT/'candidates.json').read_text(encoding='utf-8'))
    cases=json.loads((ROOT/'development.json').read_text(encoding='utf-8'))
    freeze=json.loads((ROOT/'candidate-freeze.json').read_text(encoding='utf-8'))
    runner.check(runner.digest(variants)==freeze['sha256'],'frozen candidates changed')
    runner.check(len(cases)==16 and [v['id'] for v in variants]==['S38','S47','R2A','R2B'],'scope changed')
    runner.validate(cases,variants)
    out=ROOT/'paid-output';out.mkdir(exist_ok=True)
    # Read-only authenticated metadata request; not a generation request.
    req=urllib.request.Request('https://api.anthropic.com/v1/models/claude-haiku-5-5',headers={
        'x-api-key':os.environ['ANTHROPIC_API_KEY'],'anthropic-version':'2023-06-01'})
    with urllib.request.urlopen(req,timeout=30) as f: metadata=json.loads(f.read())
    (out/'model-metadata.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2),encoding='utf-8')
    runner.check(metadata.get('id')=='claude-haiku-5-5','unexpected model')
    approval={'approved':True,'user_approval_reference':'2026-10-29 user: 승인한다; preceding request explicitly first comparison maximum128',
        'batch':'initial128','max_calls':128,'campaign_max_calls':800,'max_steps':50,
        'candidate_sha256':runner.digest(variants),'cases_sha256':runner.digest(cases),'model_verified':True,
        'github_sha':os.environ.get('GITHUB_SHA'),'github_run_id':os.environ.get('GITHUB_RUN_ID'),
        'price_source':'https://platform.claude.com/docs/en/about-claude/pricing',
        'price_verified_date':'2026-10-29','input_per_million_usd':0.10,'output_per_million_usd':0.50}
    (out/'approval-used.json').write_text(json.dumps(approval,ensure_ascii=False,indent=2),encoding='utf-8')
    # Runtime approval is confined to this checkout; committed default stays disabled.
    (ROOT/'approval.json').write_text(json.dumps(approval),encoding='utf-8')
    print('Metadata verified; initial128 authorized; retries0',flush=True)
    runner.paid_main()
    print('Initial128 complete; HOLD for semantic review; no further batch',flush=True)
if __name__=='__main__':main()

