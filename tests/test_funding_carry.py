import pytest

import read_only_server as server
from pairs_desk.funding_carry import funding_rates, pair_funding_carry

PAYLOAD = [
    {'universe': [{'name': 'BTC'}, {'name': 'ETH'}, {'name': 'OLD', 'isDelisted': True}, {'name': 'BAD'}]},
    [{'funding': '0.0000125'}, {'funding': '-0.00002'}, {'funding': '0.01'}, {'funding': 'nan'}],
]


def test_rates_skip_delisted_and_non_finite():
    assert funding_rates(PAYLOAD) == {'BTC': 0.0000125, 'ETH': -0.00002}


@pytest.mark.parametrize('payload', [None, [], [{}, []], [{'universe': []}, None], 'x'])
def test_rates_tolerate_unexpected_shapes(payload):
    assert funding_rates(payload) == {}


def test_long_pays_positive_rate_and_short_receives_it():
    # Long BTC (tasa +) paga; short ETH (tasa -) también paga: ambos restan.
    out = pair_funding_carry('BTC', 'ETH', 1000, 1000, {'BTC': 0.0000125, 'ETH': -0.00002})
    per_hour = -0.0000125 * 1000 + -0.00002 * 1000
    assert out['funding_per_day_usd'] == pytest.approx(per_hour * 24)
    assert out['funding_per_day_usd'] < 0
    assert out['funding_apr_pct'] == pytest.approx(per_hour * 24 * 365 / 1000 * 100)
    assert out['funding_long_rate_pct_h'] == pytest.approx(0.00125)
    assert out['funding_short_rate_pct_h'] == pytest.approx(-0.002)
    assert out['funding_basis'] == 'estimado_tasa_actual'


def test_pair_collects_when_short_leg_has_higher_rate():
    out = pair_funding_carry('ETH', 'BTC', 1000, 1200, {'ETH': 0.00001, 'BTC': 0.00003})
    assert out['funding_per_day_usd'] == pytest.approx((-0.00001 * 1000 + 0.00003 * 1200) * 24)
    assert out['funding_per_day_usd'] > 0


def test_xyz_coin_resolves_with_or_without_prefix():
    with_prefix = pair_funding_carry('xyz:TSLA', 'BTC', 500, 500, {'xyz:TSLA': 0.00001, 'BTC': 0.0})
    bare = pair_funding_carry('xyz:TSLA', 'BTC', 500, 500, {'TSLA': 0.00001, 'BTC': 0.0})
    assert with_prefix['funding_per_day_usd'] == pytest.approx(bare['funding_per_day_usd'])


@pytest.mark.parametrize('args', [
    ('BTC', 'ETH', 1000, 1000, {}),
    ('BTC', 'ETH', 1000, 1000, None),
    ('BTC', 'ZZZ', 1000, 1000, {'BTC': 0.00001}),
    ('BTC', 'ETH', None, 1000, {'BTC': 0.00001, 'ETH': 0.00001}),
    ('BTC', 'ETH', float('nan'), 1000, {'BTC': 0.00001, 'ETH': 0.00001}),
    ('BTC', 'ETH', -5, 1000, {'BTC': 0.00001, 'ETH': 0.00001}),
])
def test_unverifiable_inputs_give_none_never_zero(args):
    out = pair_funding_carry(*args)
    assert out['funding_per_day_usd'] is None and out['funding_apr_pct'] is None
    assert out['funding_reason']


def test_missing_leg_is_named_in_reason():
    assert 'ZZZ' in pair_funding_carry('BTC', 'ZZZ', 1, 1, {'BTC': 0.0})['funding_reason']


def test_server_rates_survive_one_failed_request(monkeypatch):
    def fake_hl(payload):
        if payload.get('dex') == 'xyz':
            raise RuntimeError('timeout')
        return PAYLOAD
    monkeypatch.setattr(server, 'hl', fake_hl)
    assert server._current_funding_rates() == {'BTC': 0.0000125, 'ETH': -0.00002}


def test_server_rates_empty_when_everything_fails(monkeypatch):
    def failing(_payload):
        raise RuntimeError('sin red')
    monkeypatch.setattr(server, 'hl', failing)
    assert server._current_funding_rates() == {}
