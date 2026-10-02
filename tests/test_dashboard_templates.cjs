// Pure template checks. These are not a rendered-browser or usability study.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../dashboard/static/app.js'), 'utf8');
const handlers = {};
const context = vm.createContext({document:{addEventListener(name,fn){handlers[name]=fn}}, console, setInterval, clearInterval});
const translations = fs.readFileSync(path.join(__dirname, '../dashboard/static/i18n.js'), 'utf8');
vm.runInContext(translations, context);
assert.equal(vm.runInContext('I18N.language', context), 'en');
vm.runInContext("I18N.setLanguage('fr')", context);
vm.runInContext(source.slice(0, source.lastIndexOf('(async()=>{')), context);
const task = {
  case:'synthetic_case',prompt:'<script>STEAL_SECRET()</script>',
  builder:{timeline:[{id:0,turn:1,kind:'tool',title:'Appel : exec',detail:'<img src=x onerror=STEAL_SECRET()>',evidence:'response-01.sse'},
    {id:1,turn:1,kind:'execution',title:'Commande terminée',detail:'ok',evidence:'events.jsonl:2'}],
    tools:[{tool:'boundary-tool',call:'call-01',feedback:{inspection_status:'observed',
      coverage:{global_geometry_validity:'not_assessed'},domain:{scope:'Boundary observations only'}},
      evidence:'boundary-feedback.json'},
      {tool:'smoke-tool',call:'call-01',feedback:{status:'completed',coverage:'Execution only'},
      projection:{feedback_delivery:{status:'complete',request:'request-04.json'}},evidence:'feedback.json'}]},
  phases:[],assertions:[],identities:[],convergence:[],logs:{},report:null,review:null
};
const fixture={plan:{model:'synthetic',budgets:{model_requests:8,authoring_seconds:600}},tasks:[task],warnings:[],artifacts:[]};
vm.runInContext('data='+JSON.stringify(fixture),context);
function render(view){return vm.runInContext(view+'(task())',context);}
assert.ok(render('overview').includes('Disponible après l’évaluation'));
assert.ok(!render('overview').includes('0,0 / 100'));
assert.ok(render('overview').includes('&lt;script&gt;STEAL_SECRET()&lt;/script&gt;'));
assert.ok(!render('overview').includes('<script>STEAL_SECRET'));
assert.ok(render('agent').includes('request-04.json'));
assert.ok(render('agent').includes('transmis intégralement'));
assert.ok(render('agent').includes('Boundary observations only'));
assert.ok(!render('agent').includes('[object Object]'));
assert.ok(render('agent').includes('&lt;img src=x onerror=STEAL_SECRET()&gt;'));
vm.runInContext("mode='replay'; replayIndex=0",context);
assert.ok(render('agent').includes('1 événements visibles'));
assert.ok(render('agent').includes('Les cartes de feedback et les autres vues restent le bilan'));
vm.runInContext("filter='edit'",context);
assert.ok(render('agent').includes('Aucun événement correspondant'));
for(const view of ['overview','agent','evaluation','artifacts','guide']){
 const html=render(view);
 assert.ok(html.includes('<h1>'),view+' must have a page title');
 assert.ok(!html.includes('undefined'),view+' must not show missing values as undefined');
}
task.report={status:'stopped',grading_enabled:false,gates:{model_builds:{passed:false,detail:'API error'}},
  checks:{geometry:{domain:null}},diagnostic_score:{score:0,categories:{}},fidelity:{}};
task.evaluation={status:'supported',trusted:false,report:task.report,definition:{score:{maximum:100,applicable_points:70},rules:{equivalence_margin_pcm:150,interval_multiplier:1.96}}};
task.review={evidence_status:'contradictory',score:null,strict_correct:false};
vm.runInContext('data.tasks[0]='+JSON.stringify(task),context);
assert.ok(render('overview').includes('0,0 / 100'));
assert.ok(render('overview').includes('succès vérifié n’est pas établi'));
assert.ok(render('evaluation').includes('Indéterminé'));
assert.ok(render('evaluation').includes('Échec'));
assert.ok(render('evaluation').includes('API error'));
task.convergence=[{generation:1,k:1.4,entropy:5,active:false},{generation:2,k:1.5,entropy:5.1,active:true}];
task.report.comparison={interval_pcm:[-30,40],delta_pcm:5,margin_pcm:150,status:'agreement'};
vm.runInContext('data.tasks[0]='+JSON.stringify(task),context);
assert.ok(render('evaluation').includes('aria-label="Écart en k-effectif'));
assert.ok(render('evaluation').includes('Entropie en bits en fonction'));
const css=fs.readFileSync(path.join(__dirname,'../dashboard/static/style.css'),'utf8');
assert.ok(css.includes('@media(max-width:760px)'));
assert.ok(css.includes(':focus-visible'));
assert.ok(!source.includes('eval('));
if(process.argv[2]){
 const retained=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
 vm.runInContext('data='+JSON.stringify(retained)+'; mode="live"; filter="all";',context);
 for(const view of ['overview','agent','evaluation','artifacts','guide']){
   const html=render(view);
   assert.ok(html.includes('<h1>'));
   assert.ok(!html.includes('[object Object]'));
 }
 assert.ok(render('overview').includes('Tolérance de température (K)'));
 assert.ok(render('overview').includes('attendu <strong>1</strong>, observé <strong>10</strong>'));
 assert.ok(render('agent').includes('request-04.json'));
 assert.ok(render('agent').includes('request-05.json'));
 assert.ok(render('evaluation').includes('96.42857142857143'));
 console.log('Retained live-run templates passed: visible 1 K / 10 K defect, feedback requests 4 and 5, original score.');
}
console.log('Dashboard template checks passed: 5 views, missing/zero/failure, feedback, replay/filter, inert text, chart labels.');
const before = vm.runInContext('JSON.stringify(data)', context);
vm.runInContext("I18N.setLanguage('en')", context);
for(const view of ['overview','agent','evaluation','artifacts','guide']){
 const html=render(view);
 assert.ok(html.includes('<h1>'));
 assert.ok(!html.includes('[object Object]'));
}
assert.ok(render('evaluation').includes('Independent evaluation'));
assert.ok(render('guide').includes('Reading guide'));
assert.equal(vm.runInContext('fmt(1.5,1)', context), '1.5');
assert.equal(vm.runInContext("eventTitle({kind:'request',turn:4})", context), 'Request 4 sent to the model');
assert.equal(vm.runInContext("eventDetail({kind:'message',detail:'Conforme'})", context), 'Conforme');
assert.equal(vm.runInContext("pre('Évaluation')", context), '<pre>Évaluation</pre>');
assert.equal(vm.runInContext('JSON.stringify(data)', context), before);
for(const saved of [null,'en','fr','invalid']){
 let written;
 const c=vm.createContext({localStorage:{getItem:()=>saved,setItem:(key,value)=>{written=value}}});
 vm.runInContext(translations,c);
 assert.equal(vm.runInContext('I18N.language',c),saved==='fr'?'fr':'en');
 vm.runInContext("I18N.setLanguage('fr')",c);
 assert.equal(written,'fr');
}
const blocked=vm.createContext({localStorage:{getItem(){throw Error('blocked')},setItem(){throw Error('blocked')}}});
vm.runInContext(translations,blocked);
assert.equal(vm.runInContext('I18N.language',blocked),'en');
vm.runInContext("I18N.setLanguage('fr')",blocked);
assert.equal(vm.runInContext('I18N.language',blocked),'fr');
console.log('Bilingual checks passed: English default, French retained, persistence/fallback, locale formatting, unchanged evidence.');
const elements = {'content':{},'language-select':{}};
const shellLabel={dataset:{i18n:'Vue d’ensemble'}};
context.document.documentElement={};
context.document.getElementById=id=>elements[id];
context.document.querySelectorAll=selector=>selector==='[data-i18n]'?[shellLabel]:[];
vm.runInContext("view='guide'; busy=true; replayIndex=3;",context);
handlers.change({target:{id:'language-select',value:'fr'}});
assert.equal(context.document.documentElement.lang,'fr');
assert.equal(shellLabel.textContent,'Vue d’ensemble');
assert.ok(elements.content.innerHTML.includes('Guide de lecture'));
handlers.change({target:{id:'language-select',value:'en'}});
assert.equal(context.document.documentElement.lang,'en');
assert.equal(shellLabel.textContent,'Overview');
assert.ok(elements.content.innerHTML.includes('Reading guide'));
assert.equal(vm.runInContext('replayIndex',context),3);
assert.equal(vm.runInContext('JSON.stringify(data)',context),before);
console.log('Language selector handler passed: shell, current view, replay position and evidence preserved.');
const catalog=JSON.parse(fs.readFileSync(path.join(__dirname,'../observation_catalog.json'),'utf8'));
const planCases=[
 ['A','guided_construction','generic_coding_guided_construction_v1'],
 ['B','guided_boundaries','generic_coding_guided_boundaries_v3'],
 ['C','guided_boundaries_smoke','generic_coding_guided_boundaries_smoke_v1']
];
for(const language of ['en','fr']){
 vm.runInContext('I18N.setLanguage('+JSON.stringify(language)+')',context);
 for(const [letter,assistance,condition] of planCases){
   vm.runInContext('data.plan='+JSON.stringify({model:'test-model',assistance,condition,budgets:{model_requests:8,authoring_seconds:600,boundary_calls:2,smoke_calls:2}}),context);
   const descriptor=catalog.configurations.find(c=>c.id===letter);
   vm.runInContext('data.configuration='+JSON.stringify({status:'supported',definition:{configuration:descriptor,tools:catalog.tools.filter(t=>descriptor.tools.includes(t.id))}}),context);
   const banner=vm.runInContext('configurationBanner(task())',context);
   assert.ok(banner.includes('Configuration '+letter));
   assert.ok(banner.includes('test-model'));
   assert.ok(banner.includes('600 s'));
   assert.ok(banner.includes(language==='en'?'Allowed':'Autorisé'));
   for(const view of ['overview','agent','evaluation','artifacts','guide']){
     vm.runInContext('view='+JSON.stringify(view)+'; render()',context);
     assert.ok(elements.content.innerHTML.includes('Configuration '+letter));
   }
 }
}
vm.runInContext("I18N.setLanguage('en')",context);
for(const plan of [{},{assistance:'generic',condition:'generic_coding_v1'},
 {assistance:'guided_construction',condition:'generic_coding_guided_boundaries_smoke_v1'},
 {condition:'unknown<script>alert(1)</script>'}]){
 vm.runInContext('data.plan='+JSON.stringify(plan)+';data.configuration={status:"unsupported",definition:null}',context);
 const banner=vm.runInContext('configurationBanner(task())',context);
 assert.ok(banner.includes('Unknown configuration'));
 assert.ok(!banner.includes('<script>'));
}
vm.runInContext('data.configuration='+JSON.stringify({status:'supported',definition:{configuration:catalog.configurations[2],tools:catalog.tools}}),context);
assert.ok(vm.runInContext('configurationBanner(task())',context).includes('Configuration C'));
console.log('Configuration checks passed: A/B/C in both languages and all views; access versus records; unknown, legacy, conflicting and escaped identities.');
