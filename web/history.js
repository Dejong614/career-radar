'use strict';
(()=>{
const $=id=>document.getElementById(id),data=JSON.parse($('history-data').textContent);
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmt=v=>v?new Date(v).toLocaleString('zh-CN'):'未知';
const names={traffic:'交通工程',insurance:'保险研发',av:'AV 研究'},colors={traffic:'#276349',insurance:'#ae623f',av:'#456d9e'};
const cities=['Seattle','Portland','Los Angeles','San Francisco','Raleigh','New York','Washington DC'];
const coords=[[-122.33,47.61],[-122.68,45.52],[-118.24,34.05],[-122.42,37.77],[-78.64,35.78],[-74.01,40.71],[-77.04,38.91]];
const months=[...new Set(data.frames.map(f=>f.observed_at.slice(0,7)))].sort();
let index=months.length-1,kind='job',timer=null;
$('month-slider').max=Math.max(0,months.length-1);$('month-slider').value=index;
function selectedFrame(){return data.frames.filter(f=>f.observed_at.startsWith(months[index])).at(-1);}
function values(frame,city){const v={...frame.counts[$('history-profile').value][kind][city]};if(kind==='job'&&!frame.traffic_jobs_collected)v.traffic=null;return v;}
function draw(){
 if(!months.length){$('snapshot-label').textContent='尚无真实历史快照。';return;}
 const frame=selectedFrame(),month=months[index],current=new Date().toISOString().slice(0,7),partial=month===current;
 $('month-label').textContent=month.replace('-',' 年 ')+' 月'+(partial?' · 部分月份':'');
 $('snapshot-label').textContent=`采用本月最后一次真实快照：${fmt(frame.observed_at)}；${data.frames.filter(f=>f.observed_at.startsWith(month)).length} 次观测。`;
 const warnings=[];if(kind==='job'&&!frame.traffic_jobs_collected)warnings.push('该月尚未采集交通全职，显示“未采集”，不当成 0。');if(frame.source_issues.length)warnings.push('当次存在失败或过期来源：'+frame.source_issues.join('、')+'；保留数据可能不完整。');
 $('history-warning').textContent=warnings.join(' ');$('history-warning').hidden=!warnings.length;
 // Fixed scale across all observed frames under this same type and scope.
 const max=Math.max(1,...data.frames.flatMap(f=>cities.map(c=>Object.values(values(f,c)).reduce((a,b)=>a+(b||0),0))));
 const ceiling=Math.ceil(max/10)*10;
 $('city-bars').innerHTML=cities.map(city=>{const row=values(frame,city),total=Object.values(row).reduce((a,b)=>a+(b||0),0);return `<div class="city-row"><span>${city==='San Francisco'?'SF Bay Area':city}</span><div class="city-stacked">${Object.entries(row).map(([t,n])=>n===null?'':`<div class="city-segment ${t}-color" style="width:${n/ceiling*100}%" title="${names[t]} ${n} 个">${n>=3?'<span>'+n+'</span>':''}</div>`).join('')}</div><span class="city-total">${total}${row.traffic===null?'*':''}</span><span class="city-counts">${Object.entries(row).map(([t,n])=>names[t]+' '+(n===null?'未采集':n)).join(' · ')}</span></div>`;}).join('');
 $('bar-scale').textContent=`共同长度尺度：0—${ceiling} 个（所有月份固定）；* 合计不含未采集方向。`;
 $('city-table').innerHTML=cities.map(c=>{const row=values(frame,c);return `<tr><td>${c}</td>${Object.values(row).map(n=>`<td>${n===null?'未采集':n}</td>`).join('')}<td>${Object.values(row).reduce((a,b)=>a+(b||0),0)}${row.traffic===null?'（部分）':''}</td></tr>`;}).join('');
 const marks=cities.map((city,i)=>{const [lon,lat]=coords[i],x=30+(lon+125)/59*780,y=20+(50-lat)/26*350,row=values(frame,city),total=Object.values(row).reduce((a,b)=>a+(b||0),0),r=8+Math.sqrt(total/max)*14;let angle=-Math.PI/2;const slices=Object.entries(row).filter(([,n])=>n>0).map(([t,n])=>{const start=angle,end=angle+n/(total||1)*Math.PI*2;angle=end;if(n===total)return `<circle r="${r}" fill="${colors[t]}"/>`;return `<path d="M0,0 L${r*Math.cos(start)},${r*Math.sin(start)} A${r},${r} 0 ${end-start>Math.PI?1:0} 1 ${r*Math.cos(end)},${r*Math.sin(end)} Z" fill="${colors[t]}"/>`;}).join('');const dx=i===5?12:i===6?-130:18;const dy=i===0?-14:i===1?29:i===2?24:i===3?-20:i===5?-18:i===6?17:15;return `<g transform="translate(${x},${y})"><title>${city}：${Object.entries(row).map(([t,n])=>names[t]+(n===null?'未采集':n)).join('，')}</title>${slices||'<circle r="5" fill="#a8b7a0"/>'}<text x="${dx}" y="${dy}" font-size="12">${city==='San Francisco'?'SF Bay Area':city}</text><text class="point-total" x="${dx}" y="${dy+22}">${total}${row.traffic===null?'*':''}</text></g>`;}).join('');
 $('metro-points').innerHTML=marks;
}
function stop(){clearInterval(timer);timer=null;$('history-play').textContent='播放 ▶';}
$('month-slider').oninput=e=>{stop();index=Number(e.target.value);draw();};
$('history-profile').onchange=draw;
$('history-kind').onclick=e=>{const b=e.target.closest('button[data-kind]');if(!b)return;kind=b.dataset.kind;for(const v of $('history-kind').querySelectorAll('button'))v.setAttribute('aria-pressed',String(v===b));draw();};
$('history-play').onclick=()=>{if(timer){stop();return;}if(index===months.length-1)index=0;$('month-slider').value=index;draw();if(months.length<2)return;$('history-play').textContent='暂停 Ⅱ';timer=setInterval(()=>{index++;$('month-slider').value=index;draw();if(index===months.length-1)stop();},1500);};
$('event-table').innerHTML=data.events.map(e=>`<tr><td>${esc(e.company)}<br>${esc(e.title)}</td><td>${e.event==='closed'?'确认关闭':'重新开放'}</td><td>${fmt(e.occurred_at)}<br><span class="small">${e.basis==='archived_snapshot'?'从历史快照恢复':'采集器记录'}</span></td><td>${e.event==='closed'?fmt(e.lower_bound)+' — '+fmt(e.upper_bound):'—'}</td></tr>`).join('')||'<tr><td colspan="4">尚无可核验的关闭 / 重开事件。未知时间不会自动填成今天。</td></tr>';
$('history-provenance').textContent=`${data.frames.length} 次真实观测；最早 ${fmt(data.frames[0]?.observed_at)}。`;
draw();
})();
