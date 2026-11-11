import {drawdownSeries,normalizePnlHistory} from './pnlModel';
import type {PnlPoint} from './pnlModel';

export type DayRow={date:string;pnl:number;cumulative?:number;partial?:boolean};
export type DayMetrics={days:number;wins:number;winPct:number;best:DayRow;worst:DayRow;avg:number;avgWin:number|null;avgLoss:number|null;profitFactor:number|null;streak:{count:number;positive:boolean}};

/** Métricas de calidad a partir del PNL diario. */
export function dayMetrics(daily:{date:string;pnl:number|null}[]|undefined|null):DayMetrics|null{
 const rows=(daily||[]).filter((d):d is DayRow=>typeof d.pnl==='number'&&Number.isFinite(d.pnl));
 if(!rows.length)return null;
 let gain=0,loss=0,total=0,best=rows[0],worst=rows[0],wins=0,lossDays=0;
 for(const d of rows){total+=d.pnl;if(d.pnl>0){gain+=d.pnl;wins++}else if(d.pnl<0){loss+=-d.pnl;lossDays++}if(d.pnl>best.pnl)best=d;if(d.pnl<worst.pnl)worst=d}
 const positive=rows[rows.length-1].pnl>=0;let count=0;
 for(let i=rows.length-1;i>=0&&(rows[i].pnl>=0)===positive;i--){if(i<rows.length-1&&Date.parse(rows[i+1].date)-Date.parse(rows[i].date)>86400000)break;count++}
 return {days:rows.length,wins,winPct:wins/rows.length*100,best,worst,avg:total/rows.length,avgWin:wins?gain/wins:null,avgLoss:lossDays?-loss/lossDays:null,profitFactor:loss>0?gain/loss:null,streak:{count,positive}};
}

/** Variación del PNL acumulado en la última ventana de `ms` milisegundos. */
export function deltaOver(history:PnlPoint[],ms:number):number|null{
 const rows=normalizePnlHistory(history);if(rows.length<2)return null;
 const end=rows[rows.length-1],target=end.time-ms;
 let base=rows[0];for(const r of rows){if(r.time<=target)base=r;else break}
 return end.pnl-base.pnl;
}

/** Total signed impact; missing coverage must never appear as a partial total. */
export function costImpact(fees:number|null|undefined,funding:number|null|undefined):number|null{
 return fees==null||funding==null?null:funding-fees;
}

export function maxDrawdown(history:PnlPoint[]):{max:number;current:number;worstTime:number|null;needed:number|null}{
 const rows=drawdownSeries(normalizePnlHistory(history));
 const s=rows.summary;
 const worst=rows.find(row=>row.drawdown===s.max&&row.drawdown<0);
 return {max:s.max,current:s.current,worstTime:worst?.time??null,needed:rows.length?-s.current:null};
}

/** Serie reducida (≤ n puntos) para sparklines. */
export function downsample(history:PnlPoint[],n=120):number[]{
 const rows=normalizePnlHistory(history);if(rows.length<=n)return rows.map(r=>r.pnl);
 const out:number[]=[];for(let i=0;i<n;i++)out.push(rows[Math.round(i*(rows.length-1)/(n-1))].pnl);return out;
}
