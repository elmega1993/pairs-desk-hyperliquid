'use strict';
const $=s=>document.querySelector(s), $$=s=>[...document.querySelectorAll(s)];
let lastChart=null,activeChart=null,closedChartInstance=null,chartLayers={initial:true,average:true,events:true,targets:true,bollinger:false},chartMode='candles';
let renderedSubKey='',chartRequest=0,closedChartRequest=0,chartRenderKey='',closedRenderId='';
let pairs=[],closedPairs=[],pnlHistory=[],operationEvents=[],chosen=null,selectedClosed=null,interval='1d',accountRange='1d',last=0,currentSub='operate',tradeStatus=null,tradeTicket=null,tradeBusy=false;
const money=(n,d=2)=>n==null?'N/D':(n<0?'−':'')+'$'+Math.abs(n).toLocaleString('en-US',{minimumFractionDigits:d,maximumFractionDigits:d});
const signed=(n,d=2)=>n==null?'N/D':(n>=0?'+':'−')+Math.abs(n).toFixed(d);
const cls=n=>n==null?'':n>=0?'pnl-positive':'pnl-negative';
const fnum=(n,d=5)=>n==null?'N/D':Number(n).toLocaleString('en-US',{maximumFractionDigits:d});
const entryRatio=p=>p.entry_ratio;
function html(s){return String(s??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;')}

const hiddenNotices=new Set();
function showNotices(items){const host=$('#notices');if(!host)return;host.innerHTML=items.filter(x=>!hiddenNotices.has(x.message)).map(x=>`<div class="notice ${x.level}"><span>${html(x.message)}</span><button type="button" aria-label="Descartar aviso" data-dismiss="${html(x.message)}">×</button></div>`).join('');host.querySelectorAll('[data-dismiss]').forEach(b=>b.onclick=()=>{hiddenNotices.add(b.dataset.dismiss);b.closest('.notice').remove()})}
function updateArmedBanner(){const banner=$('#armedBanner');if(!banner)return;const armed=!!tradeStatus?.armed;banner.hidden=!armed;document.querySelector('.op-panel')?.classList.toggle('armed',armed)}

function render(){
 const sorted=[...pairs]; const sort=$('#sort').value;
 if(sort==='pnl')sorted.sort((a,b)=>b.pnl-a.pnl);else if(sort==='name')sorted.sort((a,b)=>a.id.localeCompare(b.id));else sorted.sort((a,b)=>(a.liq??9999)-(b.liq??9999));
 $('#paircount').textContent=pairs.length;
 $('#pairlist').innerHTML=sorted.map(p=>`<button class="pair-item ${p.liq==null?'risk-unknown':p.liq<=10?'risk-high':p.liq<=25?'risk-mid':'risk-low'} ${p.id===chosen?'active':''}" data-pair="${html(p.id)}" title="${html(`Abierto: ${money(p.pnl)} | Realizado: ${money(p.realized)} | Total: ${money(p.total_pnl)} | Funding: ${money(p.funding)} | Z: ${p.z==null?'N/D':signed(p.z)}`)}"><span class="line"><b><span class="long">${html(p.long)}</span> / <span class="short">${html(p.short)}</span></b><strong class="${cls(p.pnl)}">${signed(p.pnl)}</strong></span><span class="pair-compact-meta"><span class="pair-compact-primary">${money(p.size,0)} · ${signed(p.pnl_pct)}% · F <span class="${cls(p.funding)}">${money(p.funding)}</span></span><span class="pair-compact-total ${cls(p.total_pnl)}">Total ${money(p.total_pnl)}</span></span></button>`).join('')||'<div class="muted" style="padding:10px">No hay pares completos abiertos.</div>';
 $$('.pair-item').forEach(b=>b.onclick=()=>{chosen=b.dataset.pair;render();fetchChart()});
 const p=pairs.find(p=>p.id===chosen); if(!p)return;
 $('#pairtitle').textContent=`${p.long} / ${p.short}`;$('#longleg').textContent=`L ${p.long}`;$('#shortleg').textContent=`S ${p.short}`;
 const metrics=[['Ratio',fnum(p.ratio,7),''],['Δ ratio',p.ratio_change==null?'N/D':signed(p.ratio_change)+'%',cls(p.ratio_change)],['Z 1d',p.z==null?'N/D':signed(p.z),p.z==null?'nd':Math.abs(p.z)>=2?'metric-warn':''],['Neutral.',p.imbalance==null?'N/D':signed(p.imbalance)+'%',p.imbalance==null?'nd':Math.abs(p.imbalance)>=5?'metric-warn':''],['Funding',money(p.funding),cls(p.funding)],['Liq.',p.liq==null?'N/D':fnum(p.liq,1)+'%',p.liq==null?'nd':p.liq<=10?'metric-danger':p.liq<=25?'metric-warn':'']];
 $('#metrics').innerHTML=metrics.map(([k,v,c])=>`<div class="card metric"><small>${k}</small><div class="value ${c}">${html(v)}</div></div>`).join('');
 $('#entryratio').textContent=fnum(entryRatio(p),7);const hist=p.entry_history;$('#initialratio').textContent=hist?.available?'Inicial '+fnum(hist.initial_ratio,7):'Inicial N/D';$('#historyStatus').textContent=hist?.available?'Evolución verificada':'Historial no verificable';if(renderedSubKey!==chosen+'|'+currentSub){renderSub();renderedSubKey=chosen+'|'+currentSub;fetchDailyZ(p)} else {const info=$('#tradeLegsInfo');if(info)info.textContent=`Long ${p.long}: ${money(p.long_usd)} · Short ${p.short}: ${money(p.short_usd)} · Neutralidad ${signed(p.imbalance)}%. El orden de las patas no es atómico.`;}paintLiveRatios()
}
async function state(){
 try{const r=await fetch('/api/state',{cache:'no-store'});const data=await r.json();if(!r.ok)throw Error(data.detail||'Error HTTP '+r.status);
 const zPrevious=pairs.find(x=>x.id===chosen)?.z; pairs=data.pairs;if(zPrevious!=null){const cp=pairs.find(x=>x.id===chosen);if(cp&&cp.z==null)cp.z=zPrevious;}closedPairs=data.closed_pairs||[];pnlHistory=data.pnl_history||[];operationEvents=data.operation_events||[];last=data.last_updated_ms;if(!pairs.some(p=>p.id===chosen))chosen=pairs[0]?.id||null;
 $('#totalpnl').textContent=money(data.summary.open_plus_realized);$('#totalpnl').className=cls(data.summary.open_plus_realized);$('#totalpnlcaption').textContent=data.summary.open_plus_realized==null?'historial incompleto':'abierto + realizado';
 pnlSource=data.pnl_source;renderAccount(data.summary,data.pnl_source);
 renderClosed();
 $('#openpnl').textContent=money(data.summary.unrealized);$('#openpnl').className=cls(data.summary.unrealized);
 $('#fundingpnl').textContent=money(data.summary.known_funding);$('#fundingpnl').className=cls(data.summary.known_funding);$('#fundingcaption').textContent=(data.summary.active_funding_missing+data.summary.archived_funding_missing)?'Parcial · '+data.summary.active_funding_missing+' activos y '+data.summary.archived_funding_missing+' cerrados pendientes':'activos + cerrados completos';
 $('#exposure').textContent=money(data.summary.exposure,0);$('#delta').textContent='Delta '+money(data.summary.delta,0)+' · funding '+money(data.summary.funding);
 $('#margin').textContent=data.summary.margin_pct==null?'N/D':fnum(data.summary.margin_pct,1)+'%';$('#marginbar').style.width=Math.min(100,data.summary.margin_pct||0)+'%';$('#marginbar').className=data.summary.margin_pct==null?'':data.summary.margin_pct>85?'high':data.summary.margin_pct>=60?'mid':'low';
 const ledgerAt=data.ledger?.funding?.covered_until;showNotices((data.warnings||[]).map(message=>({level:'warn',message})));updateArmedBanner();
 liveRatios.sync(pairs);render();paintLiveRatios();await fetchChart();}catch(e){$('#freshness').className='status error';$('#freshness').textContent='● sin datos';showNotices([{level:'error',message:'No se pudo consultar Hyperliquid: '+e.message}]);}
}
function renderAccount(s){
 const fields=[['Abierto',s.unrealized],['Realizado',s.realized],['Funding',s.known_funding],['Fees',s.fees==null?null:-s.fees],['Neto',s.total]];
 $('#account').innerHTML=`<h3>Cuenta · Hyperliquid</h3><div class="account-equation">${fields.map(([name,value],i)=>`${i?`<span class="equation-operator">${i===4?'=':i===3?'−':'+'}</span>`:''}<div class="card equation-part ${i===4?'equation-result':''}"><small>${name}</small><strong class="${cls(value)}">${money(value)}</strong></div>`).join('')}</div>${s.total==null?'<p class="muted">Neto N/D: funding o historial de fills de pares cerrados incompleto.</p>':''}<div class="account-secondary"><span>Margen usado <b>${money(s.margin_used)}</b></span><span>Delta long − short <b>${money(s.delta)}</b></span><span>Comisiones estimadas <b>${money(s.fees)}</b></span></div><div class="account-split"><div class="card account-chart-card"><h3>PnL total histórico</h3><div id="accountChart" class="account-chart"></div></div><div class="card account-history-card"><h3>Historial de operaciones</h3><div class="event-head"><span>Fecha</span><span>Par</span><span>Acción / Importe</span><span>Realizado</span></div><div id="accountEvents"></div></div></div><p class="muted">Margen CORE + XYZ es informativo. El realizado depende de un historial de fills completo.</p>`;
 drawPnlHistory();renderOperationHistory();
}
let pnlOptions={range:'all',resolution:'raw'},pnlDispose=null,pnlSource='local';
function drawPnlHistory(){
 const host=$('#accountChart');if(!host)return;
 if(pnlDispose)pnlDispose();
 pnlDispose=PnlChart.mount(host,pnlHistory,{...pnlOptions,source:pnlSource,onChange:value=>{pnlOptions=value}});
}
function renderOperationHistory(){
 const host=$('#accountEvents'); if(!host)return;
 host.innerHTML=(operationEvents||[]).length?`<div class="event-log account-events">${operationEvents.slice(0,80).map(e=>`<div><span>${new Date(e.time).toLocaleString('en-US')}</span><b>${html(e.pair||'')}</b><span>${e.kind==='add'?'ADD':'CIERRE'} ${money(e.amount)}</span><span class="${cls(e.realized)}">${e.kind==='close'?money(e.realized):''}</span></div>`).join('')}</div>`:'<p class="muted">Sin operaciones reconstruidas.</p>';
}
function renderClosed(){
 if(!closedPairs.some(p=>String(p.id||'')===selectedClosed))selectedClosed=closedPairs[0]?.id||null;
 const rows=closedPairs.length?[...closedPairs].sort((a,b)=>new Date(b.closed_at||0)-new Date(a.closed_at||0)).map(p=>`<button class="closed-row-btn ${String(p.id||'')===selectedClosed?'active':''}" data-closed="${html(p.id)}"><b>${html(p.long)} / ${html(p.short)}</b><span class="${cls(p.total_pnl)}">${money(p.total_pnl)}</span><span>${new Date(p.closed_at||0).toLocaleString('en-US',{month:'2-digit',day:'2-digit',year:'numeric',hour:'2-digit',minute:'2-digit'})}</span></button>`).join(''):'<p>No hay pares cerrados registrados.</p>';
 const p=closedPairs.find(x=>String(x.id||'')===selectedClosed);
 if(closedRenderId===String(selectedClosed) && $('#closedChart'))return;
 closedRenderId=String(selectedClosed);
 $('#closed').innerHTML=`<h3>Pares cerrados archivados (${closedPairs.length})</h3><div class="closed-layout"><div class="closed-table"><div class="closed-head"><span>Par</span><span>Resultado</span><span>Cierre</span></div>${rows}</div><div class="card closed-detail" id="closedDetail">${p?`<div class="selected"><strong>${html(p.long)} / ${html(p.short)}</strong><span class="muted">Neto ${money(p.total_pnl)}${p.total_pnl==null?' · fills incompletos':''} · Funding ${money(p.funding)}</span></div><div id="closedChart" class="closed-chart"><div class="chart-placeholder">Cargando gráfico…</div></div><div class="event-head"><span>Fecha</span><span>Acción</span><span>Importe</span><span>Realizado</span></div><div class="event-log">${(p.events||[]).slice(-24).reverse().map(e=>`<div><span>${new Date(e.time).toLocaleString('en-US')}</span><b>${e.kind==='add'?'ADD':'CIERRE'}</b><span>${money(e.amount)}</span><span class="${cls(e.realized)}">${e.kind==='close'?money(e.realized):''}</span></div>`).join('')||'<p class="muted">Sin eventos reconstruidos.</p>'}</div>`:'Seleccioná un par cerrado.'}</div></div>`;
 $$('.closed-row-btn').forEach(b=>b.onclick=()=>{selectedClosed=b.dataset.closed;closedRenderId='';renderClosed()});
 if(p && !$('#closed').hidden)fetchClosedChart();
}
function chartPrecision(entry,bars){
 const vals=[entry,...bars.flatMap(b=>[b.open,b.high,b.low,b.close])].filter(v=>Number.isFinite(Number(v))&&Number(v)>0).map(Number);
 const min=Math.min(...vals);
 return min<0.001?8:min<0.01?7:min<0.1?6:4;
}
function drawSvg(bars,entry,ctx=null,selector='#chart'){const el=$(selector);if(!bars.length){el.innerHTML='<div class="chart-placeholder">No hay velas disponibles para este intervalo</div>';return}
 if(window.klinecharts?.init){try{
  const engine=window.klinecharts;
  try{engine.dispose(el)}catch(e){}
  el.replaceChildren();const chart=engine.init(el,{styles:{grid:{show:true,horizontal:{color:'#202920'},vertical:{color:'#202920'}},candle:{bar:{upColor:'#44d7a8',downColor:'#fa7885'}}}});if(selector==='#chart')activeChart=chart;else closedChartInstance=chart;
  if(chart.setPriceVolumePrecision)chart.setPriceVolumePrecision(chartPrecision(entry,bars),0);
  chart.applyNewData(bars.map(b=>({timestamp:b.timestamp,open:b.open,high:b.high,low:b.low,close:b.close,volume:0})));
  if(!window._pdOverlaysReady){
   engine.registerOverlay({name:'pd_price_line',totalStep:1,lock:true,needDefaultPointFigure:false,createPointFigures:({coordinates,bounding,overlay})=>{
    if(!coordinates.length)return [];const y=coordinates[0].y,m=overlay.extendData||{};
    return [{type:'line',attrs:{coordinates:[{x:0,y},{x:bounding.width,y}]},styles:{color:m.color||'#d8ad63',size:1,dashedValue:[5,4]}},{type:'text',attrs:{x:8,y:y-8,text:m.label||''},styles:{color:m.color||'#d8ad63',size:11,fontFamily:'system-ui'}}];
   }});
   engine.registerOverlay({name:'pd_steps',totalStep:1,lock:true,needDefaultPointFigure:false,createPointFigures:({coordinates,overlay})=>{
    if(coordinates.length<2)return [];const figures=[];const m=overlay.extendData||{};for(let i=1;i<coordinates.length;i++){const a=coordinates[i-1],b=coordinates[i];if(![a.x,a.y,b.x,b.y].every(Number.isFinite))continue;figures.push({type:'line',attrs:{coordinates:[{x:a.x,y:a.y},{x:b.x,y:a.y}]},styles:{color:m.color||'#f5bd68',size:2}});figures.push({type:'line',attrs:{coordinates:[{x:b.x,y:a.y},{x:b.x,y:b.y}]},styles:{color:m.color||'#f5bd68',size:2}})}return figures;
   }});
   engine.registerOverlay({name:'pd_event',totalStep:1,lock:true,needDefaultPointFigure:false,createPointFigures:({coordinates,overlay})=>{
     if(!coordinates.length)return [];const {x,y}=coordinates[0],m=overlay.extendData||{};
     return [{type:'circle',attrs:{x,y,r:5},styles:{color:m.color||'#d8ad63',style:'fill'}},{type:'text',attrs:{x:x+8,y:y+(m.side==='below'?17:-7),text:m.label||''},styles:{color:m.color||'#d8ad63',size:11,fontFamily:'system-ui'}}];
   }});window._pdOverlaysReady=true;
  }
  const p=ctx||pairs.find(p=>p.id===chosen);
  const base=p?.management_entry_ratio,settings=p?.management_rules||{};
  const hist=p?.entry_history;
  const levels=[];
  if(chartLayers.initial && hist?.available)levels.push({label:'INICIAL',value:hist.initial_ratio,color:'#a9b2bf'});
  if(chartLayers.average)levels.push({label:'MEDIA ACTUAL',value:entry,color:'#f5bd68'});
  if(chartLayers.targets && base){for(const [label,field,def] of [['TP1','tp1_ratio_pct',10],['TP2','tp2_ratio_pct',20],['TP3','tp3_ratio_pct',20],['ADD1','add1_ratio_pct',-8],['ADD2','add2_ratio_pct',-15]]){
    levels.push({label,value:base*(1+Number(settings[field]??def)/100),color:label.startsWith('TP')?'#44d7a8':'#fa7885'});
  }}
  const lastTime=bars.at(-1).timestamp;
  for(const level of levels){if(Number.isFinite(level.value)&&level.value>0){chart.createOverlay({name:'pd_price_line',lock:true,points:[{timestamp:lastTime,value:level.value}],extendData:level})}}
  if(chartLayers.average && hist?.available && hist.steps?.length){
    const steps=hist.steps;const start=bars[0].timestamp;const end=lastTime;
    const mapped=[];const snap=t=>{let i=bars.findIndex(b=>b.timestamp>=t);return i<0?end:bars[i].timestamp};
    let previous=steps.filter(st=>st.time<=start).at(-1);
    if(previous)mapped.push({timestamp:start,value:previous.ratio});
    for(const st of steps){if(st.time<start||st.time>end)continue;const t=snap(st.time);if(mapped.length&&mapped.at(-1).timestamp===t)mapped[mapped.length-1]={timestamp:t,value:st.ratio};else mapped.push({timestamp:t,value:st.ratio})}
    if(mapped.length){if(mapped.at(-1).timestamp<end)mapped.push({timestamp:end,value:mapped.at(-1).value});if(mapped.length>=2)chart.createOverlay({name:'pd_steps',lock:true,points:mapped,extendData:{color:'#f5bd68'}})}
  }
  if(chartLayers.events){
    const markers=[];if(p?.opened_at)markers.push({timestamp:p.opened_at,label:'E',side:'below',color:'#a9b2bf',detail:'Entrada inicial'});
    for(const e of (p?.events||[]))markers.push({timestamp:e.time,label:e.kind==='add'?'A':'R',side:e.kind==='add'?'below':'above',color:e.kind==='close'&&e.realized<0?'#fa7885':'#44d7a8',detail:e.detail||'',amount:e.amount});
    for(const marker of markers){const b=bars.find(b=>b.timestamp>=marker.timestamp);if(b)chart.createOverlay({name:'pd_event',lock:true,points:[{timestamp:b.timestamp,value:marker.side==='below'?b.low:b.high}],extendData:marker})}
  }
  if(chartLayers.bollinger && bars.length>=20){
    const lines=[[],[],[]];for(let i=19;i<bars.length;i++){const values=bars.slice(i-19,i+1).map(b=>b.close);const avg=values.reduce((a,b)=>a+b,0)/20;const dev=Math.sqrt(values.reduce((a,b)=>a+(b-avg)**2,0)/20);[avg+2*dev,avg,avg-2*dev].forEach((v,j)=>lines[j].push({timestamp:bars[i].timestamp,value:v}))}
    lines.forEach((line,i)=>{line=line.filter((_,j)=>j%Math.max(1,Math.ceil(line.length/450))===0||j===line.length-1);if(line.length>=2)chart.createOverlay({name:'pd_steps',lock:true,points:line,extendData:{color:i===1?'#617889':'#4c6573'}})});
  }
  // Event details stay accessible as text through the Events tab.
  return;
 }catch(e){el.replaceChildren();console.warn('Fallback SVG de KLineChart',e)}}
 const W=1000,H=350,top=12,bottom=30,left=9,right=75;
 const visible=bars.slice(-160),vmin=Math.min(...visible.map(b=>b.low),entry||Infinity),vmax=Math.max(...visible.map(b=>b.high),entry||-Infinity),spread=vmax-vmin||1, lo=vmin-spread*.09,hi=vmax+spread*.08;
 const x=i=>left+(i+.5)*(W-left-right)/visible.length,y=v=>top+(hi-v)/(hi-lo)*(H-top-bottom),bw=Math.max(1,(W-left-right)/visible.length*.65);
 let out=`<svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" style="width:100%;height:100%" xmlns="http://www.w3.org/2000/svg"><rect width="100%" height="100%" fill="#121712"/>`;
 for(let i=0;i<6;i++){const v=lo+(hi-lo)*i/5;let yy=y(v);out+=`<line x1="${left}" y1="${yy}" x2="${W-right}" y2="${yy}" stroke="#293129" stroke-dasharray="2 4"/><text x="${W-right+7}" y="${yy+4}" fill="#a0ad9d" font-size="11">${v.toPrecision(4)}</text>`}
 visible.forEach((b,i)=>{let xx=x(i),up=b.close>=b.open,col=up?'#44d7a8':'#fa7885';out+=`<line x1="${xx}" x2="${xx}" y1="${y(b.high)}" y2="${y(b.low)}" stroke="${col}" stroke-width="1"/><rect x="${xx-bw/2}" y="${Math.min(y(b.open),y(b.close))}" width="${bw}" height="${Math.max(1,Math.abs(y(b.open)-y(b.close)))}" fill="${col}"/>`});
 if(entry && entry>=lo && entry<=hi)out+=`<line x1="${left}" x2="${W-right}" y1="${y(entry)}" y2="${y(entry)}" stroke="#d8ad63" stroke-dasharray="7 4"/><text x="${W-right-4}" text-anchor="end" y="${y(entry)-6}" fill="#d8ad63" font-size="11">Entrada ${entry.toPrecision(5)}</text>`;
 const last=visible.at(-1);out+=`<line x1="${left}" x2="${W-right}" y1="${y(last.close)}" y2="${y(last.close)}" stroke="#44d7a8" stroke-dasharray="2 4"/><text x="${W-right+6}" y="${y(last.close)+4}" fill="#44d7a8" font-size="11">${last.close.toPrecision(5)}</text></svg>`;el.innerHTML=out;
}
async function fetchChart(){
 const p=pairs.find(p=>p.id===chosen);if(!p)return;
 const wanted=p.id, wantedInterval=interval, request=++chartRequest;
 const first=lastChart?.pair!==wanted||lastChart?.interval!==wantedInterval||!activeChart;
 if(first)$('#chart').innerHTML='<div class="chart-placeholder">Cargando velas reales…</div>';
 try{
  const r=await fetch('/api/chart/'+encodeURIComponent(wanted)+'?interval='+encodeURIComponent(wantedInterval),{cache:'no-store'});
  const data=await r.json();if(!r.ok)throw Error(data.detail||'Error de velas');
  if(request!==chartRequest||chosen!==wanted||interval!==wantedInterval)return;
  const bars=data.bars||[];
  const signature=wanted+'|'+wantedInterval+'|'+bars.length+'|'+(bars.at(-1)?.timestamp??'')+'|'+(bars.at(-1)?.close??'');
  if(chartRenderKey!==signature||!activeChart){
   if(activeChart&&lastChart?.pair===wanted&&lastChart?.interval===wantedInterval&&window.klinecharts?.init){
    const previous=lastChart?.bars||[];
    // KLineCharts updateData updates the latest bar without resetting zoom or overlays.
    if(bars.length===previous.length&&bars.length&&bars.at(-1).timestamp===previous.at(-1).timestamp&&activeChart.updateData){
     activeChart.updateData({...bars.at(-1),volume:0});
    }else if(bars.length===previous.length+1&&bars.at(-2)?.timestamp===previous.at(-1)?.timestamp&&activeChart.updateData){
     activeChart.updateData({...bars.at(-1),volume:0});
    }else drawSvg(bars,p.entry_ratio,p);
   }else drawSvg(bars,p.entry_ratio,p);
   chartRenderKey=signature;
  }
  lastChart={bars,pair:wanted,interval:wantedInterval};
 }catch(e){if(request===chartRequest&&chosen===wanted&&first){$('#chart').innerHTML='<div class="chart-placeholder">Gráfico no disponible: '+html(e.message)+'</div>';activeChart=null;}}
}
async function fetchClosedChart(){
 const p=closedPairs.find(x=>String(x.id||'')===selectedClosed),host=$('#closedChart');if(!p||!host)return;
 const wanted=String(p.id||''),request=++closedChartRequest;
 if(host.dataset.loaded!==wanted+'|'+interval)host.innerHTML='<div class="chart-placeholder">Cargando velas reales…</div>';
 const controller=new AbortController(),timeout=setTimeout(()=>controller.abort(),15000);
 try{
  const r=await fetch('/api/chart/'+encodeURIComponent(wanted)+'?interval='+encodeURIComponent(interval),{signal:controller.signal,cache:'no-store'});
  const data=await r.json();if(!r.ok)throw Error(data.detail||'Error de velas');
  if(request!==closedChartRequest||String(selectedClosed)!==wanted||!$('#closedChart'))return;
  drawSvg(data.bars||[],p.entry_ratio,p,'#closedChart');$('#closedChart').dataset.loaded=wanted+'|'+interval;
 }catch(e){if(request===closedChartRequest&&String(selectedClosed)===wanted&&$('#closedChart')){
  $('#closedChart').innerHTML='<div class="chart-error">Gráfico no disponible: '+html(e.name==='AbortError'?'tiempo de espera agotado':e.message)+' <button type="button" id="retryClosedChart" class="btn">Reintentar</button></div>';
  $('#retryClosedChart').onclick=fetchClosedChart;
 }}finally{clearTimeout(timeout)}
}
$('#refresh').onclick=state;$('#sort').onchange=render;$('#interval').onchange=e=>{interval=e.target.value;$$('[data-timeframe]').forEach(b=>{b.classList.toggle('selected',b.dataset.timeframe===interval);b.setAttribute('aria-pressed',String(b.dataset.timeframe===interval))});fetchChart();if(!$('#closed').hidden)fetchClosedChart()};$$('[data-timeframe]').forEach(b=>b.onclick=()=>{$('#interval').value=b.dataset.timeframe;$('#interval').dispatchEvent(new Event('change'))});
$$('[data-page]').forEach(b=>b.onclick=()=>{$('#deskKpis').hidden=b.dataset.page!=='desk';$$('[data-page]').forEach(x=>x.classList.toggle('active',x===b));['desk','account','closed','alerts'].forEach(id=>$('#'+id).hidden=id!==b.dataset.page);if(b.dataset.page==='closed'){closedRenderId='';renderClosed();}if(b.dataset.page==='alerts')loadAlerts()});
function renderSub(){
 const p=pairs.find(x=>x.id===chosen), el=$('#opcontent');if(!p)return;tradeTicket=null;
 if(currentSub==='operate'){
  el.innerHTML=`<div class="formgrid"><label>Operación<select id="tradeAction"><option>Aumentar</option><option>Reducir</option><option>Cerrar</option></select></label><label>% por pata<input id="tradePct" type="number" min="1" max="100" value="25"></label><label>Slip. %<input id="tradeSlip" type="number" min="0.1" max="2" step="0.1" value="0.5"></label></div><div class="muted" id="tradeLegsInfo">Long ${html(p.long)}: ${money(p.long_usd)} · Short ${html(p.short)}: ${money(p.short_usd)} · Neutralidad ${signed(p.imbalance)}%. El orden de las patas no es atómico.</div><div class="op-footer"><label class="read-only"><input type="checkbox" id="armTrade" ${tradeStatus?.armed?'checked':''} ${!tradeStatus?.agent_configured?'disabled':''}> Habilitar órdenes reales (mainnet)</label><span id="tradeMode">${tradeStatus?.agent_configured?'Agent disponible':'Sin Agent'}</span><button class="btn" id="tradePreview" ${(!tradeStatus?.agent_configured||!tradeStatus?.armed||tradeStatus?.trading_blocked)?'disabled':''}>Previsualizar</button></div><div id="tradeTicket"></div>`;
  $('#tradeAction').onchange=()=>{$('#tradePct').value=$('#tradeAction').value==='Cerrar'?100:25;$('#tradePct').disabled=$('#tradeAction').value==='Cerrar';$('#tradeTicket').replaceChildren();tradeTicket=null;};
  $('#tradePreview').onclick=previewTrade;$('#armTrade').onchange=armTrading;
  if(tradeStatus?.trading_blocked){$('#tradeTicket').textContent='Órdenes bloqueadas: hay operaciones pendientes en SQLite. Verificá y conciliá desde la versión estable.';}
 }else if(currentSub==='management'){
   const r=p.management_rules||{};
   el.innerHTML=`<div class="account-grid"><div class="card metric">TP1 / TP2 / TP3<strong>${html(r.tp1_ratio_pct??10)}% / ${html(r.tp2_ratio_pct??20)}% / ${html(r.tp3_ratio_pct??20)}%</strong></div><div class="card metric">ADD1 / ADD2<strong>${html(r.add1_ratio_pct??-8)}% / ${html(r.add2_ratio_pct??-15)}%</strong></div><div class="card metric">Z-score 1d<strong>${p.z==null?'N/D':signed(p.z)}</strong></div><div class="card metric">Cambio del ratio<strong id="managementRatioChange">${signed(p.ratio_change)}%</strong></div></div><div id="managementSignals">Consultando señales del backend…</div><small>Señales informativas. No envían órdenes ni marcan escalones ejecutados.</small>`;
   fetchManagement(p);
 }else if(currentSub==='notes'){
   el.innerHTML=`<div class="account-grid"><div class="card note"><b>Tesis</b><p>${html(p.trade_note)||'Sin notas guardadas'}</p></div><div class="card note"><b>Invalidación</b><p>${html(p.invalidation_note)||'Sin invalidación guardada'}</p></div></div>`;
 }else{
  const ev=(p.events||[]).slice(-24).reverse();
  el.innerHTML=ev.length?`<div class="event-log">${ev.map(e=>`<div><span>${new Date(e.time).toLocaleString('en-US')}</span><b>${e.kind==='add'?'ADD':'CIERRE'}</b><span>${money(e.amount)}</span><span class="${cls(e.realized)}">${e.kind==='close'?money(e.realized):''}</span></div>`).join('')}</div>`:'<p class="muted">No hay eventos verificados disponibles para este par.</p>';
 }
}
$$('[data-sub]').forEach(b=>b.onclick=()=>{currentSub=b.dataset.sub;renderedSubKey=chosen+'|'+currentSub;$$('[data-sub]').forEach(x=>x.classList.toggle('active',x===b));renderSub()});
async function loadTradeStatus(){
 try{const r=await fetch('/api/trade/status',{cache:'no-store'});tradeStatus=await r.json();if(!r.ok)throw Error('No se pudo leer Agent');}
 catch(e){tradeStatus=null;console.warn(e);}
 updateArmedBanner();if(currentSub==='operate' && !tradeTicket && !$('#tradeAction')){renderSub();renderedSubKey=chosen+'|'+currentSub;}
}
async function armTrading(){
 if(!tradeStatus?.csrf)return;
 const enabled=$('#armTrade').checked;
 if(enabled && !window.confirm('Vas a habilitar órdenes REALES en Hyperliquid. Las dos patas no son atómicas. ¿Confirmás?')){$('#armTrade').checked=false;return;}
 try{const r=await fetch('/api/trade/arm',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({csrf:tradeStatus.csrf,enabled})});const data=await r.json();if(!r.ok)throw Error(data.detail||'No se pudo cambiar el estado');await loadTradeStatus();}
 catch(e){$('#tradeTicket').textContent='Error de autorización: '+e.message;$('#armTrade').checked=false;}
}
async function previewTrade(){
 if(tradeBusy || !tradeStatus?.csrf)return;
 const p=pairs.find(x=>x.id===chosen);if(!p)return;
 tradeBusy=true;$('#tradePreview').disabled=true;
 try{const r=await fetch('/api/trade/preview',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({csrf:tradeStatus.csrf,pair_id:chosen,operation:$('#tradeAction').value,fraction_pct:Number($('#tradePct').value),slippage_pct:Number($('#tradeSlip').value)})});
 const v=await r.json();if(!r.ok)throw Error(v.detail||'Previsualización rechazada');tradeTicket=v;
 const box=$('#tradeTicket');box.innerHTML=`<div class="ticket-warning">ATENCIÓN: órdenes de dinero real. No son atómicas. Ticket vence en ${v.expires_in_s}s.</div><div class="ticket-table">${v.orders.map(o=>`<div><b>${html(o.coin)}</b><span>${o.order} ${fnum(o.size,7)}</span><span>${money(o.usd)}</span><span>${o.reduce_only?'Reduce-only':''}</span></div>`).join('')}</div><div class="trade-confirm"><label><input id="acceptTicket" type="checkbox"> Confirmo ambas órdenes reales y acepto el riesgo de una sola pata.</label><button class="btn btn-danger" id="executeTrade" disabled>Enviar órdenes reales</button></div>`;
 $('#acceptTicket').onchange=()=>$('#executeTrade').disabled=!$('#acceptTicket').checked;
 $('#executeTrade').onclick=executeTrade;
 }catch(e){$('#tradeTicket').textContent='Error: '+e.message;}finally{tradeBusy=false;$('#tradePreview').disabled=false;}
}
async function executeTrade(){
 if(tradeBusy||!tradeTicket||!$('#acceptTicket')?.checked)return;
 const id=tradeTicket.ticket_id;tradeTicket=null;tradeBusy=true;$('#executeTrade').disabled=true;
 try{const r=await fetch('/api/trade/execute',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({csrf:tradeStatus.csrf,ticket_id:id,confirmation:'CONFIRMAR'})});const v=await r.json();if(!r.ok)throw Error(v.detail||'No se pudo confirmar el resultado');
 $('#tradeTicket').innerHTML=v.complete?`<p class="pnl-positive">Ambas patas confirmadas. ID ${html(v.attempt_id)}</p>`:`<p class="ticket-warning">POSIBLE DESBALANCE. Verificá Hyperliquid antes de operar de nuevo. ID ${html(v.attempt_id)}</p>`;
 await state();await loadTradeStatus();
 }catch(e){$('#tradeTicket').textContent='RESULTADO INCIERTO: '+e.message+' Revisá Hyperliquid antes de volver a operar.';await loadTradeStatus();}
 finally{tradeBusy=false;}
}
async function openAddPair(){
 const dialog=$('#addPairDialog'),notice=$('#addPairError'); notice.textContent='Cargando posiciones abiertas…';
 dialog.showModal();
 try{
  const r=await fetch('/api/trade/pair-candidates',{cache:'no-store'});const data=await r.json();
  if(!r.ok)throw Error(data.detail||'No se pudieron consultar las posiciones');
  const fill=(id,items)=>{const s=$(id);s.replaceChildren(new Option('Elegir…',''));
   for(const sym of items)s.add(new Option(sym,sym));};
  fill('#newPairLong',data.longs||[]);fill('#newPairShort',data.shorts||[]);
  notice.textContent=!(data.longs||[]).length||!(data.shorts||[]).length?'No hay suficientes posiciones sin asignar para crear un par.':'';
 }catch(e){notice.textContent='Error: '+e.message;}
}
async function saveNewPair(e){
 e.preventDefault();const notice=$('#addPairError'),button=$('#addPairSubmit');
 const long=$('#newPairLong').value,short=$('#newPairShort').value;
 if(!long||!short||long===short){notice.textContent='Elegí un long y un short distintos.';return;}
 button.disabled=true;notice.textContent='';
 try{
  // This is an authenticated local configuration write, never an order.
  if(!tradeStatus?.csrf)await loadTradeStatus();
  if(!tradeStatus?.csrf)throw Error('No se pudo autorizar la sesión local');
  const r=await fetch('/api/trade/pairs/add',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({csrf:tradeStatus.csrf,long,short})});
  const result=await r.json();if(!r.ok)throw Error(result.detail||'No se pudo agregar el par');
  chosen=result.id;$('#addPairDialog').close();await state();
 }catch(err){notice.textContent='Error: '+err.message;}finally{button.disabled=false;}
}
$('#addPairOpen').onclick=openAddPair;
$('#addPairCancel').onclick=()=>$('#addPairDialog').close();
$('#addPairForm').addEventListener('submit',saveNewPair);
let liveConnection='conectando';
const liveRatios=new LiveRatios(paintLiveRatios,status=>{liveConnection=status;paintLiveRatios()});
function paintLiveRatios(){
 const p=pairs.find(x=>x.id===chosen),quote=p?liveRatios.quote(p):null,ratio=quote?.ratio??null;
 const change=ratio!==null&&p.entry_ratio>0?(ratio/p.entry_ratio-1)*100:null;
 const values=$$('#metrics .value');
 if(p&&values.length>=2){
  values[0].textContent=fnum(ratio??p.ratio,7);
  values[1].textContent=(ratio!==null?change:p.ratio_change)==null?'N/D':signed(ratio!==null?change:p.ratio_change)+'%';
  values[1].className='value '+cls(ratio!==null?change:p.ratio_change);
  values[0].title=ratio!==null?'Precio de marca long ÷ short, en vivo':'Última lectura; sin precio en vivo vigente';
 }
 const management=$('#managementRatioChange');
 if(management&&p&&p.management_entry_ratio>0){const mc=((ratio??p.ratio)/p.management_entry_ratio-1)*100;management.textContent=signed(mc)+'%';}
 const age=last?Math.max(0,Math.floor((Date.now()-last)/1000))+' s':'sin datos';
 $('#freshness').title=liveRatios.httpError||liveRatios.streamError||'Precios de marca públicos. Si falla WebSocket, consulta automática cada 5 segundos.';
 $('#freshness').className='status '+(!last||Date.now()-last>180000||ratio===null?'error':Date.now()-last>=60000||quote.source!=='ws'?'warn':'ok');
 $('#freshness').textContent=(ratio!==null?(quote.source==='ws'?'● Ratio en vivo':'● Ratio automático · respaldo 5 s'):'● '+liveConnection+' · sin precios recientes')+' · Cuenta/velas: '+age+' · actualizar ↻';
}
window.addEventListener('pagehide',()=>liveRatios.stop());
window.addEventListener('pageshow',event=>{if(event.persisted)location.reload()});
state().then(loadTradeStatus).then(loadAlerts);
// Refresh account and risk values independently of the live ratio WebSocket.
// Avoid concurrent state reads, which could race archive confirmation.
let refreshBusy=false;
setInterval(async()=>{if(refreshBusy || document.hidden)return;refreshBusy=true;try{await state();if(!$('#alerts').hidden)await loadAlerts()}finally{refreshBusy=false}},30000);

let managementRequest=0, dailyZRequest=0;
async function fetchDailyZ(p){
 const request=++dailyZRequest, id=p.id;
 try{const r=await fetch('/api/management/'+encodeURIComponent(id),{cache:'no-store'});const v=await r.json();
  if(!r.ok||request!==dailyZRequest||chosen!==id)return;
  p.z=v.z==null||!Number.isFinite(Number(v.z))?null:Number(v.z);
  const el=$$('#metrics .value')[2];if(el)el.textContent=p.z==null?'N/D':signed(p.z);
 }catch(e){console.warn('Z diario no disponible',e)}
}

async function fetchManagement(p){
 const request=++managementRequest;
 try{
  const response=await fetch('/api/management/'+encodeURIComponent(p.id),{cache:'no-store'});
  const value=await response.json();if(!response.ok)throw Error(value.detail||'Sin datos');
  if(request!==managementRequest||chosen!==p.id)return;
  p.z=Number.isFinite(Number(value.z))&&value.z!==null?Number(value.z):null;
  const metric=$$('#metrics .value')[2];if(metric)metric.textContent=p.z==null?'N/D':signed(p.z);
  if(currentSub!=='management')return;
  const host=$('#managementSignals');if(!host)return;
  host.innerHTML=`<div class="account-grid"><div class="card metric">Toma de ganancias<strong>${html(value.tp)}</strong><small>${html(value.tp_detail)}</small></div><div class="card metric">Agregados<strong>${html(value.add)}</strong><small>${html(value.add_detail)}</small></div></div>${healthMarkup(value.health)}<p class="muted">Referencia ${value.reference==null?'N/D':fnum(value.reference,7)} · Z diario ${value.z==null?'N/D':signed(value.z)} · calculado ${new Date(value.computed_at).toLocaleTimeString('es-AR')}</p>`;
 }catch(e){if(request===managementRequest&&chosen===p.id&&currentSub==='management'&&$('#managementSignals'))$('#managementSignals').textContent='Señales N/D: '+e.message;}
}

function healthMarkup(h){
 if(!h)return '<p class="muted">Salud estadística N/D: no se pudieron verificar las velas.</p>';
 return `<div class="card health-panel"><b>Salud estadística · ${html(h.label)}</b><div class="account-grid"><div>ADF p-value<strong>${h.adf_pvalue==null?'N/D':fnum(h.adf_pvalue,4)}</strong></div><div>Half-life<strong>${h.half_life_days==null?'N/D':fnum(h.half_life_days,1)+' días aprox.'}</strong></div><div>Muestra<strong>${html(h.samples)} cierres diarios</strong></div></div><p>${html(h.reason)}</p><small>Log-ratio · ADF al 5%. Diagnóstico informativo; no modifica reglas ni garantiza reversión.</small></div>`;
}
async function loadAlerts(){
 const host=$('#alerts');if(!host)return;
 try{
  const response=await fetch('/api/alerts',{cache:'no-store'});const a=await response.json();if(!response.ok)throw Error('No se pudieron leer las alertas');
  host.innerHTML=`<h3>Alertas de escritorio</h3><div class="card health-panel"><button class="btn" id="alertsToggle">${a.enabled?'Desactivar alertas':'Activar alertas'}</button> <button class="btn" id="alertsTest">Probar aviso</button><span id="alertsTestResult"></span><p>${a.enabled?'Vigilante activado':'Vigilante desactivado'} · Revisión cada 60 segundos. Sigue con la pestaña cerrada mientras el servidor local esté encendido.</p><p>Liquidación ≤ 10% · desbalance ≥ 5% · cruces de Z ±2 · TP/ADD · patas ausentes · fallos de datos. Máximo un aviso por condición cada 15 minutos.</p><small>${a.desktop_available?'Notificaciones de escritorio disponibles; dependen de la sesión de Ubuntu.':'No se encontró notify-send. Los avisos se conservarán aquí; instalá libnotify-bin para recibirlos en Ubuntu.'} Última lectura: ${a.last_ok?new Date(a.last_ok).toLocaleString('es-AR'):'sin lectura todavía'}. ${a.error?'Error: '+html(a.error):''}</small></div><div class="event-log alert-history">${a.events.map(e=>`<div><span>${new Date(e.time).toLocaleString('en-US')}</span><span>${html(e.message)}</span><small>${e.desktop?'Enviado al escritorio':'Guardado; escritorio no disponible'}</small></div>`).join('')||'<p>Sin avisos registrados.</p>'}</div>`;
  $('#alertsTest').onclick=async()=>{
   const button=$('#alertsTest');button.disabled=true;
   try{if(!tradeStatus?.csrf)await loadTradeStatus();const response=await fetch('/api/alerts/test',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({csrf:tradeStatus?.csrf})});const result=await response.json();if(!response.ok)throw Error('Prueba rechazada');$('#alertsTestResult').textContent=result.delivered?' Aviso enviado al escritorio.':' No se pudo enviar: revisá notify-send y la sesión de Ubuntu.'}catch(e){$('#alertsTestResult').textContent=e.message}finally{button.disabled=false}
  };
  $('#alertsToggle').onclick=async()=>{
   const button=$('#alertsToggle');button.disabled=true;
   try{if(!tradeStatus?.csrf)await loadTradeStatus();const r=await fetch('/api/alerts',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({csrf:tradeStatus?.csrf,enabled:!a.enabled})});if(!r.ok)throw Error('No se pudo cambiar el vigilante');await loadAlerts()}catch(e){button.textContent=e.message;button.disabled=false}
  };
 }catch(e){host.textContent=e.message}
}

// Chart controls only mutate presentation; never interact with the trading agent.
$$('[data-layer]').forEach(input=>input.addEventListener('change',()=>{chartLayers[input.dataset.layer]=input.checked;if(lastChart?.pair===chosen){const p=pairs.find(x=>x.id===chosen);if(p)drawSvg(lastChart.bars,p.entry_ratio,p)}}));
$('#chartReset')?.addEventListener('click',()=>{if(activeChart?.scrollToRealTime)activeChart.scrollToRealTime();else if(activeChart?.scrollToTimestamp&&lastChart?.bars?.length)activeChart.scrollToTimestamp(lastChart.bars.at(-1).timestamp)});
$('#chartMode')?.addEventListener('change',e=>{chartMode=e.target.value;const p=pairs.find(x=>x.id===chosen);if(chartMode==='legs'||chartMode==='pnl'){$('#chart').innerHTML='<div class="chart-placeholder">Esta vista requiere series históricas verificadas de ambas patas / PnL y aún no está disponible. Se conserva la vista del ratio.</div>';activeChart=null;return}if(p&&lastChart?.pair===chosen)drawSvg(lastChart.bars,p.entry_ratio,p)});
