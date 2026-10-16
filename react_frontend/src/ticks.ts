/** Round, human-friendly axis ticks (1, 2, 2.5, 5 × 10^n) inside [low, high]. */
export function niceTicks(low:number,high:number,target=5):{ticks:number[];step:number}{
 if(!Number.isFinite(low)||!Number.isFinite(high)||high<=low)return {ticks:[],step:1};
 const rough=(high-low)/Math.max(1,target-1);
 const pow=Math.pow(10,Math.floor(Math.log10(rough)));
 const unit=rough/pow;
 const step=(unit<=1?1:unit<=2?2:unit<=2.5?2.5:unit<=5?5:10)*pow;
 const first=Math.ceil(low/step-1e-9),last=Math.floor(high/step+1e-9);
 const ticks:number[]=[];
 for(let i=first;i<=last;i++)ticks.push(Math.abs(i*step)<step*1e-9?0:Number((i*step).toFixed(10)));
 return {ticks,step};
}
/** Compact USD label for axis ticks: no decimals unless the step requires them. */
export function axisMoney(v:number,step:number):string{
 const decimals=step>=1?0:step>=.1?1:2;
 return `${v<0?'-':''}$${Math.abs(v).toLocaleString('en-US',{minimumFractionDigits:decimals,maximumFractionDigits:decimals})}`;
}
