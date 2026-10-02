// Execution state and rubric availability are separate; no browser rendering.
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const fixture=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
const context=vm.createContext({document:{addEventListener(){}}});
for(const name of ['i18n.js','app.js']){
 let source=fs.readFileSync(path.join(__dirname,'../dashboard/static',name),'utf8');
 if(name==='app.js')source=source.slice(0,source.lastIndexOf('(async()=>{'));
 vm.runInContext(source,context);
}
vm.runInContext('data='+JSON.stringify(fixture),context);
const before=vm.runInContext('JSON.stringify(data)',context);
for(const language of ['en','fr']){
 vm.runInContext('I18N.setLanguage('+JSON.stringify(language)+')',context);
 for(const view of ['overview','evaluation']){
  const html=vm.runInContext(view+'(task())',context);
  assert.ok(html.includes(language==='en'?'Assessment interrupted: required references unavailable':'Évaluation interrompue : références requises indisponibles'));
  assert.ok(html.includes(language==='en'?'No score was calculated.':'Aucune note n’a été calculée.'));
  assert.ok(html.includes('Package root must be a real directory'));
  assert.ok(html.includes('admission'));
  assert.ok(html.includes(language==='en'?'Original report':'Rapport original'));
  for(const misleading of ['Available after assessment','Disponible après l’évaluation','Assessment not yet completed','Évaluation non encore terminée.','Contrôles finaux en attente.','No final score at this stage']){
   assert.ok(!html.includes(misleading),view+': '+misleading);
  }
  if(view==='overview')assert.ok(html.includes('<div class="value">—</div>'));
 }
}
assert.equal(vm.runInContext('JSON.stringify(data)',context),before);
// Unknown schemas remain unsupported, rather than pretending to run or finish.
vm.runInContext('data.tasks[0].evaluation={status:"unsupported",reason:"Unknown format",report:null,operational:{state:"unavailable"}};I18N.setLanguage("en")',context);
assert.ok(!vm.runInContext('overview(task())',context).includes('Available after assessment'));
assert.ok(!vm.runInContext('evaluation(task())',context).includes('Assessment interrupted:'));
// Raw stop text remains inert, including in the prominent diagnostic.
vm.runInContext('data.tasks[0].evaluation.operational={state:"interrupted",stage:"transport",error:"<script>bad()</script>"}',context);
const html=vm.runInContext('evaluation(task())',context);
assert.ok(html.includes('&lt;script&gt;bad()&lt;/script&gt;'));
assert.ok(!html.includes('<script>bad()'));
console.log('Interrupted assessment templates passed: EN/FR cause, absent score, original report, no pending claim, inert text.');
