"""Offline, read-only walk-forward level diagnostics. CSV requires close column."""
import argparse,csv,math,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from pairs_desk.analytics import ewma_vol,equilibrium
from pairs_desk.levels_v3 import calculate

def walk_forward(prices, step=7, lookback=120, forward=30):
    rows=[]
    for t in range(lookback,len(prices)-forward,step):
        history=prices[:t]  # never use any future value in model fitting
        x=[math.log(p) for p in history]
        mu,_=equilibrium(x);vol=ewma_vol(x)
        if mu is None or vol is None:continue
        levels=calculate(history[-1],mu,vol,14,'stationary','Rango',z=0)['levels']
        future=prices[t:t+forward]
        row={'t':t,'entry':history[-1]}
        for key,barrier in levels.items():
            row[key+'_hit']=int(any(v>=barrier for v in future)) if key.startswith('tp') else int(any(v<=barrier for v in future))
        rows.append(row)
    return rows

def main():
    parser=argparse.ArgumentParser();parser.add_argument('input_csv');parser.add_argument('output_csv');args=parser.parse_args()
    with open(args.input_csv,newline='') as f:prices=[float(r['close']) for r in csv.DictReader(f)]
    if any(not math.isfinite(p) or p<=0 for p in prices):raise ValueError('Invalid closes')
    rows=walk_forward(prices)
    if not rows:raise ValueError('Insufficient historical closes')
    with open(args.output_csv,'w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    print('Ventanas evaluadas:',len(rows),'· No calibrado')
if __name__=='__main__':main()
