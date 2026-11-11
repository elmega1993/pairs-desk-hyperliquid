import pytest
from pairs_desk.ai.pair_analysis import pair_review

NOW=1_800_000_000_000


def snapshot():
    return {'as_of_ms':NOW,'pairs':[{'id':'xyz:USAR|xyz:NATGAS','long':'xyz:USAR','short':'xyz:NATGAS',
        'ratio':2.208,'entry_ratio':2.475,'ratio_change':-10.79,'long_usd':647.,'short_usd':772.,
        'pnl':-76.,'funding':-158.,'fees':3.,'liq':22.}],
        'positions':[], 'account':{'margin_pct':98.62},
        'analytics':{'as_of_ms':NOW,'pairs':{'xyz:USAR|xyz:NATGAS':{'status':'ok','z_log':-2.1,'regime':'Tendencial',
            'health':{'status':'non_stationary'},'age_vs_half_life':2.3,'funding_per_day_usd':-.5}}}}


def test_pair_units_do_not_confuse_ratio_funding_margin_and_liquidity():
    result=pair_review(snapshot(), 'xyz:USAR|xyz:NATGAS', NOW)
    observed=result['observations']
    assert observed['ratio_change_since_entry_pct']==-10.79
    assert observed['historical_funding_net_usd']==-158
    assert result['account_context']['margin_used_pct']==98.62
    assert result['liquidity']['status']=='unavailable'
    assert result['statistics']['z_log']==-2.1
    assert result['carry']['estimated_per_day_usd']==-.5


def test_unequal_notionals_expose_hidden_directional_bet_at_unchanged_ratio():
    result=pair_review(snapshot(),'xyz:USAR|xyz:NATGAS',NOW)
    assert result['hedge']['net_directional_usd']==-125
    assert result['hedge']['bias']=='net_short'
    assert result['hedge']['net_pct_of_gross']==pytest.approx(-125/1419*100)
    common=next(s for s in result['stress_tests'] if s['name']=='both_up_5pct')
    assert common['ratio_change_pct']==pytest.approx(0)
    assert common['incremental_pnl_usd']==pytest.approx(-6.25)
    assert result['alternatives']['reduce_larger_leg_to_equal_notionals']['reduction_usd']==125


def test_missing_or_stale_statistics_never_assert_mean_reversion_or_zero_carry():
    snap=snapshot();snap['analytics']['as_of_ms']=NOW-180001
    result=pair_review(snap,'xyz:USAR|xyz:NATGAS',NOW)
    assert result['statistics']['status']=='unavailable'
    assert result['carry']['estimated_per_day_usd'] is None
    assert 'mean_reversion_supported' not in result['statistics']


def test_shared_holdings_explicitly_prevent_attribution_as_independent_pair():
    snap=snapshot();snap['pairs'].append({'id':'xyz:USAR|BTC','long':'xyz:USAR','short':'BTC'})
    result=pair_review(snap,'xyz:USAR|xyz:NATGAS',NOW)
    assert result['attribution']['shared_assets']==['xyz:USAR']
    assert result['attribution']['exclusive'] is False


def test_missing_notionals_do_not_become_zero_or_produce_scenarios():
    snap=snapshot();snap['pairs'][0]['short_usd']=None
    result=pair_review(snap,'xyz:USAR|xyz:NATGAS',NOW)
    assert result['hedge']['net_directional_usd'] is None
    assert result['stress_tests']==[]
    assert result['alternatives']['reduce_larger_leg_to_equal_notionals'] is None


def test_closed_record_cannot_produce_current_position_scenarios():
    snap=snapshot();snap['closed_pairs']=snap['pairs'];snap['pairs']=[]
    with pytest.raises(ValueError,match='cerrado'):
        pair_review(snap,'xyz:USAR|xyz:NATGAS',NOW)
