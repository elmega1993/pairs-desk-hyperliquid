/* Aurora interactive chart. Uses the locally vendored, already-tested KLineCharts engine.
   Read-only: never sends orders. Lines are management targets, NOT live exchange orders. */
'use strict';
window.AuroraTradingChart=(()=>{
 let chart=null,registered=false,lastPair=null,lastBars=[];
 const $=id=>document.getElementById(id);
 const finite=x=>x!==null&&x!==undefined&&x!==''&&Number.isFinite(Number(x));
 const precision=(entry,bars)=>{const xs=[entry,...bars.flatMap(b=>[b.open,b.high,b.low,b.close])].filter(x=>finite(x)&&Number(x)>0).map(Number);if(!xs.length)return 6;const min=Math.min(...xs);return min<.001?8:min<.01?7:min<.1?6:4};
 function register(){if(registered)return;const k=window.klinecharts;
  k.registerOverlay({name:'aurora_level',totalStep:1,lock:true,needDefaultPointFigure:false,createPointFigures:({coordinates,bounding,overlay})=>{if(!coordinates.length)return [];const y=coordinates[0].y,m=overlay.extendData||{};return [{type:'line',attrs:{coordinates:[{x:0,y},{x:bounding.width,y}]},styles:{color:m.color||'#f4bb64',size:1,dashedValue:[6,4]}},{type:'text',attrs:{x:9,y:y-7,text:m.label||''},styles:{color:m.color||'#f4bb64',size:11,fontFamily:'system-ui'}}]}});
  k.registerOverlay({name:'aurora_event',totalStep:1,lock:true,needDefaultPointFigure:false,createPointFigures:({coordinates,overlay})=>{if(!coordinates.length)return [];const {x,y}=coordinates[0],m=overlay.extendData||{};return [{type:'circle',attrs:{x,y,r:5},styles:{color:m.color||'#f4bb64',style:'fill'}},{type:'text',attrs:{x:x+8,y:y+(m.side==='below'?17:-8),text:m.label||''},styles:{color:m.color||'#f4bb64',size:11,fontFamily:'system-ui'}}]}});
  k.registerOverlay({name:'aurora_steps',totalStep:1,lock:true,needDefaultPointFigure:false,createPointFigures:({coordinates,overlay})=>{const out=[],m=overlay.extendData||{};for(let i=1;i<coordinates.length;i++){const a=coordinates[i-1],b=coordinates[i];if(![a.x,a.y,b.x,b.y].every(Number.isFinite))continue;out.push({type:'line',attrs:{coordinates:[{x:a.x,y:a.y},{x:b.x,y:a.y}]},styles:{color:m.color||'#f4bb64',size:2}});out.push({type:'line',attrs:{coordinates:[{x:b.x,y:a.y},{x:b.x,y:b.y}]},styles:{color:m.color||'#f4bb64',size:2}})}return out}});
  registered=true;
 }
 function destroy(){if(chart){try{window.klinecharts.dispose($('ratio-chart'))}catch(e){}chart=null}const host=$('ratio-chart');if(host)host.replaceChildren()}
 function draw(pair,bars){lastPair=pair;lastBars=bars;destroy();const host=$('ratio-chart'),k=window.klinecharts;
  if(!k?.init){host.textContent='Motor gráfico local no disponible';return false}
  if(!bars.length){host.textContent='Sin velas verificables';return false}
  try{register();chart=k.init(host,{styles:{grid:{show:true,horizontal:{color:'#293954'},vertical:{color:'#22304a'}},candle:{bar:{upColor:'#28d8b9',downColor:'#fa6388',noChangeColor:'#9cacc9',upBorderColor:'#28d8b9',downBorderColor:'#fa6388',upWickColor:'#28d8b9',downWickColor:'#fa6388'}},xAxis:{axisLine:{color:'#344361'}},yAxis:{axisLine:{color:'#344361'}}}});
   chart.setPriceVolumePrecision?.(precision(pair.entry_ratio,bars),0);
   chart.applyNewData(bars.map(b=>({...b,volume:0})));
   const flags={average:$('layer-average')?.checked,initial:$('layer-initial')?.checked,targets:$('layer-targets')?.checked,events:$('layer-events')?.checked};
   const levels=[];if(flags.average&&finite(pair.entry_ratio)&&pair.entry_ratio>0)levels.push({label:'MEDIA ACTUAL',value:Number(pair.entry_ratio),color:'#f4bb64'});
   const hist=pair.entry_history;if(flags.initial&&hist?.available&&finite(hist.initial_ratio))levels.push({label:'ENTRADA INICIAL',value:Number(hist.initial_ratio),color:'#a9b2bf'});
   const base=Number(pair.management_entry_ratio),rules=pair.management_rules||{};
   if(flags.targets&&Number.isFinite(base)&&base>0){for(const [label,field,def] of [['TP1','tp1_ratio_pct',10],['TP2','tp2_ratio_pct',20],['TP3','tp3_ratio_pct',20],['ADD1','add1_ratio_pct',-8],['ADD2','add2_ratio_pct',-15]]){const pct=Number(rules[field]??def);if(Number.isFinite(pct))levels.push({label:label+' · OBJETIVO',value:base*(1+pct/100),color:label.startsWith('TP')?'#26d9b6':'#ff7190'})}}
   for(const level of levels)if(Number.isFinite(level.value)&&level.value>0)chart.createOverlay({name:'aurora_level',lock:true,points:[{timestamp:bars.at(-1).timestamp,value:level.value}],extendData:level});
   if(flags.average&&hist?.available&&Array.isArray(hist.steps)&&hist.steps.length){const start=bars[0].timestamp,end=bars.at(-1).timestamp;const snap=t=>bars.find(b=>b.timestamp>=t)?.timestamp??end;const mapped=[];const prev=hist.steps.filter(s=>s.time<=start).at(-1);if(prev)mapped.push({timestamp:start,value:Number(prev.ratio)});for(const s of hist.steps){if(s.time<start||s.time>end||!finite(s.ratio))continue;const ts=snap(s.time),pt={timestamp:ts,value:Number(s.ratio)};if(mapped.at(-1)?.timestamp===ts)mapped[mapped.length-1]=pt;else mapped.push(pt)}if(mapped.length&&mapped.at(-1).timestamp<end)mapped.push({timestamp:end,value:mapped.at(-1).value});if(mapped.length>1)chart.createOverlay({name:'aurora_steps',lock:true,points:mapped,extendData:{color:'#d8a957'}})}
   if(flags.events){const markers=[];if(finite(pair.opened_at))markers.push({time:Number(pair.opened_at),label:'E',side:'below',color:'#b4c0dc'});for(const e of pair.events||[])if(finite(e.time))markers.push({time:Number(e.time),label:e.kind==='add'?'ADD':'RED',side:e.kind==='add'?'below':'above',color:e.kind==='add'?'#f4bb64':'#39d9b8'});for(const m of markers){const b=bars.find(b=>b.timestamp>=m.time);if(b)chart.createOverlay({name:'aurora_event',lock:true,points:[{timestamp:b.timestamp,value:m.side==='below'?b.low:b.high}],extendData:m})}}
   chart.scrollToRealTime?.();$('chart-hover').textContent=`${bars.length} velas · rueda: zoom · arrastrar: desplazar · TP/ADD: objetivos, no órdenes`;
   return true;
  }catch(e){destroy();host.textContent='No se pudo inicializar el gráfico interactivo';console.error('Aurora chart',e);return false}
 }
 function reset(){chart?.scrollToRealTime?.()}
 return {draw,destroy,reset,redraw:()=>{if(lastPair)draw(lastPair,lastBars)}};
})();
