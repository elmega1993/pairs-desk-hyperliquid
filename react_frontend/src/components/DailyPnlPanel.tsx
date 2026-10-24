import {dailyPnl} from '../pnlModel';
import type {PnlPoint} from '../pnlModel';
import {money} from '../format';

const signed=(value:number)=>(value>=0?'+':'')+money(value);

export function DailyPnlPanel({history,source}:{history:PnlPoint[];source?:string}){
 const rows=source==='hyperliquid'?dailyPnl(history).slice().reverse():[];
 return <aside className="daily-pnl-panel" aria-label="PNL diario">
  <div className="daily-pnl-header"><div><h3>PNL diario</h3><small>Cuenta total · Hyperliquid</small></div><span className="daily-pnl-badge">{rows.length||'—'} días</span></div>
  {source!=='hyperliquid'?<p className="daily-pnl-empty">Seleccioná “Hyperliquid (cuenta)” para ver el detalle diario.</p>:!rows.length?<p className="daily-pnl-empty">Sin datos diarios disponibles.</p>:<div className="daily-pnl-list">{rows.map(row=><div className="daily-pnl-row" key={row.date}><span><b>{row.date}</b>{row.partial&&<em>Parcial</em>}</span><strong className={row.pnl>=0?'positive':'negative'}>{signed(row.pnl)}</strong><small>{money(row.cumulative)}</small></div>)}</div>}
 </aside>
}
