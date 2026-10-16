from pairs_desk.frontend_archive import archive_frontend
from pairs_desk.storage import save_settings, load_settings


def test_frontend_close_persists_realized_and_is_idempotent(tmp_path):
    path = tmp_path / 'settings.json'
    cfg = {'address': '0x' + 'a'*40, 'pairs': [{'long':'AAA','short':'BBB'}], 'closed_pairs': []}
    save_settings(path, cfg)
    fills = []
    for sym, opening, closing, pnl in [('AAA','B','A',20), ('BBB','A','B',-4)]:
        fills += [
            {'coin':sym, 'time':1000,'tid':sym+'1','side':opening,'sz':'2','px':'10','fee':'0.5','closedPnl':'0','startPosition':'0'},
            {'coin':sym, 'time':2000,'tid':sym+'2','side':closing,'sz':'2','px':'11','fee':'0.5','closedPnl':str(pnl),'startPosition':'2' if opening=='B' else '-2'},
        ]
    _, changed = archive_frontend(path, cfg['address'], {}, fills, True, now=100, min_separation=5)
    assert not changed
    _, changed = archive_frontend(path, cfg['address'], {}, fills, True, now=101, min_separation=5)
    assert not changed
    out, changed = archive_frontend(path, cfg['address'], {}, fills, True, now=106, min_separation=5)
    assert changed
    assert not out['pairs']
    assert len(out['closed_pairs']) == 1
    assert out['closed_pairs'][0]['realized'] == 16
    assert out['closed_pairs'][0]['net_realized'] == 14
    assert 'events' in out['closed_pairs'][0]
    fresh, err = load_settings(path)
    assert err is None and len(fresh['closed_pairs']) == 1
    _, changed = archive_frontend(path, cfg['address'], {}, fills, True, now=120)
    assert not changed
    assert len(load_settings(path)[0]['closed_pairs']) == 1


def test_frontend_never_archives_partial_history(tmp_path):
    path = tmp_path / 'settings.json'
    cfg = {'address':'0x' + 'b'*40, 'pairs':[{'long':'AAA','short':'BBB'}], 'closed_pairs':[]}
    save_settings(path,cfg)
    for now in (100,110,120):
        _,changed = archive_frontend(path,cfg['address'],{},[],False,now=now)
        assert not changed
    assert len(load_settings(path)[0]['pairs']) == 1


def test_frontend_requires_distinct_network_snapshot(tmp_path):
    """A repeated cached read must not confirm a flat pair, even after TTL."""
    path = tmp_path / 'settings.json'
    address = '0x' + 'c' * 40
    save_settings(path, {'address': address, 'pairs': [{'long': 'AAA', 'short': 'BBB'}], 'closed_pairs': []})
    fills = []
    for coin, opening, closing in [('AAA', 'B', 'A'), ('BBB', 'A', 'B')]:
        fills.extend([
            {'coin': coin, 'time': 1000, 'tid': coin + '1', 'side': opening,
             'sz': '1', 'px': '10', 'fee': '0', 'closedPnl': '0', 'startPosition': '0'},
            {'coin': coin, 'time': 2000, 'tid': coin + '2', 'side': closing,
             'sz': '1', 'px': '11', 'fee': '0', 'closedPnl': '1',
             'startPosition': '1' if opening == 'B' else '-1'},
        ])
    for now in (100, 110, 120):
        _, changed = archive_frontend(path, address, {}, fills, True, now=now,
                                      snapshot_token='cached-response')
        assert not changed
    result, changed = archive_frontend(path, address, {}, fills, True, now=130,
                                       snapshot_token='new-network-response')
    assert changed
    assert len(result['closed_pairs']) == 1


def test_incomplete_fills_reset_pending_confirmation(tmp_path):
    path = tmp_path / 'settings.json'
    address = '0x' + 'd' * 40
    save_settings(path, {'address': address, 'pairs': [{'long': 'AAA', 'short': 'BBB'}], 'closed_pairs': []})
    archive_frontend(path, address, {}, [], True, now=100, snapshot_token='first')
    archive_frontend(path, address, {}, [], False, now=110, snapshot_token='failed')
    _, changed = archive_frontend(path, address, {}, [], True, now=120, snapshot_token='second')
    assert not changed
