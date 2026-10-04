// Portable chart controls: synthetic outcomes, no browser or private evidence.
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const context=vm.createContext({
 document:{addEventListener(){}},
 ui:value=>value,
 esc:value=>String(value).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;'),
 fmt:(value,digits=0)=>value.toFixed(digits),
});
vm.runInContext(fs.readFileSync(path.join(__dirname,'../dashboard/static/campaign.js'),'utf8'),context);
const cohort=(id,model)=>({id,campaign_id:'synthetic',context:{model,protocol:'same'},tasks:['task'],comparable:true,conflicting_tasks:[],groups:{A:{domains:{overall:{n:3,passed:1,failed:1,unknown:1,rate:1/3,possible_rate:2/3}}}}});
const luna=cohort('luna','gpt-5.6-luna'),sol=cohort('sol','gpt-5.6-sol');
for(const c of [luna,sol])c.by_task={task:c.groups};
const fixture={cohorts:[sol,luna],records:[luna,sol].map(c=>({cohort:c.id,case:'task',task_signature:'same'}))};
const render=(cohorts,task='')=>{
 vm.runInContext('campaignData='+JSON.stringify(fixture),context);
 return vm.runInContext('campaignChart('+JSON.stringify(cohorts)+','+JSON.stringify(task)+')',context);
};
const colorMarkup=(color,model)=>new RegExp('fill="'+color+'"/><text[^>]*>'+model+'</text>');
let html=render([luna,sol]);
assert.doesNotMatch(html,/style=/); // The server's CSP rejects inline styles.
assert.match(html,/<svg[^>]*>[\s\S]*<g class="chart-legend">/);
assert.match(html,colorMarkup('#285bad','gpt-5.6-luna'));
assert.match(html,colorMarkup('#99590c','gpt-5.6-sol'));
assert.match(html,/fill="url\(#campaign-chart-unresolved\)"/);
assert.match(html,/Taux de réussite/);
assert.match(html,/33.3 %/);
assert.match(render([sol]),colorMarkup('#99590c','gpt-5.6-sol'));
assert.match(render([sol,luna]),colorMarkup('#99590c','gpt-5.6-sol'));
assert.match(render([sol],'task'),colorMarkup('#99590c','gpt-5.6-sol'));
// Missing rates and incompatible protocols must preserve the count-only gate.
sol.groups.A.domains.overall.rate=null;
html=render([luna,sol]);
assert.match(html,/Nombre de réussites/);assert.doesNotMatch(html,/Taux de réussite/);
sol.groups.A.domains.overall.rate=1/3;sol.context.protocol='different';
html=render([luna,sol]);
assert.match(html,/Nombre de réussites/);assert.doesNotMatch(html,/Taux de réussite/);
sol.context.model='<img src=x onerror=bad()>';
html=render([sol]);
assert.match(html,/&lt;img src=x onerror=bad\(\)&gt;/);assert.doesNotMatch(html,/<img/);
assert.equal(render([]),'');
console.log('Campaign chart passed: embedded legend, matching colors, stable model/task filters and ordering, unresolved key, rates/count gates, escaped labels and empty state.');
