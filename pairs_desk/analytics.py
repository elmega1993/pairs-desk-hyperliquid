"""Pure, read-only analytics on closed daily log-ratio candles."""
from __future__ import annotations
import math
import numpy as np

LEVEL_PARAMS = dict(EWMA_LAMBDA=.94, EQUILIBRIUM_WINDOW=90, HORIZON_DEFAULT=14,
                    TP_FRACTIONS=(.5, 1.), TP_MIN_ROOM_SIGMA=.75,
                    ADD_K=(1., 1.75), ADD_FRACTION=.25)
STATUS_THRESHOLDS = dict(Z_BREAK=-3., AGE_REVIEW_X=2., AGE_BROKEN_X=3., LIQ_WARN=10., LIQ_AFTER_ADD_MIN=25.)
DAY = 86400000

def closed_daily_logs(bars, now_ms):
    """Return sorted closed daily timestamps and log closes, rejecting stale/gapped data."""
    try:
        rows = sorted({int(b['timestamp']):float(b['close']) for b in bars if int(b['timestamp'])+DAY <= now_ms}.items())[-730:]
        if len(rows)<60 or any(v<=0 or not math.isfinite(v) for _,v in rows): return [], np.array([])
        times=np.array([t for t,_ in rows], dtype=np.int64)
        if np.max(np.diff(times))>4*DAY or now_ms-times[-1]>5*DAY:return [], np.array([])
        return times.tolist(), np.log(np.array([v for _,v in rows]))
    except (ValueError, TypeError, KeyError, OverflowError):return [], np.array([])

def ewma_vol(x, lam=.94):
    """Daily EWMA variance seeded by the first 30 daily log returns."""
    try:
        r=np.diff(np.asarray(x,dtype=float))[-250:]
        if len(r)<59 or not np.isfinite(r).all():return None
        variance=float(np.var(r[:30],ddof=1))
        for value in r[30:]:variance=lam*variance+(1-lam)*float(value)**2
        sigma=math.sqrt(variance)
        return sigma if sigma>=1e-9 and math.isfinite(sigma) else None
    except (ValueError, TypeError, FloatingPointError):return None

def equilibrium(x, window=90):
    a=np.asarray(x,dtype=float)
    if len(a)<window or not np.isfinite(a).all():return None,None
    mu=float(np.mean(a[-window:])); s=float(np.std(a[-window:],ddof=1))
    return (mu,s) if s>1e-9 else (None,None)

def z_log(x_live, mu, s):
    if mu is None or s is None or s<=0 or x_live is None or not math.isfinite(x_live):return None
    return (x_live-mu)/s

def age_days(opened_at_ms,now_ms):
    return max(0,(now_ms-opened_at_ms)/DAY) if opened_at_ms is not None and opened_at_ms>0 else None

def age_vs_half_life(age,half_life):
    return age/half_life if age is not None and half_life is not None and half_life>0 else None

def risk_per_sigma(n_eff,sigma_d,h):
    if any(v is None for v in (n_eff,sigma_d,h)) or min(n_eff,sigma_d,h)<0:return None,None
    return n_eff*sigma_d,n_eff*sigma_d*math.sqrt(h)

def mae_mfe(times,x,opened_at_ms,x_entry,x_live,n_eff=None):
    if opened_at_ms is None or x_entry is None or x_live is None:return {'status':'unavailable','reason':'Sin apertura o entrada verificable'}
    values=[float(v) for t,v in zip(times,x) if t>=opened_at_ms]+[x_live]
    if not values:return {'status':'unavailable','reason':'Sin recorrido posterior a apertura'}
    down=100*math.expm1(min(values)-x_entry);up=100*math.expm1(max(values)-x_entry)
    return {'status':'ok','reason':'','mae_pct':down,'mfe_pct':up,'mae_usd':n_eff*down/100 if n_eff is not None else None,'mfe_usd':n_eff*up/100 if n_eff is not None else None,'basis':'cierres diarios + ratio actual','approx':True}

def wilson(hits,n):
    p=hits/n; z=1.96; den=1+z*z/n; mid=(p+z*z/(2*n))/den; half=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/den
    return [max(0,mid-half),min(1,mid+half)]

def hit_rates(x,sigma_d,h,ks,min_blocks=20):
    """Descriptive non-overlapping path-touch frequencies; never future probabilities."""
    a=np.asarray(x,dtype=float); result={}; barrier=sigma_d*math.sqrt(h) if sigma_d else None
    for key,k in ks.items():
        paths=[a[i:i+h+1]-a[i] for i in range(0,len(a)-h,h)] if h>0 else []
        if barrier is None or len(paths)<min_blocks:result[key]={'status':'unavailable','reason':'Bloques independientes insuficientes','n_blocks':len(paths)};continue
        hits=sum((np.max(p)>=k*barrier if k>0 else np.min(p)<=k*barrier) for p in paths)
        result[key]={'status':'ok','p':hits/len(paths),'n_blocks':len(paths),'ci95':wilson(hits,len(paths))}
    return result

def pair_status(z=None,regime=None,health=None,age_ratio=None,pnl=None,liq=None,add_hit=False,add_allowed=False,tp_hit=False):
    if liq is not None and liq<=STATUS_THRESHOLDS['LIQ_WARN']:return 'LIQUIDACION','Distancia de liquidación ≤ 10%'
    if regime=='Inestable' or (z is not None and z<=-3 and health!='stationary') or (age_ratio is not None and age_ratio>3 and pnl is not None and pnl<0):return 'TESIS_ROTA','Ruptura estadística o edad excesiva de la posición'
    if tp_hit:return 'REVISAR_TP','Objetivo TP alcanzado'
    if add_hit:return ('REVISAR_ADD' if add_allowed else 'ADD_BLOQUEADO'),'Nivel ADD alcanzado; revisar filtros de riesgo'
    if age_ratio is not None and age_ratio>2:return 'REVISAR_EDAD','Duración superior a dos half-lives'
    if z is None or regime is None:return 'SIN_DATOS','Estadísticas insuficientes'
    return 'EN_TESIS','Sin alertas analíticas'
