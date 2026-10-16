"""Pure closed-pair summaries; do not infer missing ledger entries."""
from __future__ import annotations
import math

def review_closed(rows):
    reviewed=[]
    for row in rows:
        opened=row.get('opened_at');closed=row.get('closed_at')
        duration=(closed-opened)/86400000 if isinstance(opened,(int,float)) and isinstance(closed,(int,float)) and closed>=opened else None
        net=row.get('total_pnl')
        reviewed.append({'id':row.get('id') or str(row.get('long',''))+'|'+str(row.get('short','')),
                         'duration_days':duration,'net_pnl':net,'mae_pct':None,'mfe_pct':None,
                         'add_effect_usd':None,'tp_effect_usd':None,
                         'reason':'Requiere velas históricas y eventos completos para estimar efectos ADD/TP'})
    verified=[r['net_pnl'] for r in reviewed if isinstance(r['net_pnl'],(int,float)) and math.isfinite(r['net_pnl'])]
    enough=len(verified)>=10
    return {'status':'partial','pairs':reviewed,'summary':{'n_pairs':len(reviewed),'n_verified':len(verified),
            'win_rate':sum(v>0 for v in verified)/len(verified) if enough else None,
            'expectancy_usd':sum(verified)/len(verified) if enough else None,
            'reason':'' if enough else 'Muestra insuficiente (mínimo 10 cierres verificados)'}}
