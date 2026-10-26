"""Local-only opt-in order bridge. Never transports private keys to frontend."""
from __future__ import annotations
import os
import secrets
import threading
import time
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from pairs_desk.agent_vault import load_agent
from pairs_desk.trading import preview_pair, project_pair_action, execute_pair, verify_agent
from pairs_desk.trade_journal import connect, begin, finish, pending, auto_reconcile_no_effect
from pairs_desk.metrics import position_map

router=APIRouter(prefix='/api/trade')
_TOK=secrets.token_urlsafe(36)
_TICKETS={}
_LOCK=threading.RLock()
_MAX_TICKET_AGE=40
_ARMED=False


def _request_ok(request: Request, csrf: str):
    origin=request.headers.get('origin')
    host=request.headers.get('host','')
    if host not in ('127.0.0.1:8510','localhost:8510') or origin not in ('http://127.0.0.1:8510','http://localhost:8510'):
        raise HTTPException(403,'Origen local no autorizado')
    if not secrets.compare_digest(str(csrf),_TOK):
        raise HTTPException(403,'Sesión no autorizada')


def _account_and_positions():
    from read_only_server import load_settings, SETTINGS, ADDRESS, hl
    cfg,err=load_settings(SETTINGS)
    if err: raise HTTPException(409,'Configuración inválida')
    address=cfg.get('address','').strip()
    if not ADDRESS.fullmatch(address):raise HTTPException(409,'Cuenta no configurada')
    return cfg,address,hl


def _current_pair(cfg,address,hl,pair_id):
    from concurrent.futures import ThreadPoolExecutor
    pair=next((p for p in cfg.get('pairs',[]) if p.get('long')+'|'+p.get('short')==pair_id),None)
    if pair is None:raise HTTPException(404,'Par no guardado')
    with ThreadPoolExecutor(max_workers=2) as pool:
        f1=pool.submit(hl,{'type':'clearinghouseState','user':address})
        f2=pool.submit(hl,{'type':'clearinghouseState','user':address,'dex':'xyz'})
        core=position_map(f1.result())
        xyz={k if ':' in k else f'xyz:{k}': v for k,v in position_map(f2.result()).items()}
        positions={**core,**xyz}
    lp=positions.get(pair['long']);sp=positions.get(pair['short'])
    if lp is None or sp is None:raise HTTPException(409,'Pata cerrada o no disponible')
    ls=float(lp.get('szi') or 0);ss=float(sp.get('szi') or 0)
    if ls<=0 or ss>=0:raise HTTPException(409,'Dirección de pata no válida')
    def mark(p):
        n=abs(float(p.get('szi') or 0));return abs(float(p.get('positionValue') or 0))/n if n else 0
    return {'long':pair['long'],'short':pair['short'],'long_position':lp,'short_position':sp,'long_mark':mark(lp),'short_mark':mark(sp)}


def _all_positions(address, hl):
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=2) as pool:
        core_future = pool.submit(hl, {'type': 'clearinghouseState', 'user': address})
        xyz_future = pool.submit(hl, {'type': 'clearinghouseState', 'user': address, 'dex': 'xyz'})
        core = position_map(core_future.result())
        xyz = {k if ':' in k else f'xyz:{k}': v for k, v in position_map(xyz_future.result()).items()}
    return {**core, **xyz}

# Pair assignment: local-only management action; never signs or sends an order.
class AddPairInput(BaseModel):
    csrf: str
    long: str = Field(min_length=1, max_length=100)
    short: str = Field(min_length=1, max_length=100)


def _available_pair_legs(cfg, address, hl):
    from concurrent.futures import ThreadPoolExecutor
    from pairs_desk.lifecycle import pair_is_live
    with ThreadPoolExecutor(max_workers=2) as pool:
        f_core = pool.submit(hl, {'type': 'clearinghouseState', 'user': address})
        f_xyz = pool.submit(hl, {'type': 'clearinghouseState', 'user': address, 'dex': 'xyz'})
        core = position_map(f_core.result())
        xyz = {k if ':' in k else f'xyz:{k}': v for k, v in position_map(f_xyz.result()).items()}
    positions = {**core, **xyz}
    used = set()
    for pair in cfg.get('pairs', []):
        if pair_is_live(pair, positions):
            used.update((pair['long'], pair['short']))
    longs = sorted((sym for sym, pos in positions.items()
                    if float(pos.get('szi') or 0) > 0 and sym not in used), key=str.casefold)
    shorts = sorted((sym for sym, pos in positions.items()
                     if float(pos.get('szi') or 0) < 0 and sym not in used), key=str.casefold)
    return longs, shorts, positions


@router.get('/pair-candidates')
def pair_candidates(request: Request):
    # GET only returns public position symbols; no signing key is involved.
    cfg, address, hl = _account_and_positions()
    longs, shorts, _ = _available_pair_legs(cfg, address, hl)
    return {'longs': longs, 'shorts': shorts}


@router.post('/pairs/add')
def add_pair(request: Request, data: AddPairInput):
    _request_ok(request, data.csrf)
    from read_only_server import SETTINGS
    from pairs_desk.storage import load_settings, save_settings
    from pairs_desk.lifecycle import pair_leg_conflict
    from re import compile as compile_re
    asset_pattern = compile_re(r'^(?:[A-Za-z0-9._-]+:)?[A-Za-z0-9._-]+$')
    # Validate against fresh exchange state, never trust candidates from browser.
    if data.long == data.short or not asset_pattern.fullmatch(data.long) or not asset_pattern.fullmatch(data.short):
        raise HTTPException(422, 'Seleccioná dos activos válidos y distintos')
    with _LOCK:
        cfg, error = load_settings(SETTINGS)
        if error:
            raise HTTPException(409, 'Configuración inválida; guardado bloqueado')
        address = cfg.get('address', '').strip()
        from read_only_server import ADDRESS, hl
        if not ADDRESS.fullmatch(address):
            raise HTTPException(409, 'Cuenta pública no configurada')
        try:
            longs, shorts, positions = _available_pair_legs(cfg, address, hl)
        except Exception:
            raise HTTPException(503, 'No se pudieron verificar ambas posiciones en Hyperliquid')
        if data.long not in longs or data.short not in shorts:
            raise HTTPException(409, 'Las patas deben estar abiertas, sin asignar y en la dirección indicada')
        if any(p['long'] == data.long and p['short'] == data.short for p in cfg['pairs']):
            raise HTTPException(409, 'Ese par ya está guardado')
        if pair_leg_conflict(data.long, data.short, cfg['pairs'], positions):
            raise HTTPException(409, 'Una pata ya pertenece a otro par activo')
        cfg['pairs'].insert(0, {'long': data.long, 'short': data.short})
        try:
            save_settings(SETTINGS, cfg, False)
        except (OSError, RuntimeError) as exc:
            raise HTTPException(500, f'No se pudo guardar el par: {type(exc).__name__}')
        return {'ok': True, 'id': f'{data.long}|{data.short}'}


class PreviewInput(BaseModel):
    csrf: str
    pair_id: str=Field(min_length=3,max_length=128)
    operation: str
    fraction_pct: int=Field(ge=1,le=100)
    slippage_pct: float=Field(ge=0.1,le=2.0)

class ExecuteInput(BaseModel):
    csrf: str
    ticket_id: str
    confirmation: str

@router.get('/status')
def status(request: Request):
    cfg,address,hl=_account_and_positions()
    try:
        from eth_account import Account
        secret=load_agent(address)
        agent=Account.from_key(secret).address if secret else None
    except Exception:
        agent=None
    try:
        conn=connect()
        try:
            auto_reconcile_no_effect(conn,address,_all_positions(address,hl))
        except Exception:
            pass
        blocked=pending(conn,address)
        conn.close()
    except Exception:
        blocked=[('?', '?','journal_error',0)]
    return {'csrf':_TOK,'agent_configured':bool(agent),'agent':agent,'armed':_ARMED,'trading_blocked':bool(blocked),'pending':[{'id':t[0], 'pair':t[1], 'status':t[2]} for t in blocked]}

class ArmInput(BaseModel):
    csrf: str
    enabled: bool

@router.post('/arm')
def arm(request: Request,data: ArmInput):
    global _ARMED
    _request_ok(request,data.csrf)
    with _LOCK:
        _ARMED=False
        _TICKETS.clear()
        if data.enabled:
            cfg,address,hl=_account_and_positions()
            try:
                key=load_agent(address)
                if not key:raise ValueError('Agent no disponible')
                from eth_account import Account
                verify_agent(address,Account.from_key(key).address)
            except Exception as exc:
                raise HTTPException(409,f'No se pudo habilitar: {type(exc).__name__}: {str(exc)[:150]}')
            conn=connect()
            try:
                if pending(conn,address):raise HTTPException(409,'Tenés operaciones pendientes de conciliar')
            finally:conn.close()
            _ARMED=True
    return {'armed':_ARMED}

@router.post('/preview')
def preview(request: Request,data: PreviewInput):
    _request_ok(request,data.csrf)
    if data.operation not in ('Aumentar','Reducir','Cerrar'):raise HTTPException(400,'Operación no soportada')
    if data.operation=='Cerrar' and data.fraction_pct!=100:raise HTTPException(400,'Cerrar requiere 100%')
    cfg,address,hl=_account_and_positions()
    with _LOCK:
        if not _ARMED:
            raise HTTPException(409, 'Habilitá explícitamente las órdenes reales')
        conn=connect()
        try:
            if pending(conn,address):raise HTTPException(409,'Hay operaciones pendientes de conciliar')
        finally:conn.close()
        x=_current_pair(cfg,address,hl,data.pair_id)
        try:
            orders=preview_pair(x,data.operation,data.fraction_pct/100)
            projection=project_pair_action(x,data.operation,data.fraction_pct/100,data.slippage_pct/100)
        except ValueError as exc:raise HTTPException(400,str(exc))
        ticket_id=secrets.token_urlsafe(32)
        _TICKETS.clear()
        _TICKETS[ticket_id]={'account':address,'pair':data.pair_id,'operation':data.operation,'orders':orders,'slippage':data.slippage_pct/100,'created':time.monotonic()}
    clean=[{'coin':o['coin'],'order':'Comprar' if o['is_buy'] else 'Vender','reduce_only':o['reduce_only'],'size':o['size'],'usd':round(o['notional'],2)} for o in orders]
    return {'ticket_id':ticket_id,'expires_in_s':_MAX_TICKET_AGE,'orders':clean,'total_usd':round(sum(o['notional'] for o in orders),2),'projection':projection,'warning':'Las dos patas no son atómicas. Confirmar en Hyperliquid ante una respuesta incierta.'}

@router.post('/execute')
def execute(request: Request,data: ExecuteInput):
    _request_ok(request,data.csrf)
    if data.confirmation != 'CONFIRMAR':raise HTTPException(400,'Confirmación explícita requerida')
    with _LOCK:
        if not _ARMED:
            raise HTTPException(409, 'Trading deshabilitado')
        ticket=_TICKETS.pop(data.ticket_id,None)
        if not ticket:raise HTTPException(409,'Ticket inexistente o ya utilizado')
        if time.monotonic()-ticket['created']>_MAX_TICKET_AGE:
            raise HTTPException(409,'Ticket vencido. Volvé a previsualizar.')
        cfg,address,hl=_account_and_positions()
        if ticket['account'].lower()!=address.lower():raise HTTPException(409,'La cuenta cambió')
        try:secret=load_agent(address)
        except Exception:secret=None
        if not secret:raise HTTPException(409,'Agent no guardado en el llavero. Configuralo primero desde la versión estable.')
        from eth_account import Account
        try:verify_agent(address,Account.from_key(secret).address)
        except Exception as exc:raise HTTPException(409,f'Agent no autorizado: {type(exc).__name__}: {exc}')
        # The SDK independently checks leg sizes against fresh live state before sending.
        conn=connect();attempt=None
        try:
            if pending(conn,address):raise HTTPException(409,'Existe una ejecución pendiente de conciliar')
            attempt=begin(conn,address,ticket['pair'],ticket['operation'],ticket['orders'])
            try:
                result=execute_pair(ticket['orders'],address,secret,ticket['slippage'],journal=conn,attempt_id=attempt)
                complete=len(result)==2 and all(x['ok'] for x in result)
                finish(conn,attempt,'complete' if complete else 'partial')
            except Exception:
                finish(conn,attempt,'uncertain')
                raise
            clean=[{k:v for k,v in r.items() if k in ('coin','ok','size','filled_size','avg_px','oid','message')} for r in result]
            return {'complete':complete,'results':clean,'attempt_id':attempt,'requires_manual_review':not complete}
        except HTTPException:raise
        except Exception as exc:
            raise HTTPException(409,f'Resultado incierto o ejecución fallida. Verificá directamente Hyperliquid antes de reintentar. {type(exc).__name__}: {str(exc)[:160]}')
        finally:conn.close()
