'use strict';
const $ = id => document.getElementById(id);
let token = sessionStorage.getItem('bsim-admin-token') || '';
function readAccessLink() {
  const fragment = new URLSearchParams(location.hash.slice(1));
  if (fragment.has('token')) {
    token = fragment.get('token'); sessionStorage.setItem('bsim-admin-token', token);
    history.replaceState(null, '', location.pathname); notice('');
  }
}
readAccessLink();
window.addEventListener('hashchange', readAccessLink);
let state = null, truth = [], busy = false, demoRunning = false, bounds = 2200, center = [0, 0], selected = null, eventSignature = '', polling = false;
const phaseNames = {idle:'空闲',preparing:'准备中',countdown:'倒计时',ready:'接口就绪',entered:'运行中',ended:'已结束'};
const reasonNames = {user_exit:'主动退出',manual_abort:'手工中止',real_timeout:'现实时间到期',virtual_timeout:'虚拟时间到期'};
for (let i=1;i<=20;i++) { const opt = document.createElement('option'); opt.value=i; opt.textContent=`频道 ${String(i).padStart(2,'0')}`; $('channel').append(opt); }
function notice(message) { $('notice').textContent=message; $('notice').hidden=!message; }
async function api(path, data) {
  const response = await fetch(path, {method:data===undefined?'GET':'POST',headers:{Authorization:`Bearer ${token}`,'Content-Type':'application/json'},body:data===undefined?undefined:JSON.stringify(data),cache:'no-store'});
  const result=await response.json(); if (!response.ok) throw new Error(result.error||`HTTP ${response.status}`); return result;
}
function fmt(n,places=0) { return Number(n).toLocaleString('en-US',{maximumFractionDigits:places,minimumFractionDigits:places}); }
function elapsed(n) { if (n===null||n===undefined) return '—'; return `${String(Math.floor(n/60)).padStart(2,'0')}:${String(Math.floor(n%60)).padStart(2,'0')}`; }
function resultText(r) { if (r.measure_result==='direction') return `示向 ${Number(r.svd_deg).toFixed(2)}°`; return ({near:'距离过近',no_signal:'无信号',success:'清除成功',no_target_in_range:'未发现目标',user_exit:'主动退出'})[r.measure_result||r.clear_result||r.exit_reason]||'进入成功'; }
function render() {
  if (!state) return;
  const phase=state.phase;
  $('virtual').innerHTML=`${fmt(state.virtual_time_s,3)} <small>s</small>`;
  $('real').innerHTML=`${elapsed(state.remaining_real_s)} <small>min : sec</small>`;
  $('real-note').textContent=phase==='ended'?`会话结束 · ${reasonNames[state.reason]||state.reason||'已停止'}`:phase==='ready'?'窗口剩余时间；进入后最多 20 分钟':phase==='entered'?`测试窗口剩余 ${elapsed(state.window_remaining_s)}`:'开始并进入后显示可用时间';
  $('cleared').innerHTML=`${state.cleared_count} <small>个</small>`;
  $('position').innerHTML=`(${fmt(state.position[0],1)}, ${fmt(state.position[1],1)}) <small>m</small>`;
  $('current-channel').textContent=String(state.channel).padStart(2,'0');
  $('phase').textContent=phaseNames[phase]||phase; $('phase').classList.toggle('running',phase==='entered'||phase==='ready');
  $('map-status').textContent=phase==='idle'?'等待开始':phase==='ended'?`已结束 · ${reasonNames[state.reason]||state.reason||''}`:phaseNames[phase];
  $('robot-url').textContent=state.robot_url.replace('http://','');
  $('start').disabled=busy||demoRunning||state.service_running;
  $('fixture').disabled=$('start').disabled;
  $('start').textContent=phase==='ended'?'▶ 新建本地会话':'▶ 开始本地会话';
  $('abort').disabled=busy||!state.service_running||phase==='ended';
  $('enter').disabled=busy||demoRunning||phase!=='ready'||state.pending;
  for(const id of ['measure','clear','exit']) $(id).disabled=busy||demoRunning||phase!=='entered'||state.pending;
  $('demo').disabled=busy||demoRunning||phase!=='ready'||state.pending;
  $('retry').hidden=!state.pending; $('retry').disabled=busy||demoRunning;
  $('export').disabled=!state.events.length;
  $('countdown-overlay').hidden=phase!=='countdown'; $('countdown').textContent=Math.max(1,Math.ceil(state.countdown_s));
  $('event-count').textContent=state.event_total||0;
  $('activity-note').textContent=state.events.length?`${state.event_total>1000?'显示最近 1,000 条 · ':''}最新动作实时同步`:'等待第一个动作';
  $('empty').hidden=state.events.length>0;
  const signature=JSON.stringify([state.session_id,state.event_total]);
  if(signature!==eventSignature) {
    eventSignature=signature; $('events').replaceChildren();
    state.events.slice().reverse().forEach((e,i)=>{
      const tr=document.createElement('tr'), p=e.request.position;
      const values=[String((state.event_total||state.events.length)-i).padStart(2,'0'), e.path.slice(1), p?`(${fmt(p.x,1)}, ${fmt(p.y,1)})`:'—',e.request.channel?String(e.request.channel).padStart(2,'0'):'—',resultText(e.response),fmt(e.response.virtual_time_s,3)];
      values.forEach((text,j)=>{const td=document.createElement('td');if(j===4){const badge=document.createElement('span');badge.className='result'+(e.response.clear_result==='success'?' success':'');badge.textContent=text;td.append(badge);}else td.textContent=text;tr.append(td);});
      $('events').append(tr);
    });
  }
  if(state.error) notice(state.error);
  draw();
}
async function refresh() {
  if (polling) return;
  polling=true;
  try {
    const next=await api('/api/state');
    if(state&&next.session_id!==state.session_id){truth=[];selected=null;bounds=2200;center=[0,0];}
    state=next;
    if($('debug').checked){const data=await api('/api/debug/truth');truth=(data.session_id===state.session_id)?data.sources:[];}else truth=[];
    $('connection').textContent='本地服务已连接';$('connection-dot').style.background='#48b494';
    render();
  } catch(e) { $('connection').textContent='连接不可用';$('connection-dot').style.background='#c59a61';notice(e.message); }
  finally{polling=false;}
}
async function perform(name,position=null,channel=null) {
  const data={session_id:state.session_id,action:name};
  if(position!==null) data.position=position;
  if(channel!==null) data.channel=channel;
  const out=await api('/api/action',data);
  if(out.status!==200||!out.response.accepted) throw new Error(`动作未接受（HTTP ${out.status}），位置和时钟未推进。`);
  $('action-feedback').textContent=`${name} · ${resultText(out.response)} · ${fmt(out.response.virtual_time_s,3)} s`;
  return out;
}
async function run(work) { if(busy)return; busy=true;notice('');render();try{await work();}catch(e){notice(e.message);}finally{busy=false;await refresh();render();} }
$('start').onclick=()=>run(async()=>{state=await api('/api/start',{fixture:$('fixture').value});truth=[];selected=null;eventSignature='';$('action-feedback').textContent='正在倒计时，接口就绪后请点击“进入”。';render();});
$('enter').onclick=()=>run(()=>perform('enter'));
$('exit').onclick=()=>run(()=>perform('exit'));
for(const name of ['measure','clear']) $(name).onclick=()=>run(async()=>{
  if(!$('x').value.trim()||!$('y').value.trim())throw new Error('请填写 X 和 Y 坐标。');
  const p=[Number($('x').value),Number($('y').value)],ch=Number($('channel').value);
  if(!p.every(n=>Number.isFinite(n)&&Math.abs(n)<=2000000))throw new Error('坐标须为有限数值，绝对值不超过 2,000,000 米。');
  await perform(name,p,ch);
});
$('retry').onclick=()=>run(()=>perform('retry'));
$('abort').onclick=()=>$('abort-dialog').showModal();
$('cancel-abort').onclick=()=>$('abort-dialog').close();
$('confirm-abort').onclick=()=>{$('abort-dialog').close();run(async()=>{await api('/api/abort',{session_id:state.session_id});$('action-feedback').textContent='已中止，本次记录可继续导出。';});};
$('demo').onclick=()=>run(async()=>{
  demoRunning=true;
  try {for(const [name,p,c] of [['enter',null,null],['measure',[300,400],1],['measure',[300,400],2],['clear',[300,0],3],['measure',[300,0],2],['exit',null,null]]){await perform(name,p,c);await refresh();await new Promise(r=>setTimeout(r,220));}}finally{demoRunning=false;}
});
$('debug').onchange=async()=>{truth=[];$('debug-note').textContent=$('debug').checked?'已开启：金色标记为源真值，淡色区域为接收覆盖。仅在此管理页面展示。':'默认隐藏源位置、朝向和接收范围。仅用于本地调试，不进入策略观测。';draw();await refresh();};
$('bearings').onchange=draw;
$('fixture').onchange=()=>{$('fixture-help').textContent=$('fixture').value==='mixed'?'手工指定场景与零误差，仅供本地验证。':'对应附件六步计时示例；源状态和误差为测试输入。';};
$('export').onclick=()=>run(async()=>{const data=await api('/api/export'),blob=new Blob([JSON.stringify(data,null,2)],{type:'application/json'}),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=`LOCAL-actions-${state.session_id}.json`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);});
function fit() {center=[0,0];bounds=2200;if(state){const pts=[[0,0],...state.events.filter(e=>e.request.position).map(e=>[e.request.position.x,e.request.position.y]),state.position];const xs=pts.map(p=>p[0]),ys=pts.map(p=>p[1]);const minX=Math.min(-2000,...xs),maxX=Math.max(2000,...xs),minY=Math.min(-2000,...ys),maxY=Math.max(2000,...ys);center=[(minX+maxX)/2,(minY+maxY)/2];bounds=Math.max(maxX-minX,maxY-minY)/2*1.12;}draw();}
$('fit').onclick=fit;$('zoom-in').onclick=()=>{bounds=Math.max(30,bounds/1.35);draw();};$('zoom-out').onclick=()=>{bounds=Math.min(3000000,bounds*1.35);draw();};
const canvas=$('map'),ctx=canvas.getContext('2d');
function geometry(){const r=canvas.getBoundingClientRect();return {w:r.width,h:r.height,scale:Math.min(r.width,r.height)/(bounds*2),px:p=>[r.width/2+(p[0]-center[0])*Math.min(r.width,r.height)/(bounds*2),r.height/2-(p[1]-center[1])*Math.min(r.width,r.height)/(bounds*2)]};}
function draw(){
  const {w,h,scale,px}=geometry();if(!w||!h)return;const dpr=window.devicePixelRatio||1;canvas.width=Math.round(w*dpr);canvas.height=Math.round(h*dpr);ctx.setTransform(dpr,0,0,dpr,0,0);ctx.clearRect(0,0,w,h);
  const raw=bounds/5,unit=Math.pow(10,Math.floor(Math.log10(raw))),step=[1,2,5,10].map(v=>v*unit).find(v=>v>=raw)||unit*10;
  ctx.lineWidth=1;ctx.font='9px -apple-system, sans-serif';ctx.fillStyle='#a9b9b2';
  const x0=center[0]-w/2/scale,x1=center[0]+w/2/scale,y0=center[1]-h/2/scale,y1=center[1]+h/2/scale;
  for(let x=Math.ceil(x0/step)*step;x<=x1;x+=step){const a=px([x,0]);ctx.strokeStyle=x===0?'#d3e0da':'#eaf0ed';ctx.beginPath();ctx.moveTo(a[0],0);ctx.lineTo(a[0],h);ctx.stroke();if(x!==0)ctx.fillText(fmt(x),a[0]+4,Math.max(45,Math.min(h-30,a[1]+13)));}
  for(let y=Math.ceil(y0/step)*step;y<=y1;y+=step){const a=px([0,y]);ctx.strokeStyle=y===0?'#d3e0da':'#eaf0ed';ctx.beginPath();ctx.moveTo(0,a[1]);ctx.lineTo(w,a[1]);ctx.stroke();if(y!==0)ctx.fillText(fmt(y),Math.max(8,Math.min(w-40,a[0]+6)),a[1]-5);}
  const o=px([0,0]);ctx.beginPath();ctx.arc(...o,1800*scale,0,Math.PI*2);ctx.fillStyle='#e5f0e944';ctx.fill();ctx.strokeStyle='#aac5b8';ctx.setLineDash([5,5]);ctx.stroke();ctx.setLineDash([]);ctx.fillStyle='#9cafaa';ctx.fillText('O',o[0]+8,o[1]+13);ctx.fillText('X / 东',w-43,Math.max(45,Math.min(h-12,o[1]-9)));ctx.fillText('Y / 北',Math.max(8,Math.min(w-85,o[0]+40)),16);
  if($('debug').checked)for(const s of truth){const a=px([s.x,s.y]);ctx.beginPath();if(s.kind==='directional'){ctx.moveTo(...a);const angle=-s.heading*Math.PI/180;ctx.arc(...a,s.radius*scale,angle-Math.PI/2,angle+Math.PI/2);ctx.closePath();}else ctx.arc(...a,s.radius*scale,0,Math.PI*2);ctx.fillStyle=s.cleared?'#899ca505':'#d8b66c0b';ctx.strokeStyle=s.cleared?'#adbab333':'#c8aa7544';ctx.fill();ctx.lineWidth=.8;ctx.stroke();ctx.beginPath();ctx.arc(...a,4,0,Math.PI*2);ctx.fillStyle=s.cleared?'#a8b2aa':'#bb944e';ctx.fill();ctx.fillStyle='#a18b64';ctx.font='9px -apple-system,sans-serif';ctx.fillText(`CH${String(s.channel).padStart(2,'0')}${s.cleared?' · 已清除':''}`,a[0]+8,a[1]-6);}
  if(state){const points=[[0,0],...state.events.filter(e=>e.request.position).map(e=>[e.request.position.x,e.request.position.y])];ctx.beginPath();points.forEach((p,i)=>{const a=px(p);i?ctx.lineTo(...a):ctx.moveTo(...a);});ctx.lineWidth=1.8;ctx.strokeStyle='#49a18e';ctx.stroke();
    for(const e of state.events){if(!e.request.position)continue;const p=[e.request.position.x,e.request.position.y],a=px(p),r=e.response;
      if(e.path==='/measure'&&r.measure_result==='direction'&&$('bearings').checked){const angle=r.svd_deg*Math.PI/180,end=px([p[0]+1500*Math.cos(angle),p[1]+1500*Math.sin(angle)]);ctx.beginPath();ctx.moveTo(...a);ctx.lineTo(...end);ctx.strokeStyle='#6b9caf77';ctx.lineWidth=1;ctx.setLineDash([3,4]);ctx.stroke();ctx.setLineDash([]);}
      if(r.clear_result==='success'){ctx.strokeStyle='#c49d62';ctx.lineWidth=2;ctx.strokeRect(a[0]-4,a[1]-4,8,8);}else if(e.path==='/measure'){ctx.beginPath();ctx.arc(...a,3.5,0,Math.PI*2);ctx.fillStyle='#fbfdfc';ctx.fill();ctx.strokeStyle='#69a7a0';ctx.lineWidth=1.3;ctx.stroke();}}
    const dog=px(state.position);ctx.beginPath();ctx.arc(...dog,13,0,Math.PI*2);ctx.fillStyle='#2c9c8218';ctx.fill();ctx.beginPath();ctx.arc(...dog,6,0,Math.PI*2);ctx.fillStyle='#128776';ctx.fill();ctx.strokeStyle='white';ctx.lineWidth=2;ctx.stroke();ctx.font='10px -apple-system,sans-serif';ctx.fillStyle='#357d6c';ctx.fillText('ROBOT',dog[0]+12,dog[1]+4);
  }
  if(selected){const a=px(selected);ctx.strokeStyle='#648899';ctx.lineWidth=1;ctx.beginPath();ctx.moveTo(a[0]-6,a[1]);ctx.lineTo(a[0]+6,a[1]);ctx.moveTo(a[0],a[1]-6);ctx.lineTo(a[0],a[1]+6);ctx.stroke();}
}
canvas.onclick=e=>{const r=canvas.getBoundingClientRect(),g=geometry();selected=[(e.clientX-r.left-g.w/2)/g.scale+center[0],-(e.clientY-r.top-g.h/2)/g.scale+center[1]].map(v=>Math.round(v*100)/100);$('x').value=selected[0];$('y').value=selected[1];$('map-coord').textContent=`已选 (${fmt(selected[0],2)}, ${fmt(selected[1],2)}) m`;draw();};
new ResizeObserver(draw).observe(canvas.parentElement);
refresh();setInterval(refresh,600);
