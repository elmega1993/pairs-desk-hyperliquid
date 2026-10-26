from pairs_desk.context_fetch import api_coin, safe_cache_name


def test_api_coin_preserves_venue_and_normalizes_symbol():
    assert api_coin('xyz:NVDA') == 'xyz:NVDA'
    assert api_coin('XYZ:amd') == 'xyz:AMD'
    assert api_coin('sol') == 'SOL'


def test_cache_name_is_filesystem_safe():
    assert safe_cache_name('xyz:NVDA') == 'xyz_NVDA'
