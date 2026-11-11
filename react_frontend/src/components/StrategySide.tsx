import {useState} from 'react';
import type {ReactNode} from 'react';
import {money} from '../format';
import {dayMetrics} from '../strategyMetrics';
import type {StrategyDailyRow} from '../types';

const signed=(v:number|null)=>v==null?'Sin datos':(v>=0?'+':'')+money(v);
const fmtDay=(d:string)=>{const p=d.split('-');return p.length===3?`${p[2]}/${p[1]}`:d};

/** Panel lateral: barras de PNL diario + métricas de calidad + detalle por día. */
export function StrategySide({daily,reconstructed=false,asOf,sourceControl}:{daily?:StrategyDailyRow[];reconstructed?:boolean;asOf?:number|null;sourceControl?:ReactNode}){
 const rows=daily||[];const [hover,setHover]=useState<number|null>(null);
 const m=dayMetrics(rows);
 if(!rows.length||!m)return <aside className="daily-pnl-panel strat-side"><div className="daily-pnl-header"><div><h3>PNL diario</h3><small>Cuenta total · Hyperliquid</small></div></div><p className="daily-pnl-empty">Sin datos diarios disponibles.</p></aside>;
 const W=280,H=96,mid=H/2,maxAbs=Math.max(...rows.map(r=>Math.abs(r.pnl??0)),1),bw=W/rows.length,gap=Math.min(3,bw*.25);
 const cur=hover!=null?rows[hover]:null;
 return <aside className="daily-pnl-panel strat-side" aria-label="PNL diario">
  {sourceControl}
  <div className="daily-pnl-header"><div><h3>PNL diario</h3><small>{cur?fmtDay(cur.date):'Desde el 23/09 · Hyperliquid'}</small><small>{m.days} días con datos · {rows.length-m.days} sin datos</small></div>{cur?<strong className={'strat-hover '+(cur.pnl==null?'':cur.pnl>=0?'positive':'negative')}>{signed(cur.pnl)}</strong>:<span className="daily-pnl-badge">{rows.length} días</span>}</div>
  <small style={{display:'block'}}>{reconstructed?'PNL neto estimado · días de Buenos Aires.':'Cierres aproximados según muestras oficiales disponibles.'}</small>
  {reconstructed&&asOf&&<small style={{display:'block'}}>Histórico calculado: {new Date(asOf).toLocaleString('es-AR',{timeZone:'America/Argentina/Buenos_Aires',day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit'})}.</small>}
  {reconstructed&&rows.some(row=>row.quality==='approximate')&&<small style={{display:'block'}}>Desde el {fmtDay(rows.find(row=>row.quality==='approximate')!.date)}: cierres aproximados con muestras oficiales; último día parcial.</small>}
  <svg className="strat-bars" viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" onPointerLeave={()=>setHover(null)}>
   <line x1="0" x2={W} y1={mid} y2={mid} stroke="rgba(255,255,255,.18)" strokeDasharray="3 4"/>
   {rows.map((r,i)=>{const h=Math.max(1.5,Math.abs(r.pnl??0)/maxAbs*(mid-4));const y=(r.pnl??0)>=0?mid-h:mid;
    return <g key={r.date}><rect x={i*bw} y={0} width={bw} height={H} fill="transparent" onPointerEnter={()=>setHover(i)} onPointerDown={()=>setHover(i)}/><rect x={i*bw+gap/2} y={y} width={Math.max(1,bw-gap)} height={h} rx="1.5" fill={r.pnl==null?'#888':r.pnl>=0?'var(--pos)':'var(--neg)'} opacity={hover==null||hover===i?1:.38} pointerEvents="none"/></g>})}
  </svg>
  <div className="strat-metrics">
   <div><small>Días positivos</small><b>{m.wins}/{m.days} · {m.winPct.toFixed(0)}%</b></div>
   <div><small>Promedio diario</small><b className={m.avg>=0?'positive':'negative'}>{signed(m.avg)}</b></div>
   <div><small>Mejor día</small><b className="positive">{signed(m.best.pnl)}</b><em>{fmtDay(m.best.date)}</em></div>
   <div><small>Peor día</small><b className="negative">{signed(m.worst.pnl)}</b><em>{fmtDay(m.worst.date)}</em></div>
   <div><small>Profit factor</small><b>{m.profitFactor==null?'∞':m.profitFactor.toFixed(2)}</b></div>
   <div><small>Racha actual</small><b className={m.streak.positive?'positive':'negative'}>{m.streak.count} {m.streak.positive?'ganadores':'perdedores'}</b></div>
  </div>
  <div className="daily-pnl-list">{rows.slice().reverse().map((row,idx)=><div className="daily-pnl-row" key={row.date} onPointerEnter={()=>setHover(rows.length-1-idx)} onPointerLeave={()=>setHover(null)}><span><b>{row.date}</b>{row.partial&&<em>Parcial</em>}{row.quality==='approximate'&&<em>Muestra oficial</em>}</span><strong className={row.pnl==null?'':row.pnl>=0?'positive':'negative'}>{signed(row.pnl)}</strong>{row.cumulative!=null&&<small>{money(row.cumulative)}</small>}</div>)}</div>
 </aside>;
}
