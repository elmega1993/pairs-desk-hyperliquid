import type {Data} from './types';
import type {PnlPoint} from './pnlModel';

export type OfficialPnl = {value:number|null;source:'hyperliquid'|'local';series:PnlPoint[];fallback:boolean};
const finite=(value:unknown):value is number=>typeof value==='number'&&Number.isFinite(value);
function rows(value:unknown):PnlPoint[]{
 if(!Array.isArray(value))return [];
 return value.map((item:any)=>({time:Number(item?.time),pnl:Number(item?.pnl),basis:item?.basis,source:item?.source})).filter(item=>Number.isFinite(item.time)&&Number.isFinite(item.pnl));
}
export function resolveOfficialPnl(data:Pick<Data,'official_pnl'|'hl_pnl'|'summary'|'pnl_history'>|null|undefined):OfficialPnl{
 const series=rows(data?.hl_pnl?.all),reported=data?.official_pnl?.all,value=finite(reported)?reported:(series.at(-1)?.pnl??null);
 if(value!==null&&series.length)return {value,source:'hyperliquid',series,fallback:false};
 const local=rows(data?.pnl_history);
 return {value:local.at(-1)?.pnl??(finite(data?.summary?.total)?data!.summary.total:null),source:'local',series:local,fallback:true};
}
