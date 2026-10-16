export const money=(v:unknown)=>v==null||!Number.isFinite(Number(v))?'N/D':`${Number(v)<0?'-':''}$${Math.abs(Number(v)).toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2})}`;
export const num=(v:unknown,d=2)=>v==null||!Number.isFinite(Number(v))?'N/D':Number(v).toLocaleString('en-US',{minimumFractionDigits:d,maximumFractionDigits:d});
export const tone=(v:unknown)=>v==null?'':Number(v)>=0?'positive':'negative';
export const pref=(k:string,d:string)=>{try{return localStorage.getItem('pairs-react-'+k)||d}catch{return d}};
