from __future__ import annotations

import logging
import os
import re
from datetime import datetime
from html import escape
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from pairs_desk.charts import load_ratio_frame, ratio_chart
from pairs_desk.ledger import Ledger, closed_accounting, active_funding
from pairs_desk.hl_client import query, query_cached, query_with_meta, user_fills_history, user_funding_history
from pairs_desk.adaptive_levels import calculate as calculate_adaptive_levels, adaptive_signals
from pairs_desk.lifecycle import archive_closed_pairs, pair_is_live, pair_leg_conflict, reset_management_on_reopen
from pairs_desk.metrics import DEFAULT_MANAGEMENT_RULES, archived_pair_entry_ratio, closed_pair_trade_events, enrich_pair, funding_ledger_cashflow, management_signals, mark_from_position, pair_trade_events, pnl_base, position_map, pct, since_open
from pairs_desk.storage import load_settings, save_settings
from pairs_desk.exporting import build_export_rows
from pairs_desk.trading import preview_pair, execute_pair
from pairs_desk.trade_journal import connect as open_trade_journal, pending as pending_trades, begin as begin_trade, finish as finish_trade, reconcile as reconcile_trade
from pairs_desk.agent_vault import load_agent, save_agent, delete_agent

TZ = ZoneInfo('America/Argentina/Buenos_Aires')
CONFIG = Path.home() / '.config' / 'crypto-pairs-desk' / 'settings.json'
ADDRESS = re.compile(r'^0x[a-fA-F0-9]{40}$')
ASSET = re.compile(r'^(?:[A-Za-z0-9._-]+:)?[A-Za-z0-9._-]+$')
ALIASES = {'xyz:CL': 'xyz · CL (WTI)'}
LOG = logging.getLogger('pairs_desk')
if not LOG.handlers:
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s: %(message)s')

st.set_page_config(page_title='Pairs Desk', page_icon='◈', layout='wide', initial_sidebar_state='expanded')
st.markdown('''<style>
:root{--bg:#0e110e;--sf:#121712;--sf2:#1a221a;--bd:#293129;--tx:#e3e7df;--mu:#a0ad9d;--pos:#44d7a8;--neg:#fa7885;--ac:#d8ad63;--lg:#6ea8fe;--sh:#f0a35e}
.stApp{background:var(--bg);color:var(--tx)}
[data-testid="stSidebar"]{background:var(--sf);border-right:1px solid var(--bd)}
.block-container{max-width:1320px;padding-top:1.25rem;padding-bottom:2rem}
h1{font-size:1.55rem!important;letter-spacing:-.03em;margin:0!important} h2,h3{letter-spacing:-.02em}
[data-testid="stMainBlockContainer"] [data-testid="stVerticalBlock"]{gap:.45rem}
.kpi{border-top:1px solid var(--bd);padding:8px 0 4px;min-height:68px}.kpi-label{color:var(--mu);font-size:.78rem}.kpi-value{font-family:ui-monospace,Menlo,Consolas,monospace;font-variant-numeric:tabular-nums;font-size:1.5rem;font-weight:600;line-height:1.2}.kpi-sub{color:var(--mu);font-size:.75rem;margin-top:3px}
.pos{color:var(--pos)!important}.neg{color:var(--neg)!important}.ac{color:var(--ac)!important}.mu{color:var(--mu)!important}
.alerts{border:1px solid var(--bd);border-radius:7px;background:var(--sf);padding:8px 11px;font-size:.83rem;margin:4px 0 8px}.alerts.warn{border-color:var(--ac)}.alerts.ok{border-color:#315b4d}
.leg{display:inline-block;border:1px solid currentColor;border-radius:4px;padding:1px 6px;font-size:.74rem;margin-right:5px;font-weight:600}.leg-l{color:var(--lg)}.leg-s{color:var(--sh)}
.pair-head{border-top:1px solid var(--bd);padding:8px 0}.signal-grid{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin:6px 0 10px}.signal-card{border:1px solid var(--bd);border-radius:7px;background:var(--sf);padding:9px 11px}.signal-label{font-size:.72rem;color:var(--mu);text-transform:uppercase;letter-spacing:.06em}.signal-value{font-weight:700;font-size:.98rem;margin:2px 0}.signal-sub{font-size:.75rem;color:var(--mu);line-height:1.3}.mono{font-family:ui-monospace,Menlo,Consolas,monospace;font-variant-numeric:tabular-nums}
.pnl-chart-head{display:flex;align-items:baseline;gap:10px;margin-top:4px}.pnl-chart-title{font-size:.92rem;font-weight:650}.pnl-chart-value{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:1.05rem;font-weight:700}.pnl-chart-sub{font-size:.73rem;color:var(--mu)}
[data-testid="stMetric"]{background:transparent;border:0;border-top:1px solid var(--bd);border-radius:0;padding:.65rem 0}
[data-testid="stVerticalBlockBorderWrapper"]>div{background:var(--sf)!important;border-color:var(--bd)!important;border-radius:8px!important}
[data-testid="stExpander"]{background:var(--sf);border-color:var(--bd)!important}
.stButton button{border-radius:6px}.stButton button[kind="primary"]{background:var(--sf2);border:1px solid var(--bd);color:var(--tx)}
@media(max-width:640px){.block-container{padding-left:.75rem;padding-right:.75rem}.kpi-value{font-size:1.25rem}}
</style>''', unsafe_allow_html=True)


def display(symbol: str) -> str:
    if symbol in ALIASES:
        return ALIASES[symbol]
    if symbol.startswith('xyz:'):
        return 'xyz · ' + symbol.split(':', 1)[1]
    return symbol


def money(value: float | None) -> str:
    return 'No disponible' if value is None else f'${value:,.2f}'


def percent(value: float | None) -> str:
    return 'N/D' if value is None else f'{value:+,.2f}%'


def tone(value: float | None) -> str:
    return 'pos' if value is not None and value > 0 else 'neg' if value is not None and value < 0 else ''


def style_signed(value):
    if value is None or pd.isna(value):
        return ''
    try:
        number = float(value)
    except (TypeError, ValueError):
        return ''
    if number > 0:
        return 'color:#44d7a8;font-weight:600'
    if number < 0:
        return 'color:#fa7885;font-weight:600'
    return 'color:#e3e7df'


def style_liq(value):
    if value is None or pd.isna(value):
        return ''
    try:
        number = float(value)
    except (TypeError, ValueError):
        return ''
    if number < 15:
        return 'color:#fa7885;font-weight:600'
    if number < 30:
        return 'color:#d8ad63;font-weight:600'
    return 'color:#e3e7df'


def styled_pairs_table(frame: pd.DataFrame):
    display_frame = frame.drop(columns=['_id']).copy()
    styler = display_frame.style.format({
        'Tamaño USD': '$ {:,.0f}',
        'PnL abierto': '$ {:.2f}',
        'Realizado': '$ {:.2f}',
        'PnL total': '$ {:.2f}',
        'PnL abierto %': '{:+.2f} %',
        'Δ ratio %': '{:+.2f} %',
        'Z 1D': '{:+.2f}',
        'Neutralidad %': '{:+.2f} %',
        'Dist. liq. %': '{:.1f} %',
        'Funding': '$ {:.2f}',
        'Días': '{:.0f}',
    }, na_rep='N/D')
    signed_cols = ['PnL abierto', 'Realizado', 'PnL total', 'PnL abierto %', 'Δ ratio %', 'Neutralidad %', 'Funding']
    for col in signed_cols:
        styler = styler.map(style_signed, subset=[col])
    styler = styler.map(style_liq, subset=['Dist. liq. %'])
    styler = styler.set_properties(subset=['Par'], **{'font-weight': '600'})
    return styler


def style_usd_column(df: pd.DataFrame, column='USD'):
    styler = df.style.format({column: '$ {:.2f}'}, na_rep='N/D').map(style_signed, subset=[column])
    return styler


def style_risk_table(df: pd.DataFrame):
    styler = df.style.format({'Nocional': '$ {:.2f}', 'Dist. liq. %': '{:.1f} %'}, na_rep='N/D')
    styler = styler.map(style_liq, subset=['Dist. liq. %'])
    return styler


def kpi(label: str, value: str, sub: str = '', color: str = ''):
    st.markdown(f'<div class="kpi"><div class="kpi-label">{escape(label)}</div><div class="kpi-value {color}">{escape(value)}</div><div class="kpi-sub">{escape(sub)}</div></div>', unsafe_allow_html=True)


def entry_date(ts: int | None) -> str:
    return 'Sin fecha verificable' if not ts else datetime.fromtimestamp(ts / 1000, TZ).strftime('%d/%m/%Y %H:%M')


def leverage_text(p: dict) -> str:
    lev = p.get('leverage') or {}
    typ = lev.get('type', 'N/D')
    val = lev.get('value')
    return f'{typ} · {val}x' if val is not None else str(typ)


def account_metrics(core_state: dict, xyz_state: dict):
    def summary(state: dict):
        ms = state.get('marginSummary') or {}
        eq = float(ms['accountValue']) if ms.get('accountValue') is not None else None
        margin = float(ms['totalMarginUsed']) if ms.get('totalMarginUsed') is not None else None
        return eq, margin

    core_eq, core_margin = summary(core_state)
    xyz_eq, xyz_margin = summary(xyz_state)
    # No adivinamos si la cuenta usa equity unificada o separada. Si ambas fuentes
    # reportan valor, la UI las muestra por separado en vez de sumar/maximizar.
    equity = core_eq if xyz_eq is None else xyz_eq if core_eq is None else None
    margin = core_margin if xyz_margin is None else xyz_margin if core_margin is None else None
    return equity, margin, core_eq, core_margin, xyz_eq, xyz_margin


def portfolio_windows(portfolio) -> dict[str, dict]:
    """Normalize Hyperliquid's [[window, payload], ...] portfolio response."""
    if not isinstance(portfolio, list):
        return {}
    out = {}
    for item in portfolio:
        if not isinstance(item, (list, tuple)) or len(item) != 2:
            continue
        key, payload = item
        if isinstance(key, str) and isinstance(payload, dict):
            out[key] = payload
    return out


def pnl_history_frame(payload: dict | None) -> pd.DataFrame:
    rows = (payload or {}).get('pnlHistory') or []
    clean = []
    for row in rows:
        try:
            if not isinstance(row, (list, tuple)) or len(row) < 2:
                continue
            clean.append((int(row[0]), float(row[1])))
        except (TypeError, ValueError):
            continue
    if not clean:
        return pd.DataFrame(columns=['time', 'pnl'])
    frame = pd.DataFrame(clean, columns=['time', 'pnl']).drop_duplicates('time').sort_values('time')
    frame['date'] = pd.to_datetime(frame['time'], unit='ms', utc=True).dt.tz_convert(TZ)
    return frame


def historical_pnl_chart(frame: pd.DataFrame, events: list[dict] | None = None):
    fig = go.Figure()
    positive = frame['pnl'].where(frame['pnl'] >= 0)
    negative = frame['pnl'].where(frame['pnl'] < 0)
    fig.add_trace(go.Scatter(
        x=frame['date'], y=positive, mode='lines', connectgaps=False,
        line={'color': '#44d7a8', 'width': 2.4},
        hovertemplate='%{x|%d/%m/%Y %H:%M}<br><b>$%{y:,.2f}</b><extra></extra>',
        name='PnL positivo',
    ))
    fig.add_trace(go.Scatter(
        x=frame['date'], y=negative, mode='lines', connectgaps=False,
        line={'color': '#fa7885', 'width': 2.4},
        hovertemplate='%{x|%d/%m/%Y %H:%M}<br><b>$%{y:,.2f}</b><extra></extra>',
        name='PnL negativo',
    ))
    if events and not frame.empty:
        times = frame['time'].to_numpy()
        pnls = frame['pnl'].to_numpy()
        marker_rows = []
        for ev in events:
            try:
                ts = int(ev.get('time') or 0)
            except (TypeError, ValueError):
                continue
            if not ts or ts < int(times[0]) or ts > int(times[-1]):
                continue
            idx = int(abs(times - ts).argmin())
            kind = str(ev.get('kind') or '')
            realized = float(ev.get('realized') or 0)
            if kind == 'add':
                color, symbol = '#d8ad63', 'circle'
            else:
                color, symbol = ('#44d7a8', 'triangle-down') if realized >= 0 else ('#fa7885', 'triangle-down')
            marker_rows.append((frame['date'].iloc[idx], float(pnls[idx]), color, symbol, str(ev.get('label') or kind.upper()), str(ev.get('detail') or '')))
        for dt, y, color, symbol, label, detail in marker_rows:
            fig.add_trace(go.Scatter(
                x=[dt], y=[y], mode='markers',
                marker={'size': 8, 'color': color, 'symbol': symbol, 'line': {'width': 1, 'color': '#121712'}},
                text=[label],
                customdata=[[detail]],
                hovertemplate='%{x|%d/%m/%Y %H:%M}<br><b>%{text}</b><br>%{customdata[0]}<br>PnL $%{y:,.2f}<extra></extra>',
                showlegend=False,
            ))
    fig.add_hline(y=0, line_width=1, line_color='#687166')
    fig.update_layout(
        height=290, margin=dict(l=8, r=8, t=8, b=8),
        paper_bgcolor='#121712', plot_bgcolor='#121712',
        showlegend=False, hovermode='closest',
        xaxis=dict(showgrid=False, zeroline=False, color='#a0ad9d', fixedrange=False),
        yaxis=dict(showgrid=True, gridcolor='#202820', zeroline=False, color='#a0ad9d', tickprefix='$', fixedrange=False),
        hoverlabel=dict(bgcolor='#0e110e', bordercolor='#293129', font_color='#e3e7df'),
    )
    return fig


def pair_tracking_start_ms(cfg: dict, positions: dict, fills: list[dict]) -> int | None:
    starts = [int(item.get('opened_at') or 0) for item in cfg.get('closed_pairs', []) if int(item.get('opened_at') or 0) > 0]
    for pair in cfg.get('pairs', []):
        leg_starts = []
        for sym in (pair.get('long'), pair.get('short')):
            if not sym or sym not in positions:
                continue
            opened, _, _, _ = since_open(fills, sym, float(positions[sym].get('szi') or 0))
            if opened:
                leg_starts.append(int(opened))
        if leg_starts:
            starts.append(max(leg_starts))
    return min(starts) if starts else None


def pair_dashboard_events(cfg: dict, positions: dict, fills: list[dict]) -> list[dict]:
    events = []
    for pair in cfg.get('pairs', []):
        long_sym, short_sym = pair.get('long'), pair.get('short')
        if long_sym in positions and short_sym in positions:
            p = {'long': long_sym, 'short': short_sym, 'long_position': positions[long_sym], 'short_position': positions[short_sym]}
            for ev in pair_trade_events(p, fills):
                ev = dict(ev); ev['pair'] = f'{display(long_sym)}/{display(short_sym)}'
                ev['label'] = f"{ev['pair']} · {ev['label']}"
                events.append(ev)
    for item in cfg.get('closed_pairs', []):
        for ev in closed_pair_trade_events(item.get('long',''), item.get('short',''), fills, int(item.get('opened_at') or 0), int(item.get('closed_at') or 0)):
            ev = dict(ev); ev['pair'] = f"{display(item.get('long',''))}/{display(item.get('short',''))}"
            ev['label'] = f"{ev['pair']} · {ev['label']}"
            events.append(ev)
    return sorted(events, key=lambda x: int(x.get('time') or 0))


def rebased_pnl_window(portfolio_map: dict[str, dict], period: str, start_ms: int | None) -> pd.DataFrame:
    all_time = pnl_history_frame(portfolio_map.get('perpAllTime'))
    if all_time.empty:
        return all_time
    if start_ms:
        base_candidates = all_time[all_time['time'] <= start_ms]
        if base_candidates.empty:
            base_value = float(all_time['pnl'].iloc[0])
        else:
            base_value = float(base_candidates['pnl'].iloc[-1])
        all_time = all_time[all_time['time'] >= start_ms].copy()
    else:
        base_value = float(all_time['pnl'].iloc[0])
    if all_time.empty:
        return all_time
    all_time['pnl'] = all_time['pnl'] - base_value
    if period == 'TODO':
        return all_time
    key = {'24H':'perpDay', '7D':'perpWeek', '30D':'perpMonth'}[period]
    fine = pnl_history_frame(portfolio_map.get(key))
    if fine.empty:
        fine = all_time.copy()
    else:
        # Align the finer window to the cumulative PnL since the first tracked pair.
        latest_total = float(all_time['pnl'].iloc[-1])
        fine = fine.copy()
        fine['pnl'] = fine['pnl'] - float(fine['pnl'].iloc[-1]) + latest_total
        if start_ms:
            fine = fine[fine['time'] >= start_ms]
    cutoff_days = {'24H':1, '7D':7, '30D':30}[period]
    if fine.empty:
        return fine
    cutoff = int(fine['time'].iloc[-1]) - cutoff_days * 86_400_000
    return fine[fine['time'] >= cutoff].copy()


def safe_state(address: str):
    warnings = []
    try:
        core_state, core_fetched_ms = query_with_meta(type='clearinghouseState', user=address)
        core = position_map(core_state)
    except Exception as exc:
        LOG.exception('Fallo clearinghouseState Core')
        snap = st.session_state.get('last_good_snapshot')
        return snap, [f'Core no respondió: {exc}'], False

    xyz_ok = True
    try:
        xyz_state, xyz_fetched_ms = query_with_meta(type='clearinghouseState', user=address, dex='xyz')
        raw_xyz = position_map(xyz_state)
        xyz = {k if ':' in k else f'xyz:{k}': v for k, v in raw_xyz.items()}
    except Exception as exc:
        LOG.exception('Fallo clearinghouseState xyz')
        xyz_state, xyz = {}, {}
        xyz_fetched_ms = core_fetched_ms
        xyz_ok = False
        warnings.append(f'Datos incompletos: xyz no respondió ({exc})')

    fills_ok = True
    fills_complete = True
    try:
        # Use the cached first-page timestamp as part of snapshot identity.
        _, fills_fetched_ms = query_with_meta(type='userFills', user=address, aggregateByTime=False)
        ledger_result = Ledger().sync(address, query)
        if ledger_result['fills'].get('error'):
            raise RuntimeError('Fallo sincronización del ledger')
        fills = ledger_result['fills_rows']
        fills_complete = ledger_result['fills'].get('complete', False)
        if not fills_complete:
            warnings.append('Historial de fills limitado a los 10.000 más recientes: PnL realizado anterior puede ser parcial.')
    except Exception as exc:
        LOG.exception('Fallo userFills')
        fills = []
        fills_fetched_ms = core_fetched_ms
        fills_complete = False
        fills_ok = False
        warnings.append(f'Historial de fills no disponible: PnL realizado y comisiones son parciales ({exc})')

    portfolio_ok = True
    try:
        portfolio, portfolio_fetched_ms = query_with_meta(type='portfolio', user=address)
        if not isinstance(portfolio, list):
            raise ValueError('portfolio devolvió un formato inesperado')
    except Exception as exc:
        LOG.exception('Fallo portfolio')
        portfolio = []
        portfolio_fetched_ms = core_fetched_ms
        portfolio_ok = False
        warnings.append(f'Histórico de PnL no disponible ({exc})')

    critical_fetches = [core_fetched_ms, fills_fetched_ms] + ([xyz_fetched_ms] if xyz_ok else [])
    fetched_ms = min(critical_fetches)
    snap = {
        'core_state': core_state, 'xyz_state': xyz_state, 'core': core, 'xyz': xyz, 'fills': fills, 'portfolio': portfolio,
        'fetched_at': datetime.fromtimestamp(fetched_ms / 1000, TZ),
        'snapshot_token': f'{core_fetched_ms}:{xyz_fetched_ms}:{fills_fetched_ms}',
        'xyz_ok': xyz_ok, 'fills_ok': fills_ok, 'fills_complete': fills_complete, 'portfolio_ok': portfolio_ok,
    }
    # Solo un snapshot con todas las fuentes principales disponibles es "bueno".
    if xyz_ok and fills_ok:
        st.session_state['last_good_snapshot'] = snap
    return snap, warnings, True


cfg, settings_error = load_settings(CONFIG)
if settings_error:
    st.session_state['settings_broken'] = True

# El llavero del sistema se consulta una vez por sesión o cuando cambia la cuenta.
account_key = cfg['address'].strip().lower()
if st.session_state.get('_agent_loaded_for') != account_key:
    st.session_state['_agent_loaded_for'] = account_key
    st.session_state['trading_armed'] = False
    try:
        st.session_state['trading_agent_key'] = load_agent(account_key) if ADDRESS.fullmatch(account_key) else ''
        st.session_state['_agent_vault_error'] = ''
    except Exception as exc:
        st.session_state['trading_agent_key'] = ''
        st.session_state['_agent_vault_error'] = type(exc).__name__


def disconnect_trading_agent():
    st.session_state['trading_armed'] = False
    st.session_state['trading_agent_key'] = ''
    # Solo desconecta esta sesión: no borra el Agent del llavero.


def forget_trading_agent():
    st.session_state['trading_armed'] = False
    try:
        delete_agent(account_key)
        st.session_state['trading_agent_key'] = ''
        st.session_state['_agent_vault_error'] = ''
    except Exception as exc:
        st.session_state['_agent_vault_error'] = f'No se pudo borrar del llavero: {type(exc).__name__}'


with st.sidebar:
    st.markdown('## ◈ Pairs Desk')
    st.caption('CORE + XYZ · órdenes habilitables con API Agent')
    if settings_error:
        st.warning(f'settings.json no se pudo leer ({settings_error}). Guardado bloqueado para no pisarlo.')
    address = st.text_input('Dirección pública de Hyperliquid', value=cfg['address'], placeholder='0x…')
    if st.button('Guardar dirección', width='stretch'):
        if ADDRESS.fullmatch(address.strip()):
            cfg['address'] = address.strip()
            try:
                save_settings(CONFIG, cfg, bool(settings_error))
                st.rerun()
            except RuntimeError as exc:
                st.error(str(exc))
        else:
            st.error('Dirección inválida: se esperan 0x y 40 caracteres hexadecimales.')
    st.divider()
    st.markdown('#### Trading · API Wallet')
    st.caption('Solo Agent autorizado en Hyperliquid. Nunca uses la clave privada de tu wallet principal.')
    agent_input = st.text_input('Clave privada del Agent', type='password', key='trading_agent_key',
                               placeholder='0x…', help='Se puede guardar en el llavero seguro de Ubuntu, no en settings.json.')
    agent_ready = False
    if agent_input:
        try:
            from eth_account import Account
            agent_addr = Account.from_key(agent_input.strip()).address
            agent_ready = True
            st.caption(f'Agent: {agent_addr[:8]}…{agent_addr[-6:]}')
        except (ValueError, TypeError):
            st.error('Clave de Agent inválida. Verificá que sea una clave privada hexadecimal válida.')
    if st.button('Guardar Agent en llavero', disabled=not agent_ready or not ADDRESS.fullmatch(account_key), width='stretch'):
        try:
            save_agent(account_key, agent_input)
            st.session_state['_agent_vault_error'] = ''
            st.success('Clave guardada en el llavero seguro de esta PC.')
        except Exception as exc:
            st.error(f'El llavero seguro no está disponible ({type(exc).__name__}). No se guardó la clave.')
    if st.session_state.get('_agent_vault_error'):
        st.warning(f'No se pudo acceder al llavero ({st.session_state["_agent_vault_error"]}). Desbloqueá el llavero de Ubuntu e intentá nuevamente.')
    trading_armed = st.toggle('Habilitar órdenes reales', key='trading_armed', disabled=not agent_ready)
    if trading_armed:
        st.warning('MAINNET: se enviarán órdenes con dinero real. Las dos patas no son atómicas.')
    st.button('Desconectar esta sesión', width='stretch', key='disconnect_agent', on_click=disconnect_trading_agent)
    st.button('Borrar Agent guardado', width='stretch', key='forget_agent', on_click=forget_trading_agent)

head, ctl = st.columns([3, 2])
with head:
    st.title('Pairs Desk')
    st.caption('Tus operaciones como pares · Hyperliquid Core y xyz')
with ctl:
    pnl_mode = st.segmented_control('% de PnL sobre', ['Bruto', 'Una pata', 'Margen'], default='Bruto') or 'Bruto'

refresh_col, _ = st.columns([1, 5])
with refresh_col:
    if st.button('↻ Actualizar', key='refresh_top', width='stretch'):
        query_cached.clear(); st.rerun()

if not ADDRESS.fullmatch(address.strip()):
    st.info('Pegá tu dirección pública en la barra lateral para empezar.')
    st.stop()

snap, data_warnings, core_ok = safe_state(address.strip())
if not snap:
    st.error('No se pudieron leer las posiciones de Hyperliquid.')
    for warning in data_warnings:
        st.error(warning)
    st.stop()
for warning in data_warnings:
    st.error(warning)

core, xyz, fills = snap['core'], snap['xyz'], snap['fills']
positions = {**core, **xyz}
fetched_at = snap['fetched_at']
age = max(0, int((datetime.now(TZ) - fetched_at).total_seconds()))
st.caption(f"● Core {'OK' if core_ok else 'ERROR'} · xyz {'OK' if snap.get('xyz_ok', True) else 'SIN DATOS'} · fills {'OK' if snap.get('fills_ok', True) else 'PARCIAL'} · PnL hist. {'OK' if snap.get('portfolio_ok', True) else 'SIN DATOS'} · {len(core)} Core · {len(xyz)} xyz · actualizado {fetched_at:%H:%M:%S} ART · dato de hace {age} s")

# Histórico oficial de Hyperliquid, rebasado desde la primera apertura rastreada por Pairs Desk.
# Las ventanas cortas usan la serie más granular de HL y se alinean contra el acumulado desde ese inicio.
portfolio_map = portfolio_windows(snap.get('portfolio'))
pairs_start_ms = pair_tracking_start_ms(cfg, positions, fills)
main_trade_events = pair_dashboard_events(cfg, positions, fills)
pnl_head, pnl_period_col = st.columns([4, 1])
with pnl_period_col:
    pnl_period = st.segmented_control('Período PnL', ['24H', '7D', '30D', 'TODO'], default='30D', label_visibility='collapsed') or '30D'
pnl_frame = rebased_pnl_window(portfolio_map, pnl_period, pairs_start_ms)
with st.container(border=True):
    if not pnl_frame.empty:
        latest_hist_pnl = float(pnl_frame['pnl'].iloc[-1])
        hist_class = tone(latest_hist_pnl)
        since_txt = datetime.fromtimestamp(pairs_start_ms / 1000, TZ).strftime('%d/%m/%Y') if pairs_start_ms else 'inicio disponible'
        st.markdown(
            f'<div class="pnl-chart-head"><span class="pnl-chart-title">PnL histórico · Pairs Desk</span>'
            f'<span class="pnl-chart-value {hist_class}">{escape(money(latest_hist_pnl))}</span>'
            f'<span class="pnl-chart-sub">{escape(pnl_period)} · base 0 desde {escape(since_txt)}</span></div>',
            unsafe_allow_html=True,
        )
        st.plotly_chart(historical_pnl_chart(pnl_frame, main_trade_events), width='stretch', config={
            'displaylogo': False, 'scrollZoom': True,
            'modeBarButtonsToRemove': ['lasso2d', 'select2d'],
        })
    else:
        st.markdown('<div class="pnl-chart-title">PnL histórico · Pairs Desk</div>', unsafe_allow_html=True)
        st.caption('Hyperliquid no devolvió historial de PnL suficiente para este período.')
    st.caption('Fuente: `portfolio → pnlHistory` de Hyperliquid. Base 0 desde la primera apertura rastreada. Eventos: ● dorado = ADD · ▼ verde = cierre con ganancia · ▼ rojo = cierre con pérdida. Pasá el mouse por un marcador para ver el detalle.')

with st.sidebar:
    st.divider(); st.markdown('### Armar un par')
    longs = sorted((k for k, v in positions.items() if float(v.get('szi') or 0) > 0), key=str.casefold)
    shorts = sorted((k for k, v in positions.items() if float(v.get('szi') or 0) < 0), key=str.casefold)
    with st.form('new_pair'):
        long_sym = st.selectbox('Long abierto', ['Elegir…'] + longs, format_func=lambda x: display(x) if x != 'Elegir…' else x)
        short_sym = st.selectbox('Short abierto', ['Elegir…'] + shorts, format_func=lambda x: display(x) if x != 'Elegir…' else x)
        add = st.form_submit_button('Agregar par', width='stretch')
    if add:
        if long_sym == 'Elegir…' or short_sym == 'Elegir…' or long_sym == short_sym:
            st.error('Elegí una posición long y una short abiertas.')
        elif not ASSET.fullmatch(long_sym) or not ASSET.fullmatch(short_sym):
            st.error('Símbolo inválido.')
        elif pair_leg_conflict(long_sym, short_sym, cfg['pairs'], positions):
            st.error('Una de estas patas ya pertenece a otro par.')
        else:
            cfg['pairs'].insert(0, {'long': long_sym, 'short': short_sym})
            try:
                save_settings(CONFIG, cfg, bool(settings_error)); st.rerun()
            except RuntimeError as exc:
                st.error(str(exc))
    if cfg['pairs']:
        st.markdown('#### Pares guardados')
        for idx, pair in enumerate(cfg['pairs']):
            c1, c2 = st.columns([4, 1])
            c1.caption(f"{display(pair['long'])} / {display(pair['short'])}" + ('' if pair_is_live(pair, positions) else ' · pendiente de cierre/archivo'))
            if c2.button('✕', key=f'remove_{idx}'):
                cfg['pairs'].pop(idx)
                try:
                    save_settings(CONFIG, cfg, bool(settings_error)); st.rerun()
                except RuntimeError as exc:
                    st.error(str(exc))

# Persist closed pair operations only after two consecutive *healthy* live reads
# confirm that both legs are absent. A degraded snapshot can never archive data.
flat_counts = st.session_state.get('flat_pair_confirmations', {})
health = {
    'core_ok': bool(core_ok),
    'xyz_ok': bool(snap.get('xyz_ok', True)),
    'fills_ok': bool(snap.get('fills_ok', True) and snap.get('fills_complete', False)),
    'snapshot_token': snap.get('snapshot_token'),
}
if not settings_error:
    cfg_candidate, history_changed, flat_counts = archive_closed_pairs(
        cfg, positions, fills, health, flat_counts, required_confirmations=2
    )
    ledger = Ledger()
    reconciled = [closed_accounting(ledger, address.strip(), item, fills, bool(snap.get('fills_complete')))
                  for item in cfg_candidate.get('closed_pairs', [])]
    if reconciled != cfg_candidate.get('closed_pairs', []):
        cfg_candidate['closed_pairs'] = reconciled
        history_changed = True
    st.session_state['flat_pair_confirmations'] = flat_counts
    if history_changed:
        cfg = cfg_candidate
        try:
            save_settings(CONFIG, cfg, bool(settings_error))
        except Exception as exc:
            st.warning(f'No se pudo guardar el historial de pares cerrados: {exc}')
closed_history = cfg.setdefault('closed_pairs', [])

active = []
unavailable_pairs = []
assigned = set()
for pair_cfg in cfg['pairs']:
    long_sym, short_sym = pair_cfg['long'], pair_cfg['short']
    if not snap.get('xyz_ok', True) and (long_sym.startswith('xyz:') or short_sym.startswith('xyz:')):
        unavailable_pairs.append(pair_cfg)
        continue
    if long_sym not in positions or short_sym not in positions or long_sym in assigned or short_sym in assigned:
        continue
    lp, sp = positions[long_sym], positions[short_sym]
    if float(lp.get('szi') or 0) <= 0 or float(sp.get('szi') or 0) >= 0:
        continue
    lm, sm = mark_from_position(lp), mark_from_position(sp)
    le, se = float(lp.get('entryPx') or 0), float(sp.get('entryPx') or 0)
    if not lm or not sm or min(lm, sm, le, se) <= 0:
        continue
    entry_ratio = le / se
    current_ratio = lm / sm
    management_entry_ratio = float(pair_cfg.get('management_entry_ratio') or entry_ratio)
    if not pair_cfg.get('management_entry_ratio'):
        pair_cfg['management_entry_ratio'] = management_entry_ratio
        cfg['_management_baseline_dirty'] = True
    x = {'long': long_sym, 'short': short_sym, 'pair_cfg': pair_cfg, 'long_position': lp, 'short_position': sp, 'long_mark': lm, 'short_mark': sm,
         'entry_ratio': entry_ratio, 'current_ratio': current_ratio, 'ratio_change': (current_ratio / entry_ratio - 1) * 100,
         'management_entry_ratio': management_entry_ratio,
         'management_ratio_change': (current_ratio / management_entry_ratio - 1) * 100}
    enrich_pair(x, fills)
    x['funding'] = active_funding(Ledger(), address.strip(), long_sym, short_sym, fills,
                                 float(lp['szi']), float(sp['szi']), bool(snap.get('fills_complete')))
    x['total_pnl'] = (x['unrealized'] + x['realized'] - x['fees'] + x['funding']) if x['funding'] is not None and x['history_complete'] else None
    known_cycle_open = [v for v in (x.get('opened_long'), x.get('opened_short')) if v]
    cycle_opened_at = max(known_cycle_open) if known_cycle_open else None
    if reset_management_on_reopen(pair_cfg, cycle_opened_at):
        pair_cfg['management_entry_ratio'] = entry_ratio
        x['management_entry_ratio'] = entry_ratio
        x['management_ratio_change'] = (current_ratio / entry_ratio - 1) * 100
        cfg['_management_baseline_dirty'] = True
    if not snap.get('fills_complete', True):
        x['history_complete'] = False
    assigned.update((long_sym, short_sym)); active.append(x)

if cfg.pop('_management_baseline_dirty', False):
    try:
        save_settings(CONFIG, cfg, bool(settings_error))
    except Exception as exc:
        st.warning(f'No se pudo guardar la referencia de gestión: {exc}')

# Daily Z-score is only a management filter: request a compact history instead
# of the full 4998-candle chart history to reduce API weight on cold starts.
z_failures = []
for x in active:
    signal_frame = None
    try:
        signal_frame, _ = load_ratio_frame(x['long'], x['short'], '1d', samples=250)
        z = None if signal_frame.empty or signal_frame['z'].isna().all() else float(signal_frame['z'].iloc[-1])
        if z is None:
            z_failures.append(f"{display(x['long'])}/{display(x['short'])}: sin suficientes datos")
    except Exception as exc:
        z = None
        z_failures.append(f"{display(x['long'])}/{display(x['short'])}: {exc}")
    x['adaptive_levels'] = calculate_adaptive_levels(signal_frame, x['management_entry_ratio']) if signal_frame is not None and not signal_frame.empty else {'status':'unavailable','reason':'Sin histórico','levels':{},'regime':'N/D'}
    x['management_z'] = z
    pair_cfg = x['pair_cfg']
    executed_tp = [int(item.get('level')) for item in pair_cfg.get('executed_tp', []) if isinstance(item, dict) and item.get('level')]
    executed_add = [int(item.get('level')) for item in pair_cfg.get('executed_add', []) if isinstance(item, dict) and item.get('level')]
    x.update(adaptive_signals(float(x['current_ratio']), float(x['management_entry_ratio']), x['adaptive_levels'], executed_tp, executed_add))
if z_failures:
    st.warning('Z-score no disponible/parcial: ' + ' · '.join(z_failures))

archived_realized = sum(float(item.get('realized') or 0) for item in closed_history)
archived_fees = sum(float(item.get('fees') or 0) for item in closed_history)

if closed_history:
    with st.expander(f'Historial de pares cerrados ({len(closed_history)})', expanded=not active):
        sorted_closed = sorted(closed_history, key=lambda r: int(r.get('closed_at') or 0), reverse=True)
        hist_rows = []
        for item in sorted_closed:
            closed_at = int(item.get('closed_at') or 0)
            hist_rows.append({
                'Par': f"L {display(item['long'])}  ·  S {display(item['short'])}",
                'Cerrado': datetime.fromtimestamp(closed_at / 1000, TZ).strftime('%d/%m/%Y %H:%M') if closed_at else 'N/D',
                'PnL realizado': float(item.get('realized') or 0),
                'Comisiones': -float(item.get('fees') or 0),
                'Funding': item.get('funding'),
                'Neto realizado': item.get('total_pnl'),
            })
        hist_df = pd.DataFrame(hist_rows)
        hist_style = hist_df.style.format({
            'PnL realizado': '$ {:.2f}', 'Comisiones': '$ {:.2f}', 'Neto realizado': '$ {:.2f}', 'Funding': '$ {:.2f}'
        }, na_rep='N/D').map(style_signed, subset=['PnL realizado', 'Comisiones', 'Neto realizado'])
        closed_event = st.dataframe(hist_style, hide_index=True, width='stretch', on_select='rerun', selection_mode='single-row', key='closed_pairs_table')
        try:
            if closed_event.selection.rows:
                row_idx = min(closed_event.selection.rows[0], len(sorted_closed) - 1)
                st.session_state['selected_closed_pair_id'] = str(sorted_closed[row_idx].get('id') or '')
        except Exception:
            pass
        st.caption('Seleccioná un par cerrado para abrir su ciclo completo: entrada, ADD, cierres y gráfico histórico.')

    selected_closed_id = st.session_state.get('selected_closed_pair_id')
    closed_item = next((item for item in closed_history if str(item.get('id') or '') == selected_closed_id), None)
    if closed_item:
        closed_long, closed_short = closed_item['long'], closed_item['short']
        closed_opened = int(closed_item.get('opened_at') or 0)
        closed_at = int(closed_item.get('closed_at') or 0)
        closed_events = closed_pair_trade_events(closed_long, closed_short, fills, closed_opened, closed_at)
        closed_entry_ratio = archived_pair_entry_ratio(closed_long, closed_short, fills, closed_opened)
        st.markdown(f"## {display(closed_long)} / {display(closed_short)} · cerrado")
        st.markdown(f'<span class="leg leg-l">L {escape(display(closed_long))}</span><span class="leg leg-s">S {escape(display(closed_short))}</span>', unsafe_allow_html=True)
        cmeta1, cmeta2, cmeta3 = st.columns(3)
        net_closed = closed_item.get('total_pnl')
        with cmeta1: kpi('Neto realizado', money(net_closed), 'ciclo cerrado', tone(net_closed))
        with cmeta2: kpi('Apertura', datetime.fromtimestamp(closed_opened / 1000, TZ).strftime('%d/%m/%Y %H:%M') if closed_opened else 'N/D')
        with cmeta3: kpi('Cierre', datetime.fromtimestamp(closed_at / 1000, TZ).strftime('%d/%m/%Y %H:%M') if closed_at else 'N/D')
        if closed_entry_ratio:
            cc1, cc2 = st.columns([1.7, 1])
            with cc1:
                cv1, cv2 = st.columns([1.2, 1])
                with cv1: closed_view = st.segmented_control('Vista cerrado', ['Velas', 'z-score'], default='Velas', key=f'closed_view_{selected_closed_id}') or 'Velas'
                with cv2: closed_interval = st.selectbox('Temporalidad cerrado', ['15m', '1h', '4h', '1d'], index=1, label_visibility='collapsed', key=f'closed_interval_{selected_closed_id}')
                try:
                    ratio_chart(closed_long, closed_short, closed_interval, closed_entry_ratio, closed_view, 'Desde apertura', closed_opened, closed_events, closed_entry_ratio, None)
                except Exception as exc:
                    st.warning(f'Gráfico del par cerrado no disponible: {exc}')
            with cc2:
                st.markdown('### PnL del ciclo')
                closed_pnl_rows = pd.DataFrame([
                    ['Realizado', float(closed_item.get('realized') or 0)],
                    ['Comisiones', -float(closed_item.get('fees') or 0)],
                    ['NETO', net_closed],
                ], columns=['Concepto', 'USD'])
                st.dataframe(style_usd_column(closed_pnl_rows), hide_index=True, width='stretch')
                st.caption(f'Ratio de entrada reconstruido desde fills: {closed_entry_ratio:.6g}. El gráfico continúa hasta hoy para evaluar qué hizo el ratio después del cierre.')
        else:
            st.warning('No se pudo reconstruir el ratio de entrada de este ciclo con los fills disponibles.')
        if closed_events:
            closed_ev_df = pd.DataFrame([{
                'Fecha': datetime.fromtimestamp(ev['time'] / 1000, TZ).strftime('%d/%m/%Y %H:%M'),
                'Evento': 'ADD' if ev['kind'] == 'add' else 'CIERRE',
                'Monto': ev['amount'],
                'PnL realizado': ev['realized'] if ev['kind'] == 'close' else None,
            } for ev in closed_events])
            st.dataframe(closed_ev_df.style.format({'Monto':'$ {:.2f}','PnL realizado':'$ {:.2f}'}, na_rep='—').map(style_signed, subset=['PnL realizado']), hide_index=True, width='stretch')
        st.divider()

if not active:
    if unavailable_pairs:
        st.error('No se pueden evaluar los pares con una pata xyz porque esa fuente no respondió. Se muestran como sin datos, no como posiciones cerradas.')
    else:
        st.info('No hay pares completos activos. Podés armarlos desde la barra lateral.')
else:
    equity, account_margin, core_eq, core_margin, xyz_eq, xyz_margin = account_metrics(snap['core_state'], snap['xyz_state'])
    total_unreal = sum(x['unrealized'] for x in active)
    known_funding = [x.get('funding') for x in active + closed_history]
    total_funding = sum(known_funding) if all(v is not None for v in known_funding) else None
    active_realized = sum(x['realized'] for x in active)
    total_realized = active_realized + archived_realized
    total_fees = sum(x['fees'] for x in active)
    total_pnl = None if total_funding is None or not snap.get('fills_complete') or any(not x['history_complete'] for x in active) else total_unreal + total_funding + active_realized - total_fees + archived_realized - archived_fees
    pnl_partial = (not snap.get('fills_ok', True) or not snap.get('fills_complete', True) or any(not x['history_complete'] for x in active))
    total_long_notional = sum(x['long_usd'] for x in active)
    total_short_notional = sum(x['short_usd'] for x in active)
    total_notional = total_long_notional + total_short_notional
    total_pair_margin = sum(x['margin'] for x in active)
    delta = total_long_notional - total_short_notional
    total_base = {'Bruto': total_notional, 'Una pata': total_notional / 2, 'Margen': total_pair_margin}[pnl_mode]
    pnl_pct = pct(total_pnl, total_base)
    cols = st.columns(7)
    open_pnl_total = total_unreal
    with cols[0]: kpi('PnL abierto', money(open_pnl_total), 'solo no realizado · riesgo vivo', tone(open_pnl_total))
    with cols[1]: kpi('Realizado total' + (' · PARCIAL' if pnl_partial else ''), money(total_realized), f'activos {money(active_realized)} · cerrados {money(archived_realized)}', tone(total_realized))
    with cols[2]: kpi('PnL acumulado', money(total_pnl), 'abierto + funding + realizado − fees', tone(total_pnl))
    equity_sub = f'Core {money(core_eq)} / xyz {money(xyz_eq)}'
    with cols[3]: kpi('Equity' if equity is not None else 'Equity por fuente', money(equity), equity_sub)
    exposure_sub = f'L {money(total_long_notional)} + S {money(total_short_notional)} · margen {money(total_pair_margin)}'
    with cols[4]: kpi('Exposición total', money(total_notional), exposure_sub)
    with cols[5]: kpi('Delta neta', money(delta), 'long − short', tone(delta))
    with cols[6]: kpi('Funding', money(total_funding), 'acumulado desde apertura', tone(total_funding))

    unavailable_ids = {(p['long'], p['short']) for p in unavailable_pairs}
    orphaned = [p for p in cfg['pairs'] if (p['long'], p['short']) not in unavailable_ids and not any(x['long'] == p['long'] and x['short'] == p['short'] for x in active)]
    alerts = []
    for x in active:
        if x['liq_distance'] is None:
            alerts.append(f"{display(x['long'])}/{display(x['short'])}: liquidación N/D")
        elif x['liq_distance'] < 15:
            alerts.append(f"{display(x['long'])}/{display(x['short'])}: liq. {x['liq_distance']:.1f}%")
        if abs(x['imbalance']) > 10:
            alerts.append(f"{display(x['long'])}/{display(x['short'])}: neutralidad {x['imbalance']:+.1f}%")
    alerts += [f"{display(p['long'])}/{display(p['short'])}: sin ambas patas abiertas" for p in orphaned]
    alerts += [f"{display(p['long'])}/{display(p['short'])}: sin datos xyz" for p in unavailable_pairs]
    alert_class = 'warn' if alerts else 'ok'
    st.markdown(f'<div class="alerts {alert_class}"><b>Alertas</b> · {escape(" · ".join(alerts) if alerts else "Sin alertas de riesgo configuradas")}</div>', unsafe_allow_html=True)

    rows = []
    for x in active:
        base = pnl_base(x, pnl_mode)
        open_value = x['unrealized']
        total_value = x['total_pnl']
        days = None
        known_open = [v for v in (x['opened_long'], x['opened_short']) if v]
        if known_open:
            days = max(0, int((datetime.now(TZ).timestamp()*1000 - max(known_open)) / 86_400_000))
        rows.append({
            'Par': f"L {display(x['long'])}  ·  S {display(x['short'])}",
            'Tamaño USD': x['notional'],
            'PnL abierto': open_value, 'Realizado': x['realized'], 'PnL total': total_value,
            'PnL abierto %': pct(open_value, base), 'Δ ratio %': x['ratio_change'],
            'TP': x['tp'], 'ADD': x['add'], 'Z 1D': x['management_z'],
            'Neutralidad %': x['imbalance'], 'Dist. liq. %': x['liq_distance'],
            'Funding': x['funding'], 'Días': days, '_id': f"{x['long']}|{x['short']}"
        })
    frame = pd.DataFrame(rows)

    export_rows = build_export_rows(active, closed_history, TZ)
    export_df = pd.DataFrame(export_rows)
    csv_bytes = export_df.to_csv(index=False).encode('utf-8-sig')
    csv_col, copy_note = st.columns([1.15, 4.85])
    with csv_col:
        st.download_button('⇩ Exportar CSV', data=csv_bytes, file_name=f'pairs_desk_{datetime.now(TZ):%Y%m%d_%H%M}.csv', mime='text/csv', width='stretch')
    with copy_note:
        st.caption('CSV incluye pares activos y cerrados; el realizado exportado reconcilia con el Realizado total del dashboard.')

    event = st.dataframe(styled_pairs_table(frame), hide_index=True, width='stretch', on_select='rerun', selection_mode='single-row', key='pairs_table')
    selected_id = st.session_state.get('selected_pair_id')
    try:
        if event.selection.rows:
            row_idx = min(event.selection.rows[0], len(frame) - 1)
            selected_id = frame.iloc[row_idx]['_id']
            st.session_state['selected_pair_id'] = selected_id
    except Exception:
        pass
    active_by_id = {f"{item['long']}|{item['short']}": item for item in active}
    if selected_id not in active_by_id:
        selected_id = frame.iloc[0]['_id']
        st.session_state['selected_pair_id'] = selected_id
    x = active_by_id[selected_id]
    pair_key = re.sub(r'[^A-Za-z0-9_-]+', '_', selected_id)

    st.markdown(f"## {display(x['long'])} / {display(x['short'])}")
    st.markdown(f'<span class="leg leg-l">L {escape(display(x["long"]))}</span><span class="leg leg-s">S {escape(display(x["short"]))}</span>', unsafe_allow_html=True)
    z_txt = 'N/D' if x['management_z'] is None else f"{x['management_z']:+.2f}"
    tp_cls = 'pos' if x['tp'].startswith('TP') else 'ac' if x['tp'] == 'HOLD' else ''
    add_cls = 'neg' if x['add'].startswith('REVISAR') else 'ac' if x['add'] == 'WATCH' else 'mu'
    st.markdown(
        f'<div class="signal-grid">'
        f'<div class="signal-card"><div class="signal-label">Take Profit</div><div class="signal-value {tp_cls}">{escape(x["tp"])}</div><div class="signal-sub">{escape(x["tp_detail"])} · Δ gestión {x["management_ratio_change"]:+.1f}%</div></div>'
        f'<div class="signal-card"><div class="signal-label">Agregar posición</div><div class="signal-value {add_cls}">{escape(x["add"])}</div><div class="signal-sub">{escape(x["add_detail"])} · Z 1D {z_txt}</div></div>'
        f'</div>', unsafe_allow_html=True)
    with st.expander('Operar par · Hyperliquid', expanded=False):
        st.caption('Órdenes a mercado IOC. Las dos patas NO son atómicas; si falla una, la otra puede quedar ejecutada.')
        try:
            trade_db = open_trade_journal()
            unresolved = pending_trades(trade_db, address.strip()) if ADDRESS.fullmatch(address.strip()) else []
        except Exception as journal_exc:
            trade_db = None
            unresolved = [('?', '?', 'journal_unavailable', 0)]
            st.error(f'Bitácora SQLite no disponible: {journal_exc}. Trading bloqueado.')
        if unresolved:
            st.error('Trading bloqueado: existe una operación sin conciliar o la bitácora no está disponible. Revisá las órdenes y posiciones reales en Hyperliquid.')
            for pending_id, pending_pair, pending_status, _ in unresolved:
                st.caption(f'Pendiente: {pending_pair} · {pending_status} · {pending_id[:12]}')
            if trade_db is not None:
                with st.expander('Conciliar operación pendiente (tras verificar Hyperliquid)'):
                    st.warning('Antes de desbloquear, comprobá manualmente fills, órdenes abiertas y exposición de ambas patas en Hyperliquid.')
                    note = st.text_input('Qué verificaste', key=f'reconcile_note_{pair_key}', placeholder='Comprobé ambas patas y no hay órdenes pendientes…')
                    verified = st.checkbox('Confirmo que verifiqué las órdenes y posiciones en Hyperliquid', key=f'reconcile_confirm_{pair_key}')
                    if st.button('Marcar como conciliada', key=f'reconcile_btn_{pair_key}', disabled=not verified or len(note.strip()) < 10):
                        try:
                            for pending_id, *_ in unresolved:
                                reconcile_trade(trade_db, pending_id, note)
                            st.rerun()
                        except Exception as reconcile_exc:
                            st.error(str(reconcile_exc))
        trading_enabled = bool(st.session_state.get('trading_armed')) and agent_ready and not unresolved
        if not trading_enabled:
            st.info('Trading deshabilitado. Pegá la clave de tu API Wallet (Agent) en la barra lateral y activá «Habilitar órdenes reales». No necesitás configurar variables de entorno.')
        elif not core_ok or (('xyz:' in selected_id) and not snap.get('xyz_ok', False)) or age > 30:
            st.warning('Datos de posiciones incompletos o antiguos (>30 s). Actualizá antes de operar.')
        else:
            operation = st.selectbox('Operación', ['Aumentar', 'Reducir', 'Cerrar'], key=f'trade_op_{pair_key}')
            fraction_pct = st.number_input('Porcentaje de cada pata (%)', min_value=1, max_value=100, value=25, step=5, disabled=operation=='Cerrar', key=f'trade_pct_{pair_key}')
            fraction = 1.0 if operation == 'Cerrar' else fraction_pct / 100
            slip_pct = st.number_input('Deslizamiento máximo por orden (%)', min_value=0.1, max_value=2.0, value=0.5, step=0.1, key=f'trade_slip_{pair_key}')
            try:
                ticket = preview_pair(x, operation, fraction)
                st.table(pd.DataFrame([{'Activo': t['coin'], 'Orden': 'Comprar' if t['is_buy'] else 'Vender',
                                        'Cantidad aprox.': round(t['size'], 8), 'Nocional estimado USD': round(t['notional'], 2),
                                        'Reduce-only': 'Sí' if t['reduce_only'] else 'No'} for t in ticket]))
                st.caption(f'Nocional bruto aproximado: {money(sum(t["notional"] for t in ticket))}. Precio final, comisiones y ejecución pueden diferir.')
                approved = st.checkbox('Confirmo que autorizo ambas órdenes reales, y acepto el riesgo de ejecución de una sola pata.', key=f'trade_confirm_{pair_key}')
                if st.button('Enviar órdenes reales a Hyperliquid', type='primary', disabled=not approved, key=f'trade_execute_{pair_key}'):
                    fingerprint = (selected_id, operation, fraction, slip_pct, snap['snapshot_token'])
                    if st.session_state.get('last_trade_fingerprint') == fingerprint:
                        st.error('Este ticket ya fue enviado. Actualizá los datos antes de enviar otra operación.')
                    else:
                        st.session_state['last_trade_fingerprint'] = fingerprint
                        try:
                            with st.spinner('Enviando órdenes a Hyperliquid…'):
                                attempt_id = begin_trade(trade_db, address.strip(), selected_id, operation, ticket)
                                try:
                                    results = execute_pair(ticket, address.strip(), agent_input.strip(), slip_pct / 100,
                                                           journal=trade_db, attempt_id=attempt_id)
                                    completed = len(results) == 2 and all(r['ok'] for r in results)
                                    finish_trade(trade_db, attempt_id, 'complete' if completed else 'partial')
                                except Exception:
                                    finish_trade(trade_db, attempt_id, 'uncertain')
                                    raise
                            for result in results:
                                if result['ok']:
                                    st.success(f'{result["coin"]}: ejecutadas {result["filled_size"]} unidades')
                                else:
                                    st.error(f'{result["coin"]}: {result["message"]}')
                            if len(results) != 2 or any(not r['ok'] for r in results):
                                st.error('ATENCIÓN: el par puede estar desbalanceado. Revisá las posiciones y órdenes directamente en Hyperliquid.')
                            if len(results) != 2 or any(not r['ok'] for r in results):
                                st.error('Se bloquearon nuevas órdenes hasta que concilies esta operación con Hyperliquid.')
                            query_cached.clear()
                        except Exception as exc:
                            st.error(f'No se pudo completar el envío: {type(exc).__name__}: {exc}. Verificá Hyperliquid antes de reintentar.')
            except ValueError as exc:
                st.error(str(exc))
    pair_cfg = x['pair_cfg']
    done_tp = [item for item in pair_cfg.get('executed_tp', []) if isinstance(item, dict)]
    done_add = [item for item in pair_cfg.get('executed_add', []) if isinstance(item, dict)]
    mg1, mg2, mg3 = st.columns([1.3, 1.3, 3.4])
    with mg1:
        if x.get('tp_level') and st.button(f"✓ Marcar TP{x['tp_level']}", key=f"mark_tp_{pair_key}", width='stretch'):
            pair_cfg.setdefault('executed_tp', []).append({
                'level': int(x['tp_level']), 'executed_at': int(datetime.now(TZ).timestamp() * 1000),
                'notional_usd': float(x['notional']), 'ratio_change_pct': float(x['management_ratio_change']),
            })
            try:
                save_settings(CONFIG, cfg, bool(settings_error)); st.rerun()
            except Exception as exc:
                st.error(f'No se pudo guardar TP ejecutado: {exc}')
    with mg2:
        if x.get('add_level') and st.button(f"✓ Marcar ADD{x['add_level']}", key=f"mark_add_{pair_key}", width='stretch'):
            pair_cfg.setdefault('executed_add', []).append({
                'level': int(x['add_level']), 'executed_at': int(datetime.now(TZ).timestamp() * 1000),
                'notional_usd': float(x['notional']), 'ratio_change_pct': float(x['management_ratio_change']),
            })
            try:
                save_settings(CONFIG, cfg, bool(settings_error)); st.rerun()
            except Exception as exc:
                st.error(f'No se pudo guardar ADD ejecutado: {exc}')
    with mg3:
        states = []
        if done_tp: states.append('TP ejecutados: ' + ', '.join(f"TP{int(i['level'])}" for i in done_tp))
        if done_add: states.append('ADD ejecutados: ' + ', '.join(f"ADD{int(i['level'])}" for i in done_add))
        st.caption(' · '.join(states) if states else 'Sin escalones de gestión marcados como ejecutados.')

    adaptive = x.get('adaptive_levels', {})
    with st.expander('Niveles adaptativos · automático', expanded=False):
        st.caption(f"Régimen: {adaptive.get('regime', 'N/D')} · {adaptive.get('reason', '')}")
        if adaptive.get('status') == 'ok':
            for level_name, value in adaptive['levels'].items():
                st.write(f"{level_name.upper()}: {value:.6g} · {(value / x['management_entry_ratio'] - 1) * 100:+.2f}% desde referencia")
        else:
            st.warning('No se generan niveles automáticos con datos insuficientes o régimen inestable.')
    with st.expander('Reglas manuales anteriores (no activas en modo automático)'):
        rules = dict(DEFAULT_MANAGEMENT_RULES)
        rules.update(pair_cfg.get('management_rules') or {})
        r1, r2, r3, r4, r5 = st.columns(5)
        tp1 = r1.number_input('TP1 Δ ratio %', value=float(rules['tp1_ratio_pct']), step=0.5, key=f'tp1rule_{pair_key}')
        tp2 = r2.number_input('TP2 Δ ratio %', value=float(rules['tp2_ratio_pct']), step=0.5, key=f'tp2rule_{pair_key}')
        tp3 = r3.number_input('TP3 Δ ratio %', value=float(rules['tp3_ratio_pct']), step=0.5, key=f'tp3rule_{pair_key}')
        add1 = r4.number_input('ADD1 Δ ratio %', value=float(rules['add1_ratio_pct']), step=0.5, key=f'add1rule_{pair_key}')
        add2 = r5.number_input('ADD2 Δ ratio %', value=float(rules['add2_ratio_pct']), step=0.5, key=f'add2rule_{pair_key}')
        z1, z2, z3, action = st.columns(4)
        add1_z = z1.number_input('ADD1 Z', value=float(rules['add1_z']), step=0.1, key=f'add1z_{pair_key}')
        add2_z = z2.number_input('ADD2 Z', value=float(rules['add2_z']), step=0.1, key=f'add2z_{pair_key}')
        tp3_z = z3.number_input('TP3 |Z|', min_value=0.0, value=float(rules['tp3_abs_z']), step=0.1, key=f'tp3z_{pair_key}')
        if action.button('Guardar reglas', key=f'saverules_{pair_key}', width='stretch'):
            pair_cfg['management_rules'] = {
                'tp1_ratio_pct': float(tp1), 'tp2_ratio_pct': float(tp2), 'tp3_ratio_pct': float(tp3),
                'tp3_abs_z': float(tp3_z), 'add1_ratio_pct': float(add1), 'add1_z': float(add1_z),
                'add2_ratio_pct': float(add2), 'add2_z': float(add2_z),
            }
            try:
                save_settings(CONFIG, cfg, bool(settings_error)); st.rerun()
            except Exception as exc:
                st.error(f'No se pudieron guardar las reglas: {exc}')
        if done_tp or done_add:
            if st.button('↶ Deshacer último escalón ejecutado', key=f'undo_mgmt_{pair_key}'):
                candidates = []
                for key_name in ('executed_tp', 'executed_add'):
                    for idx, item in enumerate(pair_cfg.get(key_name, [])):
                        if isinstance(item, dict):
                            candidates.append((int(item.get('executed_at') or 0), key_name, idx))
                if candidates:
                    _, key_name, idx = max(candidates)
                    pair_cfg[key_name].pop(idx)
                    try:
                        save_settings(CONFIG, cfg, bool(settings_error)); st.rerun()
                    except Exception as exc:
                        st.error(f'No se pudo deshacer: {exc}')
    with st.expander('Notas e invalidación'):
        note_col, invalid_col, save_col = st.columns([2.5, 2.5, 1])
        trade_note = note_col.text_area('Nota de tesis', value=str(pair_cfg.get('trade_note') or ''), key=f'note_{pair_key}', height=90)
        invalidation_note = invalid_col.text_area('Qué invalida la tesis', value=str(pair_cfg.get('invalidation_note') or ''), key=f'invalidation_{pair_key}', height=90)
        if save_col.button('Guardar notas', key=f'savenotes_{pair_key}', width='stretch'):
            pair_cfg['trade_note'] = trade_note.strip()
            pair_cfg['invalidation_note'] = invalidation_note.strip()
            try:
                save_settings(CONFIG, cfg, bool(settings_error)); st.rerun()
            except Exception as exc:
                st.error(f'No se pudieron guardar las notas: {exc}')
        if invalidation_note.strip():
            st.warning('Invalidación definida para este par: ' + invalidation_note.strip())
        else:
            st.caption('Conviene definir explícitamente qué evento fundamental o técnico invalida la tesis antes de agregar más posición.')

    left, right = st.columns([1.65, 1])
    with left:
        c1, c2, c3 = st.columns([1.4, 1.6, 1])
        with c1: view = st.segmented_control('Vista', ['Velas', 'z-score'], default='Velas', key=f'view_{pair_key}') or 'Velas'
        with c2: range_mode = st.segmented_control('Rango', ['Todo', 'Desde apertura', '1M', '3M'], default='Todo', key=f'range_{pair_key}') or 'Todo'
        with c3: interval = st.selectbox('Temporalidad', ['15m', '1h', '4h', '1d', '1w'], index=3, label_visibility='collapsed', key=f'interval_{pair_key}')
        with st.spinner('Cargando gráfico…'):
            opened_ms = max([v for v in (x['opened_long'], x['opened_short']) if v], default=None)
            trade_events = pair_trade_events(x, fills)
            try:
                ratio_chart(x['long'], x['short'], interval, x['entry_ratio'], view, range_mode, opened_ms, trade_events, x['management_entry_ratio'], ({'adaptive_absolute_levels': x['adaptive_levels']['levels']} if x.get('adaptive_levels', {}).get('status') == 'ok' else {'adaptive_absolute_levels': {}}))
            except Exception as exc:
                st.warning(f'Gráfico no disponible: {exc}')
        if trade_events:
            pretty_events = pd.DataFrame([
                {
                    'Fecha': datetime.fromtimestamp(item['time'] / 1000, TZ).strftime('%d/%m/%Y %H:%M'),
                    'Evento': 'ADD' if item['kind'] == 'add' else 'CIERRE',
                    'Monto': item['amount'],
                    'PnL realizado': item['realized'] if item['kind'] == 'close' else None,
                }
                for item in trade_events
            ])
            ev_styler = pretty_events.style.format({'Monto': '$ {:.2f}', 'PnL realizado': '$ {:.2f}'}, na_rep='—').map(style_signed, subset=['PnL realizado'])
            st.caption('Marcadores del gráfico: ADD muestra nocional agregado aproximado; CIERRE muestra si esa reducción se hizo en ganancia o pérdida.')
            st.dataframe(ev_styler, hide_index=True, width='stretch')
    with right:
        st.markdown('### PnL de la posición')
        pnl_rows = pd.DataFrame([
            ['ABIERTO · No realizado', x['unrealized']],
            ['Realizado · ya cerrado', x['realized']],
            ['Funding acumulado', x['funding']],
            ['Comisiones', -x['fees']],
            ['TOTAL histórico', x['total_pnl']]
        ], columns=['Concepto', 'USD'])
        st.dataframe(style_usd_column(pnl_rows), hide_index=True, width='stretch')
        if not snap.get('fills_ok', True) or not x['history_complete']:
            st.warning('PnL parcial: el historial de fills no está completo; realizado y comisiones pueden faltar.')
        known_open = [v for v in (x.get('opened_long'), x.get('opened_short')) if v]
        if known_open and st.button('Contrastar funding con ledger HL', key=f'funding_check_{pair_key}', width='stretch'):
            try:
                funding_rows, funding_complete = user_funding_history(address.strip(), min(known_open))
                ledger_funding = funding_ledger_cashflow(funding_rows, [x['long'], x['short']])
                st.session_state[f'funding_check_result_{pair_key}'] = (ledger_funding, funding_complete, len(funding_rows))
            except Exception as exc:
                st.session_state[f'funding_check_result_{pair_key}'] = ('error', str(exc), 0)
        funding_check = st.session_state.get(f'funding_check_result_{pair_key}')
        if funding_check:
            if funding_check[0] == 'error':
                st.warning(f'No se pudo contrastar funding: {funding_check[1]}')
            else:
                ledger_funding, funding_complete, nrows = funding_check
                delta_funding = None if x['funding'] is None else float(ledger_funding) - float(x['funding'])
                status = 'completo' if funding_complete else 'parcial'
                st.caption(f'Ledger HL desde apertura: {money(float(ledger_funding))} · cumFunding: {money(x["funding"])} · diferencia {money(delta_funding)} · {nrows} registros ({status}).')
        st.markdown('### Patas y riesgo')
        risk = pd.DataFrame([
            [f"L {display(x['long'])}", leverage_text(x['long_position']), x['long_usd'], x['long_liq_distance']],
            [f"S {display(x['short'])}", leverage_text(x['short_position']), x['short_usd'], x['short_liq_distance']],
        ], columns=['Pata', 'Margen', 'Nocional', 'Dist. liq. %'])
        st.dataframe(style_risk_table(risk), hide_index=True, width='stretch')
        diff = abs(x['long_usd'] - x['short_usd'])
        smaller = display(x['long']) if x['long_usd'] < x['short_usd'] else display(x['short'])
        st.markdown('### Neutralidad')
        st.caption(f"Long − short = {x['imbalance']:+.2f}% del nocional. Para neutralizar con tamaños actuales: sumar aproximadamente {money(diff)} a {smaller}.")
        st.caption(f"Apertura long: {entry_date(x['opened_long'])} ART · short: {entry_date(x['opened_short'])} ART")

    with st.expander('Metodología y límites'):
        st.markdown('''- **% de PnL** usa la base seleccionada arriba: Bruto = long + short; Una pata = bruto/2; Margen = suma de `marginUsed`.
- **PnL abierto** en la tabla = `unrealizedPnl` de las patas que siguen abiertas. **Realizado** se muestra aparte y nunca se mezcla con el riesgo vivo. **PnL total histórico** = no realizado + funding acumulado + realizado − comisiones. Si el historial no alcanza hasta la apertura, se marca como parcial.
- **Ratio de entrada** = precio medio long ÷ precio medio short. El ratio por sí solo representa mejor el resultado cuando ambas patas están neutrales en USD.
- **Referencia de gestión** = ratio medio de entrada guardado la primera vez que esta versión detecta el par. No se recalcula cuando cambia el precio medio por un add, para que los gatillos no se desplacen. En pares ya abiertos al instalar esta versión, la referencia inicial será el ratio medio existente en ese momento.
- **Take Profit**: TP1 al +10% del ratio (25%), TP2 al +20% (otro 25%) y TP3 cuando además |Z 1D| ≤ 0.5 (35%), dejando 15% como runner.
- **Agregar posición**: zona ADD 1 cuando el ratio está ≤ -8% y Z 1D ≤ -2; zona ADD 2 cuando está ≤ -15% y Z 1D ≤ -2.5. Son zonas para **revisar**, no órdenes: ADD 1 presupone tesis intacta y ADD 2 además requiere estabilización. No hay tercer add.
- **Liquidación** usa la distancia entre el mark aproximado (`positionValue / tamaño`) y `liquidationPx` informado por Hyperliquid.
- El gráfico de velas usa TradingView Lightweight Charts en el navegador: crosshair con OHLC, rueda para zoom, arrastre para recorrer el histórico y escala de precio manipulable desde el eje derecho. Los datos siguen viniendo de `candleSnapshot`; en huecos solo se arrastra el cierre previo para no inventar mechas.
- La convención de signo de `cumFunding.sinceOpen` se conserva como en la versión previa: cobrado positivo = `-sinceOpen`; conviene contrastarla con la UI de Hyperliquid.''')

used = {s for x in active for s in (x['long'], x['short'])}
remaining = [k for k in positions if k not in used]
if remaining:
    with st.expander(f'Posiciones sin agrupar ({len(remaining)})'):
        rem_df = pd.DataFrame([{'Activo': display(k), 'Lado': 'Long' if float(positions[k]['szi']) > 0 else 'Short', 'PnL': float(positions[k].get('unrealizedPnl') or 0)} for k in remaining])
        st.dataframe(rem_df.style.format({'PnL': '$ {:.2f}'}).map(style_signed, subset=['PnL']), hide_index=True, width='stretch')
