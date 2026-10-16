import {useEffect,useState} from 'react';
const ago=(s:number)=>s<90?`${Math.max(0,s)} s`:`${Math.round(s/60)} min`;
export function Freshness({updatedAt,analyticsAt,error}:{updatedAt?:number;analyticsAt?:number|null;error:boolean}){
 const [now,setNow]=useState(()=>Date.now());
 useEffect(()=>{const t=window.setInterval(()=>setNow(Date.now()),5000);return()=>window.clearInterval(t)},[]);
 if(!updatedAt)return <span className="fresh bad">Sin actualización</span>;
 const age=Math.round((now-updatedAt)/1000);
 const level=error||age>120?'bad':age>60?'warn':'';
 const aAge=analyticsAt?Math.round((now-analyticsAt)/1000):null;
 return <span className={'fresh '+level} title={`Estado: ${new Date(updatedAt).toLocaleTimeString('es-AR',{hour12:false})}${aAge!==null?` · Analítica: hace ${ago(aAge)}`:' · Analítica: sin datos'}`}>{level?'⚠ ':''}Datos de hace {ago(age)}{error?' · última lectura falló':''}</span>
}
