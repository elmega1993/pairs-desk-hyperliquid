import type {Pair,PairAnalytics} from '../types';
import {buildAttention} from '../attention';
const hms=(ms:number)=>new Date(ms).toLocaleTimeString('es-AR',{hour12:false});
export function AttentionQueue({pairs,analytics,loaded,error,asOf,now,onSelect}:{pairs:Pair[];analytics:Record<string,PairAnalytics>;loaded:boolean;error:string;asOf:number|null;now:number;onSelect:(id:string)=>void}){
 const a=buildAttention(pairs,analytics,{loaded,error,asOf,now});
 const caveat=[a.stale&&(a.error?`La última actualización de analítica falló (${a.error}); se muestran datos de ${asOf?hms(asOf):'antes'}.`:`Analítica desactualizada (${asOf?hms(asOf):'sin hora'}).`),a.unverified.length&&`Sin analítica: ${a.unverified.join(', ')}.`,a.nodata.length&&`Datos estadísticos insuficientes: ${a.nodata.join(', ')}.`].filter(Boolean) as string[];
 return <section className="panel attention" aria-label="Cola de atención" data-kind={a.kind}>
  <div className="panel-title"><h2>Cola de atención</h2>{a.items.length>0&&<span className="chip">{a.items.length} {a.items.length===1?'par':'pares'}</span>}</div>
  {a.kind==='no-pairs'&&<p className="attention-msg">No hay pares abiertos para monitorear.</p>}
  {a.kind==='unavailable'&&<p className="attention-msg warn" role="alert">{error?`Analítica no disponible: ${error}. No se puede confirmar el estado de los pares.`:'Cargando analítica… Hasta que llegue, el estado de los pares no está verificado.'}</p>}
  {a.kind==='ok'&&<p className="attention-msg ok">Todos los pares en tesis · analítica de {asOf?hms(asOf):'hora desconocida'}.</p>}
  {a.kind==='alerts'&&<div className="attention-items">{a.items.map(it=><button key={it.id} onClick={()=>onSelect(it.id)} className={'attention-item sev-'+it.sev}><span className="sev-tag">{it.sev==='crit'?'● ':'▲ '}{it.label}</span><b>{it.name}</b>{it.reason&&<small>{it.reason}</small>}</button>)}</div>}
  {a.kind==='partial'&&<p className="attention-msg">Sin alertas activas en los pares verificados.</p>}
  {a.kind!=='unavailable'&&a.kind!=='no-pairs'&&caveat.map(c=><p key={c} className="attention-msg warn">{c}</p>)}
 </section>
}
