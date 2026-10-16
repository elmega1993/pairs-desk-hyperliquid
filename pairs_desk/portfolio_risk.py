"""Read-only exposure concentration with explicit unavailable metrics."""
from collections import defaultdict

def concentration(pairs):
    legs=defaultdict(lambda:{'long_usd':0.,'short_usd':0.,'pairs':[]})
    gross=0.
    for p in pairs:
        for side in ('long','short'):
            coin=p.get(side);amount=p.get(side+'_usd')
            if not coin or amount is None:continue
            amount=abs(float(amount));gross+=amount
            legs[coin][side+'_usd']+=amount
            legs[coin]['pairs'].append(p.get('id'))
    return {'status':'ok' if gross else 'unavailable','gross_usd':gross,
            'assets':{k:{**v,'pct_gross':100*(v['long_usd']+v['short_usd'])/gross if gross else None,
                           'shared_across_pairs':len(set(v['pairs']))>1} for k,v in legs.items()},
            'correlation':None,'beta_adjusted_delta':None,'reason':'Correlación y beta pendientes de series sincronizadas verificadas'}
