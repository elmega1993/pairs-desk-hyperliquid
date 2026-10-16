import json
from pathlib import Path

from pairs_desk.storage import load_settings, save_settings


def test_bad_pair_blocks_save_instead_of_silent_drop(tmp_path: Path):
    p = tmp_path / 'settings.json'
    p.write_text(json.dumps({'address': 'x', 'pairs': [{'long': 'ETH'}, {'long': 'ETH', 'short': 'BTC'}]}))
    data, err = load_settings(p)
    assert err is not None
    assert data['pairs'] == [{'long': 'ETH', 'short': 'BTC'}]
    assert data['_invalid_pairs'] == [{'long': 'ETH'}]


def test_corrupt_json_reports_error(tmp_path: Path):
    p = tmp_path / 'settings.json'; p.write_text('{bad')
    data, err = load_settings(p)
    assert err and data['address'] == '' and data['pairs'] == [] and data['closed_pairs'] == []


def test_atomic_save_and_backup(tmp_path: Path):
    p = tmp_path / 'settings.json'
    save_settings(p, {'address': 'a', 'pairs': []})
    save_settings(p, {'address': 'b', 'pairs': []})
    assert json.loads(p.read_text())['address'] == 'b'
    assert json.loads(p.with_suffix('.json.bak').read_text())['address'] == 'a'


def test_load_settings_rejects_unexpected_shapes(tmp_path: Path):
    for content in ('[]', '{"pairs": null}', '{"address": null, "pairs": []}'):
        p = tmp_path / 'settings.json'
        p.write_text(content)
        data, err = load_settings(p)
        assert err is not None
        assert data['address'] == '' and data['pairs'] == [] and data['closed_pairs'] == []
