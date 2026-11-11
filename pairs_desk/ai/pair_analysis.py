"""Deterministic pair evidence and counterfactual sensitivities, no market I/O or orders."""
from __future__ import annotations
import math


def number(value):
    if value is None or isinstance(value,bool):return None
    try:result=float(value)
    except (ValueError,TypeError,OverflowError):return None
    return result if math.isfinite(result) else None


def pair_review(snapshot, pair_id, now_ms):
    row=next((p for p in snapshot['pairs'] if p.get('id')==pair_id),None)
    if row is None:raise ValueError('El par está cerrado o no tiene posiciones abiertas verificadas')
    long_coin,short_coin=row.get('long'),row.get('short')
    long_usd,short_usd=number(row.get('long_usd')),number(row.get('short_usd'))
    valid=long_usd is not None and short_usd is not None and long_usd>=0 and short_usd>=0
    net=long_usd-short_usd if valid else None
    gross=long_usd+short_usd if valid else None
    shared=sorted({coin for other in snapshot['pairs'] if other.get('id')!=pair_id
                   for coin in (long_coin,short_coin) if coin in (other.get('long'),other.get('short'))})
    stress=[];reference=None
    if valid:
        for name,long_return,short_return in [('both_up_5pct',.05,.05),('both_down_5pct',-.05,-.05),
                ('long_up_5pct_short_flat',.05,0),('long_flat_short_up_5pct',0,.05),
                ('long_up_5pct_short_up_4_5pct',.05,.045)]:
            stress.append({'name':name,'long_return_pct':long_return*100,'short_return_pct':short_return*100,
                'ratio_change_pct':((1+long_return)/(1+short_return)-1)*100,
                'incremental_pnl_usd':long_usd*long_return-short_usd*short_return})
        reference={'larger_leg':'short' if net<0 else 'long' if net>0 else None,
                   'reduction_usd':abs(net),'result_net_directional_usd':0,
                   'meaning':'Referencia de sensibilidad, no orden: igualar nominales reduciendo la pata mayor; no equivale a hedge por beta.'}
    analytics=snapshot.get('analytics') or {}
    stamp=number(analytics.get('as_of_ms'))
    fresh=stamp is not None and 0<=now_ms-stamp<=180_000
    statistical=(analytics.get('pairs') or {}).get(pair_id) or {} if fresh else {}
    statistics={k:statistical.get(k) for k in ('status','reason','z_log','regime','sigma_daily_pct','health',
        'age_days','age_vs_half_life','horizon_days','risk_usd_per_sigma_day','risk_usd_per_sigma_h')}
    statistics['as_of_ms']=stamp if fresh else None
    if not fresh or not statistical:
        statistics.update(status='unavailable',reason='Sin analítica reciente del par; no hay evidencia suficiente para afirmar reversión a la media.')
    daily=number(statistical.get('funding_per_day_usd'))
    funding=number(row.get('funding')) if not shared else None
    carry={'estimated_per_day_usd':daily,'estimated_7d_usd':daily*7 if daily is not None else None,
           'as_of_ms':stamp if fresh and daily is not None else None,
           'assumption':'Proyección a tasa constante actual, no funding realizado ni garantía de tasa futura.',
           'reason':statistical.get('funding_reason') if fresh else 'Sin tasas verificadas recientes'}
    return {'as_of_ms':snapshot['as_of_ms'],'source':'Pair Desk · análisis del par calculado','position_state':'open',
        'pair':{'id':pair_id,'long':long_coin,'short':short_coin,'ratio_orientation':'long / short'},
        'observations':{'ratio':number(row.get('ratio')),'entry_ratio':number(row.get('entry_ratio')),
            'ratio_change_since_entry_pct':number(row.get('ratio_change')),'unrealized_pnl_usd':number(row.get('pnl')),
            'long_notional_usd':long_usd,'short_notional_usd':short_usd,'historical_funding_net_usd':funding,
            'fees_usd':number(row.get('fees')),'minimum_leg_liquidation_distance_pct':number(row.get('liq'))},
        'hedge':{'net_directional_usd':net,'gross_notional_usd':gross,
            'net_pct_of_gross':net/gross*100 if gross else None,
            'bias':None if net is None else 'net_short' if net<0 else 'net_long' if net>0 else 'dollar_neutral',
            'limitation':'Nominal neto bajo un movimiento común de ambas patas. No estima beta, correlación ni neutralidad de riesgo.'},
        'attribution':{'exclusive':not shared,'shared_assets':shared,
            'meaning':'Hay posiciones compartidas: estos nominales no son una asignación exclusiva al par. No sumar pares ni ajustar una pata sin revisar los demás.' if shared else 'No hay activos compartidos con otros pares abiertos en este snapshot.'},
        'statistics':statistics,'carry':carry,
        'liquidity':{'status':'unavailable','reason':'No hay profundidad de libro ni spread en esta lectura. Margen usado no mide liquidez.'},
        'account_context':{'margin_used_pct':number(snapshot.get('account',{}).get('margin_pct')),
            'scope':'Margen de la cuenta completa, no liquidez ni leverage calculado del par.'},
        'stress_tests':stress,
        'stress_assumptions':'Sensibilidades hipotéticas a cantidades constantes, antes de funding, fees y deslizamiento. Cambios adicionales de PNL, no PNL total ni pronóstico. No modelan liquidación.',
        'alternatives':{'keep_current_hedge':'Conserva simultáneamente la tesis relativa y el sesgo direccional medido.',
            'reduce_larger_leg_to_equal_notionals':reference,
            'reduce_both_legs':'Reducir ambas proporcionalmente baja la sensibilidad total, conservando la proporción y el sesgo porcentual.'},
        'analysis_requirements':['Usá el escenario both_up_5pct: muestra PNL adicional con ratio sin cambio. No te limites a que si el short sube pierde.',
            'No tener activos compartidos no dice nada sobre correlación. Una tesis vigente no garantiza que la pérdida sea temporal.',
            'Elegí el factor decisivo con evidencia: tesis relativa/estadística, construcción del hedge o costo de espera.',
            'Compará alternativas y sus condiciones; no aconsejes una salida solo porque el PNL es negativo.',
            'No confundas variación del ratio en % con funding en $. No deduzcas liquidez, correlación o reversión del margen usado.',
            'Una pérdida respecto de la entrada no prueba ruptura ni oportunidad. Sin tesis original, estadísticas o catalizadores, identificá la incógnita que cambia la decisión.']}
