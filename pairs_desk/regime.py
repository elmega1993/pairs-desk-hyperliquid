"""Shared descriptive regime classification."""
import numpy as np

def classify_regime(logp):
    x=np.asarray(logp,dtype=float)
    if len(x)<60 or not np.isfinite(x).all():return 'N/D'
    window=min(90,len(x)//2); t=np.arange(window,dtype=float)
    slope,intercept=np.polyfit(t,x[-window:],1)
    residual=float(np.std(x[-window:]-(intercept+slope*t),ddof=1))
    strength=abs(slope*window)/max(residual,1e-9)
    shift=abs(float(np.median(x[-window:])-np.median(x[-2*window:-window])))/max(residual,1e-9)
    return 'Inestable' if strength>12 and shift>8 else ('Tendencia' if strength>1.6 else 'Rango')
