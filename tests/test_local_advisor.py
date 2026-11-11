import json
import pytest
from pairs_desk.local_advisor import Advisor, AdvisorError, build_snapshot

T = 1_800_000_000_000


def state():
    return {'last_updated_ms': T, 'address': 'PRIVATE_ADDRESS', 'csrf': 'PRIVATE_TOKEN',
            'summary': {'exposure': 100, 'api_key': 'PRIVATE_KEY'},
            'pairs': [{'id': 'BTC|ETH', 'long': 'BTC', 'short': 'ETH', 'pnl': 5,
                       'trade_note': 'PRIVATE_NOTE'}], 'closed_pairs': [],
            'strategy': {'net_pnl': 42, 'daily': [{'date': '2026-11-10', 'pnl': None}],
                         'cost_details': {'funding_paid': -5, 'funding_received': 2, 'assets': []}}}


def test_snapshot_excludes_identity_secrets_and_free_text_notes():
    snapshot = build_snapshot(state(), {'BTC': {'szi': '1', 'positionValue': '100', 'secret': 'PRIVATE_SECRET'}})
    wire = json.dumps(snapshot)
    assert 'PRIVATE' not in wire
    assert snapshot['positions'][0]['coin'] == 'BTC'
    assert snapshot['strategy']['daily'][0]['pnl'] is None
    assert snapshot['strategy']['net_pnl'] == 42


def test_stale_or_missing_snapshot_is_rejected():
    a = Advisor(clock=lambda: T)
    with pytest.raises(AdvisorError, match='Actualiz'):
        a.snapshot()
    a.observe_state(state())
    assert a.snapshot()['as_of_ms'] == T
    a.clock = lambda: T + 90_001
    with pytest.raises(AdvisorError, match='Actualiz'):
        a.snapshot()


def test_tools_reject_orders_unknown_ids_and_extra_arguments():
    calls = []
    a = Advisor(clock=lambda: T, candles=lambda **kw: calls.append(kw))
    a.observe_state(state())
    snap = a.snapshot()
    for name, args in [('execute_order', {}), ('pair_candles', {'pair_id': 'X|Y'}),
                       ('positions', {'path': '/etc/passwd'})]:
        with pytest.raises(AdvisorError):
            a.tool(name, args, snap)
    assert calls == []
    assert a.tool('positions', {}, snap)['positions'][0]['pnl'] == 5


def test_strategy_tool_preserves_missing_data_and_validates_section():
    a = Advisor(clock=lambda: T)
    a.observe_state(state())
    result = a.tool('strategy', {'section': 'daily'}, a.snapshot())
    assert result['data'][0]['pnl'] is None
    with pytest.raises(AdvisorError):
        a.tool('strategy', {'section': 'config'}, a.snapshot())


def test_history_and_ledger_are_bounded_and_funding_is_sanitized():
    a = Advisor(clock=lambda: T, ledger=lambda kind, account: [
        {'time': T, 'delta': {'coin': 'BTC', 'usdc': '-2', 'user': 'PRIVATE_ADDRESS'}, 'hash': 'PRIVATE_HASH'}])
    a.observe_state(state())
    result = a.tool('ledger', {'kind': 'funding', 'limit': 20}, a.snapshot())
    assert 'PRIVATE' not in json.dumps(result)
    assert result['rows'][0]['delta']['usdc'] == '-2'
    with pytest.raises(AdvisorError):
        a.tool('ledger', {'kind': 'funding', 'limit': 10000}, a.snapshot())


class Response:
    def __init__(self, data=None, lines=()): self.data, self.lines = data, lines
    def raise_for_status(self): pass
    def json(self): return self.data
    def iter_lines(self):
        for line in self.lines: yield json.dumps(line).encode()
    def close(self): pass


class Transport:
    def __init__(self, rounds=(), cloud=False): self.rounds, self.cloud, self.sent = iter(rounds), cloud, []
    def post(self, url, **kwargs):
        if url.endswith('/api/show'):
            return Response({'remote_host': 'https://example.com'} if self.cloud else {'capabilities': ['completion', 'tools']})
        self.sent.append(kwargs['json'])
        return Response(lines=next(self.rounds))


def test_tool_round_trip_streams_answer_and_records_real_sources():
    transport = Transport([
        [{'message': {'content': '', 'tool_calls': [{'function': {'name': 'strategy', 'arguments': {'section': 'costs'}}}]}, 'done': True}],
        [{'message': {'content': 'El funding neto es negativo.'}, 'done': False}, {'message': {'content': ''}, 'done': True}],
    ])
    a = Advisor(clock=lambda: T, transport=transport)
    a.observe_state(state())
    events = list(a.stream('Revisá los costos', []))
    assert ''.join(e.get('text', '') for e in events if e['type'] == 'token') == 'El funding neto es negativo.'
    assert events[-1]['type'] == 'done'
    assert any(s['name'] == 'strategy' for s in events[-1]['sources'])
    assert transport.sent[0]['think'] is False
    assert transport.sent[0]['stream'] is True
    assert transport.sent[1]['messages'][-1]['role'] == 'tool'
    assert not a.busy.locked()


def test_cloud_models_never_receive_account_data():
    transport = Transport(cloud=True)
    a = Advisor(clock=lambda: T, transport=transport)
    a.observe_state(state())
    with pytest.raises(AdvisorError, match='local'):
        list(a.stream('Resumen', []))
    assert transport.sent == []
    assert not a.busy.locked()


def test_empty_or_truncated_output_is_not_claimed_as_complete():
    transport = Transport([[{'message': {'content': ''}, 'done': True}]])
    a = Advisor(clock=lambda: T, transport=transport)
    a.observe_state(state())
    with pytest.raises(AdvisorError, match='respuesta'):
        list(a.stream('Resumen', []))
    assert not a.busy.locked()


def test_ledger_is_pinned_to_snapshot_account_and_reports_coverage():
    accounts = []
    a = Advisor(clock=lambda: T, ledger=lambda kind, account: accounts.append(account) or {
        'rows': [], 'coverage': {'complete': False, 'covered_until': T-5000}})
    a.observe_state(state(), account='account-A')
    snapshot = a.snapshot()
    a.observe_state(state(), account='account-B')
    result = a.tool('ledger', {}, snapshot)
    assert accounts == ['account-A']
    assert result['coverage']['complete'] is False
    assert result['as_of_ms'] == T-5000


def test_provider_failure_is_an_unavailable_tool_not_an_internal_exception():
    def failure(**kwargs): raise RuntimeError('PRIVATE_DETAILS')
    a = Advisor(clock=lambda: T, candles=failure)
    a.observe_state(state())
    with pytest.raises(AdvisorError, match='disponibles') as error:
        a.tool('pair_candles', {'pair_id': 'BTC|ETH', 'limit': 10}, a.snapshot())
    assert 'PRIVATE' not in str(error.value)


def test_disconnect_and_cancel_release_generation_slot():
    transport = Transport([[{'message': {'content': 'Parcial'}, 'done': False}]])
    a = Advisor(clock=lambda: T, transport=transport)
    a.observe_state(state())
    with pytest.raises(AdvisorError, match='interrump'):
        list(a.stream('Resumen', []))
    assert not a.busy.locked()
    iterator = a.stream('Resumen', [])
    assert next(iterator)['type'] == 'start'
    iterator.close()
    assert not a.busy.locked()


def test_empty_reconstructed_diary_falls_back_to_official_rows():
    a = Advisor(clock=lambda: T)
    data = state()
    data['strategy']['reconstructed_daily'] = []
    a.observe_state(data)
    result = a.tool('strategy', {'section': 'daily'}, a.snapshot())
    assert result['total'] == 1
    assert result['data'][0]['date'] == '2026-11-10'
    assert result['basis'] == 'muestras oficiales'


def test_cost_assets_are_paginated_without_losing_verified_totals():
    a = Advisor(clock=lambda: T)
    data = state()
    data['strategy']['fees'] = 15
    data['strategy']['cost_details']['assets'] = [{'coin': str(i), 'impact': -i} for i in range(100)]
    a.observe_state(data)
    result = a.tool('strategy', {'section': 'costs', 'limit': 5}, a.snapshot())
    assert len(result['data']['cost_details']['assets']) == 5
    assert result['data']['cost_details']['assets_total'] == 100
    assert result['data']['fees'] == 15
