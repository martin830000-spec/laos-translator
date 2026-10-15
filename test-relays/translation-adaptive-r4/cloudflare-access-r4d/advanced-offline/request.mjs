// Offline TEST-only Cloud Translation Advanced v3 request builder.
// Never contains authentication tokens, personal test sources, or side effects.
const PROJECT = /^[a-z][a-z0-9-]{3,62}$/;
const LOCATION = /^[a-z][a-z0-9-]*$/;
const ID = /^[a-zA-Z][a-zA-Z0-9_-]{0,62}$/;
function requireValid(condition, label) { if (!condition) throw new Error(label); }
export function makeGoogleAdvancedRequest({project, location='us-central1', engine, source, target, text, glossaryId}) {
  requireValid(typeof project==='string' && PROJECT.test(project), 'INVALID_PROJECT');
  requireValid(typeof location==='string' && LOCATION.test(location), 'INVALID_LOCATION');
  requireValid(['nmt_glossary','llm_contextual_glossary'].includes(engine), 'INVALID_ENGINE');
  requireValid(['ko','lo'].includes(source) && ['ko','lo'].includes(target) && source!==target, 'INVALID_LANGUAGE_PAIR');
  requireValid(typeof text==='string' && text.trim() && [...text].length<=1000, 'INVALID_TEXT');
  requireValid(typeof glossaryId==='string' && ID.test(glossaryId), 'INVALID_GLOSSARY_ID');
  const resource=`projects/${project}/locations/${location}`;
  const body={contents:[text],mimeType:'text/plain',sourceLanguageCode:source,targetLanguageCode:target,
    model:`${resource}/models/general/${engine==='nmt_glossary'?'nmt':'translation-llm'}`,
    glossaryConfig:{glossary:`${resource}/glossaries/${glossaryId}`,ignoreCase:false,
      ...(engine==='llm_contextual_glossary'?{contextualTranslationEnabled:true}:{})}};
  return {url:`https://translation.googleapis.com/v3/${resource}:translateText`,body};
}
export function readGoogleAdvancedTranslation(response) {
  // A glossary-applied response must use glossaryTranslations, not fallback to raw translations.
  const translation=response?.glossaryTranslations?.[0]?.translatedText;
  if(typeof translation!=='string'||!translation.trim())throw new Error('GLOSSARY_TRANSLATION_MISSING');
  return translation;
}
export function classifyAdaptiveBackend429({error,reason,retryAfterMs}={}) {
  if(error!=='BACKEND_RATE_LIMIT')return 'NOT_BACKEND_RATE_LIMIT';
  if(reason==='LOCAL_RATE_LIMIT' && Number.isInteger(retryAfterMs)&&retryAfterMs>0)return `LOCAL_INTERVAL_${retryAfterMs}MS`;
  if(reason==='LOCAL_DAILY_LIMIT')return 'LOCAL_DAILY_QUOTA';
  return 'UPSTREAM_429_REASON_NOT_EXPOSED';
}
