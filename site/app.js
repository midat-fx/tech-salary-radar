"use strict";
// Радар навыков и зарплат — dashboard client (reads site/data/*.json).

const C = {acc:"#2DD4A7", s2:"#4E9CF5", s3:"#F5B950", neg:"#F47067", bd:"#262D37", tx2:"#8B949E"};
const RU_SEN = {junior:"Джуниор", mid:"Мидл", senior:"Сеньор", "staff+":"Стафф+", unspecified:"Без уровня"};
const state = {region:"all", seniority:"all"};
let DATA = {}, META = {}, TS = [], charts = {};

const $ = (id) => document.getElementById(id);
const median = (a) => { if(!a.length) return null; const s=[...a].sort((x,y)=>x-y); const m=s.length>>1;
  return s.length%2 ? s[m] : (s[m-1]+s[m])/2; };
const quant = (a,q) => { if(!a.length) return null; const s=[...a].sort((x,y)=>x-y);
  return s[Math.min(s.length-1, Math.floor(q*s.length))]; };
const kUSD = (v) => v==null ? "—" : "$"+Math.round(v/1000)+"K";
const nfmt = (v) => (v||0).toLocaleString("ru-RU").replace(/,/g," ");

// row = [region, seniority, is_remote, is_mgmt, company_idx, salary_mid_usd, skills, is_new]
const R={reg:0, sen:1, rem:2, mgmt:3, co:4, sal:5, sk:6, new:7};

function filtered(){
  return DATA.rows.filter(r=>{
    if(state.region==="remote"){ if(r[R.rem]!==1) return false; }
    else if(state.region!=="all" && r[R.reg]!==state.region) return false;
    if(state.seniority!=="all" && r[R.sen]!==state.seniority) return false;
    return true;
  });
}
const salaryRows = (rows) => rows.filter(r=>r[R.mgmt]!==1 && r[R.sal]!=null);

function fresh(){
  const el=$("freshness"); if(!META.updated_at){el.textContent="нет данных";return;}
  const ageH=(Date.now()-new Date(META.updated_at))/3.6e6;
  if(ageH>36){el.textContent="обновление задерживается";el.classList.add("warn");}
  else{const t=new Date(META.updated_at); el.textContent="данные обновлены "+t.toISOString().slice(11,16);}
}

function hero(){
  const rows=filtered(), sal=salaryRows(rows).map(r=>r[R.sal]);
  const med=median(sal);
  $("t-median").textContent=kUSD(med);
  $("t-median-mo").textContent = med? "(~"+kUSD(med/12)+"/мес)" : "";
  $("t-jobs").textContent=nfmt(rows.length);
  $("t-new").textContent=nfmt(rows.filter(r=>r[R.new]===1).length);
  const sp=(META.skill_premium||[])[0];
  $("t-skill").textContent = sp ? sp.skill+" +"+sp.premium_pct+"%" : "—";
}

function newChart(id, cfg){ if(charts[id])charts[id].destroy(); charts[id]=new Chart($(id), cfg); }
function empty(id, on, msg){ const e=$(id); e.hidden=!on; if(on)e.textContent=msg||"Радар набирает данные";
  const cv=$(id.replace("e","c")); if(cv)cv.style.visibility=on?"hidden":"visible"; }
const axis = (extra={}) => Object.assign({grid:{color:C.bd}, ticks:{color:C.tx2}}, extra);
const NOLEG = {plugins:{legend:{display:false}}};

function chartSalaryDist(){
  const sal=salaryRows(filtered()).map(r=>r[R.sal]);
  empty("e1", sal.length<30, "Мало вакансий с указанной вилкой в этом срезе");
  $("c1-title").textContent = "Сколько платят в tech-найме"+(state.region!=="all"?" · "+state.region.toUpperCase():"");
  $("c1-meth").textContent = "по "+sal.length+" вакансиям с вилкой · медиана · gross annual USD";
  if(sal.length<30){ if(charts.c1)charts.c1.destroy(); return; }
  const step=25000, max=400000, nb=max/step, labels=[], counts=new Array(nb+1).fill(0);
  for(let i=0;i<nb;i++)labels.push("$"+(i*step/1000)+"–"+((i+1)*step/1000)+"K");
  labels.push("$400K+");
  sal.forEach(v=>{ const b=v>=max?nb:Math.floor(v/step); counts[b]++; });
  const med=median(sal), p25=quant(sal,.25), p75=quant(sal,.75);
  const ann=(v,c,lbl)=>({type:"line",xMin:v/step,xMax:v/step,borderColor:c,borderWidth:1.5,
    borderDash:lbl==="медиана"?[]:[4,4],label:{display:true,content:lbl,color:c,position:"start",font:{size:10}}});
  newChart("c1",{type:"bar",data:{labels,datasets:[{data:counts,backgroundColor:C.acc+"cc"}]},
    options:{maintainAspectRatio:false,scales:{x:axis({ticks:{color:C.tx2,maxRotation:60,minRotation:0,autoSkip:true}}),y:axis({beginAtZero:true})},
      plugins:{legend:{display:false},annotation:{annotations:{
        m:ann(Math.min(med,max),C.acc,"медиана"),a:ann(Math.min(p25,max),C.tx2,"p25"),b:ann(Math.min(p75,max),C.tx2,"p75")}}}}});
}

function chartBySeniority(){
  const order=["junior","mid","senior","staff+","unspecified"];
  // region filter applies; grade select does not cut this chart (all grades shown, active highlighted)
  const base=DATA.rows.filter(r=> state.region==="remote"?r[R.rem]===1 : (state.region==="all"||r[R.reg]===state.region));
  const meds=order.map(g=>{ const a=base.filter(r=>r[R.sen]===g && r[R.mgmt]!==1 && r[R.sal]!=null).map(r=>r[R.sal]);
      return {g,med:median(a),n:a.length}; }).filter(m=>m.n>=10 && m.med!=null);   // hide thin buckets
  empty("e2", meds.length<1, "Мало данных о зарплатах по грейдам");
  if(meds.length<1){ if(charts.c2)charts.c2.destroy(); return; }
  newChart("c2",{type:"bar",data:{labels:meds.map(m=>[RU_SEN[m.g],"n="+m.n]),datasets:[{
      data:meds.map(m=>m.med), backgroundColor:meds.map(m=>m.g===state.seniority?C.acc:C.s2+"aa")}]},
    options:{maintainAspectRatio:false,...NOLEG,
      scales:{x:axis(),y:axis({beginAtZero:true,ticks:{color:C.tx2,callback:v=>kUSD(v)}})},
      plugins:{legend:{display:false},tooltip:{callbacks:{label:(c)=>kUSD(c.raw)+" · n="+meds[c.dataIndex].n}}}}});
}

function chartPremium(){
  const sp=(META.skill_premium||[]).slice(0,10);
  empty("e3", sp.length<1, "Премия навыка появится, когда LLM разметит вакансии (этап извлечения навыков идёт)");
  if(sp.length<1){ if(charts.c3)charts.c3.destroy(); return; }
  // CI crossing zero = not statistically distinguishable from "no premium" -> dimmed bar
  const solid = (s) => !(s.ci_lo != null && s.ci_lo <= 0);
  newChart("c3",{type:"bar",data:{labels:sp.map(s=>s.skill),datasets:[{data:sp.map(s=>s.premium_pct),
      backgroundColor:sp.map(s=>solid(s)?C.acc+"cc":C.acc+"44")}]},
    options:{indexAxis:"y",maintainAspectRatio:false,...NOLEG,
      scales:{x:axis({beginAtZero:true,ticks:{color:C.tx2,callback:v=>"+"+v+"%"}}),y:axis()},
      plugins:{legend:{display:false},tooltip:{callbacks:{label:(c)=>{const s=sp[c.dataIndex];
        const ci = (s.ci_lo!=null&&s.ci_hi!=null) ? " · 95% CI ["+s.ci_lo+"%, "+s.ci_hi+"%]" : "";
        const warn = solid(s) ? "" : " · статистически незначимо";
        return "С "+s.skill+": "+kUSD(s.median_with_usd)+" ("+s.n+" вак.) · премия внутри страт +"+s.premium_pct+"%"+ci+warn;}}}}}});
}

function chartRequired(){
  const rows=filtered().filter(r=>Array.isArray(r[R.sk]));
  empty("e4", rows.length<100, "Навыки ещё извлекаются из текстов вакансий");
  if(rows.length<100){ if(charts.c4)charts.c4.destroy(); return; }
  const cnt={}; rows.forEach(r=>r[R.sk].forEach(i=>{cnt[i]=(cnt[i]||0)+1;}));
  const top=Object.entries(cnt).sort((a,b)=>b[1]-a[1]).slice(0, window.innerWidth<480?10:15);
  newChart("c4",{type:"bar",data:{labels:top.map(([i])=>DATA.skills[i]),
      datasets:[{data:top.map(([,n])=>Math.round(1000*n/rows.length)/10),backgroundColor:C.s2+"cc"}]},
    options:{indexAxis:"y",maintainAspectRatio:false,...NOLEG,
      scales:{x:axis({beginAtZero:true,ticks:{color:C.tx2,callback:v=>v+"%"}}),y:axis()},
      plugins:{legend:{display:false}}}});
}

function chartWhere(){
  const bySen=(rows)=> state.seniority==="all"?rows:rows.filter(r=>r[R.sen]===state.seniority);
  const groups=[["US","us"],["EU","eu"],["Другие","other"]].map(([lbl,v])=>{
    const a=bySen(DATA.rows.filter(r=>r[R.reg]===v && r[R.mgmt]!==1 && r[R.sal]!=null)).map(r=>r[R.sal]);
    return {lbl,med:median(a),n:a.length};});
  const rem=bySen(DATA.rows.filter(r=>r[R.rem]===1 && r[R.mgmt]!==1 && r[R.sal]!=null)).map(r=>r[R.sal]);
  const ons=bySen(DATA.rows.filter(r=>r[R.rem]!==1 && r[R.mgmt]!==1 && r[R.sal]!=null)).map(r=>r[R.sal]);
  const all=[...groups,{lbl:"Remote",med:median(rem),n:rem.length},{lbl:"Офис",med:median(ons),n:ons.length}]
    .filter(g=>g.n>=10);
  empty("e5", all.length<1, "Мало вакансий с вилкой по регионам");
  if(all.length<1){ if(charts.c5)charts.c5.destroy(); return; }
  newChart("c5",{type:"bar",data:{labels:all.map(g=>g.lbl),datasets:[{data:all.map(g=>g.med),
      backgroundColor:[C.acc,C.s2,C.s3,C.acc,C.s2].map(c=>c+"cc")}]},
    options:{maintainAspectRatio:false,...NOLEG,
      scales:{x:axis(),y:axis({beginAtZero:true,ticks:{color:C.tx2,callback:v=>kUSD(v)}})},
      plugins:{legend:{display:false},tooltip:{callbacks:{label:(c)=>kUSD(c.raw)+" · n="+all[c.dataIndex].n}}}}});
}

function chartPulse(){
  empty("e6", TS.length<1, "Радар только начал собирать историю");
  if(TS.length<1){ if(charts.c6)charts.c6.destroy(); return; }
  const enoughMed = TS.filter(d=>d.median_usd!=null).length>=7;
  const ds=[{type:"line",label:"активные",data:TS.map(d=>d.active),borderColor:C.acc,backgroundColor:C.acc+"22",fill:true,yAxisID:"y",tension:.3}];
  if(enoughMed)ds.push({type:"line",label:"медиана",data:TS.map(d=>d.median_usd),borderColor:C.s3,yAxisID:"y1",tension:.3});
  newChart("c6",{data:{labels:TS.map(d=>d.date.slice(5)),datasets:ds},
    options:{maintainAspectRatio:false,
      scales:{x:axis(),y:axis({position:"left",beginAtZero:true}),
        y1:{display:enoughMed,position:"right",grid:{drawOnChartArea:false},ticks:{color:C.tx2,callback:v=>kUSD(v)}}},
      plugins:{legend:{labels:{color:C.tx2}}}}});
}

function employers(){
  const el=$("employers"); el.innerHTML="";
  (META.top_companies||[]).forEach(c=>{
    const a=document.createElement("a"); a.className="chip"; a.href=c.url; a.target="_blank"; a.rel="noopener";
    a.innerHTML=c.company+"<b>"+c.n+"</b>"; el.appendChild(a);
  });
}

function footer(){
  $("f-attr").textContent=META.attribution||"";
  $("f-salary").textContent=META.salary_note||"";
  if(META.fx&&META.fx.date)$("f-fx").textContent="Курсы на "+META.fx.date+" (base USD)"+(META.fx.stale?" · устарели":"");
  $("f-run").textContent="радар работает "+(META.days_collected||0)+" дн. · "+(META.companies_tracked||0)+" компаний";
  document.title="Радар навыков и зарплат: медиана "+kUSD(median(salaryRows(DATA.rows).map(r=>r[R.sal])))+" в tech-найме";
}

function renderAll(){ hero(); chartSalaryDist(); chartBySeniority(); chartPremium(); chartRequired(); chartWhere(); chartPulse(); }

function wire(){
  $("seg-region").addEventListener("click",(e)=>{ const b=e.target.closest("button"); if(!b)return;
    [...e.currentTarget.children].forEach(x=>x.classList.remove("on")); b.classList.add("on");
    state.region=b.dataset.v; renderAll(); });
  $("sel-seniority").addEventListener("change",(e)=>{ state.seniority=e.target.value; renderAll(); });
}

async function boot(){
  if(window["chartjs-plugin-annotation"]) Chart.register(window["chartjs-plugin-annotation"]);
  Chart.defaults.color=C.tx2; Chart.defaults.font.family="Inter,system-ui,sans-serif";
  try{
    [DATA, META, TS] = await Promise.all([
      fetch("data/latest.json").then(r=>r.json()),
      fetch("data/meta.json").then(r=>r.json()),
      fetch("data/timeseries.json").then(r=>r.json()),
    ]);
  }catch(e){ console.error("data load failed", e); return; }
  fresh(); wire(); employers(); footer(); renderAll();
}
boot();
