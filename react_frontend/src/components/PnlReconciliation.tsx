import {money} from '../format';
import {reconcile} from '../reconcile';
export function PnlReconciliation({summary,last,basis,source}:{summary:Record<string,number|null>;last?:number|null;basis?:string;source?:string}){
 const r=reconcile(summary,{last,basis,source});
 return <div className="pnl-recon" data-status={r.status}>
  <div className="pnl-recon-formula">{r.parts.map((p,i)=><span key={p.label}>{i>0&&<i>{p.sign<0?'−':'+'}</i>}<small>{p.label}</small> <b>{money(p.value)}</b></span>)}<i>=</i><span><small>Neto calculado</small> <b>{money(r.calc)}</b></span><span className="pnl-recon-total"><small>Neto verificado</small> <b>{money(r.total)}</b></span></div>
  {r.notes.map(n=><p key={n} className="pnl-recon-note">{n}</p>)}
 </div>
}
