import type {Data} from '../types';
import {expenseTone,money,num,tone} from '../format';
import type {OfficialPnl} from '../pnlSource';
import {PnlMiniChart} from './PnlMiniChart';

export function PortfolioKpis({data,official}:{data:Data|null;official:OfficialPnl}){
 const summary=data?.summary||{};
 const pairs=data?.pairs||[];
 const unrealizedSeries=(data?.pnl_history||[]).map((row:any)=>({time:Number(row.time??row.timestamp),pnl:Number(row.unrealized??row.open)})).filter((row:any)=>Number.isFinite(row.time)&&Number.isFinite(row.pnl));
 const dayOfficial:{time:number;pnl:number}[]=((data?.hl_pnl as any)?.['1d']||[]).map((row:any)=>({time:Number(row?.time),pnl:Number(row?.pnl)})).filter((row:any)=>Number.isFinite(row.time)&&Number.isFinite(row.pnl));
 const legPnl=(key:'long_pnl'|'short_pnl')=>{if(!pairs.length)return 0;const values=pairs.map(pair=>Number(pair[key]));return values.every(Number.isFinite)?values.reduce((total,value)=>total+value,0):null};
 const net=official.value??summary.total??summary.net_known_subtotal;
 const totalLabel=official.source==='hyperliquid'?'PNL TOTAL · HYPERLIQUID':summary.total==null?'PNL CONOCIDO (PARCIAL)':'PNL NETO TOTAL';
 const accountValue=summary.account_value_total??summary.equity_core;
 const freeMargin=accountValue==null||summary.margin_used==null?null:accountValue-summary.margin_used;
 const breakdown=[['FUNDING HISTÓRICO',summary.account_funding],['COMISIONES HISTÓRICAS',summary.fees],['PNL LONGS',legPnl('long_pnl')],['PNL SHORTS',legPnl('short_pnl')]] as const;
 const accountRisk=[['VALOR TOTAL CUENTA',accountValue],['EXPOSICIÓN',summary.exposure],['MARGEN USADO',summary.margin_used],['MARGEN LIBRE',freeMargin]] as const;
 const kpiRows=[['PNL NO REALIZADO',summary.unrealized,'Flotante de posiciones abiertas'],[totalLabel,net,official.fallback?'Fallback local · Hyperliquid sin serie':'Toda la cuenta · fuente oficial'],['COSTOS Y DESCOMPOSICIÓN',null,null],['CUENTA Y RIESGO',null,null]] as const;
 return <section className="kpis">
  {kpiRows.map(([label,value,note],idx)=>{
   if(label==='COSTOS Y DESCOMPOSICIÓN')return <article className="panel kpi kpi-breakdown" key={label}><label>{label}</label><div className="kpi-breakdown-grid">{breakdown.map(([item,itemValue])=><div key={item}><small>{item}</small><strong className={item==='COMISIONES HISTÓRICAS'?expenseTone(itemValue):tone(itemValue)}>{money(itemValue)}</strong></div>)}</div></article>;
   if(label==='CUENTA Y RIESGO')return <article className="panel kpi kpi-account-risk" key={label}><label>{label}</label><div className="kpi-account-risk-grid">{accountRisk.map(([item,itemValue])=><div key={item}><small>{item}</small><strong className={item==='EXPOSICIÓN'?'neutral':tone(itemValue)}>{money(itemValue)}</strong></div>)}</div></article>;
   return <article className={'panel kpi '+(idx===1?'kpi-official':'')} key={String(label)}><label>{label}{idx===1&&data?.warnings?.length?<span className="kpi-warn" role="img" aria-label="Datos parciales" title={'Datos parciales: '+data.warnings.join(' · ')}> ⚠</span>:null}</label><strong className={label==='EXPOSICIÓN'?'neutral':tone(value)}>{money(value)}</strong><small>{note}</small>{(idx===0||idx===1)&&<PnlMiniChart points={idx===0?unrealizedSeries:(dayOfficial.length>1?dayOfficial:official.series)} positive={Number(value??0)>=0} label={idx===0?'PNL no realizado, últimas 24 horas':'PNL total oficial, últimas 24 horas'}/>}</article>;
  })}
 </section>;
}
