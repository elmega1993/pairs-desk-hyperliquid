"""Opt-in local desktop watcher. Public data only; no trading imports."""
from __future__ import annotations
import json
import os
from pathlib import Path
import shutil
import subprocess
import threading
import time

ROOT=Path.home()/'.local/share/crypto-pairs-desk'


class Watcher:
    def __init__(self, poll, root=None, notify=None):
        self.root=Path(root or ROOT); self.poll=poll
        self.notify=notify or self.desktop
        self.lock=threading.RLock(); self.stop_event=threading.Event(); self.thread=None
        self.enabled=False; self.events=[]; self.conditions={}; self.last_ok=None; self.last_error=None; self.failures=0
        try:
            saved=json.loads((self.root/'alerts.json').read_text())
            self.enabled=saved.get('enabled') is True
            self.events=saved.get('events',[])[-200:]
            self.conditions=saved.get('conditions',{})
        except (OSError,ValueError):pass

    def persist(self):
        self.root.mkdir(parents=True,exist_ok=True)
        temp=self.root/'alerts.json.tmp'
        temp.write_text(json.dumps({'enabled':self.enabled,'events':self.events[-200:],'conditions':self.conditions},ensure_ascii=False))
        temp.chmod(0o600);os.replace(temp,self.root/'alerts.json')

    def configure(self, enabled):
        with self.lock:
            before=self.enabled;self.enabled=bool(enabled)
            try:self.persist()
            except OSError:self.enabled=before;raise
            if not self.enabled:self.conditions.clear()
        if enabled:self.start()

    def start(self):
        with self.lock:
            if self.thread and self.thread.is_alive():return
            self.stop_event.clear()
            self.thread=threading.Thread(target=self.run,name='pairs-desk-alerts',daemon=True);self.thread.start()

    def run(self):
        while not self.stop_event.is_set():
            if self.enabled:self.tick()
            self.stop_event.wait(60)

    @staticmethod
    def desktop(title, body):
        executable=shutil.which('notify-send')
        if not executable:return False
        try:
            return subprocess.run([executable,'--app-name=Pairs Desk','--',title,body],timeout=3,
                                  stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode==0
        except (OSError,subprocess.TimeoutExpired):return False

    def condition(self, account, key, active, recovered, message, now):
        ident=account+'|'+key
        previous=self.conditions.get(ident,{'active':False,'last':0})
        if recovered:previous['active']=False
        if active and (not previous['active'] or now-previous['last']>=900):
            if now-previous['last']>=900 or previous['last']==0:
                delivered=self.notify('Pairs Desk',message)
                self.events.append(dict(time=int(now*1000),account=account,key=key,message=message,desktop=bool(delivered)))
                self.events=self.events[-200:];previous['last']=now
            previous['active']=True
        self.conditions[ident]=previous

    def tick(self, now=None):
        now=time.time() if now is None else now
        try:
            account, observations=self.poll()
            with self.lock:
                if not self.enabled:return
                self.last_ok=int(now*1000);self.last_error=None;self.failures=0
                self.condition('', 'data',False,True,'',now)
                for key,active,recovered,message in observations:
                    self.condition(account,key,active,recovered,message,now)
                self.persist()
        except Exception as exc:
            with self.lock:
                if not self.enabled:return
                self.failures+=1;self.last_error=type(exc).__name__
                if self.failures>=2:
                    self.condition('', 'data',True,False,'Datos sin verificar: fallaron dos lecturas consecutivas. Revisá la conexión.',now)
                try:self.persist()
                except OSError:pass

    def status(self):
        with self.lock:
            return dict(enabled=self.enabled,last_ok=self.last_ok,error=self.last_error,
                        desktop_available=shutil.which('notify-send') is not None,
                        events=list(reversed(self.events[-40:])))


def observations(cfg, positions, signals):
    result=[]
    for pair in cfg.get('pairs',[]):
        key=pair['long']+'|'+pair['short'];label=pair['long']+'/'+pair['short']
        lp,sp=positions.get(pair['long']),positions.get(pair['short'])
        missing=not lp or not sp
        result.append((key+':leg',missing,not missing,label+': una o ambas patas no están abiertas. Verificá el cierre.'))
        if missing:continue
        if float(lp.get('szi',0))<=0 or float(sp.get('szi',0))>=0:
            result.append((key+':direction',True,False,label+': dirección de patas inesperada.'));continue
        result.append((key+':direction',False,True,''))
        lu,su=abs(float(lp['positionValue'])),abs(float(sp['positionValue']))
        imbalance=abs(lu-su)/(lu+su)*100 if lu+su else 0
        result.append((key+':neutral',imbalance>=5,imbalance<=4,f'{label}: desbalance {imbalance:.1f}% del nocional total.'))
        from .metrics import liquidation_distance
        distances=[liquidation_distance(p,abs(float(p['positionValue'])/float(p['szi']))) for p in (lp,sp)]
        known=[v for v in distances if v is not None]
        if known:
            distance=min(known)
            result.append((key+':liq',distance<=10,distance>=12,f'{label}: distancia estimada a liquidación {distance:.1f}%.'))
        sig=signals.get(key)
        if sig:
            result.append((key+':signal_data',False,True,''))
            for kind in ('tp','add'):
                result.append((key+':'+kind,bool(sig.get(kind+'_level')),not sig.get(kind+'_level'),label+': '+str(sig.get(kind))+' · '+str(sig.get(kind+'_detail'))))
            z=sig.get('z')
            if z is not None:result.append((key+':z',abs(z)>=2,abs(z)<=1.7,f'{label}: Z diario {z:.2f}. Revisá la salud estadística antes de actuar.'))
        else:
            result.append((key+':signal_data',True,False,label+': señales sin datos verificables.'))
    return result
