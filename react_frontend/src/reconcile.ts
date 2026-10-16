/** Reconciles the headline net PNL with its components and with the chart's last point. */
export type Reconciliation={status:'ok'|'mismatch'|'partial';calc:number|null;total:number|null;parts:{label:string;value:number|null;sign:1|-1}[];notes:string[]};
const fin=(v:unknown):number|null=>typeof v==='number'&&Number.isFinite(v)?v:null;
const usd=(v:number)=>`${v<0?'-':''}$${Math.abs(v).toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2})}`;
export function reconcile(summary:Record<string,number|null|undefined>,chart:{last?:number|null;basis?:string;source?:string}|null):Reconciliation{
 const realized=fin(summary.realized),fees=fin(summary.fees),funding=fin(summary.funding),unreal=fin(summary.unrealized),total=fin(summary.total);
 const parts=[{label:'Realizado',value:realized,sign:1 as const},{label:'Comisiones',value:fees,sign:-1 as const},{label:'Funding',value:funding,sign:1 as const},{label:'Flotante',value:unreal,sign:1 as const}];
 const missing=parts.filter(p=>p.value===null).map(p=>p.label.toLowerCase());
 const notes:string[]=[];
 let calc:number|null=null;let status:Reconciliation['status']='ok';
 if(missing.length){status='partial';notes.push(`Neto no verificable: falta ${missing.join(', ')}.`)}
 else{
  calc=unreal!+realized!-fees!+funding!;
  if(total!==null&&Math.abs(calc-total)>0.5){status='mismatch';notes.push(`El neto verificado (${usd(total)}) difiere de la suma de componentes (${usd(calc)}) en ${usd(Math.abs(total-calc))}.`)}
 }
 const ref=total??calc;
 if(chart&&chart.last!=null&&Number.isFinite(chart.last)&&ref!==null){
  if(chart.source&&chart.source!=='local')notes.push('El gráfico usa el historial de toda la cuenta en Hyperliquid, no solo estos pares: no es comparable con el neto.');
  else if(chart.basis==='gross')notes.push('El último punto del gráfico es bruto (sin funding completo): no es comparable con el neto.');
  else if(Math.abs(chart.last-ref)>Math.max(1,Math.abs(ref)*0.02)){if(status==='ok')status='mismatch';notes.push(`El último punto del gráfico (${usd(chart.last)}) no coincide con el neto actual (${usd(ref)}).`)}
 }
 return {status,calc,total,parts,notes};
}
