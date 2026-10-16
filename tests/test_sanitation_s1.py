"""Conservative validation of analytical ADD recommendations (no execution)."""
import math
from pairs_desk.levels_v3 import calculate


def test_low_liquidation_blocks_add():
    r = calculate(1, math.log(1.5), .03, 14, 'stationary', 'Rango', z=-1, liq=20, n_eff=1000)
    assert r['add_allowed'] is False
    assert 'liquidación' in r['level_reasons']['add1']


def test_unknown_liquidation_is_explicit():
    r = calculate(1, math.log(1.5), .03, 14, 'stationary', 'Rango', z=-1)
    assert any('no verificada' in warning for warning in r['add_warnings'])
    assert any('Correlación' in warning for warning in r['add_warnings'])


def test_invalid_fraction_and_nonfinite_z():
    r = calculate(1, math.log(1.5), .03, 14, 'stationary', 'Rango', z=-1, add_fraction=-1)
    assert r['status'] == 'unavailable'
    assert not r['levels']
    r = calculate(1, math.log(1.5), .03, 14, 'stationary', 'Rango', z=float('nan'))
    assert not r['add_allowed']


def test_invalid_numeric_input_is_unavailable():
    assert calculate('bad', 0, .02, 14, 'stationary', 'Rango')['status'] == 'unavailable'
