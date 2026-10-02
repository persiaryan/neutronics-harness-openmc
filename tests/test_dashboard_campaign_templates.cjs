// Template/event checks, not a rendered-browser usability claim.
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');
const fixture=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
const handlers={};
const elements={content:{},'run-select':{},'case-select':{},'language-select':{},auto:{checked:true},error:{},connection:{},'campaign-sessions':{scrollIntoView(){}}};
const document={documentElement:{},getElementById:id=>elements[id],querySelectorAll:()=>[],addEventListener(name,fn){(handlers[name]??=[]).push(fn)}};
const context=vm.createContext({document,console,setInterval,clearInterval});
for(const file of ['i18n.js','campaign.js','app.js']){
 let source=fs.readFileSync(path.join(__dirname,'../dashboard/static',file),'utf8');
 if(file==='app.js')source=source.slice(0,source.lastIndexOf('(async()=>{'));
 vm.runInContext(source,context);
}
vm.runInContext('campaignData='+JSON.stringify(fixture)+'; view="campaign";',context);
for(const language of ['en','fr']){
 vm.runInContext('I18N.setLanguage('+JSON.stringify(language)+');render()',context);
 const html=elements.content.innerHTML;
 assert.ok(html.includes(language==='en'?'Results by domain':'Résultats par domaine'));
 assert.ok(html.includes(language==='en'?'Sessions behind the results':'Sessions derrière les résultats'));
 assert.ok(html.includes('Configuration A'));
 assert.ok(!html.includes('undefined'));
 assert.ok(!html.includes('[object Object]'));
 assert.equal(elements['run-select'].disabled,true);
}
// Click from the materials/C matrix to the corresponding records.
const button={dataset:{campaignDomain:'materials',campaignConfig:'C'}};
for(const fn of handlers.click)fn({target:{closest:()=>button}});
assert.equal(vm.runInContext('drillDomain',context),'materials');
assert.equal(vm.runInContext('drillConfig',context),'C');
for(const fn of handlers.change)fn({target:{id:'campaign-outcome',value:'fail'}});
assert.equal(vm.runInContext('drillOutcome',context),'fail');
// No condition is invented in empty groups; no HTML from run names is executed.
vm.runInContext('campaignData.records[0].run_name="<img src=x onerror=bad()>";drillConfig="";drillOutcome="all";render()',context);
assert.ok(elements.content.innerHTML.includes('&lt;img src=x onerror=bad()&gt;'));
assert.ok(!elements.content.innerHTML.includes('<img src=x'));
// Navigation retains the target case name, avoiding accidental cross-task drilldown.
const first=fixture.records[0];
vm.runInContext('busy=true',context);
const open={dataset:{campaignOpen:String(first.run),campaignIndex:String(first.task_index),campaignCase:first.case}};
for(const fn of handlers.click)fn({target:{closest:()=>open}});
assert.equal(vm.runInContext('view',context),'evaluation');
assert.equal(vm.runInContext('runIndex',context),first.run);
assert.equal(vm.runInContext('pendingCampaignCase',context),first.case);
// Campaign fetch failures retain old results and show a visible error.
(async()=>{
 context.fetch=async()=>{throw Error('offline')};
 vm.runInContext('view="campaign";I18N.setLanguage("en")',context);
 await vm.runInContext('refreshCampaign(true)',context);
 assert.ok(elements.content.innerHTML.includes('offline'));
 assert.ok(elements.content.innerHTML.includes('Results by domain'));
 vm.runInContext('campaignData={cohorts:[],records:[],assignments:0,warnings:[]};render()',context);
 assert.ok(elements.content.innerHTML.includes('No retained results'));
 console.log('Campaign templates passed: EN/FR, drilldown, filters, task navigation, escaped text, empty state and stale-data errors.');
})().catch(e=>{console.error(e);process.exitCode=1});
