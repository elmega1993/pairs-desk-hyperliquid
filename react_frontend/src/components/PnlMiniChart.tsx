import {useMemo,useRef,useState} from 'react';
import type {PnlPoint} from '../pnlModel';
import {buildMiniSeries,nearestRow,spanLabel} from '../miniSeries';
import type {MiniRow} from '../miniSeries';
import {money,signedMoney,tone} from '../format';

const stamp=(time:number)=>new Date(time).toLocaleString('es-AR',{day:'2-digit',month:'short',hour:'2-digit',minute:'2-digit',hour12:false}).replace('.','');

// Mini gráfico de las últimas 24 h: escala propia, mín/máx, variación del período y cursor con fecha y PNL del momento.
export function PnlMiniChart({points,positive,label,now}:{points:PnlPoint[];positive:boolean;label:string;now?:number}){
 const series=useMemo(()=>buildMiniSeries(points,now??Date.now()),[points,now]);
 const plot=useRef<HTMLDivElement>(null),[hover,setHover]=useState<MiniRow|null>(null);
 if(!series)return <div className="pnl-mini-empty" role="img" aria-label={label}><small>Sin historial suficiente de las últimas 24 h</small></div>;
 const clock=Math.round(series.spanMs/60_000),side=positive?'positive':'negative';
 const move=(event:React.PointerEvent<HTMLDivElement>)=>{const box=plot.current?.getBoundingClientRect();if(!box||box.width<=0)return;setHover(nearestRow(series,(event.clientX-box.left)/box.width))};
 return <div className="pnl-mini-wrap" role="img" aria-label={label+' · '+spanLabel(series.spanMs)}>
  <div className="pnl-mini-head">{hover
   ?<><span className="pnl-mini-when">{stamp(hover.time)}</span><b className="pnl-mini-now">{money(hover.pnl)}</b></>
   :<><span title={clock<23*60?'Todavía hay menos de 24 h de historial guardado':'Últimas 24 horas'}>{clock<23*60?'últimas '+spanLabel(series.spanMs):'24 h'}</span><b className={tone(series.delta)} title="Variación en el período">{signedMoney(series.delta)}</b></>}</div>
  <div className="pnl-mini-plot" ref={plot} onPointerMove={move} onPointerDown={move} onPointerLeave={()=>setHover(null)} onPointerCancel={()=>setHover(null)}>
   <svg className={'pnl-mini '+side} viewBox="0 0 100 40" preserveAspectRatio="none" aria-hidden="true">
    {series.zeroY!=null&&<line className="pnl-mini-zero" x1="0" x2="100" y1={series.zeroY} y2={series.zeroY} vectorEffect="non-scaling-stroke"/>}
    {series.segments.map((segment,index)=>segment.length>1?<polyline key={index} points={segment.map(point=>point.x.toFixed(2)+','+point.y.toFixed(2)).join(' ')} fill="none" vectorEffect="non-scaling-stroke"/>:null)}
   </svg>
   <i className={'pnl-mini-dot '+side} style={{top:(series.end.y/40*100)+'%'}}/>
   {hover&&<><i className="pnl-mini-cursor" style={{left:hover.x+'%'}}/><i className={'pnl-mini-dot pnl-mini-hover '+side} style={{left:hover.x+'%',top:(hover.y/40*100)+'%'}}/></>}
  </div>
  <div className="pnl-mini-foot"><span>mín {money(series.min)}</span><span>máx {money(series.max)}</span></div>
 </div>;
}
