from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/'react_frontend'/'src'

def test_radar_selection_never_scrolls_to_top():
    app=(SRC/'App.tsx').read_text()
    assert 'window.scrollTo' not in app
    assert '<PositionRadar pairs={pairs}' in app
    assert 'onSelect={setSelected}' in app

def test_sidebar_sorting_shares_radar_state():
    app=(SRC/'App.tsx').read_text()
    sidebar=(SRC/'components'/'PositionList.tsx').read_text()
    assert '<PositionList pairs={pairs}' in app
    assert 'onSort={changeSort}' in app
    for field in ['pnl:desc','realized:desc','pnl_pct:desc','size:desc','funding:desc','name:asc']:
        assert field in sidebar
    assert 'aria-label="Ordenar posiciones"' in sidebar
    assert 'window.scrollTo' not in sidebar

def test_sort_does_not_change_pair_or_scroll():
    app=(SRC/'App.tsx').read_text()
    assert 'const changeSort=(key:string)=>setSort(previous=>key.includes(\':\')?key:nextSort(previous,key));' in app
    assert 'overflow-anchor:none' in (SRC/'style.css').read_text()
