'use strict';
// One selectable execution = one task attempt, including legacy multi-task batches.
let navigationData=null;
const navChoice={campaign:'',model:'',configuration:'',task:''};
const executionKey=r=>String(r.run)+':'+String(r.task_index);
const executionState=s=>ui(({not_started:'Non démarrée',authoring:'Construction',assessment:'Évaluation',verification:'Vérification',completed:'Terminée',interrupted:'Interrompue',missing:'Manquante'})[s]||s||'Inconnu');
function campaignName(id){return navigationData?.campaigns?.find(c=>c.id===id)?.name||ui('Hors campagne déclarée');}
function navigationSelect(id, values, current){
 const el=$(id);if(!el)return current;
 const selected=values.some(v=>v[0]===current)?current:values[0]?.[0]||'';
 el.innerHTML=values.map(([value,label])=>`<option value="${esc(value)}" ${value===selected?'selected':''}>${esc(label)}</option>`).join('');
 return selected;
}
function renderNavigation(preferCurrent=false){
 if(!navigationData||!$('campaign-select'))return;
 let rows=navigationData.records;
 const current=preferCurrent?rows.find(r=>r.run===runIndex&&r.task_index===taskIndex):null;
 if(current)Object.assign(navChoice,{campaign:current.campaign_id||'',model:current.context.model||'',configuration:current.configuration,task:current.case});
 const choices=(key,label)=>[...new Set(rows.map(key))].map(v=>[v,label(v)]);
 navChoice.campaign=navigationSelect('campaign-select',choices(r=>r.campaign_id||'',campaignName),navChoice.campaign);
 rows=rows.filter(r=>(r.campaign_id||'')===navChoice.campaign);
 navChoice.model=navigationSelect('model-select',choices(r=>r.context.model||'',v=>v||ui('Inconnu')),navChoice.model);
 rows=rows.filter(r=>(r.context.model||'')===navChoice.model);
 navChoice.configuration=navigationSelect('configuration-select',choices(r=>r.configuration,v=>'Configuration '+v),navChoice.configuration);
 rows=rows.filter(r=>r.configuration===navChoice.configuration);
 navChoice.task=navigationSelect('case-select',choices(r=>r.case,v=>v),navChoice.task);
 rows=rows.filter(r=>r.case===navChoice.task);
 const key=navigationSelect('run-select',rows.map(r=>[executionKey(r),`${r.repeat!=null?ui('Répétition')+' '+r.repeat:r.run_name} · ${executionState(r.lifecycle)}`]),String(runIndex)+':'+String(taskIndex));
 const selected=rows.find(r=>executionKey(r)===key);
 if(selected){runIndex=selected.run;taskIndex=selected.task_index;}
 for(const id of ['campaign-select','model-select','configuration-select','case-select','run-select'])if($(id))$(id).disabled=view==='campaign';
}
async function refreshNavigation(){
 const response=await fetch('/api/campaign',{cache:'no-store'});
 if(!response.ok)throw Error(ui('Liste des exécutions indisponible'));
 navigationData=await response.json();
 renderNavigation(true);
}
function navigationChanged(e){
 if(!navigationData)return false;
 const fields={'campaign-select':'campaign','model-select':'model','configuration-select':'configuration','case-select':'task'};
 if(fields[e.target.id])navChoice[fields[e.target.id]]=e.target.value;
 else if(e.target.id==='run-select'){
  const r=navigationData.records.find(r=>executionKey(r)===e.target.value);
  if(r){runIndex=r.run;taskIndex=r.task_index;}
 }else return false;
 renderNavigation(false);previous='';replayIndex=0;refresh(true);return true;
}
function executionBanner(){
 const row=data?.executions?.find(r=>r.task_index===taskIndex);
 if(!row)return '';
 const study=data.campaigns?.find(c=>c.id===row.campaign_id);
 return `<section class="notice"><strong>${esc(ui('Exécution'))}</strong> · ${esc(row.campaign_name||ui('Hors campagne déclarée'))} → ${esc(row.context.model)} → ${esc(row.configuration)} → ${esc(row.case)}${row.repeat!=null?' → '+esc(ui('Répétition'))+' '+esc(row.repeat):''}
 <p>${esc(executionState(row.lifecycle))}${study?' · '+esc(ui('État de la campagne'))+': '+esc(campaignState(study.state)):''}</p>
 ${study?.error?`<p class="warning">${esc(study.error)}</p>`:''}
 ${row.batch_kind==='legacy_batch'?`<p>${esc(ui('Lot historique : chaque tâche correspond à une exécution indépendante.'))}</p>`:''}
 ${details('execution-identity',ui('Identités de l’exécution'),{campaign_id:row.campaign_id,execution_id:row.execution_id,identity_source:row.identity_source,task:row.case,repeat:row.repeat,declared_reference_scope:row.declared_reference_scope,observed_reference_scope:row.observed_reference_scope,membership_conflicts:row.membership_conflicts})}</section>`;
}
