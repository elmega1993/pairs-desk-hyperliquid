import {useCallback,useEffect,useState} from 'react';
type S={csrf:string;armed:boolean;trading_blocked:boolean};
async function req<T>(path:string,body?:object):Promise<T>{const r=await fetch(path,{method:body?'POST':'GET',headers:body?{'Content-Type':'application/json'}:undefined,body:body?JSON.stringify(body):undefined,cache:'no-store'});const d=await r.json();if(!r.ok)throw Error(typeof d.detail==='string'?d.detail:`HTTP ${r.status}`);return d as T}
/** Always-visible trading state. Reads on mount, on tab focus and when PairActions changes it (no polling: /status reads the keyring). */
export function TradeBadge(){
 const [s,setS]=useState<S|null>(null),[err,setErr]=useState(''),[busy,setBusy]=useState(false);
 const load=useCallback(async()=>{try{const v=await req<S>('/api/trade/status');setS(v);setErr('')}catch(e){setS(null);setErr(String(e))}},[]);
 useEffect(()=>{void load();const vis=()=>{if(document.visibilityState==='visible')void load()};const ev=()=>void load();document.addEventListener('visibilitychange',vis);window.addEventListener('pairs-desk-trade-status',ev);return()=>{document.removeEventListener('visibilitychange',vis);window.removeEventListener('pairs-desk-trade-status',ev)}},[load]);
 const disarm=async()=>{if(!s)return;setBusy(true);try{await req('/api/trade/arm',{csrf:s.csrf,enabled:false})}catch(e){setErr(String(e))}finally{setBusy(false);await load()}};
 if(!s)return <span className="trade-badge unknown" title={err}>Estado de órdenes desconocido</span>;
 if(s.armed)return <span className="trade-badge armed" role="status">● ÓRDENES REALES HABILITADAS <button disabled={busy} onClick={()=>void disarm()}>{busy?'Deshabilitando…':'Deshabilitar'}</button></span>;
 if(s.trading_blocked)return <span className="trade-badge blocked" role="status">Trading bloqueado: operaciones pendientes de conciliar</span>;
 return <span className="trade-badge off">Órdenes deshabilitadas</span>;
}
