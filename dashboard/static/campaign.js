'use strict';
let campaignData=null, campaignBusy=false, campaignError='', campaignRead=null;
let cohortId='', campaignModel='', campaignTask='', drillConfig='', drillDomain='overall', drillCheck='', drillOutcome='all';
let campaignStudy=null;
const campaignState=s=>ui(({prepared:'Préparée',running:'En cours',complete:'Terminée',paused_on_incident:'Arrêtée sur incident'})[s]||s||'Inconnu');
function studyChoices(){
 const values=(campaignData?.campaigns||[]).map(c=>[c.id,c.name]);
 if(campaignData?.records.some(r=>!r.campaign_id))values.push(['',ui('Hors campagne déclarée')]);
 if(!values.some(v=>v[0]===campaignStudy))campaignStudy=values[0]?.[0]??'';
 return values;
}
function studyCohorts(){studyChoices();return (campaignData?.cohorts||[]).filter(c=>(c.campaign_id||'')===campaignStudy);}
function studyOverview(){
 const study=campaignData?.campaigns?.find(c=>c.id===campaignStudy);
 if(!study)return `<div class="notice">${esc(ui('Sélection sans plan de campagne : effectif attendu et complétude inconnus.'))}</div>`;
 const count=study.counts||{};
 return `<section class="panel"><h2>${esc(study.name)}</h2><div class="metrics">${metric(ui('Prévues'),study.expected,ui('Inventaire du plan'))}${metric(ui('Terminées'),count.completed||0,ui('Résultat et revue disponibles'))}${metric(ui('Non démarrées'),count.not_started||0,ui('Aucun résultat attribué'))}${metric(ui('En cours'),(count.authoring||0)+(count.assessment||0)+(count.verification||0),ui('Dernier état enregistré'))}${metric(ui('Interrompues'),count.interrupted||0,ui('Consulter les preuves'))}${metric(ui('Manquantes'),study.missing,ui('Plan ou dossier absent'))}</div><p><strong>${esc(ui('État de la campagne'))}: ${esc(campaignState(study.state))}</strong></p>${study.error?`<p class="notice warning">${esc(study.error)}</p>`:''}${study.conflicts?`<p class="notice warning">${esc(ui('Exécutions en conflit avec le plan'))}: ${study.conflicts}</p>`:''}<p>${esc(ui('Périmètre de référence prévu'))}: ${esc(study.reference_scope||ui('Inconnu'))}</p><p class="muted">${esc(ui('Les états décrivent les dernières traces enregistrées, pas une garantie de processus vivant. Les exécutions non terminées restent sans verdict.'))}</p></section>`;
}
const campaignLabel=d=>d==='overall'?ui('Réussite complète'):d==='hard_gates'?ui('Contrôles obligatoires'):recordedLabel(campaignSelection()?.definition?.domain_labels?.[d],d);
const pct=v=>v==null?'—':fmt(100*v,1)+' %';
function groupsForCheck(c,d,n){return d==='hard_gates'?c.definition?.gates?.[n]:c.definition?.checks?.[d]?.[n];}
function campaignSelection(){
 const available=studyCohorts().filter(c=>!campaignModel||c.context.model===campaignModel);
 return available.find(c=>c.id===cohortId)||available[0];
}
function campaignMetric(s){
 if(!s?.n)return `<span class="muted">${esc(ui('Aucune session'))}</span>`;
 return `<strong>${pct(s.rate)}</strong>${s.rate==null?'':`<meter min="0" max="1" value="${s.rate}" aria-label="${esc(ui('Taux de réussite'))}">${pct(s.rate)}</meter>`}<small>${s.passed} ${esc(ui('réussites'))} · ${s.failed} ${esc(ui('échecs'))} · ${s.unknown} ${esc(ui('indéterminés'))}</small><small>n = ${s.n} · ${esc(ui('Bornes'))}: ${pct(s.rate)} – ${pct(s.possible_rate)}</small>`;
}
function campaignChart(cohorts, task){
 const series=cohorts.map(c=>({cohort:c,model:(c.context.model||ui('Inconnu'))+(cohorts.filter(x=>x.context.model===c.context.model).length>1?' · '+c.id.slice(0,6):''),groups:task?c.by_task[task]:c.groups}));
 const configs=[...new Set(series.flatMap(s=>Object.keys(s.groups||{})))].filter(k=>series.some(s=>s.groups?.[k]?.domains.overall.n>0)).sort((a,b)=>a.localeCompare(b,undefined,{numeric:true}));
 if(!configs.length)return '';
 // The existing gate covers each cohort. A shared plot additionally needs
 // matching assessment definitions, execution budgets and task identities.
 const comparisonKey=c=>JSON.stringify([
   c.campaign_id,c.context.protocol,c.context.rubric,c.context.definition,
   c.context.profile,c.context.budgets,c.context.reference_scope,
   task?[task]:[...c.tasks].sort(),
   [...new Set(campaignData.records.filter(r=>r.cohort===c.id&&(!task||r.case===task)).map(r=>r.task_signature))].sort()
 ]);
 const sameContext=series.every(s=>comparisonKey(s.cohort)===comparisonKey(series[0].cohort));
 const rates=sameContext&&series.every(s=>s.cohort.comparable&&(!task?!s.cohort.conflicting_tasks.length:!s.cohort.conflicting_tasks.includes(task))&&configs.every(k=>Number.isFinite(s.groups?.[k]?.domains.overall.rate)));
 const stats=series.flatMap(s=>configs.map(k=>s.groups?.[k]?.domains.overall).filter(Boolean));
 const maximum=rates?100:Math.max(1,...stats.map(s=>s.n));
 // Use the full campaign inventory so filtering cannot relabel a bar color.
 const colorOrder=(campaignData?.cohorts||cohorts).filter(c=>c.campaign_id===cohorts[0].campaign_id).slice().sort((a,b)=>(a.context.model||'').localeCompare(b.context.model||'')||a.id.localeCompare(b.id));
 const colors=['#285bad','#99590c','#087d72','#864cb0','#a63760'];
 const color=c=>colors[colorOrder.findIndex(x=>x.id===c.id)%colors.length];
 const legendHeight=(series.length+1)*22;
 const width=Math.max(640,configs.length*series.length*82+100,...series.map(s=>90+s.model.length*8)),top=45+legendHeight,bottom=285+legendHeight,left=55,right=width-25;
 const slot=(right-left)/configs.length,bar=Math.min(55,slot/(series.length+1));
 const y=v=>bottom-(bottom-top)*v/maximum;
 const ticks=[...new Set(Array.from({length:6},(_,i)=>rates?maximum*i/5:Math.round(maximum*i/5)))];
 const axis=ticks.map(v=>`<line x1="${left}" x2="${right}" y1="${y(v)}" y2="${y(v)}" stroke="#dbe3e5"/><text x="${left-10}" y="${y(v)+4}" text-anchor="end">${esc(fmt(v,0))}${rates?' %':''}</text>`).join('');
 const bars=configs.map((config,i)=>series.map((s,j)=>{
   const v=s.groups?.[config]?.domains.overall;
   const x=left+slot*(i+.5)+(j-series.length/2)*bar;
   if(!v?.n)return `<text x="${x+bar/2}" y="${bottom-8}" text-anchor="middle">—</text>`;
   const value=rates?100*v.rate:v.passed;
   const upper=rates?100*(v.possible_rate??v.rate):v.passed+v.unknown;
   const label=rates?pct(v.rate):String(v.passed);
   const description=`${s.model} · ${config}: ${label}; ${v.passed} ${ui('réussites')}, ${v.failed} ${ui('échecs')}, ${v.unknown} ${ui('indéterminés')}; n = ${v.n}`;
   return `<g><title>${esc(description)}</title><rect x="${x+3}" y="${y(value)}" width="${bar-6}" height="${bottom-y(value)}" fill="${color(s.cohort)}"/>${upper>value?`<rect x="${x+3}" y="${y(upper)}" width="${bar-6}" height="${y(value)-y(upper)}" fill="url(#campaign-chart-unresolved)" stroke="#556877"/>`:''}<text class="chart-value" x="${x+bar/2}" y="${y(upper)-9}" text-anchor="middle">${esc(label)}</text></g>`;
 }).join('')+`<text x="${left+slot*(i+.5)}" y="${bottom+27}" text-anchor="middle">${esc(config)}</text>`).join('');
 const note=rates?ui('Barres pleines : taux établi, avec un poids égal par tâche. Partie hachurée : résultats indéterminés pouvant augmenter ce taux ; ce n’est pas un intervalle de confiance.'):ui('Les pourcentages comparatifs sont indisponibles ou les groupes ont des contextes différents. Le graphique montre les effectifs enregistrés, sans recalculer de taux.');
 const legend=`<g class="chart-legend">${series.map((s,i)=>`<g><rect x="${left}" y="${8+i*22}" width="14" height="14" rx="2" fill="${color(s.cohort)}"/><text x="${left+24}" y="${20+i*22}">${esc(s.model)}</text></g>`).join('')}<g><rect x="${left}" y="${8+series.length*22}" width="14" height="14" rx="2" fill="url(#campaign-chart-unresolved)" stroke="#556877"/><text x="${left+24}" y="${20+series.length*22}">${esc(ui('indéterminés'))}</text></g></g>`;
 const table=`<div class="table-scroll"><table><caption>${esc(ui('Valeurs du graphique'))}</caption><thead><tr>${['Modèle','Configuration','réussites','échecs','indéterminés','observations'].map(k=>`<th scope="col">${esc(ui(k))}</th>`).join('')}</tr></thead><tbody>${series.flatMap(s=>configs.map(k=>{const v=s.groups?.[k]?.domains.overall;return `<tr><th scope="row">${esc(s.model)}</th><td>${esc(k)}</td>${v?[v.passed,v.failed,v.unknown,v.n].map(n=>`<td>${n}</td>`).join(''):'<td colspan="4">—</td>'}</tr>`})).join('')}</tbody></table></div>`;
 return `<section class="panel campaign-chart"><h2>${esc(ui('Réussite par modèle et configuration'))}</h2><p>${esc(task||ui(rates?'Toutes les tâches · poids égaux':'Toutes les tâches'))}</p><p class="muted" id="campaign-chart-note">${esc(note)}</p><div class="table-scroll"><svg viewBox="0 0 ${width} ${330+legendHeight}" width="${width}" height="${330+legendHeight}" role="img" aria-labelledby="campaign-chart-title" aria-describedby="campaign-chart-note"><title id="campaign-chart-title">${esc(ui('Réussite par modèle et configuration'))} — ${esc(rates?ui('Taux de réussite'):ui('Nombre de réussites'))}</title><defs><pattern id="campaign-chart-unresolved" width="6" height="6" patternUnits="userSpaceOnUse"><rect width="6" height="6" fill="#f3f6f5"/><path d="M0 6L6 0" stroke="#87969e"/></pattern></defs>${legend}<text x="${left}" y="${18+legendHeight}">${esc(rates?ui('Taux de réussite'):ui('Nombre de réussites'))}</text>${axis}${bars}</svg></div><p class="muted">${esc(ui('Les résultats indéterminés restent visibles. Les effectifs ne sont pas des taux ; consulter le tableau lorsque les tailles des groupes diffèrent.'))}</p><details data-key="campaign-chart-values"><summary>${esc(ui('Valeurs du graphique'))}</summary>${table}</details></section>`;
}
function campaignView(){
 const heading=title(ui('Comparer les résultats enregistrés'),ui('Comparaison des configurations'),ui('Chaque exécution est une tentative sur une tâche. La campagne définit les répétitions prévues.'));
 if(!campaignData)return heading+empty(campaignError||ui('Chargement de la campagne…'));
 const studies=studyChoices();
 const models=[...new Set(studyCohorts().map(c=>c.context.model||''))].sort();
 if(campaignModel&&!models.includes(campaignModel))campaignModel='';
 const available=studyCohorts().filter(c=>!campaignModel||c.context.model===campaignModel);
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
 return heading+warning+`<div class="toolbar">${filter('study-select',ui('Campagne'),studies.map(([id,name])=>option(id,name,id===campaignStudy)).join(''))}</div>`+studyOverview()+`<div class="notice">${esc(ui('Les comparaisons restent dans la campagne sélectionnée. Les groupes séparent les modèles ; les divergences de protocole bloquent les taux.'))}</div>`+
 `<div class="toolbar campaign-filters">${filter('campaign-model',ui('Modèle'),option('',ui('Tous les modèles'),!campaignModel)+models.map(m=>option(m,m||ui('Inconnu'),m===campaignModel)).join(''))}${filter('campaign-cohort',ui('Groupe de comparaison'),available.map(x=>option(x.id,`${x.context.model||'?'} · ${x.context.protocol||'?'} · ${x.context.budgets.model_requests??'?'} req · ${x.context.reference_scope} · ${x.id.slice(0,6)}`,x.id===c.id)).join(''))}${filter('campaign-task',ui('Tâche'),option('',ui('Toutes les tâches · poids égaux'),!selectedTask)+c.tasks.map(t=>option(t,t,t===selectedTask)).join(''))}</div>`+
 `<p class="muted">${esc(ui('Utiliser ces filtres pour comparer, puis ouvrir une exécution depuis les tableaux.'))}</p>`+
 campaignChart(available,selectedTask)+
 (!eligible?`<div class="notice warning">${esc(ui('Comparaison limitée : identités manquantes, versions de tâche ou budgets d’outils différents. Les écarts entre configurations sont masqués.'))} ${esc(c.conflicting_tasks.join(', '))}</div>`:'')+
 (c.excluded?`<div class="notice warning">${c.excluded} ${esc(ui('observations sans configuration reconnue : exclues des agrégats par configuration, conservées dans le détail.'))}</div>`:'')+
 `<div class="campaign-cards">${configs.map(config=>`<section class="panel"><h2>Configuration ${esc(config)}</h2><div class="campaign-value">${campaignMetric(groups[config].domains.overall)}</div><p class="muted">${esc(ui('Réussite complète · poids égal par tâche'))}</p></section>`).join('')}</div>`+
 `<div class="status-row">${configs.flatMap((a,i)=>configs.slice(i+1).map(b=>[a,b])).map(pair=>badge(delta(pair[0],pair[1]))).join('')}</div>`+
 `<section class="panel"><h2>${esc(ui('Résultats par domaine'))}</h2><p class="muted">${esc(ui('Cliquer sur une cellule pour retrouver les sessions et leurs preuves. Un domaine réussit lorsque tous ses contrôles requis réussissent.'))}</p><div class="table-scroll"><table class="campaign-matrix"><thead><tr><th>${esc(ui('Domaine'))}</th>${configs.map(config=>'<th>'+esc(config)+'</th>').join('')}</tr></thead><tbody>${c.domains.map(domain=>`<tr><th>${esc(campaignLabel(domain))}</th>${configs.map(config=>`<td><button class="campaign-cell ${drillConfig===config&&drillDomain===domain&&!drillCheck?'selected':''}" data-campaign-domain="${domain}" data-campaign-config="${esc(config)}" aria-label="${esc(campaignLabel(domain))}, ${config}">${campaignMetric(groups[config].domains[domain])}</button></td>`).join('')}</tr>`).join('')}</tbody></table></div></section>`+
 `<section class="panel"><h2>${esc(ui('Contrôles détaillés'))}</h2>${Object.keys(groups[configs[0]].checks).map(domain=>`<details data-key="campaign-checks-${domain}"><summary>${esc(campaignLabel(domain))}</summary><div class="table-scroll"><table><thead><tr><th>${esc(ui('Contrôle requis'))}</th>${configs.map(config=>'<th>'+esc(config)+'</th>').join('')}</tr></thead><tbody>${Object.keys(groups[configs[0]].checks[domain]).map(check=>`<tr><th>${esc(recordedLabel((domain==='hard_gates'?c.definition?.gates:c.definition?.checks?.[domain])?.[check]?.label,check))}</th>${configs.map(config=>`<td><button class="campaign-cell" data-campaign-domain="${domain}" data-campaign-check="${check}" data-campaign-config="${esc(config)}">${campaignMetric(groups[config].checks[domain][check])}</button></td>`).join('')}</tr>`).join('')}</tbody></table></div></details>`).join('')}</section>`+
 `<section class="panel"><h2>${esc(ui('Couverture par tâche'))}</h2><p class="muted">${esc(ui('Les effectifs peuvent différer. Une tâche absente dans une configuration rend son taux global indisponible. Les répétitions manquantes ne sont détectables que si leurs répertoires préparés sont chargés.'))}</p><div class="table-scroll"><table><thead><tr><th>${esc(ui('Tâche'))}</th>${configs.map(config=>'<th>'+esc(config)+'</th>').join('')}</tr></thead><tbody>${tasks.map(t=>`<tr><th><button class="button" data-campaign-task="${esc(t)}">${esc(t)}</button></th>${configs.map(config=>`<td>${campaignMetric(c.by_task[t][config].domains.overall)}</td>`).join('')}</tr>`).join('')}</tbody></table></div></section>`+
 `<section class="panel"><h2>${esc(ui('Effort et score diagnostique'))}</h2><p class="muted">${esc(ui('Moyennes sur les valeurs disponibles, avec leur effectif. Les tokens incomplets sont exclus. Ces moyennes ne remplacent pas le taux de réussite.'))}</p><div class="table-scroll"><table><thead><tr><th>${esc(ui('Mesure'))}</th>${configs.map(config=>'<th>'+esc(config)+'</th>').join('')}</tr></thead><tbody>${[['elapsed_seconds',ui('Temps de construction (s)')],['tokens',ui('Tokens enregistrés')],['requests',ui('Requêtes agent')],['score',ui('Score diagnostique')+' / '+(c.definition?.score.maximum??'—')]].map(([key,label])=>`<tr><th>${esc(label)}</th>${configs.map(config=>{const v=groups[config].efforts[key];return `<td>${fmt(v.mean,1)} <small>(n = ${v.n})</small></td>`}).join('')}</tr>`).join('')}</tbody></table></div></section>`+
 `<section class="panel" id="campaign-sessions"><h2>${esc(ui('Exécutions derrière les résultats'))}</h2><p>${esc(campaignLabel(drillDomain))}${drillCheck?' · '+esc(ui(labels[drillCheck]||drillCheck)):''}</p><div class="toolbar">${filter('campaign-config',ui('Configuration'),option('',ui('Toutes'),!drillConfig)+[...configs,'?'].map(v=>option(v,v,v===drillConfig)).join(''))}${filter('campaign-outcome',ui('Résultat du contrôle sélectionné'),[['all','Tous'],['pass','Conforme'],['fail','Échec'],['unknown','Indéterminé']].map(([v,l])=>option(v,ui(l),v===drillOutcome)).join(''))}<span>${rows.length} ${esc(ui('observations'))}</span></div><div class="table-scroll"><table><thead><tr><th>${esc(ui('Exécution'))}</th><th>${esc(ui('Tâche'))}</th><th>${esc(ui('Configuration'))}</th><th>${esc(ui('Répétition'))}</th><th>${esc(ui('État'))}</th><th>${esc(ui('Résultat'))}</th><th>${esc(ui('Preuves'))}</th></tr></thead><tbody>${rows.map(r=>`<tr><td>${esc(r.run_name)}</td><td>${esc(r.case)}</td><td>${esc(r.configuration)}</td><td>${esc(r.repeat??'—')}</td><td>${esc(typeof executionState==='function'?executionState(r.lifecycle):r.lifecycle||'—')}</td><td>${verdict(selected(r)==='pass'?true:selected(r)==='fail'?false:null)}<small>${esc(r.report_status)} · ${esc(r.review_status)} · ${esc(r.evaluation_status)}${r.evaluation_reason?' · '+esc(r.evaluation_reason):''}</small></td><td><button class="button" data-campaign-open="${r.run}" data-campaign-index="${r.task_index}" data-campaign-case="${esc(r.case)}">${esc(ui('Ouvrir l’évaluation'))}</button></td></tr>`).join('')}</tbody></table></div>${!rows.length?empty(ui('Aucune session pour ces filtres.')):''}</section>`+
 `<section class="panel guide"><h2>${esc(ui('Comment lire les pourcentages'))}</h2><p>${esc(ui('Pour chaque tâche : réussites établies / toutes les observations chargées. Le taux global est la moyenne de ces taux par tâche. Un résultat indéterminé reste dans le dénominateur.'))}</p><p>${esc(ui('Les bornes montrent le taux si tous les indéterminés échouaient ou réussissaient. Elles ne sont pas un intervalle de confiance statistique. Avec peu de répétitions, les écarts restent descriptifs.'))}</p><p>${esc(ui('Les domaines non observés après un arrêt restent indéterminés. Seuls les verdicts accompagnés d’une revue cohérente et du barème reconnu sont agrégés. Le dashboard ne relance pas la vérification.'))}</p><p>${esc(ui('Les différences entre configurations ne prouvent pas une causalité. La configuration des requêtes non enregistrée, les tâches réutilisées et les biais partagés limitent l’interprétation.'))}</p>${details('campaign-context',ui('Identités et budgets du groupe'),{...c.context,context_conflicts:c.context_conflicts, membership_conflicts:c.membership_conflicts, definition:c.definition, configurations:c.configurations, assistance_budgets:c.assistance_budgets,conflicting_tasks:c.conflicting_tasks,conflicting_tool_budgets:c.conflicting_tool_budgets})}${campaignData.warnings.length?details('campaign-warnings',ui('Fichiers illisibles ou incomplets'),campaignData.warnings):''}</section>`;
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
 if(id==='study-select'){campaignStudy=e.target.value;campaignModel='';cohortId='';campaignTask='';render();return;}
 if(!['campaign-model','campaign-cohort','campaign-task','campaign-config','campaign-outcome'].includes(id))return;
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
