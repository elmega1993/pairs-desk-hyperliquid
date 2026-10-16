import {useId,useLayoutEffect,useMemo,useState} from 'react';
import type {KeyboardEvent,PointerEvent as RPointerEvent} from 'react';
import {money} from './format';
import {axisMoney,niceTicks} from './ticks';
import {gapThreshold,gapTotal,includeZero,normalizePnlHistory,pnlStats,runningPeaks,toSegments} from './pnlModel';
import type {PnlPoint} from './pnlModel';
export type {PnlPoint};
export {normalizePnlHistory};
const L=64,R=16,T=14,B=30;
const POS='#2ed8b5',NEG='#ff6c8c';
const hm=(ms:number)=>new Date(ms).toLocaleTimeString('es-AR',{hour:'2-digit',minute:'2-digit',hour12:false});
const dm=(ms:number)=>new Date(ms).toLocaleDateString('es-AR',{day:'numeric',month:'numeric'});
const formatDate=(ms:number)=>new Date(ms).toLocaleString('es-AR',{day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false});
const signed=(v:number)=>(v>0?'+':'')+money(v);
const tone=(v:number)=>v>=0?'positive':'negative';
const duration=(ms:number)=>{const m=Math.round(ms/60000);return m<60?`${m} min`:`${Math.floor(m/60)} h${m%60?` ${m%60} min`:''}`};
function sourceChip(source:string|undefined,basis:string|undefined,mixed:boolean,missingMs:number,fallback:boolean){
 const chips:{text:string;level:'ok'|'warn'|'muted'}[]=[];
 if(fallback)chips.push({text:'Hyperliquid no devolvió datos: se muestra el registro local',level:'warn'});
 if(source&&source!=='local')chips.push({text:'Fuente: Hyperliquid · PNL de perps de toda la cuenta (no solo estos pares)',level:'ok'});
 else if(fallback){}
 else if(basis==='gross')chips.push({text:'Base bruta: funding incompleto',level:'warn'});
 else if(basis==='net')chips.push({text:'Fuente: local · base neta',level:'ok'});
 else chips.push({text:'Fuente: local · base sin identificar',level:'muted'});
 if(mixed)chips.push({text:'La serie cambió de base: estadísticas desde ese punto',level:'warn'});
 if(missingMs>0)chips.push({text:`Sin registro: ${duration(missingMs)} (app cerrada o pestaña dormida)`,level:'muted'});
 return chips;
}
export function PnlChart({history,scale='auto',source,fallback=false}:{history:PnlPoint[];scale?:'auto'|'zero';source?:string;fallback?:boolean}){
 const uid=useId().replace(/:/g,'');
 const [hover,setHover]=useState<number|null>(null);
 const [box,setBox]=useState<HTMLDivElement|null>(null);
 const [size,setSize]=useState({w:900,h:230});
 useLayoutEffect(()=>{const el=box;if(!el)return;const apply=()=>{const r=el.getBoundingClientRect();if(r.width>0&&r.height>0)setSize(prev=>Math.round(r.width)===prev.w&&Math.round(r.height)===prev.h?prev:{w:Math.round(r.width),h:Math.round(r.height)})};apply();if(typeof ResizeObserver==='undefined')return;const ro=new ResizeObserver(apply);ro.observe(el);return()=>ro.disconnect()},[box]);
 const W=size.w,H=size.h;
 const rows=useMemo(()=>normalizePnlHistory(history),[history]);
 const stats=useMemo(()=>pnlStats(rows),[rows]);
 const peaks=useMemo(()=>runningPeaks(rows),[rows]);
 const geometry=useMemo(()=>{
  if(rows.length<2)return null;
  const minT=rows[0].time,maxT=rows[rows.length-1].time;
  let minV=Infinity,maxV=-Infinity;for(const r of rows){if(r.pnl<minV)minV=r.pnl;if(r.pnl>maxV)maxV=r.pnl}
  if(includeZero(minV,maxV,scale)){minV=Math.min(0,minV);maxV=Math.max(0,maxV)}
  const pad=Math.max((maxV-minV)*.08,.01),low=minV-pad,high=maxV+pad;
  const x=(t:number)=>L+(t-minT)/(maxT-minT||1)*(W-L-R);
  const y=(v:number)=>T+(high-v)/(high-low)*(H-T-B);
  const y0=Math.min(H-B,Math.max(T,y(0)));
  const {segments,breaks}=toSegments(rows,gapThreshold(rows));
  // Min/max per pixel bucket inside each segment: keeps spikes without drawing enormous paths.
  const limit=W-L-R;
  const sample=(seg:PnlPoint[])=>{
   if(seg.length<=limit*2)return seg;
   const buckets=new Map<number,{min:PnlPoint;max:PnlPoint}>();
   for(const r of seg){const k=Math.floor(x(r.time));const b=buckets.get(k);if(!b)buckets.set(k,{min:r,max:r});else{if(r.pnl<b.min.pnl)b.min=r;if(r.pnl>b.max.pnl)b.max=r}}
   return [seg[0],...Array.from(buckets.values()).flatMap(b=>b.min.time<=b.max.time?[b.min,b.max]:[b.max,b.min]),seg[seg.length-1]].sort((a,b)=>a.time-b.time);
  };
  const drawn=segments.map(sample);
  const lines=drawn.filter(s=>s.length>1).map(s=>s.map((r,i)=>(i?'L':'M')+x(r.time).toFixed(2)+' '+y(r.pnl).toFixed(2)).join(' '));
  const areas=drawn.filter(s=>s.length>1).map((s,i)=>`${lines[i]} L${x(s[s.length-1].time).toFixed(2)} ${y0.toFixed(2)} L${x(s[0].time).toFixed(2)} ${y0.toFixed(2)} Z`);
  const dots=drawn.filter(s=>s.length===1).map(s=>({cx:x(s[0].time),cy:y(s[0].pnl)}));
  const {ticks,step}=niceTicks(low,high,H<200?4:5);
  return {x,y,y0,minT,maxT,ticks,step,lines,areas,dots,breaks};
 },[rows,W,H,scale]);
 if(!geometry||!stats)return <div className="empty">Historial insuficiente para el período seleccionado</div>;
 const {x,y,y0,minT,maxT,ticks,step,lines,areas,dots,breaks}=geometry;
 const compact=W<520;
 const span=maxT-minT;
 const xTicks=Math.max(2,Math.min(5,Math.floor(W/(compact?80:150))));
 const axisDate=span<=2*86400000?hm:dm;
 const current=hover!==null&&hover<rows.length?rows[hover]:null;
 const prev=hover!==null&&hover>0?rows[hover-1]:null;
 const stepOk=!!(current&&prev&&!breaks.some(b=>b.time===current.time));
 const nearest=(px:number)=>{const t=minT+(px-L)/(W-L-R)*(maxT-minT);let a=0,b=rows.length-1;while(a<b){const m=(a+b)>>1;if(rows[m].time<t)a=m+1;else b=m}return a>0&&Math.abs(rows[a-1].time-t)<Math.abs(rows[a].time-t)?a-1:a};
 const onMove=(e:RPointerEvent<SVGSVGElement>)=>{const rect=e.currentTarget.getBoundingClientRect();const px=e.clientX-rect.left;if(px<L||px>W-R){setHover(null);return}setHover(nearest(px))};
 const onKey=(e:KeyboardEvent<SVGSVGElement>)=>{
  const last=rows.length-1;const at=hover??last;
  if(e.key==='ArrowLeft'){e.preventDefault();setHover(Math.max(0,at-(e.shiftKey?10:1)))}
  else if(e.key==='ArrowRight'){e.preventDefault();setHover(Math.min(last,at+(e.shiftKey?10:1)))}
  else if(e.key==='Home'){e.preventDefault();setHover(0)}
  else if(e.key==='End'){e.preventDefault();setHover(last)}
  else if(e.key==='Escape')setHover(null);
 };
 const lastRow=rows[rows.length-1];
 const chips=sourceChip(source,lastRow.basis,stats.mixedBasis,gapTotal(breaks),fallback);
 const gapBands=breaks.filter(b=>b.kind==='gap'&&x(b.time)-x(b.from)>=6);
 const basisMarks=breaks.filter(b=>b.kind==='basis');
 const dotFill=(v:number)=>v>=0?POS:NEG;
 const deltaLabel=stats.mixedBasis?'Cambio desde el cambio de base':'Cambio del período';
 return <div className="pnl-chart">
  <div className="pnl-stats">
   <div><small>PNL ACTUAL</small><b className={tone(stats.last)}>{money(stats.last)}</b></div>
   <div><small>{deltaLabel.toUpperCase()}</small><b className={tone(stats.delta)}>{signed(stats.delta)}</b></div>
   <div><small>MÁX / MÍN</small><b>{money(stats.max.pnl)} / {money(stats.min.pnl)}</b></div>
   <div><small>DESDE EL MÁXIMO</small><b className={stats.fromPeak<0?'negative':''}>{money(stats.fromPeak)}</b></div>
  </div>
  <div className="pnl-chips">{chips.map(c=><span key={c.text} className={'pnl-chip '+c.level}>{c.text}</span>)}</div>
  <div className="pnl-plot" ref={setBox}><svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} role="img" tabIndex={0} aria-label="Evolución histórica del PNL en dólares. Flechas izquierda y derecha para inspeccionar puntos." onPointerMove={onMove} onPointerDown={onMove} onPointerLeave={()=>setHover(null)} onKeyDown={onKey} onBlur={()=>setHover(null)}>
   <defs>
    <clipPath id={uid+'up'}><rect x={L} y={T} width={W-L-R} height={Math.max(0,y0-T)}/></clipPath>
    <clipPath id={uid+'dn'}><rect x={L} y={y0} width={W-L-R} height={Math.max(0,H-B-y0)}/></clipPath>
   </defs>
   {ticks.map(v=><g key={v}><line x1={L} x2={W-R} y1={y(v)} y2={y(v)} stroke={v===0?'#9b89ba':'#30405c'} strokeDasharray={v===0?'5 4':'3 5'}/><text x={L-9} y={y(v)+4} fill={v===0?'#cdbfe8':'#9caec9'} fontSize="12" textAnchor="end">{axisMoney(v,step)}</text></g>)}
   {Array.from({length:xTicks},(_,i)=>{const t=minT+(maxT-minT)*i/(xTicks-1);return <text key={i} x={x(t)} y={H-9} fill="#9caec9" fontSize="12" textAnchor={i===0?'start':i===xTicks-1?'end':'middle'}>{axisDate(t)}</text>})}
   {gapBands.map(b=><rect key={'g'+b.time} x={x(b.from)} y={H-B-5} width={x(b.time)-x(b.from)} height={5} rx="1.5" fill="#8fa3c7" fillOpacity=".55"><title>{'Sin registro: '+duration(b.time-b.from)}</title></rect>)}
   {basisMarks.map(b=>{const px=x(b.time);const end=px>W-R-110;return <g key={'b'+b.time}><line x1={px} x2={px} y1={T} y2={H-B} stroke="#8c9dbd" strokeDasharray="1 4" strokeWidth="1.5"/><text x={px+(end?-5:5)} y={T+11} fill="#9caec9" fontSize="11" textAnchor={end?'end':'start'}>Cambio de base</text></g>})}
   {(['up','dn'] as const).map(side=><g key={side} clipPath={`url(#${uid+side})`}>
    {areas.map((d,i)=><path key={'a'+i} d={d} fill={side==='up'?POS:NEG} fillOpacity=".12"/>)}
    {lines.map((d,i)=><path key={'l'+i} d={d} fill="none" stroke={side==='up'?POS:NEG} strokeWidth="2.25" strokeLinejoin="round" vectorEffect="non-scaling-stroke"/>)}
    {dots.map((d,i)=><circle key={'d'+i} cx={d.cx} cy={d.cy} r="2.5" fill={side==='up'?POS:NEG}/>)}
   </g>)}
   {stats.max.pnl!==stats.min.pnl&&<>
    <circle cx={x(stats.max.time)} cy={y(stats.max.pnl)} r="3.5" fill={dotFill(stats.max.pnl)} stroke="#101a2c" strokeWidth="1.5"><title>{'Máximo '+money(stats.max.pnl)}</title></circle>
    <circle cx={x(stats.min.time)} cy={y(stats.min.pnl)} r="3.5" fill={dotFill(stats.min.pnl)} stroke="#101a2c" strokeWidth="1.5"><title>{'Mínimo '+money(stats.min.pnl)}</title></circle>
   </>}
   <circle cx={x(lastRow.time)} cy={y(lastRow.pnl)} r="4.5" fill={dotFill(lastRow.pnl)} stroke="#101a2c" strokeWidth="2"/>
   {current&&<><line x1={x(current.time)} x2={x(current.time)} y1={T} y2={H-B} stroke="#a5a9d3" strokeDasharray="4 4"/><circle cx={x(current.time)} cy={y(current.pnl)} r="5" fill={dotFill(current.pnl)} stroke="#101a2c" strokeWidth="2"/></>}
  </svg></div>
  <div className="pnl-readout">{current?<>
   <span>{formatDate(current.time)}</span><strong className={tone(current.pnl)}>{money(current.pnl)}</strong>
   <span className={stepOk?tone(current.pnl-prev!.pnl):'muted'}>{stepOk?(current.pnl-prev!.pnl>=0?'▲ ':'▼ ')+signed(current.pnl-prev!.pnl):'—'}</span>
   <span className="muted">desde máx {money(current.pnl-peaks[hover!])}</span>
  </>:<span className="muted">Pasá el cursor sobre el gráfico (o usá ← →) para ver el detalle.</span>}</div>
 </div>
}
