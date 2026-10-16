import {useMemo} from 'react';
import type {Bar} from './types';
export function ZScorePane({bars,windowSize=60}:{bars:Bar[];windowSize?:number}){
 const points=useMemo(()=>bars.map((bar,i)=>{if(i+1<windowSize)return null;const values=bars.slice(i+1-windowSize,i+1).map(b=>b.close);const avg=values.reduce((a,b)=>a+b,0)/values.length;const std=Math.sqrt(values.reduce((a,b)=>a+(b-avg)**2,0)/values.length);return {time:bar.timestamp,z:std>0?(bar.close-avg)/std:0}}).filter((x):x is {time:number;z:number}=>x!==null),[bars,windowSize]);
 if(points.length<2)return <div className="zscore-pane">Z-score ({windowSize}): se necesitan {windowSize} cierres sincronizados.</div>;
 const width=900,height=145,pad=22,span=height-2*pad;
 const y=(z:number)=>pad+(3-Math.max(-3,Math.min(3,z)))/6*span;
 const path=points.map((p,i)=>`${i?'L':'M'}${(i/(points.length-1)*width).toFixed(2)},${y(p.z).toFixed(2)}`).join(' ');
 return <div className="zscore-pane"><div className="zscore-heading">Z-SCORE · {windowSize} CIERRES <strong>{points.at(-1)!.z.toFixed(2)}</strong> <small>±1 / ±2 · basado en cierres del ratio</small></div><svg viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none" role="img" aria-label="Z-score móvil sobre cierres del ratio">{[-2,-1,0,1,2].map(n=><g key={n}><line x1="0" x2={width} y1={y(n)} y2={y(n)} stroke={n===0?'#8d9ab1':'#4d5775'} strokeDasharray={n===0?'0':'4 5'}/><text x="5" y={y(n)-3} fill="#9cabcb" fontSize="11">{n}</text></g>)}<path d={path} stroke="#b59cff" fill="none" strokeWidth="2" vectorEffect="non-scaling-stroke"/></svg></div>
}
