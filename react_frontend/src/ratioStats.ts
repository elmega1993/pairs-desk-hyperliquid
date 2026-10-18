export type RatioStats={
  current:number;
  sampleSize:number;
  percentile:number;
  mean:number;
  standardDeviation:number;
  zScore:number;
  percentiles:{p10:number;p25:number;p50:number;p75:number;p90:number};
  histogram:{low:number;high:number;count:number;maxCount:number}[];
  forward:{horizon:number;sampleSize:number;up:number;down:number;flat:number;medianChange:number}|null;
};

type RatioBar={close?:unknown;timestamp?:unknown};
const round=(value:number,digits=4)=>Number(value.toFixed(digits));
const quantile=(values:number[],q:number)=>{
  if(!values.length)return NaN;
  const position=(values.length-1)*q;
  const lower=Math.floor(position),upper=Math.ceil(position);
  if(lower===upper)return values[lower];
  return values[lower]+(values[upper]-values[lower])*(position-lower);
};
const median=(values:number[])=>quantile([...values].sort((a,b)=>a-b),.5);

export function buildRatioStats(bars:RatioBar[],windowSize=90,horizon=14):RatioStats|null{
  const values=bars.map(bar=>Number(bar.close)).filter(value=>Number.isFinite(value)&&value>0);
  if(values.length<2)return null;
  const sample=values.slice(-Math.max(2,Math.floor(windowSize)));
  const current=sample.at(-1)!;
  const ordered=[...sample].sort((a,b)=>a-b);
  const mean=sample.reduce((sum,value)=>sum+value,0)/sample.length;
  const variance=sample.reduce((sum,value)=>sum+(value-mean)**2,0)/sample.length;
  const standardDeviation=Math.sqrt(variance);
  const lessOrEqual=ordered.filter(value=>value<=current).length;
  const forwardValues=sample.slice(0,Math.max(0,sample.length-Math.max(1,horizon)));
  const changes:number[]=[];
  let up=0,down=0,flat=0;
  for(let i=0;i<forwardValues.length;i++){
    const target=sample[i+Math.max(1,horizon)];
    if(!Number.isFinite(target)||forwardValues[i]<=0)continue;
    const change=target/forwardValues[i]-1;
    changes.push(change);
    if(change>0)up++; else if(change<0)down++; else flat++;
  }
  const total=up+down+flat;
  const histogramBins=8;
  const min=ordered[0],max=ordered.at(-1)!;
  const width=max>min?(max-min)/histogramBins:1;
  const counts=Array.from({length:histogramBins},()=>0);
  for(const value of sample){const index=Math.min(histogramBins-1,Math.max(0,Math.floor((value-min)/width)));counts[index]++;}
  const maxCount=Math.max(...counts,1);
  return {
    current:round(current),sampleSize:sample.length,percentile:round(lessOrEqual/ordered.length*100,1),
    mean:round(mean),standardDeviation:round(standardDeviation),zScore:standardDeviation?round((current-mean)/standardDeviation):0,
    percentiles:{p10:round(quantile(ordered,.1)),p25:round(quantile(ordered,.25)),p50:round(quantile(ordered,.5)),p75:round(quantile(ordered,.75)),p90:round(quantile(ordered,.9))},
    histogram:counts.map((count,index)=>({low:round(min+index*width),high:round(min+(index+1)*width),count,maxCount})),
    forward:total?{horizon:Math.max(1,horizon),sampleSize:total,up:round(up/total*100,1),down:round(down/total*100,1),flat:round(flat/total*100,1),medianChange:round(median(changes)*100,2)}:null,
  };
}
