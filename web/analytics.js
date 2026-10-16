/* Shared pure metrics: a job contributes at most once to a skill or pair. */
(function(root){
function analyze(jobs, tracks=['traffic','insurance','av']) {
  const counts=Object.fromEntries(tracks.map(t=>[t,new Map()]));
  const sizes=Object.fromEntries(tracks.map(t=>[t,jobs.filter(j=>j.track===t).length]));
  const totals=new Map(),pairs=new Map();
  for(const job of jobs){
    const names=[...new Set(job.skills.map(s=>s.name))].sort();
    for(const skill of names){counts[job.track].set(skill,(counts[job.track].get(skill)||0)+1);totals.set(skill,(totals.get(skill)||0)+1);}
    for(let i=0;i<names.length;i++) for(let k=i+1;k<names.length;k++){
      const key=JSON.stringify([names[i],names[k]]);
      const pair=pairs.get(key)||{a:names[i],b:names[k],count:0,tracks:new Set()};
      pair.count++;pair.tracks.add(job.track);pairs.set(key,pair);
    }
  }
  const skillRanks=Object.fromEntries(tracks.map(t=>[t,[...counts[t]].map(([name,count])=>({name,count,rate:count/sizes[t]})).sort((a,b)=>b.count-a.count||a.name.localeCompare(b.name))]));
  const cross=[...totals].map(([name,count])=>{
    const rates=Object.fromEntries(tracks.map(t=>[t,sizes[t]?(counts[t].get(name)||0)/sizes[t]:null]));
    const coverage=tracks.filter(t=>(counts[t].get(name)||0)>0).length;
    const available=Object.values(rates).filter(v=>v!==null);
    return {name,count,rates,coverage,score:available.reduce((a,b)=>a+b,0)/(available.length||1)};
  }).filter(s=>s.coverage>=2).sort((a,b)=>b.coverage-a.coverage||b.score-a.score||b.count-a.count||a.name.localeCompare(b.name));
  const pairRanks=[...pairs.values()].filter(p=>p.count>=3&&p.tracks.size>=2).map(p=>({...p,tracks:[...p.tracks],jaccard:p.count/(totals.get(p.a)+totals.get(p.b)-p.count)})).sort((a,b)=>b.jaccard-a.jaccard||b.count-a.count||a.a.localeCompare(b.a));
  return {sizes,skillRanks,cross,pairs:pairRanks};
}
if(typeof module!=='undefined'&&module.exports) module.exports={analyze};
else root.CareerAnalytics={analyze};
})(typeof window==='undefined'?globalThis:window);
