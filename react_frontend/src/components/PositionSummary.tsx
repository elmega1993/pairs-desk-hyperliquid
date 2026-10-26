import type {Pair} from '../types';
import {money,tone} from '../format';

export function PositionSummary({pair}:{pair:Pair|null}){
 if(!pair)return <div className="panel details"><h2>Resumen del par</h2><p>Sin posición</p></div>;
 const fields:[string,unknown,boolean,boolean][]=[
  ['Exposición total',pair.size,true,false],
  [`LONG ${pair.long}`,pair.long_pnl,true,true],
  [`SHORT ${pair.short}`,pair.short_pnl,true,true],
  ['Nominal long',pair.long_usd,true,false],['Nominal short',pair.short_usd,true,false],
  ['PNL flotante',pair.pnl,true,false],['PNL realizado',pair.realized,true,false],['PNL neto',pair.total_pnl,true,false],
  ['Funding',pair.funding,true,false],['Comisiones',pair.fees,true,false],
 ];
 return <div className="panel details"><h2>Resumen del par</h2>{fields.map(([label,value,numeric,highlight])=><div className={'detail-row '+(highlight?'leg-row ':'')+(label==='Exposición total'?'exposure-row':'')} key={label}><span>{label}</span><b className={label==='Exposición total'||label==='Nominal long'||label==='Nominal short'?'neutral':numeric?tone(value):''}>{numeric?money(value):String(value??'N/D')}</b></div>)}</div>;
}
