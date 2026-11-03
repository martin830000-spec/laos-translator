'use strict';
// Offline proposal graph. No HTTP sender and no execution entry point.
const {ID,digest}=require('./contracts.cjs');
const CAPS={DISCOVERY_A:40,BACK_REFINEMENT_B:24,FROZEN_INDEPENDENT_FINAL:64};
const APPROVAL={campaign_id:ID,authorized:false,execution_enabled:false,user_approved_limit:0,maximum_new_attempts:0,actual_consumed:0,unused_approved:0,proposed_limit:128,status:'PROPOSAL_ONLY_LOCKED',automatic_retries:0,judge_calls:0};
function graph(phase,cases){if(!Object.hasOwn(CAPS,phase))throw new Error('PHASE');const count={DISCOVERY_A:10,BACK_REFINEMENT_B:8,FROZEN_INDEPENDENT_FINAL:16}[phase];if(cases.length!==count||cases.filter(c=>c.side==='K').length!==count/2||cases.filter(c=>c.side==='L').length!==count/2||new Set(cases.map(c=>c.id)).size!==count)throw new Error('BALANCED_UNIQUE_CASES');let tasks=[];
 const add=(c,arm,stage,depends_on,profile)=>{const t={slot:tasks.length+1,case_id:c.id,side:c.side,arm,stage,profile};if(depends_on)t.depends_on=depends_on;tasks.push(t);return t.slot;};
 for(const c of cases){const profile=c.side==='K'?'K_NEUTRAL_31':'L_STANCE_38';
  if(phase==='BACK_REFINEMENT_B'){const f=add(c,'NEW','first',null,profile);add(c,'BACK_SERVICE','back',f,'SERVICE_BACK');add(c,'BACK_COMPACT','back',f,'COMPACT_BACK');}
  else for(const arm of ['SERVICE','NEW']){const f=add(c,arm,'first',null,arm==='SERVICE'?'SERVICE_FIRST':profile);add(c,arm,'back',f,phase==='DISCOVERY_A'||arm==='SERVICE'?'SERVICE_BACK':'COMPACT_BACK');}
 }
 return {campaign_id:ID,phase,proposed_only:true,data_bound:false,cap:CAPS[phase],tasks};
}
function validate(g){if(g.campaign_id!==ID||g.proposed_only!==true||g.data_bound!==false||g.cap!==CAPS[g.phase]||g.tasks.length!==g.cap)throw new Error('PROPOSAL_CONTRACT');const by=new Map();for(const t of g.tasks){if(by.has(t.slot)||!['K','L'].includes(t.side))throw new Error('SLOT');if(t.stage==='back'){const d=by.get(t.depends_on);if(!d||d.stage!=='first'||d.case_id!==t.case_id||d.side!==t.side||Object.keys(t).some(k=>['input','source','context','original','answer','grade','history'].includes(k)))throw new Error('FIRST_ONLY_DEPENDENCY');if(g.phase!=='BACK_REFINEMENT_B'&&d.arm!==t.arm)throw new Error('ARM');}else if(t.stage!=='first')throw new Error('STAGE');by.set(t.slot,t);}if(g.phase==='BACK_REFINEMENT_B'){for(const f of g.tasks.filter(t=>t.stage==='first')){const b=g.tasks.filter(t=>t.depends_on===f.slot);if(b.length!==2||new Set(b.map(t=>t.profile)).size!==2)throw new Error('SAME_FIRST_PAIR_REQUIRED');}}return true;}
function forbidPaidExecution(approval=APPROVAL){if(approval.campaign_id!==ID||approval.authorized!==true||approval.execution_enabled!==true||approval.user_approved_limit<=0)throw new Error('NEW_EXPLICIT_APPROVAL_REQUIRED');throw new Error('PAID_TRANSPORT_NOT_INSTALLED_IN_FREE_PHASE');}
function normalizedHash(text){return digest(text.normalize('NFKC').toLowerCase().replace(/[\p{P}\p{Z}\s]/gu,''));}
function excludeExposed(cases,history){const ids=new Set(history.map(c=>c.id)),hashes=new Set(history.map(c=>c.hash)),clusters=new Set(history.map(c=>c.cluster).filter(Boolean));return cases.filter(c=>!ids.has(c.id)&&!hashes.has(c.hash)&&(!c.cluster||!clusters.has(c.cluster)));}
function freeze(snapshot,sourceSelectionHash){return {campaign_id:ID,contract_sha256:digest(snapshot),selection_metadata_sha256:sourceSelectionHash,final_source_opened:false,status:'DEVELOPMENT_BASELINE_ONLY_FINAL_REFREEZE_AFTER_B_REQUIRED'};}
module.exports={CAPS,APPROVAL,graph,validate,forbidPaidExecution,normalizedHash,excludeExposed,freeze};
