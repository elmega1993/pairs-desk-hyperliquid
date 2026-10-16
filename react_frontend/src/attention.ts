/** Attention queue model. An unavailable or incomplete analysis must never read as "all clear". */
export type Sev='crit'|'warn'|'info'|'nodata'|'ok';
export type StatusMeta={label:string;sev:Sev;rank:number};
const META:Record<string,StatusMeta>={
 LIQUIDACION:{label:'Liquidación cercana',sev:'crit',rank:0},
 TESIS_ROTA:{label:'Tesis rota',sev:'crit',rank:1},
 ADD_BLOQUEADO:{label:'ADD bloqueado',sev:'warn',rank:2},
 REVISAR_EDAD:{label:'Revisar edad',sev:'warn',rank:3},
 REVISAR_TP:{label:'Revisar TP',sev:'info',rank:4},
 REVISAR_ADD:{label:'Revisar ADD',sev:'info',rank:5},
 SIN_DATOS:{label:'Sin datos',sev:'nodata',rank:9},
 EN_TESIS:{label:'En tesis',sev:'ok',rank:10},
};
/** Unknown states are surfaced as warnings instead of being hidden. */
export function statusMeta(status?:string|null):StatusMeta|null{
 if(!status)return null;
 return META[status]||{label:status.replace(/_/g,' ').toLowerCase(),sev:'warn',rank:3.5};
}
type P={id:string;long:string;short:string};
type A={pair_status?:string;pair_status_reason?:string};
export type AttentionItem={id:string;name:string;label:string;sev:Sev;reason:string};
export type Attention={kind:'no-pairs'|'unavailable'|'alerts'|'partial'|'ok';items:AttentionItem[];unverified:string[];nodata:string[];stale:boolean;error:string;okCount:number;asOf:number|null};
export const STALE_ANALYTICS_MS=180000;
export function buildAttention(pairs:P[],analytics:Record<string,A>,ctx:{loaded:boolean;error?:string;asOf?:number|null;now:number}):Attention{
 const base={items:[] as AttentionItem[],unverified:[] as string[],nodata:[] as string[],error:ctx.error||'',asOf:ctx.asOf??null,okCount:0};
 if(!pairs.length)return {...base,kind:'no-pairs',stale:false};
 if(!ctx.loaded)return {...base,kind:'unavailable',stale:false};
 const stale=!!ctx.error||(ctx.asOf!=null&&ctx.now-ctx.asOf>STALE_ANALYTICS_MS);
 const ranked:{item:AttentionItem;rank:number}[]=[];
 for(const p of pairs){
  const name=`${p.long}/${p.short}`;const meta=statusMeta(analytics[p.id]?.pair_status);
  if(!meta){base.unverified.push(name);continue}
  if(meta.sev==='ok'){base.okCount++;continue}
  if(meta.sev==='nodata'){base.nodata.push(name);continue}
  ranked.push({rank:meta.rank,item:{id:p.id,name,label:meta.label,sev:meta.sev,reason:analytics[p.id]?.pair_status_reason||''}});
 }
 ranked.sort((a,b)=>a.rank-b.rank||a.item.name.localeCompare(b.item.name));
 const items=ranked.map(r=>r.item);
 const incomplete=base.unverified.length>0||base.nodata.length>0||stale;
 return {...base,items,stale,kind:items.length?'alerts':incomplete?'partial':'ok'};
}
