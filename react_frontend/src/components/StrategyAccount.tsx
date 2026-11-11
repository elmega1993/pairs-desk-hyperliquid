import {useState} from 'react';
import {PnlChart} from '../PnlChart';
import {filterPnlRange} from '../pnlModel';
import type {StrategyData} from '../types';
import {money,num} from '../format';
import {StrategySide} from './StrategySide';
import {costImpact,dayMetrics,deltaOver,downsample,maxDrawdown} from '../strategyMetrics';

const periods=[['all','Desde el inicio'],['30d','30 días'],['7d','7 días'],['1d','24 horas']] as const;
const signed=(value:number|null|undefined)=>value==null?'N/D':(value>=0?'+':'')+money(value);
const DAY=86400000;
const signClass=(value:number|null|undefined)=>value==null?'':value>=0?'positive':'negative';
const localDate=(time:number)=>new Date(time).toLocaleDateString('es-AR',{timeZone:'America/Argentina/Buenos_Aires'});
function StatRow({label,value,suffix=''}:{label:string;value:number|null|undefined;suffix?:string}){
 return <div className="strategy-stat-row"><span>{label}</span><strong className={signClass(value)}>{signed(value)}{value==null?'':suffix}</strong></div>;
}

function Spark({values}:{values:number[]}){
 if(values.length<2)return null;
 const min=Math.min(...values,0),max=Math.max(...values,0),span=max-min||1,W=240,H=56;
 const pts=values.map((v,i)=>`${(i/(values.length-1)*W).toFixed(1)},${(H-3-(v-min)/span*(H-6)).toFixed(1)}`);
 const last=pts[pts.length-1].split(',');
 return <svg className="hero-spark" viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" aria-hidden="true">
  <defs><linearGradient id="heroSparkG" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="var(--pos)" stopOpacity=".35"/><stop offset="1" stopColor="var(--pos)" stopOpacity="0"/></linearGradient></defs>
  <path d={`M0,${H} L${pts.join(' L')} L${W},${H} Z`} fill="url(#heroSparkG)"/>
  <polyline points={pts.join(' ')} fill="none" stroke="var(--pos)" strokeWidth="2" vectorEffect="non-scaling-stroke" strokeLinejoin="round"/>
  <circle cx={last[0]} cy={last[1]} r="3" fill="var(--pos)"/>
 </svg>;
}

export function StrategyAccount({strategy}:{strategy:StrategyData|null|undefined}){
 const [period,setPeriod]=useState('all');
 const [dailySource,setDailySource]=useState('reconstructed');
 if(!strategy)return <section className="panel strategy-account"><h2>Cuenta / Estrategia</h2><p className="empty">Todavía no hay datos de la estrategia desde el 23/09/2026.</p></section>;
 const history=filterPnlRange(strategy.history,period);
 const projection=strategy.funding_projection;
 const start=strategy.start_ms?new Date(strategy.start_ms).toLocaleDateString('es-AR',{timeZone:'UTC'}):'23/09/2026';
 const net=strategy.net_pnl,gross=strategy.gross_pnl;
 const d24=deltaOver(strategy.history,DAY),d7=deltaOver(strategy.history,7*DAY),d30=deltaOver(strategy.history,30*DAY);
 const dd=maxDrawdown(strategy.history);
 const reconstructed=dailySource==='reconstructed'&&!!strategy.reconstructed_daily?.length;
 const dailyRows=reconstructed?strategy.reconstructed_daily!:strategy.daily;
 const dm=dayMetrics(dailyRows);
 const fees=strategy.fees==null?null:-strategy.fees;
 const costs=costImpact(strategy.fees,strategy.funding);
 const details=strategy.cost_details;
 const costPct=costs!=null&&costs<0&&gross&&gross>0?Math.abs(costs)/gross*100:null;
 const perDay=projection?.per_day_usd;
 const fundingShare=perDay!=null&&perDay<0&&dm&&dm.avg>0?Math.abs(perDay)/dm.avg*100:null;
 const deltas:[string,number|null][]=[['24h',d24],['7d',d7],['30d',d30]];
 return <section className="strategy-account">
  <div className="panel-title strategy-heading"><div><h2>Cuenta / Estrategia</h2><small>Seguimiento desde {start} · no depende del saldo actual retirado</small><small className="strategy-reconciliation">Hyperliquid All-time {signed(strategy.official_all_time_pnl)} · valor al inicio {signed(strategy.official_start_pnl)}</small></div><div className="strategy-periods" role="group" aria-label="Período del gráfico">{periods.map(([value,label])=><button key={value} className={period===value?'active':''} onClick={()=>setPeriod(value)}>{label}</button>)}</div></div>
  <div className="strategy-hero">
   <div className="hero-card">
    <small>PNL NETO</small>
    <b className={'hero-value '+((net||0)>=0?'positive':'negative')}>{signed(net)}</b>
    <div className="hero-sub"><span title="ROI desde el inicio sobre el capital operativo" className={'hero-roi '+((strategy.roi_pct||0)>=0?'positive':'negative')}>ROI {strategy.roi_pct==null?'N/D':(strategy.roi_pct>=0?'+':'')+num(strategy.roi_pct,2)+'%'}</span><span>Capital inicial {money(strategy.initial_capital)}</span><span>Bruto {signed(gross)}</span></div>
    <div className="hero-deltas">{deltas.map(([label,v])=><span key={label} className={v==null?'':v>=0?'positive':'negative'}><small>{label}</small>{v==null?'N/D':signed(v)}</span>)}</div>
    <details className="strategy-details hero-details"><summary>Ver detalle del PNL</summary>
     <StatRow label="Realizado · antes de costos" value={strategy.realized}/>
     <StatRow label="Flotante actual" value={strategy.unrealized}/>
     <StatRow label="Bruto reconstruido" value={gross}/>
     <p>El neto oficial ya incluye comisiones y funding. El flotante es actual; las muestras pueden diferir en horario.</p>
    </details>
    <Spark values={downsample(strategy.history)}/>
   </div>
   <div className="strategy-stat"><small>Costos acumulados</small><b className={signClass(costs)}>{signed(costs)}</b>
    <StatRow label="Comisiones" value={fees}/><StatRow label="Funding neto" value={strategy.funding}/>
    <span className="stat-note">{costPct!=null?`Consumieron el ${num(costPct,1)}% del PNL bruto`:costs==null?'Cobertura incompleta · total no disponible':costs>0?'Los ingresos superan los costos':'Impacto neto en el resultado'}</span>
    <span>Desde {start}</span>
    <details className="strategy-details"><summary>Ver detalle de costos</summary>
     <StatRow label="Funding cobrado" value={details?.funding_received}/><StatRow label="Funding pagado" value={details?.funding_paid}/>
     <p>Funding histórico del ledger. Las comisiones incluyen descuentos o rebates si los hubo.</p>
     <h3>Impacto por activo</h3><p>Primero los que más restan. Importes desde {start}.</p>
     <div className="strategy-breakdown">{details?.assets==null?<p>Desglose no disponible con cobertura incompleta.</p>:details.assets.length?details.assets.map(row=><div className="strategy-asset" key={row.coin}>
      <StatRow label={row.coin} value={row.impact}/>
      <StatRow label="Comisiones" value={-row.fees}/><StatRow label="Funding" value={row.funding}/>
     </div>):<p>Sin movimientos en el período.</p>}</div>
    </details>
   </div>
   <div className={'strategy-stat'+(perDay!=null&&perDay<0?' warn':'')}><small>Funding proyectado</small><b className={signClass(perDay)}>{perDay==null?'N/D':signed(perDay)+'/día'}</b>
    <StatRow label="Longs / día" value={projection?.long_per_day_usd}/><StatRow label="Shorts / día" value={projection?.short_per_day_usd}/>
    <span>{projection?.per_30d_usd==null?'Sin tasa disponible':`30 días: ${signed(projection.per_30d_usd)}`}</span>
    <span className="stat-note">Estimado con tasas actuales · pueden cambiar</span>
    <span>{projection?.as_of_ms?`Tasas del ${new Date(projection.as_of_ms).toLocaleString('es-AR',{timeZone:'America/Argentina/Buenos_Aires',day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit'})}`:'Sin fecha de tasas disponible'}</span>
    {fundingShare!=null&&<span className="stat-note">≈{num(fundingShare,0)}% del PNL diario promedio</span>}
    <details className="strategy-details"><summary>Ver proyección por par</summary>
     <p>Si tasas y posiciones se mantuvieran constantes. No es funding ya cobrado.</p>
     <div className="strategy-breakdown">{projection?.pairs==null?<p>{projection?.reason||'Sin cobertura suficiente para el desglose.'}</p>:projection.pairs.length?projection.pairs.map((row,i)=><div className="strategy-asset" key={`${row.long}/${row.short}/${i}`}>
      <StatRow label={`${row.long} / ${row.short}`} value={row.per_day_usd} suffix="/día"/>
      <StatRow label={`Long ${row.long}`} value={row.long_per_day_usd}/><StatRow label={`Short ${row.short}`} value={row.short_per_day_usd}/>
     </div>):<p>Sin pares activos.</p>}</div>
    </details>
   </div>
   <div className="strategy-stat"><small>Drawdown máximo</small><b className={dd.needed==null?'':'negative'}>{dd.needed==null?'N/D':money(dd.max)}</b>
    <span>{dd.worstTime?`Peor retroceso: ${localDate(dd.worstTime)}`:dd.needed==null?'Sin muestras oficiales':'Sin retrocesos registrados'}</span>
    <StatRow label="Retroceso actual" value={dd.needed==null?null:dd.current}/>
    <StatRow label="Para volver al máximo" value={dd.needed}/>
    <span className="stat-note">{dd.needed===0?'En máximos':'Desde el máximo de PNL acumulado'}</span>
   </div>
   <div className="strategy-stat"><small>Días positivos{reconstructed?' · estimados':''}</small><b>{dm?`${dm.wins}/${dm.days}`:'N/D'}</b>
    <span>{dm?`${num(dm.winPct,0)}% de los días con datos`:'Sin datos diarios'}</span>
    <StatRow label="Promedio ganador" value={dm?.avgWin}/><StatRow label="Promedio perdedor" value={dm?.avgLoss}/>
    <details className="strategy-details"><summary>Ver detalle de días</summary>
     <StatRow label={dm?`Mejor · ${dm.best.date}`:'Mejor día'} value={dm?.best.pnl}/>
     <StatRow label={dm?`Peor · ${dm.worst.date}`:'Peor día'} value={dm?.worst.pnl}/>
     <p>Los promedios excluyen días sin datos y días en cero. Pueden incluir el día actual parcial. {reconstructed?'Cierres diarios estimados.':'Variaciones entre muestras oficiales.'}</p>
    </details>
   </div>
  </div>
  <div className="panel strategy-chart"><div className="strategy-chart-note">Curva oficial rebaseda desde el 23/09 · Hyperliquid All-time se muestra arriba como referencia</div><PnlChart history={history} source="hyperliquid" summary={{realized:strategy.realized,unrealized:strategy.unrealized}} eventsVisible={false} ddHeight={110} sidebar={<StrategySide key={reconstructed?'reconstructed':'official'} daily={dailyRows} reconstructed={reconstructed} asOf={strategy.reconstructed_as_of_ms} sourceControl={!!strategy.reconstructed_daily?.length&&<div className="strategy-periods" role="group" aria-label="Fuente del PNL diario"><button type="button" className={reconstructed?'active':''} onClick={()=>setDailySource('reconstructed')}>Estimado diario</button><button type="button" className={!reconstructed?'active':''} onClick={()=>setDailySource('official')}>Muestras oficiales</button></div>}/>}/></div>
 </section>;
}
