/* Local interactive PnL chart. No interpolation or synthetic samples. */
(function(root){
 const ranges={'1d':864e5,'7d':7*864e5,'30d':30*864e5,'90d':90*864e5};
 function series(rows,range='all',resolution='raw'){
  const map=new Map();
  for(const r of rows||[])if(r.time!=null&&r.pnl!=null&&Number.isFinite(Number(r.time))&&Number.isFinite(Number(r.pnl)))map.set(Number(r.time),{time:Number(r.time),pnl:Number(r.pnl),basis:r.basis||'legacy'});
  let data=[...map.values()].sort((a,b)=>a.time-b.time);
  if(data.length&&ranges[range])data=data.filter(r=>r.time>=data.at(-1).time-ranges[range]);
  const step={ '1h':36e5,'4h':144e5,'1d':864e5 }[resolution];
  if(step){const bins=new Map();for(const r of data)bins.set(Math.floor(r.time/step)+':'+r.basis,r);data=[...bins.values()].sort((a,b)=>a.time-b.time)}
  return data;
 }
 function niceStep(span){const raw=Math.abs(span)/4||1;const p=Math.pow(10,Math.floor(Math.log10(raw)));const n=raw/p;return (n<=1?1:n<=2?2:n<=5?5:10)*p}
 function mount(host,rows,options={}){
  let range=options.range||'all',resolution=options.resolution||'raw';
  const money=n=>new Intl.NumberFormat('en-US',{style:'currency',currency:'USD',minimumFractionDigits:2,maximumFractionDigits:2}).format(n);
  const date=t=>new Date(t).toLocaleString('en-US');
  host.innerHTML=`<div class="pnl-controls"><label>Período <select data-range aria-label="Período del PnL"><option value="1d">1 día</option><option value="7d">7 días</option><option value="30d">30 días</option><option value="90d">90 días</option><option value="all">Todo</option></select></label><label>Detalle <select data-resolution aria-label="Detalle del PnL"><option value="raw">Todos los puntos</option><option value="1h">1 hora</option><option value="4h">4 horas</option><option value="1d">1 día</option></select></label></div><div class="pnl-readout" aria-live="polite">Pasá el mouse para consultar fecha y PnL</div><div class="pnl-surface" tabindex="0" role="img" aria-label="Histórico de PnL. Flechas izquierda y derecha para recorrer los puntos."></div><div class="pnl-note"></div>`;
  const surface=host.querySelector('.pnl-surface'),readout=host.querySelector('.pnl-readout'),note=host.querySelector('.pnl-note');
  const rs=host.querySelector('[data-range]'),ds=host.querySelector('[data-resolution]');rs.value=range;ds.value=resolution;
  let data=[],index=0,showPoint=()=>{};
  function draw(){
   data=series(rows,range,resolution);
   note.textContent=(options.source==='local'?'Registro local':'Histórico de cuenta Hyperliquid')+' · '+data.length+' puntos · '+(resolution==='raw'?'Datos originales':'Último dato disponible de cada intervalo')+'. No se inventan puntos faltantes.';
   if(!data.length){surface.innerHTML='<div class="chart-placeholder">Sin datos en este período</div>';readout.textContent='Sin datos';return}
   const W=Math.max(440,surface.clientWidth||800),H=300,L=16,R=100,T=18,B=35;
   const times=data.map(r=>r.time),values=data.map(r=>r.pnl),min=values.reduce((a,b)=>Math.min(a,b),Infinity),max=values.reduce((a,b)=>Math.max(a,b),-Infinity),span=max-min||Math.max(1,Math.abs(max)*.05),low=min-span*.08,high=max+span*.08;
   const tickStep=niceStep(high-low);const start=times[0],end=times.at(-1),dt=end-start||1;
   const x=t=>L+(t-start)/dt*(W-L-R),y=v=>T+(high-v)/(high-low)*(H-T-B);
   let svg=`<svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" aria-hidden="true">`;
   for(let i=0;i<5;i++){const v=Math.ceil(low/tickStep)*tickStep+i*tickStep,yy=y(v);svg+=`<line x1="${L}" x2="${W-R}" y1="${yy}" y2="${yy}" stroke="#293129" stroke-dasharray="3 4"/><text x="${W-R+8}" y="${yy+4}" fill="#a0ad9d" font-size="11">${money(v)}</text>`}
   for(let i=0;i<4;i++){const t=start+(end-start)*i/3;svg+=`<text x="${L+(W-L-R)*i/3}" y="${H-10}" text-anchor="${i===0?'start':i===3?'end':'middle'}" fill="#a0ad9d" font-size="11">${new Date(t).toLocaleDateString('en-US',{day:'2-digit',month:'2-digit'})}${end-start<2*864e5?' '+new Date(t).toLocaleTimeString('en-US',{hour:'2-digit',minute:'2-digit'}):''}</text>`}
   const d=data.map((r,i)=>(!i||r.basis!==data[i-1].basis?'M':'L')+x(r.time)+' '+y(r.pnl)).join(' ');
   svg+=`<path d="${d}" fill="none" stroke="#44d7a8" stroke-width="2"/><g data-cursor visibility="hidden"><line data-cross x1="0" x2="0" y1="${T}" y2="${H-B}" stroke="#a0ad9d" stroke-dasharray="4 4"/><line data-horizontal x1="${L}" x2="${W-R}" stroke="#a0ad9d" stroke-dasharray="4 4"/><circle data-dot r="4" fill="#44d7a8" stroke="#101510" stroke-width="2"/></g></svg>`;
   surface.innerHTML=svg;
   showPoint=i=>{index=Math.max(0,Math.min(data.length-1,i));const r=data[index],xx=x(r.time),yy=y(r.pnl);surface.querySelector('[data-cursor]').setAttribute('visibility','visible');const cross=surface.querySelector('[data-cross]');cross.setAttribute('x1',xx);cross.setAttribute('x2',xx);const h=surface.querySelector('[data-horizontal]');h.setAttribute('y1',yy);h.setAttribute('y2',yy);const dot=surface.querySelector('[data-dot]');dot.setAttribute('cx',xx);dot.setAttribute('cy',yy);readout.textContent=date(r.time)+' · PnL '+money(r.pnl)+(r.basis==='gross'?' · abierto + realizado, sin funding ni fees':r.basis==='net'?' · neto':r.basis==='legacy'?' · registro anterior':' · cuenta HL');};
   surface.onpointermove=e=>{const rect=surface.getBoundingClientRect(),target=start+((e.clientX-rect.left)*W/rect.width-L)/(W-L-R)*dt;let lo=0,hi=data.length-1;while(lo<hi){const mid=(lo+hi)>>1;if(data[mid].time<target)lo=mid+1;else hi=mid}if(lo>0&&target-data[lo-1].time<data[lo].time-target)lo--;showPoint(lo)};
   surface.onpointerleave=()=>showPoint(data.length-1);
   showPoint(data.length-1);
  }
  surface.onkeydown=e=>{if(e.key==='ArrowLeft'||e.key==='ArrowRight'){e.preventDefault();showPoint(index+(e.key==='ArrowLeft'?-1:1))}};
  const change=()=>{range=rs.value;resolution=ds.value;options.onChange?.({range,resolution});draw()};rs.onchange=change;ds.onchange=change;
  draw();const observer=new ResizeObserver(()=>draw());observer.observe(surface);
  return ()=>observer.disconnect();
 }
 root.PnlChart={series,mount};if(typeof module!=='undefined')module.exports={series};
})(typeof window!=='undefined'?window:globalThis);
