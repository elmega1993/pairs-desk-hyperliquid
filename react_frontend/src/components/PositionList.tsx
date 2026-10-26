import React,{useRef,type ReactNode} from 'react';
import type {Pair,PairAnalytics,PositionRatioChange} from '../types';
import {money,num,tone} from '../format';
import {parseSort} from '../sort';

const ratioChange=(value:number|null|undefined)=>value==null||!Number.isFinite(Number(value))?'N/D':(Number(value)>=0?'+':'')+num(value)+'%';
const sortOptions=[['pnl:desc','PNL flotante · mayor primero'],['realized:desc','PNL realizado · mayor primero'],['total_pnl:desc','PNL total · mayor primero'],['pnl_pct:desc','PNL % · mayor primero'],['size:desc','Exposición · mayor primero'],['funding:desc','Funding · mayor primero'],['name:asc','Par · A-Z']] as const;

/** Compact position rail: operational summary only; full details stay in Resumen del par. */
export function PositionList({pairs,selected,search,sort,onSearch,onSort,onSelect,analytics: _analytics,ratioChanges,actions}:{actions?:ReactNode;pairs:Pair[];selected:string;search:string;sort:string;onSearch:(s:string)=>void;onSort:(key:string)=>void;onSelect:(id:string)=>void;analytics?:Record<string,PairAnalytics>;ratioChanges?:Record<string,PositionRatioChange>}){
 const {key}=parseSort(sort);
 const listRef=useRef<HTMLDivElement>(null);
 return <section className="panel positions" aria-label="Mis posiciones">
  {actions&&<div className="positions-actions">{actions}</div>}
  <div className="panel-title"><h2>Mis posiciones</h2><span className="chip">{pairs.length} pares</span></div>
  <details className="position-filters">
   <summary>Filtros y orden <span>{key==='name'?'Par':key==='pnl'?'PNL flotante':key==='pnl_pct'?'PNL %':key==='total_pnl'?'PNL total':key==='realized'?'Realizado':key==='size'?'Exposición':'Funding'}</span></summary>
   <div className="filters-panel"><input aria-label="Buscar par" placeholder="Buscar par…" value={search} onChange={e=>onSearch(e.target.value)}/><select aria-label="Ordenar posiciones" value={sort} onChange={e=>onSort(e.target.value)}>{sortOptions.map(([value,label])=><option key={value} value={value}>{label}</option>)}</select></div>
  </details>
  <div ref={listRef} className="position-list">{pairs.map(p=>{const changes=ratioChanges?.[p.id];return <button type="button" key={p.id} className={'position '+(selected===p.id?'chosen':'')} onClick={()=>onSelect(p.id)}><span><b>{p.long} / {p.short}</b><small className="position-ratio-change" title="Cambio del ratio">1h <span className={tone(changes?.['1h'])}>{ratioChange(changes?.['1h'])}</span> · 24h <span className={tone(changes?.['24h'])}>{ratioChange(changes?.['24h'])}</span></small></span><span className="right"><b className={tone(p.pnl)}>{money(p.pnl)}</b><small className={tone(p.pnl_pct)}>{num(p.pnl_pct)}%</small></span></button>})}</div>
  {!pairs.length&&<p className="position-empty">No hay posiciones que coincidan.</p>}
 </section>
}
