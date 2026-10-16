"""Smoke de navegador para la UI React (requiere playwright, Chromium y react_dist compilado).

Se omite si falta cualquiera de ellos. Usa datos simulados: no toca el backend ni la red.
"""
import math
import random
import re
import time
from pathlib import Path

import pytest

BASE = Path(__file__).resolve().parents[1]
DIST = BASE / 'react_dist'
KLINE = BASE / 'pairs_desk' / 'vendor' / 'klinecharts.min.js'

sync_api = pytest.importorskip('playwright.sync_api')
pytestmark = pytest.mark.skipif(not (DIST / 'index.html').exists(), reason='Compilar antes: cd react_frontend && npm run build')


def _state():
    random.seed(4)
    now = int(time.time() * 1000)
    spec = [('ETH', 'BTC', 1.2, -84.3), ('SOL', 'AVAX', -3.1, 41.2), ('ARB', 'OP', 5.4, 126.8), ('DOGE', 'SHIB', -8.2, -212.5)]
    pairs = [dict(id=f'{l}-{s}', long=l, short=s, pnl=pnl, realized=round(pnl * .2, 2), total_pnl=pnl, funding=round(random.uniform(-6, 9), 2),
                  fees=3.0, size=2000 + i * 500, long_usd=1000 + i * 250, short_usd=1000 + i * 240, pnl_pct=pct, ratio=1 + i * .1,
                  entry_ratio=1 + i * .1, ratio_change=pct, opened_at=now - 86400000 * (i + 2), events=[], entry_history=[])
             for i, (l, s, pct, pnl) in enumerate(spec)]
    value, history = 0.0, []
    for k in range(80):
        value += random.uniform(-35, 48)
        history.append(dict(timestamp=now - (80 - k) * 3 * 3600 * 1000, pnl=round(value, 2)))
    summary = dict(total=-100.0, unrealized=-100.0, realized=10.0, funding=1.0, exposure=9000.0, net_missing_funding_count=0, net_known_subtotal=-100.0)
    return dict(pairs=pairs, summary=summary, warnings=[], pnl_history=history, last_updated_ms=now)


def _bars():
    now, close, out = int(time.time() * 1000), 2.0, []
    for k in range(200):
        open_ = close
        close = open_ * (1 + random.uniform(-.012, .012))
        out.append(dict(timestamp=now - (200 - k) * 3600 * 1000, open=open_, high=max(open_, close) * 1.004, low=min(open_, close) * .996, close=close))
    return out


@pytest.fixture(scope='module')
def page():
    state = _state()
    with sync_api.sync_playwright() as pw:
        try:
            browser = pw.chromium.launch()
        except Exception as error:  # Chromium no instalado
            pytest.skip(f'Chromium no disponible: {error}')
        pg = browser.new_page(viewport=dict(width=1440, height=900))
        pg.errors = []
        pg.on('pageerror', lambda e: pg.errors.append(str(e)))
        pg.on('console', lambda m: pg.errors.append(m.text) if m.type == 'error' else None)

        def handle(route):
            path = route.request.url.split('//', 1)[1].split('/', 1)[1].split('?')[0]
            if path in ('react', 'react/'):
                route.fulfill(path=str(DIST / 'index.html'), content_type='text/html')
            elif path.startswith('react/assets/'):
                route.fulfill(path=str(DIST / path[len('react/assets/'):]))
            elif path == 'vendor/klinecharts.min.js':
                route.fulfill(path=str(KLINE), content_type='application/javascript')
            elif path == 'api/state':
                route.fulfill(json=state)
            elif path.startswith('api/chart/'):
                route.fulfill(json=_bars())
            else:
                route.fulfill(json=dict(enabled=False, armed=False, csrf='x', trading_blocked=False, shorts=[], longs=[]))

        pg.route('http://localhost:9999/**', handle)
        pg.goto('http://localhost:9999/react')
        pg.wait_for_selector('.pnl-plot svg')
        pg.wait_for_timeout(600)
        yield pg
        browser.close()


def test_no_console_errors(page):
    assert page.errors == []


@pytest.mark.parametrize('width', [1440, 1000, 700, 390])
def test_pnl_svg_uses_real_container_width(page, width):
    page.set_viewport_size(dict(width=width, height=900))
    page.wait_for_timeout(400)
    view_w, real_w = page.evaluate("()=>{const s=document.querySelector('.pnl-plot svg');return [Number(s.getAttribute('viewBox').split(' ')[2]),Math.round(s.getBoundingClientRect().width)]}")
    assert abs(view_w - real_w) <= 1


def test_pnl_labels_are_not_clipped_or_overlapping(page):
    for width in (1440, 390):
        page.set_viewport_size(dict(width=width, height=900))
        page.wait_for_timeout(400)
        boxes = page.evaluate("""()=>{const plot=document.querySelector('.pnl-plot').getBoundingClientRect();
          return [...document.querySelectorAll('.pnl-plot svg text')].map(t=>{const b=t.getBoundingClientRect();return {l:b.left,r:b.right,t:b.top,b:b.bottom,pl:plot.left,pr:plot.right,pt:plot.top,pb:plot.bottom}})}""")
        assert boxes
        assert all(b['b'] <= b['pb'] + 0.5 and b['t'] >= b['pt'] - 0.5 and b['l'] >= b['pl'] - 0.5 and b['r'] <= b['pr'] + 0.5 for b in boxes)
        bottom = max(b['t'] for b in boxes)
        xs = sorted((b for b in boxes if b['t'] >= bottom - 3), key=lambda b: b['l'])  # solo la fila del eje X
        assert len(xs) >= 2
        assert all(a['r'] <= b['l'] for a, b in zip(xs, xs[1:])), 'etiquetas del eje X superpuestas'


def test_pnl_y_ticks_are_round(page):
    page.set_viewport_size(dict(width=1440, height=900))
    page.wait_for_timeout(400)
    labels = page.evaluate("()=>[...document.querySelectorAll('.pnl-plot svg text')].map(t=>t.textContent).filter(t=>t.startsWith('$')||t.startsWith('-$'))")
    assert labels and all(re.fullmatch(r'-?\$[\d,]+(\.\d+)?', t) for t in labels)
    assert '$0' in labels


def test_exposure_is_neutral_and_radar_marks_selection(page):
    page.set_viewport_size(dict(width=1440, height=900))
    page.wait_for_timeout(300)
    assert page.locator('.kpi strong.neutral').count() == 1
    assert page.locator('.bottom tbody tr.selected').count() == 1
    assert page.locator('.bottom td.num').count() > 0
    align = page.evaluate("()=>getComputedStyle(document.querySelector('.bottom td.num')).textAlign")
    assert align == 'right'


def test_chart_footer_has_reset_button(page):
    assert page.locator('.chart-footer .chart-reset').count() == 1
