'use strict';
(()=>{
const $=id=>document.getElementById(id),data=JSON.parse($('people-data').textContent);
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const safe=v=>{try{return new URL(v).protocol==='https:'?esc(v):'#';}catch{return '#';}};
const fieldNames={traffic:'交通研究 / 高校',insurance:'保险业',av:'AV 公司',other:'其他土木 / 高校',unknown:'现职待核验'};
const cohortNames={transport_stats:'交通研究 + 统计硕士',civil_stats:'其他土木 + 统计硕士',adjacent:'相近路线 · 不进入双学位统计'};
function card(p){return `<article class="panel person"><div class="meta"><span class="badge">${cohortNames[p.cohort]}</span><span>${p.current_confirmed?'公开任职记录可确认':'现职 / 时间范围待核验'}</span></div><h3>${esc(p.name)}</h3><p><strong>${esc(p.role)}</strong><br><span class="small">${esc(p.organization)}</span></p><div class="education">${p.education.map(esc).join('<br>')}</div><div class="tags">${p.skills.map(s=>`<span class="tag">${esc(s)}</span>`).join('')}</div><div style="margin-top:13px">${p.path.map(step=>`<div class="path-step"><span>${esc(step.period)}</span><span>${esc(step.label)}</span></div>`).join('')}</div><p class="small">${esc(p.note)}</p><div class="sources">${p.sources.map(s=>{const health=data.source_health?.[s.url];return `<a href="${safe(s.url)}" target="_blank" rel="noopener noreferrer">${esc(s.label)} ↗</a><span class="source-status">支持：${esc(s.supports)}${health?' · 自动检查：'+(health.status==='reachable_keywords_present'?'可访问、关键字存在':health.status==='needs_review'?'文字变化，需复核':'暂不可访问')+'（'+esc(health.checked_at.slice(0,10))+'）':''}</span>`;}).join('')}</div></article>`;}
function draw(){const cohort=$('cohort').value,rows=data.profiles.filter(p=>p.cohort!=='adjacent'&&(cohort==='dual'||p.cohort===cohort));const counts=Object.fromEntries(Object.keys(fieldNames).map(k=>[k,0]));for(const p of rows)counts[p.current_confirmed?p.field:'unknown']++;
 $('sample-note').textContent=`${rows.length} 位已核验学历组合 · ${rows.filter(p=>p.current_confirmed).length} 位有可确认的当前任职记录`;
 $('people-summary').innerHTML=Object.entries(fieldNames).map(([k,label])=>`<div class="panel"><span>${label}</span><b>${counts[k]}</b><div class="mini-bar" role="img" aria-label="${label}：样本 ${counts[k]} 人"><div class="mini-fill" style="width:${rows.length?counts[k]/rows.length*100:0}%"></div></div></div>`).join('');
 $('share-note').textContent=rows.length<10?'样本不足 10 人，暂不展示去向百分比。“保险 0 / AV 0”仅指本次已核验双学位样本，不能推断行业中无人。':`样本内比例（分母 ${rows.length} 人，含未知去向）：`+Object.entries(counts).map(([k,n])=>fieldNames[k]+' '+Math.round(n/rows.length*100)+'%').join('；')+'。便利样本，不代表总体。';
 $('people-grid').innerHTML=rows.map(card).join('')||'<p class="empty">当前人群尚无已核验案例。</p>';
 const roles=new Map();for(const p of rows.filter(p=>p.current_confirmed)){const members=roles.get(p.role)||[];members.push(p.name);roles.set(p.role,members);} $('roles').innerHTML=[...roles].sort((a,b)=>b[1].length-a[1].length).map(([role,members])=>`<tr><td>${esc(role)}</td><td>${members.length}</td><td>${members.map(esc).join('、')}</td></tr>`).join('')||'<tr><td colspan="3">现职资料不足，暂不排名。</td></tr>';
}
$('cohort').onchange=draw;$('adjacent-grid').innerHTML=data.profiles.filter(p=>p.cohort==='adjacent').map(card).join('');$('review-date').textContent=`人工证据核验日期：${data.reviewed_at}。范围：${data.scope}`;draw();
})();
