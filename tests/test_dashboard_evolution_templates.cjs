// Requires synthetic state/campaign fixtures from tests.test_dashboard_contracts.
// Pure templates and handlers; no claim about rendered-browser layout.
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');
const state=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
const campaign=JSON.parse(fs.readFileSync(process.argv[3],'utf8'));
const elements={content:{},'run-select':{},'case-select':{}};
const context=vm.createContext({document:{getElementById:id=>elements[id],querySelectorAll:()=>[],addEventListener(){}},console});
for(const name of ['i18n.js','campaign.js','app.js']){
 let source=fs.readFileSync(path.join(__dirname,'../dashboard/static',name),'utf8');
 if(name==='app.js')source=source.slice(0,source.lastIndexOf('(async()=>{'));
 vm.runInContext(source,context);
}
vm.runInContext('data='+JSON.stringify(state)+';campaignData='+JSON.stringify(campaign),context);
for(const language of ['en','fr']){
 vm.runInContext('I18N.setLanguage('+JSON.stringify(language)+')',context);
 for(const view of ['overview','agent','evaluation','artifacts','guide']){
  vm.runInContext('view='+JSON.stringify(view)+';render()',context);
  const html=elements.content.innerHTML;
  assert.ok(html.includes('Configuration D'));
  assert.ok(!html.includes('undefined'));
  assert.ok(!html.includes('[object Object]'));
  if(view==='overview')assert.ok(html.includes(language==='en'?'10.0 / 10':'10,0 / 10'));
  if(view==='agent'){
   assert.ok(html.includes(language==='en'?'Thermal probe':'Sonde thermique'));
   assert.ok(html.includes('not_established_by_completion'));
  }
  if(view==='evaluation'){
   assert.ok(html.includes(language==='en'?'Temperature balance':'Bilan de température'));
   assert.ok(html.includes('±75 pcm'));
   assert.ok(!html.includes('±150 pcm'));
   assert.ok(!html.includes('95 %'));
   assert.ok(html.includes('301'));
  }
 }
 vm.runInContext('view="campaign";cohortId=campaignData.cohorts.find(c=>c.definition.score.maximum===10).id;render()',context);
 assert.ok(elements.content.innerHTML.includes('Configuration D'));
 assert.ok(elements.content.innerHTML.includes(language==='en'?'Thermal balance':'Bilan thermique'));
 assert.ok(elements.content.innerHTML.includes(language==='en'?'Temperature balance':'Bilan de température'));
 assert.ok(elements.content.innerHTML.includes(language==='en'?'Diagnostic score / 10':'Score diagnostique / 10'));
 assert.ok(!elements.content.innerHTML.includes('undefined'));
}
// Unsupported/invalid reports show a diagnostic and retain inert original text.
for(const status of ['unsupported','invalid']){
 vm.runInContext('data.tasks[0].evaluation='+JSON.stringify({status,reason:'reader diagnostic',report:null,trusted:false})+';data.tasks[0].report={format:"<script>bad()</script>"};view="evaluation";render()',context);
 assert.ok(elements.content.innerHTML.includes('reader diagnostic'));
 assert.ok(elements.content.innerHTML.includes('&lt;script&gt;bad()&lt;/script&gt;'));
 assert.ok(!elements.content.innerHTML.includes('<script>bad()'));
}
console.log('Evolution templates passed: D, new tool/domain/criterion, scale 10, margin 75, EN/FR, unsupported/invalid reports.');
