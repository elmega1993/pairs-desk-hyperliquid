import type {Pair,PairAnalytics} from '../types';
import {money,num,signedMoney,tone} from '../format';
const rate=(v:unknown)=>v==null||!Number.isFinite(Number(v))?'N/D':num(v,4)+'%/h';
export function fundingTitle(a?:PairAnalytics){
 if(a?.funding_per_day_usd==null)return a?.funding_reason||'Sin estimación de funding';
 return `Estimado con las tasas vigentes (cambian cada hora). Long ${rate(a.funding_long_rate_pct_h)} · Short ${rate(a.funding_short_rate_pct_h)} · ${num(a.funding_apr_pct,1)}% anual sobre el nominal. Positivo: el par cobra; negativo: paga.`;
}
export function PairDetail({pair,analytics}:{pair:Pair|null;analytics?:PairAnalytics}){
 if(!pair)return null;
 const fields:[string,string,string?,string?][]=[['Estado',analytics?.pair_status||'N/D'],['Motivo',analytics?.pair_status_reason||'N/D'],['Riesgo por σ diario',money(analytics?.risk_usd_per_sigma_day)],['MAE',num(analytics?.mae_pct)+'%'],['MFE',num(analytics?.mfe_pct)+'%'],['Funding/día (est.)',signedMoney(analytics?.funding_per_day_usd),fundingTitle(analytics),analytics?.funding_per_day_usd==null?'':tone(analytics.funding_per_day_usd)],['PnL long',money(pair.long_pnl as number)],['PnL short',money(pair.short_pnl as number)],['Tesis',String(pair.trade_note||'N/D')],['Invalidación',String(pair.invalidation_note||'N/D')]];
 return <div className="pair-analytics-detail"><h3>Analítica del par</h3>{fields.map(([k,v,title,cls])=><div className="detail-row" key={k}><span>{k}</span><b title={title} className={cls}>{v}</b></div>)}</div>
}
