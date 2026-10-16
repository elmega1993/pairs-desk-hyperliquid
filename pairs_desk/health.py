"""Informative stationarity diagnostics. Never used to authorize orders."""
from __future__ import annotations
import math
import time
import numpy as np


def assess_series(values, days_per_bar=1.0):
    out = dict(status='unavailable', label='N/D', reason='', samples=len(values),
               adf_pvalue=None, phi=None, half_life_bars=None, half_life_days=None)
    try:
        x = np.asarray(values, dtype=float)
        if len(x) < 60:
            out['reason'] = 'Se necesitan al menos 60 observaciones.'; return out
        if not np.isfinite(x).all() or np.ptp(x) < 1e-10:
            out['reason'] = 'Serie inválida o constante.'; return out
        from statsmodels.tsa.stattools import adfuller
        p = float(adfuller(x, regression='c', autolag='AIC')[1])
        if not math.isfinite(p): raise ValueError('ADF no finito')
        out['adf_pvalue'] = p
        a,b=x[:-1],x[1:]; centered=a-a.mean(); ss=float(centered@centered)
        phi=float(centered@(b-b.mean())/ss)
        residual=b-(b.mean()-phi*a.mean()+phi*a)
        se=math.sqrt(float(residual@residual)/(len(a)-2)/ss)
        out['phi']=phi
        if p >= .05:
            out.update(status='inconclusive',label='Reversión no confirmada',reason='ADF no rechaza raíz unitaria al 5%; un Z extremo puede acompañar una tendencia.')
            return out
        out.update(status='stationary',label='Evidencia de estacionariedad',reason='ADF rechaza raíz unitaria en esta ventana; no garantiza reversión futura.')
        if 0 < phi < 1 and phi+1.96*se < 1:
            half=-math.log(2)/math.log(phi)
            if math.isfinite(half) and half <= len(x)/2:
                out.update(half_life_bars=half,half_life_days=half*days_per_bar)
        if out['half_life_bars'] is None:
            out['reason'] += ' Half-life no estimable con suficiente evidencia AR(1).'
        return out
    except ImportError:
        out['reason']='Falta statsmodels; reiniciá con el iniciador para instalar dependencias.'
    except (ValueError, TypeError, ZeroDivisionError, np.linalg.LinAlgError):
        out['reason']='No se pudo estimar una estadística válida.'
    return out


def pair_health(bars, now_ms=None):
    now=int(time.time()*1000) if now_ms is None else int(now_ms)
    try:
        # Daily candles are timestamped at opening; exclude the current candle.
        closed=sorted({int(b['timestamp']):b for b in bars if int(b['timestamp'])+86_400_000 <= now}.values(),key=lambda b:int(b['timestamp']))[-250:]
        values=[float(b['close']) for b in closed]
        if any(v<=0 or not math.isfinite(v) for v in values): raise ValueError()
        times=[int(b['timestamp']) for b in closed]
        if len(times)>1 and max(np.diff(times))>4*86_400_000: raise ValueError()
        if times and now-times[-1]>5*86_400_000: raise ValueError()
        step=(times[-1]-times[0])/(len(times)-1)/86_400_000 if len(times)>1 else 1
        result=assess_series(np.log(values),step)
        result.update(last_closed_ms=times[-1] if times else None, basis='log-ratio · velas diarias cerradas',days_approximate=step!=1)
        return result
    except (ValueError,TypeError,KeyError):
        return dict(status='unavailable',label='N/D',reason='Velas inválidas, vencidas o huecos de más de cuatro días.',adf_pvalue=None,half_life_bars=None,half_life_days=None,samples=0)
