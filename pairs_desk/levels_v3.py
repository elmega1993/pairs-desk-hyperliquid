"""Descriptive levels v3. Pure functions; no trading, network or persistence."""
from __future__ import annotations
import math
from .analytics import LEVEL_PARAMS, STATUS_THRESHOLDS

def calculate(reference,mu,sigma_d,h,health_status,regime,z=None,age_ratio=None,liq=None,n_eff=None,add_fraction=None):
    result={'status':'unavailable','reason':'Datos insuficientes','levels':{},'level_reasons':{},'basis':'log-ratio · no calibrado','approx':True}
    # Reject invalid numeric inputs before producing actionable-looking levels.
    numeric = (reference, mu, sigma_d, h)
    if any(not isinstance(v, (int, float)) or not math.isfinite(v) for v in numeric):
        return result
    if min(reference, sigma_d, h) <= 0:
        return result
    if add_fraction is not None and (not isinstance(add_fraction, (int, float)) or not math.isfinite(add_fraction) or not 0 < add_fraction <= 1):
        result['reason'] = 'Fracción ADD inválida'
        return result
    entry=math.log(reference); sigma_h=sigma_d*math.sqrt(h)
    if sigma_h<=1e-9:return result
    levels={}; reasons={};room=mu-entry
    if room>=LEVEL_PARAMS['TP_MIN_ROOM_SIGMA']*sigma_h:
        for i,f in enumerate(LEVEL_PARAMS['TP_FRACTIONS'],1):levels[f'tp{i}']=math.exp(entry+f*room)
    else:
        reasons.update(tp1='Sin recorrido de reversión suficiente',tp2='Sin recorrido de reversión suficiente')
    for i,k in enumerate(LEVEL_PARAMS['ADD_K'],1):levels[f'add{i}']=math.exp(entry-k*sigma_h)
    gates=[]
    if health_status!='stationary':gates.append('Estacionariedad no confirmada')
    if regime=='Inestable':gates.append('Régimen inestable')
    if z is None or not isinstance(z, (int, float)) or not math.isfinite(z) or z <= STATUS_THRESHOLDS['Z_BREAK']:
        gates.append('Z no verificable o ruptura extrema')
    if age_ratio is not None and (not isinstance(age_ratio, (int, float)) or not math.isfinite(age_ratio) or age_ratio > STATUS_THRESHOLDS['AGE_REVIEW_X']):
        gates.append('Edad no verificable o superior a 2 half-lives')
    # A liquidation estimate is only advisory: never silently call it verified.
    warnings = []
    if liq is None or not isinstance(liq, (int, float)) or not math.isfinite(liq):
        warnings.append('Liquidación posterior al ADD no verificada')
    elif liq / (1 + (LEVEL_PARAMS['ADD_FRACTION'] if add_fraction is None else add_fraction)) < STATUS_THRESHOLDS['LIQ_AFTER_ADD_MIN']:
        gates.append('Distancia estimada a liquidación posterior al ADD inferior al mínimo')
    warnings.append('Correlación entre patas no verificada')
    for key in ('add1','add2'):
        if gates:reasons[key]='ADD bloqueado: '+', '.join(gates)
    fraction=LEVEL_PARAMS['ADD_FRACTION'] if add_fraction is None else add_fraction
    scenarios={}
    if n_eff is not None and n_eff>0:
        for key,level in levels.items():
            if key.startswith('tp'):scenarios[key]={'pnl_at_level_usd':n_eff*(level/reference-1),'approx':True}
            else:
                added=n_eff*fraction
                scenarios[key]={'added_usd':added,'new_avg_entry_ratio':(n_eff*reference+added*level)/(n_eff+added),'new_liq_distance_pct':liq/(1+fraction) if isinstance(liq, (int, float)) and math.isfinite(liq) else None,'approx':True}
    result.update(status='ok' if len(levels)==4 else 'partial',reason='Niveles descriptivos sin calibración walk-forward',levels=levels,level_reasons=reasons,add_warnings=warnings,add_allowed=not gates,horizon_days=h,sigma_h=sigma_h,equilibrium_ratio=math.exp(mu),scenarios=scenarios)
    return result
