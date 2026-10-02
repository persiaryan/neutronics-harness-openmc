'use strict';
let campaignData=null, campaignBusy=false, campaignError='', campaignRead=null;
let cohortId='', campaignModel='', campaignTask='', drillConfig='', drillDomain='overall', drillCheck='', drillOutcome='all';
const campaignLabel=d=>d==='overall'?ui('Réussite complète'):d==='hard_gates'?ui('Contrôles obligatoires'):recordedLabel(campaignSelection()?.definition?.domain_labels?.[d],d);
const pct=v=>v==null?'—':fmt(100*v,1)+' %';
function groupsForCheck(c,d,n){return d==='hard_gates'?c.definition?.gates?.[n]:c.definition?.checks?.[d]?.[n];}
function campaignSelection(){
 const available=(campaignData?.cohorts||[]).filter(c=>!campaignModel||c.context.model===campaignModel);
 return available.find(c=>c.id===cohortId)||available[0];
}
function campaignMetric(s){
 if(!s?.n)return `<span class="muted">${esc(ui('Aucune session'))}</span>`;
 return `<strong>${pct(s.rate)}</strong>${s.rate==null?'':`<meter min="0" max="1" value="${s.rate}" aria-label="${esc(ui('Taux de réussite'))}">${pct(s.rate)}</meter>`}<small>${s.passed} ${esc(ui('réussites'))} · ${s.failed} ${esc(ui('échecs'))} · ${s.unknown} ${esc(ui('indéterminés'))}</small><small>n = ${s.n} · ${esc(ui('Bornes'))}: ${pct(s.rate)} – ${pct(s.possible_rate)}</small>`;
}
function campaignView(){
 const heading=title(ui('Comparer les résultats enregistrés'),ui('Comparaison des configurations'),ui('Chaque observation correspond à une tâche dans une session. Les modèles et protocoles distincts restent séparés.'));
 if(!campaignData)return heading+empty(campaignError||ui('Chargement de la campagne…'));
 const models=[...new Set(campaignData.cohorts.map(c=>c.context.model||''))].sort();
 const available=campaignData.cohorts.filter(c=>!campaignModel||c.context.model===campaignModel);
 const c=campaignSelection();
 const warning=campaignError?`<div role="alert" class="notice warning">${esc(campaignError)}</div>`:'';
 if(!c)return heading+warning+empty(ui('Aucun résultat enregistré. Ajouter des répertoires de session au serveur.'));
 const configs=Object.keys(c.configurations);
 if(drillCheck&&!groupsForCheck(c,drillDomain,drillCheck))drillCheck='';
 if(!c.domains.includes(drillDomain)){drillDomain='overall';drillCheck='';}
 const selectedTask=c.tasks.includes(campaignTask)?campaignTask:'';
 const groups=selectedTask?c.by_task[selectedTask]:c.groups;
 const tasks=selectedTask?[selectedTask]:c.tasks;
 const allRows=campaignData.records.filter(r=>r.cohort===c.id&&(!selectedTask||r.case===selectedTask));
 const selected=(r)=>drillCheck?r.checks[drillDomain]?.[drillCheck]||'unknown':r.domains[drillDomain];
 const rows=allRows.filter(r=>(!drillConfig||r.configuration===drillConfig)&&(drillOutcome==='all'||selected(r)===drillOutcome));
 const eligible=c.comparable&&(!selectedTask?!c.conflicting_tasks.length:!c.conflicting_tasks.includes(selectedTask));
 const delta=(a,b)=>{
   const x=groups[a].domains.overall,y=groups[b].domains.overall;
   if(!eligible||x.rate==null||y.rate==null)return `${b}−${a}: ${ui('non comparable')}`;
   const value=100*(y.rate-x.rate);
   return `${b}−${a}: ${value>0?'+':''}${fmt(value,1)} ${ui('points')} (${ui('bornes')}: ${fmt(100*(y.rate-x.possible_rate),1)} / ${fmt(100*(y.possible_rate-x.rate),1)})`;
 };
 const filter=(id,label,options)=>`<label>${esc(label)}<select id="${id}">${options}</select></label>`;
 const option=(value,label,selected)=>`<option value="${esc(value)}" ${selected?'selected':''}>${esc(label)}</option>`;
 return heading+warning+`<div class="notice">${esc(ui('Périmètre : tous les répertoires explicitement chargés dans ce serveur. Aucun lancement depuis cette vue.'))} ${campaignData.assignments} ${esc(ui('observations chargées'))} · ${campaignData.cohorts.length} ${esc(ui('groupes de comparaison'))}.</div>`+
 `<div class="toolbar campaign-filters">${filter('campaign-model',ui('Modèle'),option('',ui('Tous les modèles'),!campaignModel)+models.map(m=>option(m,m||ui('Inconnu'),m===campaignModel)).join(''))}${filter('campaign-cohort',ui('Groupe compatible'),available.map(x=>option(x.id,`${x.context.model||'?'} · ${x.context.protocol||'?'} · ${x.context.budgets.model_requests??'?'} req · ${x.context.reference_scope} · ${x.id.slice(0,6)}`,x.id===c.id)).join(''))}${filter('campaign-task',ui('Tâche'),option('',ui('Toutes les tâches · poids égaux'),!selectedTask)+c.tasks.map(t=>option(t,t,t===selectedTask)).join(''))}</div>`+
 `<p class="muted">${esc(ui('Les sélecteurs Session et Tâche de la barre supérieure concernent les vues individuelles. Ici, utiliser les filtres de comparaison.'))}</p>`+
 (!eligible?`<div class="notice warning">${esc(ui('Comparaison limitée : identités manquantes, versions de tâche ou budgets d’outils différents. Les écarts entre configurations sont masqués.'))} ${esc(c.conflicting_tasks.join(', '))}</div>`:'')+
 (c.excluded?`<div class="notice warning">${c.excluded} ${esc(ui('observations sans configuration reconnue : exclues des agrégats par configuration, conservées dans le détail.'))}</div>`:'')+
 `<div class="campaign-cards">${configs.map(config=>`<section class="panel"><h2>Configuration ${esc(config)}</h2><div class="campaign-value">${campaignMetric(groups[config].domains.overall)}</div><p class="muted">${esc(ui('Réussite complète · poids égal par tâche'))}</p></section>`).join('')}</div>`+
 `<div class="status-row">${configs.flatMap((a,i)=>configs.slice(i+1).map(b=>[a,b])).map(pair=>badge(delta(pair[0],pair[1]))).join('')}</div>`+
 `<section class="panel"><h2>${esc(ui('Résultats par domaine'))}</h2><p class="muted">${esc(ui('Cliquer sur une cellule pour retrouver les sessions et leurs preuves. Un domaine réussit lorsque tous ses contrôles requis réussissent.'))}</p><div class="table-scroll"><table class="campaign-matrix"><thead><tr><th>${esc(ui('Domaine'))}</th>${configs.map(config=>'<th>'+esc(config)+'</th>').join('')}</tr></thead><tbody>${c.domains.map(domain=>`<tr><th>${esc(campaignLabel(domain))}</th>${configs.map(config=>`<td><button class="campaign-cell ${drillConfig===config&&drillDomain===domain&&!drillCheck?'selected':''}" data-campaign-domain="${domain}" data-campaign-config="${esc(config)}" aria-label="${esc(campaignLabel(domain))}, ${config}">${campaignMetric(groups[config].domains[domain])}</button></td>`).join('')}</tr>`).join('')}</tbody></table></div></section>`+
 `<section class="panel"><h2>${esc(ui('Contrôles détaillés'))}</h2>${Object.keys(groups[configs[0]].checks).map(domain=>`<details data-key="campaign-checks-${domain}"><summary>${esc(campaignLabel(domain))}</summary><div class="table-scroll"><table><thead><tr><th>${esc(ui('Contrôle requis'))}</th>${configs.map(config=>'<th>'+esc(config)+'</th>').join('')}</tr></thead><tbody>${Object.keys(groups[configs[0]].checks[domain]).map(check=>`<tr><th>${esc(recordedLabel((domain==='hard_gates'?c.definition?.gates:c.definition?.checks?.[domain])?.[check]?.label,check))}</th>${configs.map(config=>`<td><button class="campaign-cell" data-campaign-domain="${domain}" data-campaign-check="${check}" data-campaign-config="${esc(config)}">${campaignMetric(groups[config].checks[domain][check])}</button></td>`).join('')}</tr>`).join('')}</tbody></table></div></details>`).join('')}</section>`+
 `<section class="panel"><h2>${esc(ui('Couverture par tâche'))}</h2><p class="muted">${esc(ui('Les effectifs peuvent différer. Une tâche absente dans une configuration rend son taux global indisponible. Les répétitions manquantes ne sont détectables que si leurs répertoires préparés sont chargés.'))}</p><div class="table-scroll"><table><thead><tr><th>${esc(ui('Tâche'))}</th>${configs.map(config=>'<th>'+esc(config)+'</th>').join('')}</tr></thead><tbody>${tasks.map(t=>`<tr><th><button class="button" data-campaign-task="${esc(t)}">${esc(t)}</button></th>${configs.map(config=>`<td>${campaignMetric(c.by_task[t][config].domains.overall)}</td>`).join('')}</tr>`).join('')}</tbody></table></div></section>`+
 `<section class="panel"><h2>${esc(ui('Effort et score diagnostique'))}</h2><p class="muted">${esc(ui('Moyennes sur les valeurs disponibles, avec leur effectif. Les tokens incomplets sont exclus. Ces moyennes ne remplacent pas le taux de réussite.'))}</p><div class="table-scroll"><table><thead><tr><th>${esc(ui('Mesure'))}</th>${configs.map(config=>'<th>'+esc(config)+'</th>').join('')}</tr></thead><tbody>${[['elapsed_seconds',ui('Temps de construction (s)')],['tokens',ui('Tokens enregistrés')],['requests',ui('Requêtes agent')],['score',ui('Score diagnostique')+' / '+(c.definition?.score.maximum??'—')]].map(([key,label])=>`<tr><th>${esc(label)}</th>${configs.map(config=>{const v=groups[config].efforts[key];return `<td>${fmt(v.mean,1)} <small>(n = ${v.n})</small></td>`}).join('')}</tr>`).join('')}</tbody></table></div></section>`+
 `<section class="panel" id="campaign-sessions"><h2>${esc(ui('Sessions derrière les résultats'))}</h2><p>${esc(campaignLabel(drillDomain))}${drillCheck?' · '+esc(ui(labels[drillCheck]||drillCheck)):''}</p><div class="toolbar">${filter('campaign-config',ui('Configuration'),option('',ui('Toutes'),!drillConfig)+[...configs,'?'].map(v=>option(v,v,v===drillConfig)).join(''))}${filter('campaign-outcome',ui('Résultat du contrôle sélectionné'),[['all','Tous'],['pass','Conforme'],['fail','Échec'],['unknown','Indéterminé']].map(([v,l])=>option(v,ui(l),v===drillOutcome)).join(''))}<span>${rows.length} ${esc(ui('observations'))}</span></div><div class="table-scroll"><table><thead><tr><th>${esc(ui('Session'))}</th><th>${esc(ui('Tâche'))}</th><th>${esc(ui('Configuration'))}</th><th>${esc(ui('Résultat'))}</th><th>${esc(ui('Preuves'))}</th></tr></thead><tbody>${rows.map(r=>`<tr><td>${esc(r.run_name)}</td><td>${esc(r.case)}</td><td>${esc(r.configuration)}</td><td>${verdict(selected(r)==='pass'?true:selected(r)==='fail'?false:null)}<small>${esc(r.report_status)} · ${esc(r.review_status)} · ${esc(r.evaluation_status)}${r.evaluation_reason?' · '+esc(r.evaluation_reason):''}</small></td><td><button class="button" data-campaign-open="${r.run}" data-campaign-index="${r.task_index}" data-campaign-case="${esc(r.case)}">${esc(ui('Ouvrir l’évaluation'))}</button></td></tr>`).join('')}</tbody></table></div>${!rows.length?empty(ui('Aucune session pour ces filtres.')):''}</section>`+
 `<section class="panel guide"><h2>${esc(ui('Comment lire les pourcentages'))}</h2><p>${esc(ui('Pour chaque tâche : réussites établies / toutes les observations chargées. Le taux global est la moyenne de ces taux par tâche. Un résultat indéterminé reste dans le dénominateur.'))}</p><p>${esc(ui('Les bornes montrent le taux si tous les indéterminés échouaient ou réussissaient. Elles ne sont pas un intervalle de confiance statistique. Avec peu de répétitions, les écarts restent descriptifs.'))}</p><p>${esc(ui('Les domaines non observés après un arrêt restent indéterminés. Seuls les verdicts accompagnés d’une revue cohérente et du barème reconnu sont agrégés. Le dashboard ne relance pas la vérification.'))}</p><p>${esc(ui('Les différences entre configurations ne prouvent pas une causalité. La configuration des requêtes non enregistrée, les tâches réutilisées et les biais partagés limitent l’interprétation.'))}</p>${details('campaign-context',ui('Identités et budgets du groupe'),{...c.context,definition:c.definition, configurations:c.configurations, assistance_budgets:c.assistance_budgets,conflicting_tasks:c.conflicting_tasks,conflicting_tool_budgets:c.conflicting_tool_budgets})}${campaignData.warnings.length?details('campaign-warnings',ui('Fichiers illisibles ou incomplets'),campaignData.warnings):''}</section>`;
}

async function refreshCampaign(force=false){
 if(campaignBusy||(!force&&!$('auto').checked))return;
 campaignBusy=true;
 try{
   const response=await fetch('/api/campaign',{cache:'no-store'});
   if(!response.ok)throw Error(ui('Comparaison indisponible')+' ('+response.status+')');
   campaignData=await response.json();campaignError='';campaignRead=new Date();
   $('error').hidden=true;
   $('connection').textContent=ui('Lecture à ')+campaignRead.toLocaleTimeString(I18N.locale);
 }catch(e){campaignError=e.message+ui(' · Les dernières données restent affichées, elles peuvent être périmées.');}
 finally{campaignBusy=false;if(view==='campaign')render();}
}
document.addEventListener('change',e=>{
 const id=e.target.id;
 if(!id.startsWith('campaign-'))return;
 if(id==='campaign-model'){campaignModel=e.target.value;cohortId='';campaignTask='';}
 if(id==='campaign-cohort'){cohortId=e.target.value;campaignTask='';}
 if(id==='campaign-task')campaignTask=e.target.value;
 if(id==='campaign-config')drillConfig=e.target.value;
 if(id==='campaign-outcome')drillOutcome=e.target.value;
 render();
});
document.addEventListener('click',e=>{
 const b=e.target.closest('button');if(!b)return;
 if(b.dataset.campaignDomain){drillDomain=b.dataset.campaignDomain;drillCheck=b.dataset.campaignCheck||'';drillConfig=b.dataset.campaignConfig;render();$('campaign-sessions')?.scrollIntoView({behavior:'smooth',block:'start'});}
 if(b.dataset.campaignTask){campaignTask=b.dataset.campaignTask;render();}
 if(b.dataset.campaignOpen!==undefined){runIndex=+b.dataset.campaignOpen;taskIndex=+b.dataset.campaignIndex;pendingCampaignCase=b.dataset.campaignCase;view='evaluation';previous='';replayIndex=0;$('run-select').value=String(runIndex);refresh(true);}
});
