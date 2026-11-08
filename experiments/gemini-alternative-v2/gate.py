"""Offline V2 approval validator. This module cannot send model requests."""
CAMPAIGNS={m:f'GEMINI{m}_ALTERNATIVE_V2_20261108' for m in ('35','36')}
def validate(model,approval,config,ledger,backup):
    if model not in CAMPAIGNS:raise ValueError('MODEL_NOT_APPROVED')
    if approval['campaign']!=CAMPAIGNS[model] or config['campaign']!=CAMPAIGNS[model]:raise ValueError('CAMPAIGN_MISMATCH')
    if approval['authorized_max']!=500:raise ValueError('CAP_CHANGED')
    actual=sum(x.get('counted_attempt',False) for x in ledger)
    if config['cumulative_actual']!=actual:raise ValueError('LEDGER_MISMATCH')
    n=config['max_new']
    if type(n) is not int or n<0 or actual+n>500:raise ValueError('CAP_EXCEEDED')
    if not config['enabled']:
        if n!=0:raise ValueError('LOCK_INCONSISTENT')
        return 'LOCKED'
    if n==0:raise ValueError('EMPTY_STAGE')
    if not backup.get('end_to_end_plaintext_verified'):raise ValueError('BACKUP_GATE_NOT_PASSED')
    if not backup.get('owner_only') or not backup.get('remote_sha256_match'):raise ValueError('BACKUP_UNSAFE')
    if any(x.get('unknown_after_send') for x in ledger):raise ValueError('UNRESOLVED_SEND')
    return 'GATE_VALID_ONLY_NOT_EXECUTION_AUTHORIZATION'
