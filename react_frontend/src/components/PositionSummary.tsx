import type {Pair} from '../types';
import {money,tone} from '../format';

export function PositionSummary({pair}:{pair:Pair|null}){
 if(!pair)return <div className="panel details"><h2>Resumen del par</h2><p>Sin posición</p></div>;
 const fields:[string,unknown][]=[
  ['Long',pair.long],['Short',pair.short],
  ['Nominal long',pair.long_usd],['Nominal short',pair.short_usd],['Exposición total',pair.size],
  ['PNL flotante',pair.pnl],['PNL realizado',pair.realized],['PNL neto',pair.total_pnl],
  ['Funding',pair.funding],['Comisiones',pair.fees],
 ];
 return <div className="panel details"><h2>Resumen del par</h2>{fields.map(([label,value])=>{const numeric=['Nominal long','Nominal short','Exposición total','PNL flotante','PNL realizado','PNL neto','Funding','Comisiones'].includes(label);return <div className="detail-row" key={label}><span>{label}</span><b className={numeric?tone(value):''}>{numeric?money(value):String(value??'N/D')}</b></div>})}</div>;
}
