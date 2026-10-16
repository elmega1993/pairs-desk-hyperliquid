import type {Pair,PairAnalytics} from '../types';
import {money,num} from '../format';
export function PairDetail({pair,analytics}:{pair:Pair|null;analytics?:PairAnalytics}){
 if(!pair)return null;
 const fields=[['Estado',analytics?.pair_status||'N/D'],['Motivo',analytics?.pair_status_reason||'N/D'],['Riesgo por σ diario',money(analytics?.risk_usd_per_sigma_day)],['MAE',num(analytics?.mae_pct)+'%'],['MFE',num(analytics?.mfe_pct)+'%'],['Funding/día',money(analytics?.funding_per_day_usd)],['PnL long',money(pair.long_pnl as number)],['PnL short',money(pair.short_pnl as number)],['Tesis',String(pair.trade_note||'N/D')],['Invalidación',String(pair.invalidation_note||'N/D')]];
 return <div className="pair-analytics-detail"><h3>Analítica del par</h3>{fields.map(([k,v])=><div className="detail-row" key={k}><span>{k}</span><b>{v}</b></div>)}</div>
}
