import json
import sqlite3

from pairs_desk.learning_data import DataPaths, load_learning_snapshot


def make_db(path, table='events'):
    con = sqlite3.connect(path)
    if table == 'events':
        con.execute('CREATE TABLE events (account TEXT, kind TEXT, identity TEXT, time INTEGER, payload TEXT)')
        con.execute('INSERT INTO events VALUES (?,?,?,?,?)', ('a', 'fills', '1', 100, json.dumps({'coin': 'AAA', 'time': 100})))
    con.commit()
    con.close()


def test_loader_reads_settings_and_sqlite_without_exposing_address(tmp_path):
    settings = tmp_path / 'settings.json'
    settings.write_text(json.dumps({'address': '0xprivate', 'pairs': [], 'closed_pairs': [{'long': 'AAA', 'short': 'BBB'}]}))
    ledger = tmp_path / 'ledger.sqlite3'
    make_db(ledger)

    snapshot = load_learning_snapshot(DataPaths(settings=settings, ledger=ledger))

    assert len(snapshot.closed_pairs) == 1
    assert snapshot.sources['ledger'].rows == 1
    assert 'address' not in snapshot.as_public_dict()


def test_loader_reports_corrupt_settings_without_writing(tmp_path):
    settings = tmp_path / 'settings.json'
    original = '{not-json'
    settings.write_text(original)

    snapshot = load_learning_snapshot(DataPaths(settings=settings))

    assert snapshot.closed_pairs == []
    assert snapshot.sources['settings'].error
    assert settings.read_text() == original


def test_loader_continues_when_sqlite_is_missing(tmp_path):
    settings = tmp_path / 'settings.json'
    settings.write_text(json.dumps({'pairs': [], 'closed_pairs': []}))

    snapshot = load_learning_snapshot(DataPaths(settings=settings, ledger=tmp_path / 'missing.sqlite3'))

    assert snapshot.closed_pairs == []
    assert snapshot.sources['ledger'].available is False


def test_loader_reads_market_pair_catalog(tmp_path):
    settings = tmp_path / 'settings.json'
    settings.write_text(json.dumps({'pairs': [], 'closed_pairs': []}))
    market = tmp_path / 'market.sqlite3'
    con = sqlite3.connect(market)
    con.execute('CREATE TABLE pairs (pair_id TEXT, long_instrument_id TEXT, short_instrument_id TEXT, label TEXT, active INTEGER, metadata_json TEXT)')
    con.execute('INSERT INTO pairs VALUES (?,?,?,?,?,?)', ('A__B', 'A', 'B', 'A/B', 1, '{}'))
    con.commit()
    con.close()

    snapshot = load_learning_snapshot(DataPaths(settings=settings, market=market))

    assert snapshot.market_pairs == [{'pair_id': 'A__B', 'long_instrument_id': 'A', 'short_instrument_id': 'B', 'label': 'A/B', 'active': 1, 'metadata_json': {}}]
    assert snapshot.sources['market'].available is True
