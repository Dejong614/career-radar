'use strict';
const $=id=>document.getElementById(id);
const escapeHTML=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const safeURL=v=>{try{const u=new URL(v);return u.protocol==='https:'?escapeHTML(u.href):'#';}catch{return '#';}};
const fmt=v=>v?new Date(v).toLocaleString('zh-CN',{year:'numeric',month:'short',day:'numeric',hour:'2-digit',minute:'2-digit'}):'未公开';
const pct=v=>v===null?'—':`${Math.round(v*100)}%`;
const labels={traffic:'交通工程',insurance:'保险研发',av:'自动驾驶研究'};
let data=JSON.parse($('snapshot').textContent),track='all',page=1,networkWarning='';
const perPage=12;
let kind='job';
function kindOf(j){return j.kind||(/intern|co[ -]?op/i.test(j.title+' '+j.employment)?'intern':/contract|temporary|part.time/i.test(j.employment)?'other':'unspecified');}
function subject(j){return j.background_match||{level:'adjacent',reasons:[],flags:[]};}
function baseJobs(){const query=$('search').value.trim().toLowerCase(),city=$('city').value,scope=$('profile').value;return data.jobs.filter(j=>
  (kind==='intern'?kindOf(j)==='intern':['job','unspecified'].includes(kindOf(j)))&&
  (scope==='all'||scope==='core'&&subject(j).level==='core'||scope==='focused'&&subject(j).level!=='adjacent')&&
  (city==='all'?j.metros.some(m=>m!=='US Remote')||$('remote').checked:j.metros.includes(city))&&
  ($('remote').checked||!j.metros.every(m=>m==='US Remote'))&&
  (!query||[j.title,j.company,j.location,...j.skills.map(s=>s.name)].join(' ').toLowerCase().includes(query)));
}
function matchBlock(j){const m=subject(j);return `<div class="match-note"><span class="tag ${m.level}">${{core:'重点研究匹配',related:'相关主题',adjacent:'相邻工程方向'}[m.level]}</span> ${kindOf(j)==='unspecified'?'<span class="small">雇主未注明岗位类型</span>':''}${m.reasons.map(r=>`<p>${escapeHTML(r.label)}：${escapeHTML(r.evidence)}</p>`).join('')}${m.flags.map(f=>`<p class="warn">${escapeHTML(f)}</p>`).join('')}</div>`;}
function render(){
 const base=baseJobs(),a=CareerAnalytics.analyze(base),top=Number($('top').value);
 $('metrics').innerHTML=Object.entries(labels).map(([t,label])=>`<div class="metric"><span class="label">${label}</span><b>${a.sizes[t]}</b><span class="hint">${kind==='intern'?'INTERNSHIP / CO-OP':'研究与专业职位'} · 当前筛选</span></div>`).join('');
 const rows=base.filter(j=>track==='all'||j.track===track);
 const sort=$('sort').value;
 rows.sort((a,b)=>sort==='match'?(({core:3,related:2,adjacent:1}[subject(b).level]-{core:3,related:2,adjacent:1}[subject(a).level])||(Date.parse(b.first_seen)||0)-(Date.parse(a.first_seen)||0)):sort==='company'?a.company.localeCompare(b.company):sort==='posted'?(Date.parse(b.posted_at)||0)-(Date.parse(a.posted_at)||0):(Date.parse(b.first_seen)||0)-(Date.parse(a.first_seen)||0));
 const pages=Math.max(1,Math.ceil(rows.length/perPage));page=Math.min(page,pages);
 $('resultcount').textContent=`${rows.length} 个职位 · ${new Set(rows.map(j=>j.company)).size} 家公司`;
 $('jobs').innerHTML=rows.slice((page-1)*perPage,page*perPage).map(job=>`<article class="job"><div><div class="meta"><span class="badge ${job.track}">${labels[job.track]}</span><strong>${escapeHTML(job.company)}</strong><span>${escapeHTML(job.employment)}</span>${job.pending_closure?'<span class="warn">上次未检出，待再次确认</span>':''}</div><h3><a href="${safeURL(job.url)}" target="_blank" rel="noopener noreferrer">${escapeHTML(job.title)} ↗</a></h3>${matchBlock(job)}<div class="tags">${job.skills.slice(0,8).map(s=>`<span class="tag">${escapeHTML(s.name)}</span>`).join('')||'<span class="small">未命中技能词典，请查看原始描述</span>'}</div>${job.skills.length?`<details><summary>技能证据 · ${job.skills.length} 项</summary>${job.skills.map(s=>`<div class="evidence"><b>${escapeHTML(s.name)}</b> · ${{required:'要求段落',preferred:'优先段落',mentioned:'描述提及'}[s.level]}<q>${escapeHTML(s.evidence)}</q></div>`).join('')}</details>`:''}</div><div class="job-side"><span>${escapeHTML(job.location)}</span><span>发布：${fmt(job.posted_at)}</span><span>首次发现：${fmt(job.first_seen)}</span>${job.application_deadline?`<span>雇主截止：${fmt(job.application_deadline)}</span>`:''}<a href="${safeURL(job.url)}" target="_blank" rel="noopener noreferrer">查看雇主职位 →</a></div></article>`).join('')||'<div class="empty">当前筛选下没有匹配职位。可以扩大城市范围、包含远程，或查看下方来源状态。</div>';
 $('prev').disabled=page<=1;$('next').disabled=page>=pages;$('page').textContent=`${page} / ${pages}`;
 $('skillgrid').innerHTML=Object.entries(labels).map(([t,label])=>`<div class="panel skill-panel ${t}"><h3>${label}</h3><p>${a.sizes[t]} 个职位 · ${base.filter(j=>j.track===t&&j.skills.length).length} 个命中技能 · TOP ${top}</p>${a.skillRanks[t].slice(0,top).map(s=>`<div class="barrow"><div class="barlabels"><span>${escapeHTML(s.name)}</span><span>${s.count} 职位 · ${pct(s.rate)}</span></div><div class="track" role="img" aria-label="${escapeHTML(s.name)} ${s.count} 个职位，${pct(s.rate)}"><div class="fill" style="width:${s.rate*100}%"></div></div></div>`).join('')||'<p class="empty">样本不足，暂无技能排名。</p>'}</div>`).join('');
 $('cross').innerHTML=a.cross.slice(0,top).map(s=>`<tr><td>${escapeHTML(s.name)}</td>${Object.keys(labels).map(t=>`<td><span class="heat" style="background:rgba(139,181,85,${s.rates[t]===null?.04:.08+s.rates[t]*.5})">${pct(s.rates[t])}</span></td>`).join('')}<td>${s.coverage}/3</td></tr>`).join('')||'<tr><td colspan="5">至少两个方向有相同技能后显示。— 表示该方向无样本。</td></tr>';
 $('pairs').innerHTML=a.pairs.slice(0,top).map((p,i)=>`<div class="pair"><span class="rank">${String(i+1).padStart(2,'0')}</span><span>${escapeHTML(p.a)} + ${escapeHTML(p.b)}<br><small>${p.count} 个同现职位 · ${p.tracks.length} 个方向</small></span><b>${pct(p.jaccard)}</b></div>`).join('')||'<p class="empty">暂无满足同现 ≥ 3 个职位且跨 ≥ 2 个方向的技能搭配。</p>';
 renderStatus();
}
function renderStatus(){
 const stale=s=>!s.last_success||Date.now()-Date.parse(s.last_success)>36*3600*1000;
 const failures=data.sources.filter(s=>s.error||stale(s));
 const successes=data.sources.filter(s=>s.last_success);
 const latest=successes.map(s=>s.last_success).sort().at(-1);
 $('freshness').textContent=`最近成功采集：${fmt(latest)} · 按本地时间`;
 $('banner').textContent=[networkWarning,failures.length?`${failures.length}/${data.sources.length} 个来源失败、未采集或超过 36 小时；对应职位可能不完整或已过期，请查看来源状态。`:''].filter(Boolean).join(' ');
 $('coverage').textContent=`${successes.length}/${data.sources.length} 个来源曾采集成功；快照生成于 ${fmt(data.generated_at)}。统计范围限已配置雇主。`;
 $('sourcegrid').innerHTML=data.sources.map(s=>`<div class="source"><a href="${safeURL(s.homepage)}" target="_blank" rel="noopener noreferrer">${escapeHTML(s.company)} ↗</a> <span class="${s.error||stale(s)?'warn':'ok'}">${s.error?'采集失败':stale(s)?'未采集 / 已过期':'采集成功'}</span><small>${labels[s.track]} · ${escapeHTML(s.provider)}<br>成功：${fmt(s.last_success)}<br>检索 ${s.scanned||0} · 匹配 ${s.matched||0}${s.coverage_note?`<br>${escapeHTML(s.coverage_note)}`:''}${s.error?`<br>${escapeHTML(s.error)}`:''}</small></div>`).join('');
}
$('kind-switch').addEventListener('click',event=>{const b=event.target.closest('button[data-kind]');if(!b)return;kind=b.dataset.kind;page=1;for(const button of $('kind-switch').querySelectorAll('button'))button.setAttribute('aria-pressed',String(button===b));render();});
function init(){const params=new URLSearchParams(location.search);if(['traffic','insurance','av'].includes(params.get('track'))){track=params.get('track');for(const button of $('tabs').querySelectorAll('button'))button.setAttribute('aria-pressed',String(button.dataset.track===track));}for(const city of data.metros){const option=document.createElement('option');option.value=city;option.textContent=city;$('city').append(option);}render();}
for(const id of ['search','city','sort','profile','remote','top']) $(id).addEventListener(id==='search'?'input':'change',()=>{page=1;render();});
$('tabs').addEventListener('click',event=>{const button=event.target.closest('button[data-track]');if(!button)return;track=button.dataset.track;page=1;for(const b of $('tabs').querySelectorAll('button'))b.setAttribute('aria-pressed',String(b===button));render();});
$('reset').onclick=()=>{$('search').value='';$('city').value='all';$('profile').value='focused';$('remote').checked=false;$('sort').value='match';track='all';page=1;for(const b of $('tabs').querySelectorAll('button'))b.setAttribute('aria-pressed',String(b.dataset.track==='all'));render();};
$('prev').onclick=()=>{page--;render();$('opportunities').scrollIntoView({behavior:'smooth'});};
$('next').onclick=()=>{page++;render();$('opportunities').scrollIntoView({behavior:'smooth'});};
async function refresh(){if(location.protocol==='file:')return;try{const response=await fetch(`data/jobs.json?t=${Date.now()}`,{cache:'no-store'});if(!response.ok)throw Error('HTTP '+response.status);const fresh=await response.json();if(![1,2].includes(fresh.schema_version)||!Array.isArray(fresh.jobs)||!Array.isArray(fresh.sources))throw Error('Invalid snapshot');data=fresh;networkWarning='';render();}catch{networkWarning='无法读取最新快照，正在显示网页内嵌的已有数据。';renderStatus();}}
const analyticsScript=document.createElement('script');analyticsScript.src='web/analytics.js';analyticsScript.onload=()=>{init();refresh();setInterval(refresh,5*60*1000);};analyticsScript.onerror=()=>{$('banner').textContent='分析模块无法加载，请刷新页面。';};document.head.append(analyticsScript);
