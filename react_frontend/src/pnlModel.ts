/** Pure PNL series logic (no imports, so it can be unit-tested in Node). */
export type PnlPoint={time:number;pnl:number;basis?:string;realized?:number|null;unrealized?:number|null;exposure?:number|null;marginUsed?:number|null};
export type SeriesBreak={kind:'gap'|'basis';from:number;time:number;fromPnl:number;pnl:number};
export type PnlEvent={time:number;kind?:string;pair?:string;status?:string};
export type PnlEventGroup={time:number;label:string;count:number;items:PnlEvent[]};

export function normalizePnlHistory(rows:PnlPoint[]):PnlPoint[]{
 return rows.filter(r=>Number.isFinite(r.time)&&Number.isFinite(r.pnl)).map(r=>({...r,time:r.time<1e11?r.time*1000:r.time})).sort((a,b)=>a.time-b.time).filter((r,i,a)=>i===a.length-1||r.time!==a[i+1].time);
}

export type DailyPnlRow={date:string;pnl:number;cumulative:number;partial:boolean};
const dailyDate=new Intl.DateTimeFormat('en-CA',{timeZone:'America/Argentina/Buenos_Aires',year:'numeric',month:'2-digit',day:'2-digit'});
export function dailyPnl(rows:PnlPoint[]):DailyPnlRow[]{
 const groups=new Map<string,PnlPoint[]>();
 normalizePnlHistory(rows).forEach(row=>{const date=dailyDate.format(new Date(row.time));const group=groups.get(date)||[];group.push(row);groups.set(date,group)});
 const result:DailyPnlRow[]=[];let previous:number|null=null;
 groups.forEach((group,date)=>{
  const first=group[0],last=group[group.length-1];
  result.push({date,pnl:last.pnl-(previous===null?first.pnl:previous),cumulative:last.pnl,partial:previous===null});
  previous=last.pnl;
 });
 return result;
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

type DrawdownPoint=PnlPoint&{peak:number;drawdown:number};
type DrawdownSeries=DrawdownPoint[]&{summary:{max:number;current:number;currentDuration:number;recoveryMs:number|null}};
export function drawdownSeries(rows:PnlPoint[]):DrawdownSeries{
 if(!rows.length){const empty=[] as DrawdownSeries;empty.summary={max:0,current:0,currentDuration:0,recoveryMs:null};return empty}
 const out:Array<PnlPoint&{peak:number;drawdown:number}>=[];
 let peak=-Infinity,peakTime=rows[0].time,max=0,recoveryMs:null|number=null;
 let priorDrawdown=false,priorPeakTime=rows[0].time;
 rows.forEach((row,index)=>{
  const basisChanged=index>0&&row.basis&&rows[index-1].basis&&row.basis!==rows[index-1].basis;
  if(basisChanged){peak=-Infinity;priorDrawdown=false;recoveryMs=null}
  if(index===0||row.pnl>peak){
   if(index>0&&priorDrawdown)recoveryMs=row.time-priorPeakTime;
   peak=row.pnl;peakTime=row.time;priorPeakTime=peakTime;priorDrawdown=false;
  }
  const drawdown=row.pnl-peak;
  if(drawdown<0)priorDrawdown=true;
  else if(drawdown===0&&priorDrawdown)recoveryMs=row.time-priorPeakTime;
  if(drawdown<max)max=drawdown;
  out.push({...row,peak,drawdown});
 });
 const last=out[out.length-1];
 const result=out as DrawdownSeries;
 result.summary={max,current:last.drawdown,currentDuration:last.drawdown<0?last.time-peakTime:0,recoveryMs:last.drawdown===0?recoveryMs:null};
 return result;
}

export function drawdownDomain(rows:PnlPoint[]):{low:number;high:number}{
 const min=Math.min(0,...drawdownSeries(rows).map(row=>row.drawdown));
 return {low:min-Math.max(Math.abs(min)*.08,1),high:0};
}

export function historicalComponent(row:PnlPoint,field:'realized'|'unrealized',index:number,lastIndex:number,current:number|null|undefined):number|null{
 const point=row[field];
 if(point!=null&&Number.isFinite(Number(point)))return Number(point);
 return index===lastIndex&&current!=null&&Number.isFinite(Number(current))?Number(current):null;
}

const EVENT_LABELS:Record<string,string>={open:'apertura',opened:'apertura',add:'ADD',reduce:'reducción',red:'reducción',close:'cierre',closed:'cierre'};
export function groupPnlEvents(events:PnlEvent[],spacingMs=2*60*60*1000):PnlEventGroup[]{
 const clean=events.filter(e=>Number.isFinite(Number(e.time))).map(e=>({...e,time:Number(e.time)<1e11?Number(e.time)*1000:Number(e.time)})).sort((a,b)=>a.time-b.time);
 const groups:PnlEventGroup[]=[];
 for(const event of clean){
  const last=groups.at(-1);
  if(last&&event.time-last.time<=spacingMs){last.items.push(event);last.count++;last.time=Math.round((last.time+event.time)/2);continue}
  groups.push({time:event.time,label:'',count:1,items:[event]});
 }
 for(const group of groups){
  const pairs=Array.from(new Set(group.items.map(e=>e.pair).filter(Boolean))) as string[];
  const pair=pairs.length===1?pairs[0]:pairs.length>1?`${pairs.length} pares`:undefined;
  const kinds=Array.from(new Set(group.items.map(e=>EVENT_LABELS[String(e.kind||e.status||'evento').toLowerCase()]||String(e.kind||e.status||'evento'))));
  group.label=(pair?pair+' · ':'')+kinds.join(' + ');
 }
 return groups;
}
