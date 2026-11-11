import type {AvailableAsset} from './types';
export type AssetSort='name'|'24h:desc'|'24h:asc'|'7d:desc'|'7d:asc';
export const ASSET_SORT_OPTIONS:{value:AssetSort;label:string}[]=[{value:'name',label:'Orden: A–Z'},{value:'24h:desc',label:'Mayor suba 24h'},{value:'24h:asc',label:'Mayor baja 24h'},{value:'7d:desc',label:'Mayor suba 7d'},{value:'7d:asc',label:'Mayor baja 7d'}];
export const VOLUME_OPTIONS=[{value:'0',label:'Cualquier volumen'},{value:'100000',label:'Vol. 24h > $100k'},{value:'1000000',label:'Vol. 24h > $1M'},{value:'10000000',label:'Vol. 24h > $10M'}];
const finite=(v:unknown):v is number=>typeof v==='number'&&Number.isFinite(v);
// Clic en el encabezado: primero mayor suba, luego mayor baja, luego A–Z.
export function nextAssetSort(current:AssetSort,period:'24h'|'7d'):AssetSort{if(current===period+':desc')return (period+':asc') as AssetSort;if(current===period+':asc')return 'name';return (period+':desc') as AssetSort}
// Los activos sin dato (N/D) quedan SIEMPRE al final, sea cual sea el sentido.
export function sortAssets(assets:AvailableAsset[],sort:AssetSort):AvailableAsset[]{
 const byName=(a:AvailableAsset,b:AvailableAsset)=>a.symbol.localeCompare(b.symbol)||a.venue.localeCompare(b.venue);
 if(sort==='name')return [...assets].sort(byName);
 const [period,direction]=sort.split(':') as ['24h'|'7d','asc'|'desc'];const dir=direction==='asc'?1:-1;
 const value=(a:AvailableAsset)=>period==='24h'?a.change_24h_pct:a.change_7d_pct;
 return [...assets].sort((a,b)=>{const av=value(a),bv=value(b);if(!finite(av)&&!finite(bv))return byName(a,b);if(!finite(av))return 1;if(!finite(bv))return -1;return dir*(av-bv)||byName(a,b)});
}
export const filterByVolume=(assets:AvailableAsset[],minimum:number)=>minimum>0?assets.filter(a=>finite(a.day_volume_usd)&&a.day_volume_usd>=minimum):assets;
// Ratio LONG/SHORT: (1+long)/(1+short)-1, a partir de los cambios de cada pata.
export function pairChangePct(longPct?:number|null,shortPct?:number|null):number|null{if(!finite(longPct)||!finite(shortPct))return null;const denominator=1+shortPct/100;if(denominator<=0)return null;return ((1+longPct/100)/denominator-1)*100}
