"""Descriptive, read-only adaptive ratio levels. Never creates execution orders."""
from __future__ import annotations
import math
import numpy as np
import pandas as pd


def calculate(frame: pd.DataFrame, reference: float) -> dict:
    base = {'status':'unavailable','regime':'N/D','reason':'Histórico insuficiente o inválido',
            'levels':{},'level_reasons':{},'horizon_days':14}
    if frame is None or 'c' not in frame or not math.isfinite(reference) or reference <= 0:
        return base
    prices = pd.to_numeric(frame['c'], errors='coerce').replace([np.inf,-np.inf],np.nan).dropna()
    prices = prices[prices > 0].iloc[-730:]
    if len(prices) < 60:
        return {**base,'reason':f'Histórico diario insuficiente ({len(prices)}/60 velas)'}
    logp = np.log(prices.to_numpy(dtype=float))
    daily = np.diff(logp)
    volatility = float(np.std(daily[-min(60,len(daily)):],ddof=1))
    if not np.isfinite(volatility) or volatility < 1e-9:
        return {**base,'reason':'Volatilidad no verificable'}
    window = min(90,len(logp)//2)
    t = np.arange(window,dtype=float)
    slope, intercept = np.polyfit(t,logp[-window:],1)
    residual_sigma = float(np.std(logp[-window:]-(intercept+slope*t),ddof=1))
    strength = abs(slope*window)/max(residual_sigma,1e-9)
    shift = abs(float(np.median(logp[-window:])-np.median(logp[-2*window:-window])))/max(residual_sigma,1e-9)
    unstable = strength > 12 and shift > 8
    regime = 'Inestable' if unstable else ('Tendencia' if strength > 1.6 else 'Rango')
    horizon = 14
    # Observed horizon moves; compute each tail independently. Never force four levels.
    moves = logp[horizon:]-logp[:-horizon]
    down = np.sort(moves[moves < -1e-9])
    up = np.sort(moves[moves > 1e-9])
    levels, reasons = {}, {}
    specs = [('add1',down,.75,-1),('add2',down,.25,-1),
             ('tp1',up,.25,1),('tp2',up,.75,1)]
    for name, sample, quantile, sign in specs:
        if len(sample) < 8:
            reasons[name]=f'Solo {len(sample)} movimientos históricos del signo requerido (mínimo 8)'
            continue
        change = float(np.quantile(sample,quantile))
        if sign*change <= 0:
            reasons[name]='No hay movimientos válidos para este objetivo'
            continue
        price = float(reference*math.exp(change))
        if math.isfinite(price) and price > 0:
            levels[name]=price
        else:
            reasons[name]='Nivel numérico inválido'
    # Extreme regimes are allowed for descriptive TPs but ADDs are suppressed
    # to avoid encouraging averaging into a structural break.
    if unstable:
        for key in ('add1','add2'):
            levels.pop(key,None)
            reasons[key]='ADD bloqueado: tendencia o desplazamiento estructural extremo'
    status = 'ok' if len(levels)==4 else ('partial' if levels else 'unavailable')
    reason = ('Régimen inestable: ADD deshabilitados; TP solo descriptivos' if unstable else
              'Cuantiles históricos de movimientos a 14 días, no probabilidades de ejecución')
    return {'status':status,'regime':regime,'reason':reason,'levels':levels,
            'level_reasons':reasons,'horizon_days':horizon,'samples':len(moves),
            'daily_volatility_pct':100*volatility,'trend_strength':round(float(strength),2)}


def adaptive_signals(current: float, reference: float, result: dict, done_tp=(), done_add=()) -> dict:
    levels = result.get('levels') or {}
    if not math.isfinite(current) or current <= 0:
        levels={}
    tp_done, add_done = set(done_tp), set(done_add)
    def signal(kind, done):
        keys=[f'{kind}{i}' for i in (1,2) if i not in done]
        if not keys:
            return ('TP COMPLETO' if kind=='tp' else 'NO ADD · LÍMITE','Escalones completados',None)
        key=keys[0]
        if key not in levels:
            return ('N/D · adaptativo',(result.get('level_reasons') or {}).get(key,result.get('reason','Sin datos')),None)
        hit=current >= levels[key] if kind=='tp' else current <= levels[key]
        number=int(key[-1]); label='REVISAR TP' if kind=='tp' else 'REVISAR ADD'
        return (f'{label} {number}' if hit else ('HOLD' if kind=='tp' else 'WATCH'),
                f'{key.upper()}: {levels[key]:.6g} · {result.get("regime","N/D")}',number if hit else None)
    tp,td,tn=signal('tp',tp_done)
    add,ad,an=signal('add',add_done)
    return {'tp':tp,'tp_detail':td,'tp_level':tn,'add':add,'add_detail':ad,'add_level':an}
