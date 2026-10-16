"use strict";
// Aurora Beta: preferences are local to this browser. No trade endpoints.
(()=>{
 const KEY='pairs-desk-aurora-beta-v1';let saved={};try{saved=JSON.parse(localStorage.getItem(KEY)||'{}')||{}}catch{}
 const persist=()=>{try{localStorage.setItem(KEY,JSON.stringify(saved))}catch{}};
 const workspace=document.getElementById('workspace');
 const clamp=(v,min,max)=>Math.min(max,Math.max(min,v));
 function applyLayout(){if(!workspace)return;workspace.style.setProperty('--pane-left',(saved.left||260)+'px');workspace.style.setProperty('--pane-right',(saved.right||290)+'px')}
 applyLayout();
 document.querySelectorAll('[data-handle]').forEach(handle=>{
  handle.addEventListener('pointerdown',e=>{if(matchMedia('(max-width:1250px)').matches)return;e.preventDefault();handle.setPointerCapture(e.pointerId);workspace.classList.add('dragging');const start=e.clientX,left=saved.left||260,right=saved.right||290,which=handle.dataset.handle;const move=ev=>{const width=workspace.clientWidth;const delta=ev.clientX-start;if(which==='left')saved.left=clamp(left+delta,210,Math.min(520,width-right-430));else saved.right=clamp(right-delta,230,Math.min(520,width-left-430));applyLayout()};const end=()=>{handle.removeEventListener('pointermove',move);handle.removeEventListener('pointerup',end);handle.removeEventListener('pointercancel',end);workspace.classList.remove('dragging');persist();window.dispatchEvent(new Event('resize'))};handle.addEventListener('pointermove',move);handle.addEventListener('pointerup',end);handle.addEventListener('pointercancel',end)});
  handle.addEventListener('keydown',e=>{if(!['ArrowLeft','ArrowRight'].includes(e.key))return;e.preventDefault();const n=e.key==='ArrowRight'?20:-20;if(handle.dataset.handle==='left')saved.left=clamp((saved.left||260)+n,210,520);else saved.right=clamp((saved.right||290)-n,230,520);applyLayout();persist();window.dispatchEvent(new Event('resize'))});
 });
 document.getElementById('layout-reset')?.addEventListener('click',()=>{saved.left=260;saved.right=290;applyLayout();persist();window.dispatchEvent(new Event('resize'))});
 const range=document.getElementById('pnl-range'),sort=document.getElementById('pair-sort');
 if(range){range.value=['all','1d','7d','30d'].includes(saved.range)?saved.range:'all';range.addEventListener('change',()=>{saved.range=range.value;persist();if(Array.isArray(window.AuroraBeta?.history)&&typeof pnlChart==='function')pnlChart(document.getElementById('pnl-chart'),window.AuroraBeta.filterHistory(window.AuroraBeta.history))})}
 if(sort){sort.value=['pnl','pnl_asc','realized','funding','pct','size','name'].includes(saved.sort)?saved.sort:'pnl';sort.addEventListener('change',()=>{saved.sort=sort.value;persist()})}
 window.AuroraBeta={history:[],preferredPair:()=>saved.pair||null,savePair:id=>{saved.pair=id;persist()},saveHistory(rows){this.history=rows},filterHistory(rows){if(!Array.isArray(rows)||range?.value==='all')return rows;const ms={'1d':864e5,'7d':6048e5,'30d':2592e6}[range?.value];if(!ms)return rows;const end=Math.max(...rows.map(x=>Number(x.time)).filter(Number.isFinite));return rows.filter(x=>Number(x.time)>=end-ms)}};
})();
