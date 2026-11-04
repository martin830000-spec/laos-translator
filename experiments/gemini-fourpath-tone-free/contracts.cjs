'use strict';
// Research only. No provider transport or app routing.
const inherited=require('../gemini31-first-free/contracts.cjs');
const assets=require('../gemini-assets/contracts.cjs');
const APPROVAL=Object.freeze({authorized:false,execution_enabled:false,max_new:0,actual_consumed:0});
const REMOVED=' The message is from a wife to their husband; explicit grammatical people override this setting.';
function buildBack(path,variant,displayedFIRST){
 if(arguments.length!==3||!['KB','LB'].includes(path)||typeof displayedFIRST!=='string'||!displayedFIRST.trim())throw TypeError('FIRST_ONLY');
 if(variant==='FROZEN')return inherited.buildBack(path,displayedFIRST);
 if(path!=='LB'||variant!=='LEGACY31U_ROLE_NEUTRAL')throw TypeError('CANDIDATE_SCOPE');
 const q=assets.build('LB','M31','LEGACY31U',displayedFIRST);
 const p=q.payload.system_instruction.parts[0],n=p.text.split(REMOVED).length-1;
 if(n!==1)throw Error('FROZEN_PROMPT_DRIFT');
 p.text=p.text.replace(REMOVED,'');
 return {...q,version:'TONE_FREE_20261105_R1/LB/LEGACY31U_ROLE_NEUTRAL'};
}
function inspectBack(raw,path,variant,first){
 if(arguments.length!==4||!['KB','LB'].includes(path)||!['FROZEN','LEGACY31U_ROLE_NEUTRAL'].includes(variant)||(variant!=='FROZEN'&&path!=='LB'))throw TypeError('INSPECT_SCOPE');
 return inherited.inspectBack(raw,path,first);
}
function assess({meaning,tone,naturalness}){
 if(!['P0','P1','P2','REVIEW'].includes(meaning)||![tone,naturalness].every(x=>['PASS','MINOR','ISSUE','REVIEW'].includes(x)))throw TypeError('AXES');
 // REVIEW is uncertainty, never coerced to a failure. MINOR passes.
 return {meaning,tone,naturalness,known_important_issue:['P0','P1'].includes(meaning)||[tone,naturalness].includes('ISSUE'),uncertain:[meaning,tone,naturalness].includes('REVIEW'),acceptable:meaning==='P2'&&[tone,naturalness].every(x=>['PASS','MINOR'].includes(x))};
}
function run(){throw Error('UNAPPROVED_ZERO_CALLS_NO_TRANSPORT');}
module.exports={APPROVAL,REMOVED,buildBack,inspectBack,assess,run,buildFirst:inherited.buildFirst,inspectFirst:inherited.inspectFirst,buildControl:inherited.buildControl};
