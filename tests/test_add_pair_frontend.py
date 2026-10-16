from pathlib import Path
from fastapi.testclient import TestClient
from read_only_server import app
from pairs_desk.lifecycle import pair_leg_conflict


def test_frontend_new_pair_visible():
    html = (Path(__file__).parents[1] / 'frontend' / 'index.html').read_text()
    assert 'id="addPairOpen"' in html
    assert 'id="newPairLong"' in html
    assert 'id="newPairShort"' in html


def test_add_pair_requires_local_csrf():
    response = TestClient(app).post('/api/trade/pairs/add', json={
        'csrf': 'invalid', 'long': 'ZK', 'short': 'STRK',
    }, headers={'Origin': 'http://127.0.0.1:8510', 'Host': '127.0.0.1:8510'})
    assert response.status_code == 403


def test_closed_old_pair_does_not_block_reused_long():
    positions = {'LINK': {'szi':'4'}, 'PYTH': {'szi':'-100'}}
    assert not pair_leg_conflict('LINK', 'PYTH', [{'long':'LINK','short':'SAND'}], positions)


def test_active_pair_blocks_reused_leg():
    positions = {'LINK': {'szi':'4'}, 'SAND': {'szi':'-5'}, 'PYTH': {'szi':'-100'}}
    assert pair_leg_conflict('LINK', 'PYTH', [{'long':'LINK','short':'SAND'}], positions)
