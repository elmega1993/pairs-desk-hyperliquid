import pytest

import read_only_server as server
from pairs_desk.funding_carry import aggregate_funding_projection, funding_rates, pair_funding_carry

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


def test_aggregate_funding_projection_sums_active_pairs_and_horizons():
    pairs = [
        {'long': 'BTC', 'short': 'ETH', 'long_usd': 1000, 'short_usd': 1000},
        {'long': 'ETH', 'short': 'BTC', 'long_usd': 500, 'short_usd': 500},
    ]
    result = aggregate_funding_projection(pairs, {'BTC': 0.00001, 'ETH': 0.0})

    assert result['available'] is True
    assert result['per_day_usd'] == pytest.approx(-0.12)
    assert result['per_week_usd'] == pytest.approx(-0.84)
    assert result['per_30d_usd'] == pytest.approx(-3.6)


def test_aggregate_funding_projection_stays_unavailable_when_one_pair_is_missing_data():
    pairs = [
        {'long': 'BTC', 'short': 'ETH', 'long_usd': 1000, 'short_usd': 1000},
        {'long': 'BTC', 'short': 'MISSING', 'long_usd': 500, 'short_usd': 500},
    ]

    result = aggregate_funding_projection(pairs, {'BTC': 0.00001, 'ETH': 0.0})

    assert result['available'] is False
    assert result['per_day_usd'] is None


def test_server_rates_survive_one_failed_request(monkeypatch):
    def fake_hl(payload):
        if payload.get('dex') == 'xyz':
            raise RuntimeError('timeout')
        return PAYLOAD
    monkeypatch.setattr(server, 'hl', fake_hl)
    monkeypatch.setattr(server, '_FUNDING_RATE_CACHE', None)
    assert server._current_funding_rates() == {'BTC': 0.0000125, 'ETH': -0.00002}


def test_server_rates_empty_when_everything_fails(monkeypatch):
    def failing(_payload):
        raise RuntimeError('sin red')
    monkeypatch.setattr(server, 'hl', failing)
    monkeypatch.setattr(server, '_FUNDING_RATE_CACHE', None)
    assert server._current_funding_rates() == {}


def test_server_rates_are_cached_for_the_projection_ttl(monkeypatch):
    calls = []

    def fake_hl(payload):
        calls.append(payload)
        return PAYLOAD

    monkeypatch.setattr(server, 'hl', fake_hl)
    monkeypatch.setattr(server, '_FUNDING_RATE_CACHE', None)

    assert server._current_funding_rates(now_ms=1_000) == {'BTC': 0.0000125, 'ETH': -0.00002}
    assert server._current_funding_rates(now_ms=2_000) == {'BTC': 0.0000125, 'ETH': -0.00002}
    assert len(calls) == 2
    server._current_funding_rates(now_ms=server.FUNDING_RATE_TTL_MS + 2_000)
    assert len(calls) == 4


def test_projection_exposes_signed_long_short_and_pair_contributions():
    result = aggregate_funding_projection([
        {'long': 'BTC', 'short': 'ETH', 'long_usd': 1000, 'short_usd': 500},
    ], {'BTC': 0.00001, 'ETH': 0.00003})
    assert result['long_per_day_usd'] == pytest.approx(-0.24)
    assert result['short_per_day_usd'] == pytest.approx(0.36)
    assert result['per_day_usd'] == pytest.approx(0.12)
    assert result['pairs'][0]['long'] == 'BTC'
    assert result['pairs'][0]['per_day_usd'] == pytest.approx(0.12)


def test_projection_incomplete_never_presents_partial_leg_sums():
    result = aggregate_funding_projection([
        {'long': 'BTC', 'short': 'MISSING', 'long_usd': 1000, 'short_usd': 500},
    ], {'BTC': 0.00001})
    assert result['long_per_day_usd'] is None
    assert result['short_per_day_usd'] is None
    assert result['pairs'] is None


def test_projection_without_positions_has_zero_leg_totals():
    result = aggregate_funding_projection([], {})
    assert result['long_per_day_usd'] == result['short_per_day_usd'] == 0
    assert result['pairs'] == []


def test_account_projection_counts_shared_positions_once_and_includes_unpaired_assets():
    pairs = [
        {'long': 'BTC', 'short': 'ETH', 'long_usd': 1000, 'short_usd': 500},
        {'long': 'BTC', 'short': 'SOL', 'long_usd': 1000, 'short_usd': 500},
    ]
    positions = {
        'BTC': {'szi': '1', 'positionValue': '1000'},
        'ETH': {'szi': '-1', 'positionValue': '-500'},
        'SOL': {'szi': '-1', 'positionValue': '-500'},
        'UNPAIRED': {'szi': '1', 'positionValue': '200'},
    }
    out = aggregate_funding_projection(pairs, {'BTC': .00001, 'ETH': 0, 'SOL': 0, 'UNPAIRED': .00001}, positions=positions)
    assert out['long_per_day_usd'] == pytest.approx(-.288)
    assert out['short_per_day_usd'] == 0
    assert out['per_day_usd'] == pytest.approx(-.288)
    assert out['pairs'] is None
    assert out['reason']


def test_account_projection_hides_total_if_unpaired_asset_rate_is_missing():
    out = aggregate_funding_projection([], {}, positions={'BTC': {'szi': '1', 'positionValue': '1000'}})
    assert out['available'] is False
    assert out['per_day_usd'] is None
