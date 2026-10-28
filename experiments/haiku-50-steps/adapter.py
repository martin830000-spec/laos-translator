"""TEST S47 request adapter. Builds payload and extracts explicit translation field; makes no API calls or retries."""

import json

from pathlib import Path

BASE = 'Translate the supplied message faithfully between Korean and Lao. Keep people, actions, objects, negation, time, quantities, symptoms, emotion and speech act unchanged. Do not add gender, ownership, names or facts that are absent. Preserve ambiguity rather than guessing. Return only the requested translation.'

BACK = 'This is independent backtranslation. Translate only the visible message supplied now. You do not know any earlier original. Preserve its errors and extraneous content; do not repair or reconstruct it.'

SCHEMA = {'type': 'object', 'properties': {'translation': {'type': 'string'}}, 'required': ['translation'], 'additionalProperties': False}

def payload(text, side, stage, v):
    src, dst = ('Korean', 'Lao') if (side == 'K') == (stage == 'first') else ('Lao', 'Korean')
    if v.get('legacy_prompt'):
        return {'model': 'claude-haiku-5-5', 'max_tokens': 512, 'thinking': {'type': 'disabled'}, 'output_config': {'effort': 'low'}, 'messages': [{'role': 'user', 'content': v['legacy_prompt'] + f'\nTranslate from {src} to {dst}:\n<source>\n{text}\n</source>'}]}
    instruction = (v.get('back_prompt', v.get('prompt', BASE)) if stage == 'back' else v.get('prompt', BASE)) + (' ' + BACK if stage == 'back' else '')
    if v.get('notes') and (not v.get('notes_in_user')):
        instruction += ' ' + v['notes']
    if v.get('back_notes') and stage == 'back':
        instruction += ' ' + v['back_notes']
    if v.get('sense_groups'):
        instruction += ' ' + ' '.join((g['note'] for g in v['sense_groups'] if any((t in text for t in g['triggers']))))
    q = {'model': 'claude-haiku-5-5', 'max_tokens': v.get('max_tokens', 2048), 'thinking': {'type': v.get('thinking', 'disabled')}, 'output_config': {'effort': v.get('effort', 'low')}, 'system': instruction, 'messages': [{'role': 'user', 'content': f'Translate {src} to {dst}.\n<message>\n{text}\n</message>'}]}
    if v.get('notes_in_user'):
        q['messages'][0]['content'] = 'Terminology instructions: ' + v.get('notes', '') + '\n' + q['messages'][0]['content']
    if v.get('schema'):
        schema = json.loads(json.dumps(SCHEMA))
        if v['schema'] == 'ledger':
            schema['properties'] = {'source_facts': {'type': 'array', 'items': {'type': 'string'}, 'description': 'Brief literal facts grounded only in the supplied text; retain uncertainty.'}, **schema['properties']}
            schema['required'] = ['source_facts', 'translation']
        if v['schema'] == 'roles':
            schema['properties'] = {'source_people': {'type': 'array', 'items': {'type': 'string'}, 'description': 'Only people explicitly in the supplied source; retain unspecified identity.'}, 'source_events': {'type': 'array', 'items': {'type': 'string'}, 'description': 'Literal actor-action-object facts with polarity and tense from the visible source.'}, **schema['properties']}
            schema['required'] = ['source_people', 'source_events', 'translation']
        if v['schema'] == 'evidence':
            schema['properties'] = {'source_spans': {'type': 'array', 'items': {'type': 'string'}, 'description': 'Verbatim short quotations from the supplied source covering people, relation, polarity, symptoms and key facts. Copy original spans exactly; do not infer attributes or translate these quotations.'}, **schema['properties']}
            schema['required'] = ['source_spans', 'translation']
        q['output_config']['format'] = {'type': 'json_schema', 'schema': schema}
        if v.get('tool_output'):
            del q['output_config']['format']
            q['tools'] = [{'name': 'emit_translation', 'description': 'Return the source-grounded translation without executing any external action.', 'strict': True, 'input_schema': schema}]
            q['tool_choice'] = {'type': 'tool', 'name': 'emit_translation'}
    return q

CANDIDATE = json.loads((Path(__file__).parent / "claude50-candidate.json").read_text(encoding="utf-8"))["candidate"]

def build_request(text, side, stage):
    if side not in ("K", "L") or stage not in ("first", "back"):
        raise ValueError("side K/L; stage first/back")
    return payload(text, side, stage, CANDIDATE)

def extract_translation(response):
    if response.get("stop_reason") != "end_turn":
        raise ValueError("Incomplete response; no automatic retry")
    raw = "".join(b.get("text", "") for b in response.get("content", []) if b.get("type") == "text")
    obj = json.loads(raw)
    text = obj.get("translation")
    if not isinstance(text, str) or not text.strip():
        raise ValueError("Missing translation; no automatic repair")
    return text

