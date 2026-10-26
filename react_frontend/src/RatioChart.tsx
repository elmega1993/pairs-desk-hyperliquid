import {useEffect,useMemo,useRef,useState,type ReactNode} from 'react';
import type {Bar,Pair,AdaptiveLevels} from './types';
import {ZScorePane} from './ZScorePane';
import {buildRatioStats} from './ratioStats';
import {indicatorIsStacked,indicatorPaneConfig,indicatorPaneId} from './indicatorConfig';
import {clearTrackedOverlays,rememberOverlay,type OverlayTracker} from './overlayLifecycle';

type ChartInstance={applyNewData:(bars:unknown[])=>void;createOverlay:(args:unknown)=>unknown;setPriceVolumePrecision?:(p:number,v:number)=>void;scrollToRealTime?:()=>void;resize?:()=>void;removeOverlay?:(id?:string)=>void;createIndicator?:(value:string|Record<string,unknown>,isStack?:boolean,pane?:{id:string})=>unknown;overrideIndicator?:(override:Record<string,unknown>,paneId?:string)=>unknown;setStyles?:(styles:unknown)=>void;removeIndicator?:(paneId:string,name?:string)=>void;getOverlays?:()=>unknown[];applyMoreData?:(bars:unknown[])=>void};
type Engine={registerIndicator?:(definition:unknown)=>void;init:(host:HTMLElement,options:unknown)=>ChartInstance;dispose:(host:HTMLElement)=>void;registerOverlay:(definition:unknown)=>void};
declare global {interface Window{klinecharts?:Engine}}
export type ChartLayers={average:boolean;initial:boolean;targets:boolean;events:boolean};
type StatLayers={percentiles:boolean;zscore:boolean;histogram:boolean;forward:boolean};
const finite=(value:unknown):value is number=>value!==null&&value!==undefined&&value!==''&&Number.isFinite(Number(value));
let overlaysRegistered=false;
// Eje X con nombres de mes («ago», «21 ago») en vez de números; otros formatos quedan como estaban.
function monthAxisDate(dtf:Intl.DateTimeFormat,timestamp:number,format:string,type:number){
 const timeZone=dtf?.resolvedOptions?.().timeZone;const d=new Date(timestamp);
 const part=(o:Intl.DateTimeFormatOptions)=>new Intl.DateTimeFormat('es-AR',{timeZone,...o}).format(d).replace('.','');
 if(type===2){
  if(format==='YYYY-MM')return part({month:'numeric'})==='1'?part({month:'short',year:'2-digit'}):part({month:'short'});
  if(format==='YYYY')return part({year:'numeric'});
  if(format==='MM-DD')return part({day:'numeric',month:'short'});
  if(format==='YYYY-MM-DD')return part({day:'numeric',month:'short',year:'2-digit'});
  if(format==='MM-DD HH:mm')return part({day:'numeric',month:'short'})+' '+part({hour:'2-digit',minute:'2-digit',hour12:false});
 }
 const f=new Intl.DateTimeFormat('en-CA',{timeZone,year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hourCycle:'h23'}).formatToParts(d).reduce((a:Record<string,string>,x)=>{a[x.type]=x.value;return a},{});
 return format.replace('YYYY',f.year).replace('MM',f.month).replace('DD',f.day).replace('HH',f.hour).replace('mm',f.minute);
}
function register(k:Engine){if(overlaysRegistered)return;
 // Un texto vacío igual dibuja una cajita azul en KLineCharts: se descarta si no hay etiqueta.
 const reg=(d:any)=>{const original=d.createPointFigures;k.registerOverlay({...d,createPointFigures:(args:unknown)=>{const figures=original(args);return Array.isArray(figures)?figures.filter((f:any)=>!(f?.type==='text'&&!f?.attrs?.text)):figures}})};
 reg({name:'react_level',totalStep:1,lock:true,needDefaultPointFigure:false,createPointFigures:({coordinates,bounding,overlay}:any)=>{if(!coordinates.length)return [];const y=coordinates[0].y,m=overlay.extendData||{};return [{type:'line',attrs:{coordinates:[{x:0,y},{x:bounding.width,y}]},styles:{color:m.color||'#f4bb64',size:1,dashedValue:[6,4]}},{type:'text',attrs:{x:8,y:y-7,text:m.label||''},styles:{color:m.color||'#f4bb64',size:10,fontFamily:'system-ui',backgroundColor:'transparent',borderColor:'transparent',borderSize:0}}]}});
 reg({name:'react_event',totalStep:1,lock:true,needDefaultPointFigure:false,createPointFigures:({coordinates,overlay}:any)=>{if(!coordinates.length)return [];const {x,y}=coordinates[0],m=overlay.extendData||{};return [{type:'circle',attrs:{x,y,r:5},styles:{color:m.color||'#f4bb64',style:'fill'}},{type:'text',attrs:{x:x+8,y:y+(m.side==='below'?17:-8),text:m.label||''},styles:{color:m.color||'#f4bb64',size:11,fontFamily:'system-ui',backgroundColor:'transparent',borderColor:'transparent',borderSize:0}}]}});
 reg({name:'react_steps',totalStep:1,lock:true,needDefaultPointFigure:false,createPointFigures:({coordinates,overlay}:any)=>{const result=[],m=overlay.extendData||{};for(let i=1;i<coordinates.length;i++){const a=coordinates[i-1],b=coordinates[i];if(![a.x,a.y,b.x,b.y].every(Number.isFinite))continue;result.push({type:'line',attrs:{coordinates:[{x:a.x,y:a.y},{x:b.x,y:a.y}]},styles:{color:m.color||'#d8a957',size:2}});result.push({type:'line',attrs:{coordinates:[{x:b.x,y:a.y},{x:b.x,y:b.y}]},styles:{color:m.color||'#d8a957',size:2}})}return result}});
 reg({name:'react_stat_band',totalStep:1,lock:true,needDefaultPointFigure:false,createPointFigures:({coordinates,bounding,overlay}:any)=>{if(coordinates.length<2)return [];const top=Math.min(coordinates[0].y,coordinates[1].y),bottom=Math.max(coordinates[0].y,coordinates[1].y),m=overlay.extendData||{};return [{type:'rect',attrs:{x:0,y:top,width:bounding.width,height:Math.max(1,bottom-top)},styles:{color:m.fill||'#8d7ff522',style:'fill'}},{type:'text',attrs:{x:12,y:top+14,text:m.label||''},styles:{color:m.color||'#b7a9ff',size:10,fontFamily:'system-ui',backgroundColor:'transparent',borderColor:'transparent',borderSize:0}}]}});
 reg({name:'react_stat_line',totalStep:1,lock:true,needDefaultPointFigure:false,createPointFigures:({coordinates,bounding,overlay}:any)=>{if(!coordinates.length)return [];const m=overlay.extendData||{},y=coordinates[0].y;return [{type:'line',attrs:{coordinates:[{x:0,y},{x:bounding.width,y}]},styles:{color:m.color||'#b7a9ff',size:1,dashedValue:[4,4]}},{type:'text',attrs:{x:8,y:y-5,text:m.label||''},styles:{color:m.color||'#b7a9ff',size:10,fontFamily:'system-ui',backgroundColor:'transparent',borderColor:'transparent',borderSize:0}}]}});
 reg({name:'react_stat_hist',totalStep:1,lock:true,needDefaultPointFigure:false,createPointFigures:({coordinates,bounding,overlay}:any)=>{if(coordinates.length<2)return [];const a=coordinates[0],b=coordinates[1],m=overlay.extendData||{},y=Math.min(a.y,b.y),height=Math.max(1,Math.abs(a.y-b.y)),width=Math.max(3,Number(m.width)||3);return [{type:'rect',attrs:{x:bounding.width-width,y,width,height},styles:{color:m.color||'#8d7ff566',style:'fill'}}]}});
 overlaysRegistered=true;
}

// ---- Línea del ratio: verde sobre tu entrada, roja debajo (reemplaza las velas japonesas) ----
const ENTRY_LINE='PAIRS_ENTRY_LINE',LINE_UP='#3ddc97',LINE_DOWN='#ff7b8f';
let entryLineRegistered=false;
function registerEntryLine(k:Engine){
 if(entryLineRegistered||!k.registerIndicator)return;
 k.registerIndicator({name:ENTRY_LINE,shortName:'',series:'price',calcParams:[],figures:[],calc:()=>[],
  createTooltipDataSource:()=>({name:'',calcParamsText:'',features:[],legends:[]}),
  draw:({ctx,kLineDataList,indicator,visibleRange,bounding,xAxis,yAxis}:any)=>{
   const data=kLineDataList as {close:number}[];if(!data?.length)return true;
   const from=Math.max(0,visibleRange.from-1),to=Math.min(data.length-1,visibleRange.to);
   const pts:{x:number;y:number}[]=[];
   for(let i=from;i<=to;i++){const c=Number(data[i]?.close);if(!Number.isFinite(c))continue;const x=xAxis.convertToPixel(i),y=yAxis.convertToPixel(c);if(Number.isFinite(x)&&Number.isFinite(y))pts.push({x,y})}
   if(pts.length<2)return true;
   const entry=Number(indicator.calcParams?.[0]),hasEntry=Number.isFinite(entry)&&entry>0;
   const w=bounding.width,h=bounding.height;
   const ey=hasEntry?Math.max(0,Math.min(h,yAxis.convertToPixel(entry))):0;
   const trace=()=>{ctx.beginPath();pts.forEach((q,i)=>i?ctx.lineTo(q.x,q.y):ctx.moveTo(q.x,q.y))};
   const part=(top:number,bottom:number,color:string,glow:string,fillA:string,fillB:string)=>{
    if(bottom-top<=0)return;
    ctx.save();ctx.beginPath();ctx.rect(0,top,w,bottom-top);ctx.clip();
    // relleno entre la línea y el nivel de entrada, con degradado
    const g=ctx.createLinearGradient(0,top,0,bottom);g.addColorStop(0,fillA);g.addColorStop(1,fillB);
    trace();ctx.lineTo(pts[pts.length-1].x,ey);ctx.lineTo(pts[0].x,ey);ctx.closePath();ctx.fillStyle=g;ctx.fill();
    // línea con brillo (glow)
    ctx.shadowColor=glow;ctx.shadowBlur=8;ctx.lineWidth=2.2;ctx.lineJoin='round';ctx.lineCap='round';ctx.strokeStyle=color;trace();ctx.stroke();
    ctx.restore()};
   if(!hasEntry){part(0,h,LINE_UP,'rgba(61,220,151,.6)','rgba(61,220,151,.02)','rgba(61,220,151,.28)')}
   else{
    part(0,ey,LINE_UP,'rgba(61,220,151,.6)','rgba(61,220,151,.02)','rgba(61,220,151,.28)');
    part(ey,h,LINE_DOWN,'rgba(255,123,143,.6)','rgba(255,123,143,.28)','rgba(255,123,143,.02)')}
   // punto en el último dato visible
   if(to===data.length-1){const q=pts[pts.length-1],up=!hasEntry||Number(data[to].close)>=entry,c=up?LINE_UP:LINE_DOWN;
    ctx.beginPath();ctx.arc(q.x,q.y,7,0,Math.PI*2);ctx.fillStyle=up?'rgba(61,220,151,.22)':'rgba(255,123,143,.22)';ctx.fill();
    ctx.beginPath();ctx.arc(q.x,q.y,4,0,Math.PI*2);ctx.fillStyle=c;ctx.fill();ctx.lineWidth=2;ctx.strokeStyle='#1f1f1e';ctx.stroke()}
   return true}});
 entryLineRegistered=true}
const entryOf=(pair:Pair|null|undefined)=>finite(pair?.entry_ratio)&&Number(pair?.entry_ratio)>0?Number(pair?.entry_ratio):null;
function applyEntryLine(chart:ChartInstance,pair:Pair|null|undefined){try{chart.overrideIndicator?.({name:ENTRY_LINE,calcParams:[entryOf(pair)]},'candle_pane')}catch{}}
function precision(entry:unknown,bars:Bar[]){const nums=[entry,...bars.flatMap(b=>[b.open,b.high,b.low,b.close])].filter(v=>finite(v)&&Number(v)>0).map(Number);if(!nums.length)return 6;const min=Math.min(...nums);return min<.001?8:min<.01?7:min<.1?6:4}
function addTrackedOverlay(chart:ChartInstance,tracker:OverlayTracker,args:unknown){rememberOverlay(tracker,chart.createOverlay(args))}
function renderLevels(chart:ChartInstance,pair:Pair,bars:Bar[],layers:ChartLayers,adaptive:AdaptiveLevels|null,tracker:OverlayTracker,showLabels=false){clearTrackedOverlays(tracker,id=>chart.removeOverlay?.(id));const levels:{label:string;value:number;color:string}[]=[];
 if(layers.average&&finite(pair.entry_ratio)&&Number(pair.entry_ratio)>0)levels.push({label:'MEDIA ACTUAL',value:Number(pair.entry_ratio),color:'#f4bb64'});
 const hist=pair.entry_history as {available?:boolean;initial_ratio?:number;steps?:{time:number;ratio:number}[]}|undefined;
 if(layers.initial&&hist?.available&&finite(hist.initial_ratio))levels.push({label:'ENTRADA INICIAL',value:Number(hist.initial_ratio),color:'#a9b2bf'});
 if(layers.targets&&(adaptive?.status==='ok'||adaptive?.status==='partial')){
   for(const [key,label] of [['tp1','TP1'],['tp2','TP2'],['add1','ADD1'],['add2','ADD2']] as const){
     const value=adaptive.levels[key];
     if(Number.isFinite(value)&&value>0)levels.push({label:label+' · ADAPTATIVO',value,color:key.startsWith('tp')?'#26d9b6':'#ff7190'});
   }
 }
 // Merge labels for overlapping targets without changing their actual prices.
 const priceSpan=Math.max(...bars.map(b=>b.high))-Math.min(...bars.map(b=>b.low));
 const grouped=new Set<number>();for(let i=0;i<levels.length;i++){if(grouped.has(i))continue;const level=levels[i];const group=[level];for(let j=i+1;j<levels.length;j++){if(!grouped.has(j)&&priceSpan>0&&Math.abs(level.value-levels[j].value)/priceSpan<.009){group.push(levels[j]);grouped.add(j)}}const visibleLabels=group.filter(g=>!/^TP\d|^ADD\d/.test(g.label)).map(g=>g.label);addTrackedOverlay(chart,tracker,{name:'react_level',lock:true,points:[{timestamp:bars[bars.length-1].timestamp,value:level.value}],extendData:{...level,label:showLabels?visibleLabels.join(' / '):''}})}
 if(layers.average&&hist?.available&&Array.isArray(hist.steps)&&hist.steps.length){const start=bars[0].timestamp,end=bars[bars.length-1].timestamp;const snap=(t:number)=>bars.find(b=>b.timestamp>=t)?.timestamp??end;const points:{timestamp:number;value:number}[]=[];const prev=hist.steps.filter(s=>s.time<=start).at(-1);if(prev)points.push({timestamp:start,value:Number(prev.ratio)});for(const step of hist.steps){if(step.time<start||step.time>end||!finite(step.ratio))continue;const pt={timestamp:snap(step.time),value:Number(step.ratio)};if(points.at(-1)?.timestamp===pt.timestamp)points[points.length-1]=pt;else points.push(pt)}if(points.length&&points.at(-1)!.timestamp<end)points.push({timestamp:end,value:points.at(-1)!.value});if(points.length>1)addTrackedOverlay(chart,tracker,{name:'react_steps',lock:true,points,extendData:{color:'#d8a957'}})}
 if(layers.events){const markers:{time:number;label:string;side:string;color:string}[]=[];if(finite(pair.opened_at))markers.push({time:Number(pair.opened_at),label:'E',side:'below',color:'#b4c0dc'});for(const event of (Array.isArray(pair.events)?pair.events:[]) as {time?:number;kind?:string}[])if(finite(event.time))markers.push({time:Number(event.time),label:event.kind==='add'?'ADD':'RED',side:event.kind==='add'?'below':'above',color:event.kind==='add'?'#3ddc97':'#ff7b8f'});for(const marker of markers){const bar=bars.find(b=>b.timestamp>=marker.time);if(bar)addTrackedOverlay(chart,tracker,{name:'react_event',lock:true,points:[{timestamp:bar.timestamp,value:marker.side==='below'?bar.low:bar.high}],extendData:{...marker,label:showLabels?marker.label:''}})}}
}
function renderStats(chart:ChartInstance,bars:Bar[],stats:ReturnType<typeof buildRatioStats>,layers:StatLayers,tracker:OverlayTracker,showLabels=false){
 clearTrackedOverlays(tracker,id=>chart.removeOverlay?.(id));
 if(!stats||!bars.length)return;
 const start=bars[0].timestamp,end=bars.at(-1)!.timestamp;
 const point=(value:number)=>({timestamp:end,value});
 if(layers.percentiles){
   addTrackedOverlay(chart,tracker,{name:'react_stat_band',lock:true,points:[point(stats.percentiles.p75),point(stats.percentiles.p25)],extendData:{label:showLabels?'P75–P25 · zona normal':'',color:'#b9a8ff',fill:'#8d7ff522'}});
   addTrackedOverlay(chart,tracker,{name:'react_stat_band',lock:true,points:[point(stats.percentiles.p90),point(stats.percentiles.p75)],extendData:{label:showLabels?'P90–P75 · extendida':'',color:'#f4bb64',fill:'#f4bb6417'}});
   addTrackedOverlay(chart,tracker,{name:'react_stat_band',lock:true,points:[point(stats.percentiles.p25),point(stats.percentiles.p10)],extendData:{label:showLabels?'P25–P10 · extendida':'',color:'#71b8ff',fill:'#71b8ff12'}});
   for(const [label,value,color] of [['Mediana',stats.percentiles.p50,'#b9a8ff'],['P90',stats.percentiles.p90,'#f4bb64'],['P10',stats.percentiles.p10,'#71b8ff']] as const)addTrackedOverlay(chart,tracker,{name:'react_stat_line',lock:true,points:[{timestamp:start,value}],extendData:{label:showLabels?`${label} ${value}`:'',color}});
 }
 if(layers.histogram){const maxWidth=76;for(const bin of stats.histogram){const width=maxWidth*bin.count/bin.maxCount;addTrackedOverlay(chart,tracker,{name:'react_stat_hist',lock:true,points:[point(bin.high),point(bin.low)],extendData:{width,color:'#8d7ff566'}})}}
}
export function RatioChart({pair,bars,layers,adaptive,error,interval,onLoadOlder,moreLoading,lead,onLayerChange}:{lead?:ReactNode;onLayerChange?:(key:keyof ChartLayers,value:boolean)=>void;pair:Pair|null;bars:Bar[];layers:ChartLayers;adaptive:AdaptiveLevels|null;error:string;interval:string;onLoadOlder:()=>void;moreLoading:boolean}){
 const [indicators,setIndicators]=useState<string[]>(()=>{try{return JSON.parse(localStorage.getItem('pairs-chart-indicators')||'[]')}catch{return []}});
 const [hoverLabels,setHoverLabels]=useState(false);const [showTools,setShowTools]=useState(false);const [drawing,setDrawing]=useState('');const [chartFull,setChartFull]=useState(false);const [statLayers,setStatLayers]=useState<StatLayers>({percentiles:true,zscore:true,histogram:true,forward:true});
 const drawingNames:Record<string,string>={line:'segment',ray:'rayLine',horizontal:'horizontalStraightLine',vertical:'verticalStraightLine',fib:'fibonacciLine',rect:'rect',parallel:'parallelStraightLine',text:'simpleAnnotation'};
 const toggleIndicator=(name:string)=>setIndicators(prev=>{const next=prev.includes(name)?prev.filter(x=>x!==name):[...prev,name];localStorage.setItem('pairs-chart-indicators',JSON.stringify(next));return next});
 const addDrawing=(name:string)=>{setDrawing(name);try{chart.current?.createOverlay({name:drawingNames[name],lock:false})}catch(e){console.error('Herramienta de dibujo',e)}};
 const drawingsKey='pairs-chart-drawings:'+String(pair?.id||'')+':'+interval;
 const saveDrawings=()=>{try{localStorage.setItem(drawingsKey,JSON.stringify((chart.current?.getOverlays?.()||[]).filter((o:any)=>o?.name&&Object.values(drawingNames).includes(o.name))));setDrawing('guardado')}catch(e){console.error(e)}};
 const labelsRef=useRef(false),host=useRef<HTMLDivElement>(null),chart=useRef<ChartInstance|null>(null),layersRef=useRef(layers),pairRef=useRef(pair),levelOverlayIds=useRef<OverlayTracker>(new Set()),statOverlayIds=useRef<OverlayTracker>(new Set());
 layersRef.current=layers;pairRef.current=pair;labelsRef.current=hoverLabels;
 const stats=useMemo(()=>buildRatioStats(bars,180,14),[bars]);
 const signature=JSON.stringify(pair?{id:pair.id,entry_ratio:pair.entry_ratio,entry_history:pair.entry_history,management_entry_ratio:pair.management_entry_ratio,management_rules:pair.management_rules,opened_at:pair.opened_at,events:pair.events,adaptive}:null);
 useEffect(()=>{const el=host.current,k=window.klinecharts;if(!el||!k||!pairRef.current||!bars.length)return;register(k);registerEntryLine(k);let instance:ChartInstance|null=null;try{instance=k.init(el,{customApi:{formatDate:monthAxisDate},styles:{grid:{show:true,horizontal:{color:'#33322f'},vertical:{color:'#2b2a28'}},candle:{type:'area',area:{lineSize:2,lineColor:'rgba(0,0,0,0)',backgroundColor:[{offset:0,color:'rgba(0,0,0,0)'},{offset:1,color:'rgba(0,0,0,0)'}],point:{show:false}},tooltip:{showRule:'always',showType:'standard',text:{family:'Inter, system-ui, sans-serif',size:11,color:'#c9d6ed'},custom:[{title:'Hora: ',value:'{time}'},{title:'Ratio: ',value:'{close}'}]},priceMark:{high:{textFamily:'Inter, system-ui, sans-serif'},low:{textFamily:'Inter, system-ui, sans-serif'},last:{text:{family:'Inter, system-ui, sans-serif'}}},bar:{upColor:'#3ddc97',downColor:'#ff7b8f',upBorderColor:'#3ddc97',downBorderColor:'#ff7b8f',upWickColor:'#3ddc97',downWickColor:'#ff7b8f'}},xAxis:{axisLine:{color:'#3a3935'},tickText:{family:'Inter, system-ui, sans-serif',size:11,color:'#a3a097'}},yAxis:{axisLine:{color:'#3a3935'},tickText:{family:'Inter, system-ui, sans-serif',size:11,color:'#a3a097'}},crosshair:{horizontal:{text:{family:'Inter, system-ui, sans-serif',size:11}},vertical:{text:{family:'Inter, system-ui, sans-serif',size:11}}}}});chart.current=instance;try{instance.createIndicator?.({name:ENTRY_LINE,calcParams:[entryOf(pairRef.current)]},true,{id:'candle_pane'})}catch(e){console.error('Línea del ratio',e);try{instance.setStyles?.({candle:{area:{lineColor:LINE_UP,backgroundColor:[{offset:0,color:'rgba(61,220,151,.02)'},{offset:1,color:'rgba(61,220,151,.25)'}]}}})}catch{}}levelOverlayIds.current.clear();statOverlayIds.current.clear();instance.setPriceVolumePrecision?.(precision(pairRef.current.entry_ratio,bars),0);instance.applyNewData(bars.map(b=>({...b,volume:0})));renderLevels(instance,pairRef.current,bars,layersRef.current,adaptive,levelOverlayIds.current,labelsRef.current);renderStats(instance,bars,stats,statLayers,statOverlayIds.current,labelsRef.current);instance.scrollToRealTime?.()}catch(e){console.error('Ratio chart',e)}
 const observer=new ResizeObserver(()=>instance?.resize?.());observer.observe(el);return()=>{observer.disconnect();chart.current=null;try{k.dispose(el)}catch{}};
 // Reinitialize only when selecting a different pair or interval; candles update separately.
 },[pair?.id,interval,Boolean(bars.length)]);
 useEffect(()=>{if(!chart.current||!bars.length)return;try{chart.current.applyNewData(bars.map(b=>({...b,volume:0})));if(pairRef.current&&bars.length){renderLevels(chart.current,pairRef.current,bars,layersRef.current,adaptive,levelOverlayIds.current,labelsRef.current);renderStats(chart.current,bars,stats,statLayers,statOverlayIds.current,labelsRef.current)}}catch(e){console.error('Velas',e)}},[bars]);
 useEffect(()=>{if(!chart.current)return;for(const name of ['MA','EMA','BOLL','RSI','MACD']){try{chart.current.removeIndicator?.(indicatorPaneId(name),name)}catch{}}for(const name of indicators){try{chart.current.createIndicator?.(name,indicatorIsStacked(name),indicatorPaneConfig(name))}catch(e){console.warn('Indicador',name,e)}}},[indicators,pair?.id,interval]);
 useEffect(()=>{const k=window.klinecharts,el=host.current;if(!k||!el||!chart.current||!pairRef.current||!bars.length)return; // preserve scroll/zoom on layer or level changes by retaining chart instance
 try{applyEntryLine(chart.current,pairRef.current);renderLevels(chart.current,pairRef.current,bars,layersRef.current,adaptive,levelOverlayIds.current,labelsRef.current);renderStats(chart.current,bars,stats,statLayers,statOverlayIds.current,labelsRef.current)}catch(e){console.error('Error actualizando niveles',e)};
 },[signature,JSON.stringify(layers),JSON.stringify(statLayers),stats,hoverLabels]);
 const statToggle=(key:keyof StatLayers)=>setStatLayers(prev=>({...prev,[key]:!prev[key]}));
 return <div className={chartFull?'chart-pro chart-pro-full':'chart-pro'}><div className="chart-pro-toolbar"><div className="chart-pro-bar">{lead}<span className="chart-pro-spacer"/><button type="button" className={showTools?'active':''} aria-expanded={showTools} onClick={()=>setShowTools(v=>!v)} title="Capas, estadística, dibujo e indicadores">Herramientas {showTools?'▴':'▾'}</button><button type="button" onClick={()=>setChartFull(v=>!v)} title={chartFull?'Salir de pantalla completa':'Pantalla completa'} aria-label={chartFull?'Salir de pantalla completa':'Pantalla completa'}>{chartFull?'✕':'⛶'}</button></div>{showTools&&<div className="chart-pro-drawer">{onLayerChange&&<div className="chart-pro-row layer-controls">{([['average','Media'],['initial','Inicial'],['targets','TP / ADD'],['events','Operaciones']] as const).map(([k,l])=><label key={k}><input id={'layer-'+k} type="checkbox" checked={layers[k]} onChange={e=>onLayerChange(k,e.target.checked)}/>{l}</label>)}</div>}<div className="chart-pro-row stats-toolbar"><span>Estadística</span><button className={statLayers.percentiles?'active':''} onClick={()=>statToggle('percentiles')}>Percentiles</button><button className={statLayers.zscore?'active':''} onClick={()=>statToggle('zscore')}>Z-score</button><button className={statLayers.histogram?'active':''} onClick={()=>statToggle('histogram')}>Histograma</button><button className={statLayers.forward?'active':''} onClick={()=>statToggle('forward')}>Prob. 14d</button></div><div className="chart-pro-row chart-pro-tools">{([['line','Tendencia'],['ray','Rayo'],['horizontal','Horizontal'],['vertical','Vertical'],['fib','Fibonacci'],['rect','Rectángulo'],['parallel','Canal'],['text','Etiqueta']] as const).map(([id,label])=><button key={id} type="button" title={label} className={drawing===id?'active':''} onClick={()=>addDrawing(id)}>{label}</button>)}<button onClick={()=>chart.current?.removeOverlay?.()} title="Eliminar dibujos y referencias (se reponen al actualizar)">Borrar</button><button onClick={()=>setDrawing('')}>Cursor</button></div><div className="chart-pro-row chart-pro-indicators">{['MA','EMA','BOLL','RSI','MACD'].map(name=><button type="button" key={name} className={indicators.includes(name)?'active':''} onClick={()=>toggleIndicator(name)}>{name}</button>)}<button onClick={onLoadOlder} disabled={moreLoading}>{moreLoading?'Cargando…':'← Más historial'}</button></div></div>}</div><div className="chart-stats-summary">{stats?<><div><small>Ratio actual</small><b>{stats.current}</b></div><div><small>Percentil</small><b>{stats.percentile}</b></div><div><small>Z-score 90d</small><b className={stats.zScore>=0?'positive':'negative'}>{stats.zScore>=0?'+':''}{stats.zScore}</b></div><div><small>Zona</small><b>{stats.percentile>=90?'extrema alta':stats.percentile>=75?'extendida':stats.percentile<=10?'extrema baja':stats.percentile<=25?'extendida':'normal'}</b></div>{statLayers.forward&&stats.forward&&<div><small>Próx. 14d</small><b>{stats.forward.up}% ↑ · {stats.forward.down}% ↓</b><em>{stats.forward.sampleSize} casos históricos</em></div>}</>:<span>Sin datos suficientes para estadística</span>}</div><div className="chartbox" onMouseEnter={()=>setHoverLabels(true)} onMouseLeave={()=>setHoverLabels(false)}><div ref={host} id="ratio-chart"/>{error&&<div className="chart-status">{error}</div>}</div>{statLayers.zscore&&<ZScorePane bars={bars}/>}<div className="chart-footer"><span title={adaptive?.reason||'Esperando cálculo'}>{adaptive===null?'ADD/TP: calculando…':(adaptive.status==='ok'||adaptive.status==='partial')?['ADD/TP',adaptive.regime,adaptive.horizon_days?adaptive.horizon_days+'d':''].filter(Boolean).join(' · '):'ADD/TP: N/D'}</span><div className="chart-hover" title="Estadística descriptiva de la ventana reciente; no es una predicción ni una señal de órdenes. Velas del ratio sintéticas: las mechas no representan necesariamente extremos simultáneos. Rueda: zoom · arrastrar: desplazar. TP/ADD son objetivos, no órdenes.">{bars.length} velas · ⓘ</div><button className="chart-reset" type="button" onClick={()=>chart.current?.scrollToRealTime?.()}>Ir a hoy ↦</button></div></div>;
}
