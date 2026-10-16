import React,{useRef} from 'react';
import type {Pair,PairAnalytics} from '../types';
import {statusMeta} from '../attention';
import {money,num,tone} from '../format';
import {parseSort} from '../sort';

const sortFields=[['pnl','Flotante'],['realized','Realizado'],['total_pnl','Total'],['pnl_pct','PNL %'],['size','Exposición'],['funding','Funding'],['name','Par']] as const;

/** Sidebar sorting shares the exact same state as the radar; never navigates or scrolls the document. */
export function PositionList({pairs,selected,search,sort,onSearch,onSort,onSelect,analytics}:{pairs:Pair[];selected:string;search:string;sort:string;onSearch:(s:string)=>void;onSort:(key:string)=>void;onSelect:(id:string)=>void;analytics?:Record<string,PairAnalytics>}){
 const {key,direction}=parseSort(sort);
 const listRef=useRef<HTMLDivElement>(null);
 return <section className="panel positions" aria-label="Mis posiciones">
  <div className="panel-title"><h2>Mis posiciones</h2><span className="chip">{pairs.length} pares</span></div>
  <div className="filters"><input aria-label="Buscar par" placeholder="Buscar par…" value={search} onChange={e=>onSearch(e.target.value)}/></div>
  <div className="position-sort" role="group" aria-label="Ordenar posiciones">
   {sortFields.map(([field,label])=><button key={field} type="button" aria-pressed={key===field} className={'position-sort-button '+(key===field?'selected':'')} onClick={()=>onSort(field)} title={'Ordenar por '+label}>{label}<span aria-hidden="true">{key===field?(direction==='asc'?' ↑':' ↓'):' ↕'}</span></button>)}
  </div>
  <div ref={listRef} className="position-list">{pairs.map(p=><button type="button" key={p.id} className={'position '+(selected===p.id?'chosen':'')} onClick={()=>onSelect(p.id)}><span><b>{p.long} / {p.short}{(()=>{const m=statusMeta(analytics?.[p.id]?.pair_status);return m&&(m.sev==='crit'||m.sev==='warn'||m.sev==='info')?<em className={'pos-status sev-'+m.sev} title={analytics?.[p.id]?.pair_status_reason||m.label}>{m.sev==='crit'?'● ':'▲ '}{m.label}</em>:null})()}</b><small>{money(p.size)} nominal{analytics?.[p.id]?.liq_distance_pct!=null?` · liq. ${num(analytics[p.id].liq_distance_pct,1)}%`:''}</small></span><span className="right"><b className={tone(p.pnl)}>{money(p.pnl)}</b><small>{num(p.pnl_pct)}%</small></span></button>)}</div>
  {!pairs.length&&<p className="position-empty">No hay posiciones que coincidan.</p>}
 </section>
}
