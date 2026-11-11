// Serie compacta para la mini línea de las cards: ventana de 24 h, agrupada y con escala propia.
export type MiniPoint={time:number;pnl:number};
export type MiniRow={time:number;pnl:number;x:number;y:number};
export type MiniSeries={rows:MiniRow[];segments:{x:number;y:number}[][];end:{x:number;y:number};zeroY:number|null;min:number;max:number;first:number;last:number;delta:number;spanMs:number;points:number};
export const DAY_MS=86_400_000;
export const BUCKET_MS=15*60_000;   // 24 h ≈ 96 puntos: se ve la tendencia, no el ruido minuto a minuto
export const GAP_MS=45*60_000;      // piso del umbral de hueco; el umbral real se adapta a la frecuencia de la serie (ver gapThreshold)
const TOP=4,BOTTOM=36;              // márgenes dentro del viewBox 0..40

// Última lectura de cada tramo de 15 min dentro de las últimas `windowMs`. El último tramo conserva el valor actual exacto.
export function windowSeries(points:MiniPoint[],now:number,windowMs=DAY_MS):MiniPoint[]{
 const start=now-windowMs,byBucket=new Map<number,MiniPoint>();
 for(const point of [...points].sort((a,b)=>a.time-b.time)){if(!Number.isFinite(point.time)||!Number.isFinite(point.pnl)||point.time<start||point.time>now+BUCKET_MS)continue;byBucket.set(Math.floor(point.time/BUCKET_MS),point)}
 return [...byBucket.values()].sort((a,b)=>a.time-b.time);
}
// Series con pocos puntos (p. ej. 1 punto por hora de Hyperliquid) NO tienen huecos entre cada lectura: el umbral se adapta a la separación típica.
export function gapThreshold(times:number[]):number{const deltas:number[]=[];for(let i=1;i<times.length;i++)deltas.push(times[i]-times[i-1]);if(!deltas.length)return GAP_MS;deltas.sort((a,b)=>a-b);return Math.max(GAP_MS,4*deltas[(deltas.length-1)>>1])}
// Lectura más cercana a una posición horizontal (0..1) del gráfico, para el cursor interactivo.
export function nearestRow(series:MiniSeries,fraction:number):MiniRow{const target=Math.min(1,Math.max(0,fraction))*100;let best=series.rows[0];for(const row of series.rows)if(Math.abs(row.x-target)<Math.abs(best.x-target))best=row;return best}
export function buildMiniSeries(points:MiniPoint[],now:number,windowMs=DAY_MS):MiniSeries|null{
 const rows=windowSeries(points,now,windowMs);if(rows.length<2)return null;
 const t0=rows[0].time,t1=rows[rows.length-1].time,spanMs=t1-t0;if(spanMs<=0)return null;
 const values=rows.map(row=>row.pnl),lo=Math.min(...values),hi=Math.max(...values),last=values[values.length-1];
 // Escala ajustada al rango de las últimas 24 h (con aire arriba y abajo); un rango casi plano no se agranda como si fuera ruido enorme.
 const minSpan=Math.max(1,Math.abs(last)*0.01),raw=Math.max(hi-lo,minSpan),pad=raw*0.12,yMin=(lo+hi)/2-raw/2-pad,yMax=(lo+hi)/2+raw/2+pad;
 const y=(value:number)=>BOTTOM-((value-yMin)/(yMax-yMin))*(BOTTOM-TOP),x=(time:number)=>((time-t0)/spanMs)*100;
 const maxGap=gapThreshold(rows.map(row=>row.time)),segments:{x:number;y:number}[][]=[];let current:{x:number;y:number}[]=[];
 rows.forEach((row,index)=>{if(index>0&&row.time-rows[index-1].time>maxGap){if(current.length)segments.push(current);current=[]}current.push({x:x(row.time),y:y(row.pnl)})});
 if(current.length)segments.push(current);
 return {rows:rows.map(row=>({time:row.time,pnl:row.pnl,x:x(row.time),y:y(row.pnl)})),segments,end:{x:100,y:y(last)},zeroY:yMin<0&&yMax>0?y(0):null,min:lo,max:hi,first:values[0],last,delta:last-values[0],spanMs,points:rows.length};
}
export function spanLabel(spanMs:number):string{const minutes=Math.round(spanMs/60_000);if(minutes>=23*60)return '24 h';if(minutes>=90)return Math.round(minutes/60)+' h';return Math.max(1,minutes)+' min'}
