"""Validate a future GET models metadata response, no network or silent aliasing."""
EXPECTED={'gemini-3.1-flash-lite':{'minimal','low','medium','high'},'gemini-3.5-flash-lite':{'minimal','low','medium','high'},'gemini-3.8-flash':{'low','medium','high'}}
def validate_metadata(model,thinking,max_output,metadata):
 if model not in EXPECTED or thinking not in EXPECTED[model]:raise ValueError('UNSUPPORTED_MODEL_THINKING')
 if metadata.get('name')!='models/'+model:raise ValueError('MODEL_ALIAS_OR_UNAVAILABLE')
 if 'generateContent'not in metadata.get('supportedGenerationMethods',[]):raise ValueError('METHOD_UNAVAILABLE')
 if type(metadata.get('outputTokenLimit'))is not int or max_output>metadata['outputTokenLimit']:raise ValueError('OUTPUT_LIMIT')
 return True
