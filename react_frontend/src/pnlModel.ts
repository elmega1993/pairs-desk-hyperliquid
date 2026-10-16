/** Pure PNL series logic (no imports, so it can be unit-tested in Node). */
export type PnlPoint={time:number;pnl:number;basis?:string};
export type SeriesBreak={kind:'gap'|'basis';from:number;time:number;fromPnl:number;pnl:number};

export function normalizePnlHistory(rows:PnlPoint[]):PnlPoint[]{
 return rows.filter(r=>Number.isFinite(r.time)&&Number.isFinite(r.pnl)).map(r=>({...r,time:r.time<1e11?r.time*1000:r.time})).sort((a,b)=>a.time-b.time).filter((r,i,a)=>i===a.length-1||r.time!==a[i+1].time);
}

/** Snapshots are only written while the app is open, so long holes are real "no data" periods. */
export function gapThreshold(rows:PnlPoint[]):number{
 const steps:number[]=[];for(let i=1;i<rows.length;i++)steps.push(rows[i].time-rows[i-1].time);
 if(!steps.length)return 15*60000;
 steps.sort((a,b)=>a-b);
 return Math.max(steps[steps.length>>1]*5,15*60000);
}

/** Split into drawable segments at time gaps and at accounting-basis changes (net vs gross). */
export function toSegments(rows:PnlPoint[],threshold=gapThreshold(rows)):{segments:PnlPoint[][];breaks:SeriesBreak[]}{
 const segments:PnlPoint[][]=[];const breaks:SeriesBreak[]=[];
 let current:PnlPoint[]=[];
 rows.forEach((r,i)=>{
  if(i>0){
   const p=rows[i-1];
   const basis=!!r.basis&&!!p.basis&&r.basis!==p.basis;
   const gap=r.time-p.time>threshold;
   if(basis||gap){breaks.push({kind:basis?'basis':'gap',from:p.time,time:r.time,fromPnl:p.pnl,pnl:r.pnl});segments.push(current);current=[]}
  }
  current.push(r);
 });
 if(current.length)segments.push(current);
 return {segments,breaks};
}

const RANGE_MS:Record<string,number>={'1d':86400000,'7d':604800000,'30d':2592000000};
/** Picks the curve to draw. Hyperliquid's own windows are continuous; the local log has holes when the app was not running. */
export function pickPnlSeries(hl:Record<string,PnlPoint[]>|undefined,local:PnlPoint[],range:string,want:'hl'|'local',now:number):{rows:PnlPoint[];source:'hyperliquid'|'local';fallback:boolean}{
 const h=hl?.[range]??[];
 if(want==='hl'&&h.length>1)return {rows:h,source:'hyperliquid',fallback:false};
 const ms=RANGE_MS[range];
 const rows=ms?local.filter(r=>now-(r.time<1e11?r.time*1000:r.time)<=ms):local;
 return {rows,source:'local',fallback:want==='hl'};
}

/** Total time without records (sum of gaps), in ms. */
export function gapTotal(breaks:SeriesBreak[]):number{return breaks.reduce((n,b)=>b.kind==='gap'?n+(b.time-b.from):n,0)}

/** Auto scale: include zero only when the data crosses it or sits close to it; otherwise fit the range. */
export function includeZero(min:number,max:number,mode:'auto'|'zero'):boolean{
 if(mode==='zero')return true;
 if(min<=0&&max>=0)return true;
 const nearest=Math.min(Math.abs(min),Math.abs(max));
 return nearest<=(max-min);
}

/** Running maximum that restarts when the basis changes (peaks are not comparable across bases). */
export function runningPeaks(rows:PnlPoint[]):number[]{
 const out:number[]=[];let peak=-Infinity;
 rows.forEach((r,i)=>{if(i>0&&r.basis&&rows[i-1].basis&&r.basis!==rows[i-1].basis)peak=-Infinity;peak=Math.max(peak,r.pnl);out.push(peak)});
 return out;
}

export type PnlStats={first:number;last:number;delta:number;max:PnlPoint;min:PnlPoint;fromPeak:number;maxDrawdown:number;mixedBasis:boolean;startTime:number};
/** Stats over the latest run with a single basis. `mixedBasis` tells the UI the series changed basis. */
export function pnlStats(rows:PnlPoint[]):PnlStats|null{
 if(!rows.length)return null;
 let start=0;
 for(let i=1;i<rows.length;i++)if(rows[i].basis&&rows[i-1].basis&&rows[i].basis!==rows[i-1].basis)start=i;
 const run=rows.slice(start);
 let max=run[0],min=run[0],peak=run[0].pnl,maxDD=0;
 for(const r of run){
  if(r.pnl>max.pnl)max=r;if(r.pnl<min.pnl)min=r;
  peak=Math.max(peak,r.pnl);maxDD=Math.min(maxDD,r.pnl-peak);
 }
 const last=run[run.length-1];
 return {first:run[0].pnl,last:last.pnl,delta:last.pnl-run[0].pnl,max,min,fromPeak:last.pnl-max.pnl,maxDrawdown:maxDD,mixedBasis:start>0,startTime:run[0].time};
}
