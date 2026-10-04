// Optional real-browser QA. Use an installed Playwright via DASHBOARD_PLAYWRIGHT_MODULE.
// No dependency is added to the dashboard. Point at the synthetic fixture server.
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {chromium}=require(process.env.DASHBOARD_PLAYWRIGHT_MODULE||'playwright');
const base=process.argv[2]||'http://127.0.0.1:8767';
const output=process.argv[3]||'scratch/dashboard-browser-qa';
fs.mkdirSync(output,{recursive:true});

(async()=>{
 const browser=await chromium.launch({headless:true,...(process.env.DASHBOARD_BROWSER_EXECUTABLE?{executablePath:process.env.DASHBOARD_BROWSER_EXECUTABLE}:{})});
 const context=await browser.newContext({viewport:{width:1440,height:1000}});
 const page=await context.newPage();const errors=[],policyErrors=[];
 page.on('pageerror',error=>errors.push(error.message));
 page.on('console',message=>{if(message.type()==='error'&&/Content Security Policy|violates.*directive/i.test(message.text()))policyErrors.push(message.text());});
 const waitRun=async(model,config,task)=>page.waitForFunction(({model,config,task})=>!busy&&data?.plan?.model===model&&data?.configuration?.definition?.configuration?.id===config&&data?.tasks?.[taskIndex]?.case===task,{model,config,task});
 try{
  await page.goto(base);await page.waitForFunction(()=>document.querySelector('#run-select').options.length>0&&!busy);
  assert.equal(await page.locator('#language-select').inputValue(),'en');
  await page.selectOption('#campaign-select','campaign-one');
  await page.selectOption('#model-select','model-one');
  await page.selectOption('#configuration-select','A');
  await page.selectOption('#case-select','task-two');await waitRun('model-one','A','task-two');
  assert.match(await page.locator('main').innerText(),/94.6/);
  // Rapid navigation with a delayed response must never relabel stale evidence.
  let release,started;
  const delayed=new Promise(resolve=>started=resolve);
  const gate=new Promise(resolve=>release=resolve);
  const routeHandler=async route=>{started();await gate;await route.continue();};
  const targetIndex=await page.evaluate(()=>navigationData.records.find(r=>r.campaign_id==='campaign-one'&&r.configuration==='A'&&r.case==='task-one').run);
  const delayedPattern='**/api/state?run='+targetIndex;
  await page.route(delayedPattern,routeHandler);
  await page.selectOption('#case-select','task-one');
  await Promise.race([delayed,new Promise((_,reject)=>setTimeout(()=>reject(Error('Expected navigation request was not sent')),5000))]);
  await page.selectOption('#configuration-select','B');release();
  await waitRun('model-one','B','task-one');await page.unroute(delayedPattern,routeHandler);
  assert.match(await page.locator('main').innerText(),/Not started/);
  assert.doesNotMatch(await page.locator('main').innerText(),/100\.0 \/ 100/);
  await page.selectOption('#model-select','model-two');await waitRun('model-two','C','task-one');
  // A legacy multi-task batch is navigated as separate task attempts.
  await page.selectOption('#campaign-select','');
  await page.selectOption('#case-select','legacy-two');await waitRun('model-one','A','legacy-two');
  assert.match(await page.locator('main').innerText(),/Legacy batch/);
  assert.equal(await page.locator('#run-select option').count(),1);
  // Every view renders in both languages; language persists across reload.
  for(const language of ['fr','en']){
   await page.selectOption('#language-select',language);
   for(const view of ['overview','agent','evaluation','artifacts','guide','campaign']){
    await page.click(`[data-view="${view}"]`);
    await page.waitForFunction(()=>!busy&&!campaignBusy);
    assert.equal(await page.locator('#error').isVisible(),false);
    assert.doesNotMatch(await page.locator('main').innerText(),/\[object Object\]|undefined/);
   }
  }
  await page.selectOption('#language-select','fr');await page.reload();
  await page.waitForFunction(()=>document.querySelector('#run-select').options.length>0&&!busy);
  assert.equal(await page.locator('#language-select').inputValue(),'fr');
  await page.selectOption('#language-select','en');
  // Campaign boundaries, planned counts, drilldown and individual navigation.
  await page.click('[data-view="campaign"]');await page.waitForFunction(()=>!campaignBusy&&campaignData);
  await page.selectOption('#study-select','campaign-one');
  assert.match(await page.locator('main').innerText(),/Synthetic resource stop/);
  await page.selectOption('#campaign-model','model-one');
  await page.click('[data-campaign-domain="materials"][data-campaign-config="A"]');
  await page.selectOption('#campaign-outcome','fail');
  const buttons=page.locator('[data-campaign-open]');assert.equal(await buttons.count(),1);
  await buttons.first().click();await waitRun('model-one','A','task-two');
  assert.match(await page.locator('main h1').innerText(),/evaluation/i);
  await page.click('[data-view="campaign"]');await page.waitForFunction(()=>!campaignBusy);
  await page.selectOption('#study-select','campaign-two');
  assert.doesNotMatch(await page.locator('#campaign-task').innerText(),/task-two/);
  assert.equal(await page.locator('#execution-navigation').isVisible(),false);
  await page.evaluate(()=>window.scrollTo(0,0));await page.waitForFunction(()=>scrollY===0);
  await page.screenshot({path:path.join(output,'campaign-desktop.png'),fullPage:true});
  await page.locator('#auto').uncheck();
  await page.selectOption('#study-select','campaign-one');
  await page.selectOption('#campaign-model','');
  assert.match(await page.locator('#campaign-chart-title').textContent(),/Number of successful runs/);
  assert.match(await page.locator('.campaign-chart svg .chart-legend').textContent(),/model-one.*model-two.*unresolved/);
  // The visible SVG legend must match each model's bars, including after filtering.
  await page.selectOption('#study-select','campaign-models');
  await page.selectOption('#campaign-model','');
  const legendColors=async()=>page.locator('.campaign-chart svg .chart-legend > g').evaluateAll(rows=>Object.fromEntries(rows.map(row=>[row.querySelector('text').textContent,row.querySelector('rect').getAttribute('fill')])));
  assert.match(await page.locator('#campaign-chart-title').textContent(),/Success rate/);
  const colors=await legendColors();
  assert.equal(colors['gpt-5.6-luna'],'#285bad');
  assert.equal(colors['gpt-5.6-sol'],'#99590c');
  const checkLegend=async()=>{
   await page.waitForFunction(()=>!campaignBusy&&!busy);
   const legend=page.locator('.campaign-chart svg .chart-legend');
   await legend.scrollIntoViewIfNeeded();assert.ok(await legend.isVisible());
   assert.ok(await legend.locator('text').evaluateAll(rows=>rows.every(row=>row.getBoundingClientRect().height>=10)),'Legend text must remain readable');
   const mapping=await legendColors();
   const bars=await page.locator('.campaign-chart svg > g:not(.chart-legend)').evaluateAll(rows=>rows.filter(row=>row.querySelector('title')).map(row=>({title:row.querySelector('title').textContent,fill:row.querySelector('rect').getAttribute('fill')})));
   assert.ok(bars.length>0);
   for(const bar of bars){
    const model=bar.title.split(' · ')[0];assert.equal(bar.fill,mapping[model]);assert.equal(bar.fill,colors[model]);
   }
   // Swatches and text occupy the SVG viewport, without overlapping the plot.
   assert.ok(await legend.evaluate(g=>{const svg=g.ownerSVGElement.viewBox.baseVal,b=g.getBBox();return b.x>=0&&b.y>=0&&b.x+b.width<=svg.width&&b.y+b.height<Number(g.nextElementSibling.getAttribute('y'));}));
  };
  for(const language of ['en','fr']){
   await page.selectOption('#language-select',language);
   await checkLegend();
   assert.ok((await legendColors())[language==='en'?'unresolved':'indéterminés']);
   await page.locator('.campaign-chart').screenshot({path:path.join(output,'model-legends-'+language+'.png')});
  }
  await page.selectOption('#campaign-model','gpt-5.6-sol');await checkLegend();
  assert.deepEqual(Object.keys(await legendColors()).sort(),['gpt-5.6-sol','indéterminés'].sort());
  await page.selectOption('#campaign-model','');
  await page.setViewportSize({width:390,height:844});await checkLegend();
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
  await page.locator('.campaign-chart').screenshot({path:path.join(output,'model-legends-mobile.png')});
  await page.setViewportSize({width:1440,height:1000});
  await page.selectOption('#language-select','en');
  await page.selectOption('#study-select','campaign-two');
  // Network failure retains evidence and displays a visible stale-data notice.
  await page.route('**/api/campaign',route=>route.abort());
  await page.evaluate(()=>refreshCampaign(true));
  assert.match(await page.locator('main').innerText(),/stale|périmées/);
  await page.unroute('**/api/campaign');await page.evaluate(()=>refreshCampaign(true));
  // Escaped task text, inert evidence artifacts, and keyboard focus.
  await page.click('[data-view="overview"]');await page.waitForFunction(()=>!busy);
  assert.equal(await page.locator('#execution-navigation').isVisible(),true);
  await page.locator('[data-key="prompt"] summary').click();
  assert.equal(await page.evaluate(()=>window.INJECTED),undefined);
  assert.equal(await page.locator('main img').count(),0);
  await page.keyboard.press('Tab');
  assert.ok(await page.evaluate(()=>document.activeElement!==document.body));
  // Narrow layout: no horizontal page overflow; navigation remains usable.
  await page.setViewportSize({width:390,height:844});
  for(const view of ['overview','agent','evaluation','artifacts','guide','campaign']){
   await page.click(`[data-view="${view}"]`);await page.waitForFunction(()=>!busy&&!campaignBusy);
   assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),view+' overflows mobile viewport');
  }
  await page.evaluate(()=>window.scrollTo(0,0));await page.waitForFunction(()=>scrollY===0);
  await page.screenshot({path:path.join(output,'campaign-mobile.png'),fullPage:true});
  assert.deepEqual(errors,[]);assert.deepEqual(policyErrors,[]);
  const result={status:'passed',browser:await browser.version(),checks:['cascade navigation','legacy batch','rapid delayed-response navigation','EN/FR six views','language persistence','campaign separation','matrix drilldown','stale network state','inert text','keyboard focus','390px mobile overflow','SVG model legends EN/FR','legend/bar color matching','stable filtered colors','mobile legend bounds','count-mode legend','no CSP violations'],screenshots:['campaign-desktop.png','campaign-mobile.png','model-legends-en.png','model-legends-fr.png','model-legends-mobile.png']};
  fs.writeFileSync(path.join(output,'result.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result));
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1});
