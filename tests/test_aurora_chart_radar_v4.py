from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def test_pnl_chart_clipped_and_axis():
    js=(ROOT/'aurora/aurora.js').read_text()
    css=(ROOT/'aurora/aurora.css').read_text()
    assert 'pnl-plot-clip' in js
    assert 'money(v)' in js
    assert 'toLocaleDateString' in js
    assert '.pnl-chart svg{width:100%;height:100%;overflow:hidden' in css

def test_radar_sort_and_full_list():
    html=(ROOT/'aurora/index.html').read_text()
    js=(ROOT/'aurora/aurora.js').read_text()
    for field in ('pnl_desc','realized_desc','funding_desc','pct_desc','size_desc','name'):
        assert f'value="{field}"' in html
    assert 'for(const p of ordered)' in js

def test_net_subtotal_is_distinguished():
    backend=(ROOT/'read_only_server.py').read_text()
    js=(ROOT/'aurora/aurora.js').read_text()
    assert "summary['net_known_subtotal']" in backend
    assert 'Subtotal conocido' in js
    assert 's.total ?? s.net_known_subtotal' in js
