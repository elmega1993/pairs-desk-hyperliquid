import pytest
from pairs_desk.native_twap import NativeTwapStore, overlap_sql

ORDERS = [dict(coin='BTC', is_buy=True, reduce_only=False, size=1, original_size=2, mark=200),
          dict(coin='xyz:GOLD', is_buy=False, reduce_only=False, size=2, original_size=3, mark=200)]


def test_reservation_is_shared_and_durable(tmp_path):
    path = tmp_path / 'orders.sqlite3'
    store = NativeTwapStore(path)
    job = store.reserve('ACCOUNT', 'pair', 'Aumentar', 30, False, ORDERS, now_ms=1000)
    assert 'account' not in job
    assert NativeTwapStore(path).overlap('account', ['BTC'])
    with pytest.raises(RuntimeError):
        store.reserve('account', 'other', 'Aumentar', 30, False, ORDERS)
    assert not store.overlap('different', ['BTC'])


def test_validation_precedes_reservation(tmp_path):
    store = NativeTwapStore(tmp_path / 'db')
    for minutes in [True, 4, 10081, 5.5]:
        with pytest.raises(ValueError):
            store.reserve('a', 'p', 'Aumentar', minutes, False, ORDERS)
    assert store.list('a') == []

from types import SimpleNamespace
from eth_account import Account
from pairs_desk.native_twap import submit_pair, cancel_pair
from pairs_desk import trade_journal


def ack(tid):
    return {'status': 'ok', 'response': {'type': 'twapOrder', 'data': {'status': {'running': {'twapId': tid}}}}}


class FakeExchange:
    def __init__(self, responses):
        self.wallet = Account.from_key('0x' + '11' * 32)
        self.vault_address, self.expires_after = None, None
        self.base_url = 'https://api.hyperliquid.xyz'
        self.responses, self.posts, self.reads = list(responses), [], []
        self.info = SimpleNamespace(name_to_asset=lambda c: {'BTC': 0, 'xyz:GOLD': 100001}[c],
                                    asset_to_sz_decimals={0: 3, 100001: 2}, user_state=self.state)

    def state(self, account, dex):
        self.reads.append(dex)
        return {'assetPositions': [{'position': {'coin': c, 'szi': s}} for c, s in [('BTC', '2'), ('xyz:GOLD', '-3')]]}

    def _post_action(self, action, signature, nonce):
        assert len(self.reads) == 2  # Every leg preflights before any submission.
        assert signature and 'r' in signature
        self.posts.append((action, nonce))
        result = self.responses.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


def execute(tmp_path, responses, **kwargs):
    store, ex = NativeTwapStore(tmp_path / 'db'), FakeExchange(responses)
    job = submit_pair(store, 'a', 'pair', 'Aumentar', kwargs.pop('orders', ORDERS), 30, False, 'unused',
                      exchange_factory=lambda *_: ex, clock=lambda: 100000, **kwargs)
    return store, ex, job


def test_posts_exact_native_actions_prepared_sizes_and_monotonic_nonces(tmp_path):
    orders = [dict(o, size=o['size'] + .00099) for o in ORDERS]
    store, ex, job = execute(tmp_path, [ack(10), ack(20)], orders=orders)
    assert job['status'] == 'running'
    assert ex.posts[0][0] == {'type': 'twapOrder', 'twap': {'a': 100001, 'b': False, 's': '2', 'r': False, 'm': 30, 't': False}}
    assert ex.posts[1][0]['twap']['s'] == '1'
    assert ex.posts[1][1] > ex.posts[0][1]
    assert [l['asset'] for l in job['legs']] == [100001, 0]
    assert [l['twap_id'] for l in NativeTwapStore(store.path).get('a', job['id'])['legs']] == [10, 20]


@pytest.mark.parametrize('response,status', [(TimeoutError('SECRET key'), 'uncertain'),
                                           ({'status': 'err', 'response': 'SECRET key'}, 'rejected'),
                                           ({'status': 'ok'}, 'uncertain')])
def test_first_ambiguous_or_rejected_stops_second_without_persisting_raw_errors(tmp_path, response, status):
    store, ex, job = execute(tmp_path, [response])
    assert len(ex.posts) == 1
    assert job['status'] == status
    assert 'SECRET' not in str(job)
    assert store.overlap('a', ['BTC']) == (status == 'uncertain')
    assert cancel_pair(store, 'a', job['id'], 'unused', exchange_factory=lambda *_: ex)['status'] == status
    assert len(ex.posts) == 1


@pytest.mark.parametrize('response,expected', [({'status': 'err', 'response': 'no'}, 'running'),
                                             (TimeoutError(), 'uncertain')])
def test_second_failure_cancels_first_without_inventing_rollback(tmp_path, response, expected):
    cancelled = {'status': 'ok', 'response': {'type': 'twapCancel', 'data': {'status': 'success'}}}
    store, ex, job = execute(tmp_path, [ack(10), response, cancelled])
    assert len(ex.posts) == 3
    assert ex.posts[-1][0] == {'type': 'twapCancel', 'a': 100001, 't': 10}
    assert job['legs'][0]['status'] == 'cancel_requested'
    assert job['legs'][0]['executed_size'] is None
    assert job['status'] == expected
    assert store.overlap('a', ['BTC'])


def test_preflight_failure_second_leg_posts_nothing(tmp_path):
    store, ex = NativeTwapStore(tmp_path / 'db'), FakeExchange([])
    ex.info.asset_to_sz_decimals.pop(0)
    with pytest.raises(KeyError):
        submit_pair(store, 'a', 'p', 'Aumentar', ORDERS, 30, False, 'unused', exchange_factory=lambda *_: ex)
    assert ex.posts == [] and store.list('a') == []


def test_reserved_before_send_crash_recovers_without_resubmitting(tmp_path):
    store = NativeTwapStore(tmp_path / 'db')
    job = store.reserve('a', 'p', 'Aumentar', 30, False, ORDERS, now_ms=100000)
    store._leg(job['id'], 0, 100000, status='submitting', before_send_ms=100000)
    restarted = NativeTwapStore(store.path)
    assert restarted.get('a', job['id'])['status'] == 'uncertain'
    signature = {'coin': 'BTC', 'side': 'B', 'sz': '1', 'minutes': 30, 'randomize': False, 'reduceOnly': False, 'timestamp': 100100,
                 'executedSz': '0.2', 'executedNtl': '20'}
    restarted.ingest_state('a', '', [[99, signature]], 101000)
    recovered = restarted.get('a', job['id'])
    assert recovered['legs'][0]['twap_id'] == 99
    assert recovered['legs'][0]['executed_size'] == .2
    assert recovered['legs'][1]['status'] == 'pending'
    assert restarted.overlap('a', ['BTC'])


def test_cancel_ack_stays_nonterminal_until_history_and_preserves_partial(tmp_path):
    store, ex, job = execute(tmp_path, [ack(10), ack(20)])
    ex.responses = [{'status': 'ok', 'response': {'data': {'status': 'success'}}}] * 2
    cancelled = cancel_pair(store, 'a', job['id'], 'unused', exchange_factory=lambda *_: ex, clock=lambda: 101000)
    assert all(l['status'] == 'cancel_requested' for l in cancelled['legs'])
    assert store.overlap('a', ['BTC'])
    history = [{'twapId': tid, 'state': {'coin': coin, 'executedSz': size, 'executedNtl': '10'},
                'status': {'status': 'terminated', 'description': 'SECRET'}, 'time': 102000}
               for tid, coin, size in [(10, 'xyz:GOLD', '.1'), (20, 'BTC', '0')]]
    store.ingest_history('a', history, 102001)
    final = store.get('a', job['id'])
    assert final['status'] == 'partial' and final['legs'][0]['executed_size'] == .1
    assert not store.overlap('a', ['BTC']) and 'SECRET' not in str(final)


def test_state_scopes_dex_and_absence_is_uncertain_never_finished(tmp_path):
    store, _, job = execute(tmp_path, [ack(10), ack(20)])
    store.ingest_state('different', '', [], 100500)
    assert store.get('a', job['id'])['status'] == 'running'
    store.ingest_state('a', '', [], 100500)
    current = store.get('a', job['id'])
    assert current['legs'][0]['status'] == 'running'
    assert current['legs'][1]['status'] == 'uncertain'
    store.ingest_state('a', '', [[20, {'coin': 'BTC', 'executedSz': '.4', 'executedNtl': '4'}]], 101000)
    store.ingest_state('a', '', [], 100700)
    assert store.get('a', job['id'])['legs'][1]['status'] == 'running'


def test_complete_requires_both_terminal_exchange_status_and_quantities(tmp_path):
    store, _, job = execute(tmp_path, [ack(10), ack(20)])
    for dex, tid, coin, qty in [('xyz', 10, 'xyz:GOLD', '2'), ('', 20, 'BTC', '1')]:
        store.ingest_state('a', dex, [[tid, {'coin': coin, 'executedSz': qty, 'executedNtl': '100'}]], 101000)
    assert store.get('a', job['id'])['status'] == 'running'
    events = [{'twapId': tid, 'state': {'coin': coin}, 'status': {'status': 'finished'}, 'time': 102000}
              for tid, coin in [(10, 'xyz:GOLD'), (20, 'BTC')]]
    store.ingest_history('a', events, 102000)
    assert store.get('a', job['id'])['status'] == 'complete'
    store.ingest_state('a', '', [], 103000)
    assert store.get('a', job['id'])['status'] == 'complete'


def test_finished_partial_is_incomplete_and_stale_history_cannot_regress(tmp_path):
    store, _, job = execute(tmp_path, [ack(10), ack(20)])
    events = [{'twapId': tid, 'state': {'coin': coin, 'executedSz': '.1'}, 'status': {'status': 'finished'}, 'time': 102000}
              for tid, coin in [(10, 'xyz:GOLD'), (20, 'BTC')]]
    store.ingest_history('a', events, 103000)
    assert store.get('a', job['id'])['status'] == 'incomplete'
    store.ingest_history('a', [{'twapId': 10, 'state': {'coin': 'xyz:GOLD'}, 'status': {'status': 'activated'}, 'time': 101000}], 104000)
    assert store.get('a', job['id'])['status'] == 'incomplete'


def test_history_without_id_requires_exact_unique_signature(tmp_path):
    store, _, job = execute(tmp_path, [ack(10), ack(20)])
    state = dict(coin='BTC', side='B', sz='1', minutes=30, randomize=False, reduceOnly=False, timestamp=100000, executedSz='1')
    event = dict(state=state, status={'status': 'finished'}, time=101000)
    store.ingest_history('a', [dict(event, state=dict(state, sz='99'))], 101000)
    assert store.get('a', job['id'])['legs'][1]['status'] == 'running'
    store.ingest_history('a', [event], 101000)
    assert store.get('a', job['id'])['legs'][1]['status'] == 'finished'


def test_fill_ids_dedup_coin_tid_order_and_scope_without_hash_grouping(tmp_path):
    store, _, job = execute(tmp_path, [ack(10), ack(20)])
    rows = [{'twapId': tid, 'fill': {'coin': coin, 'tid': trade, 'sz': '.1', 'px': '20', 'time': ts, 'hash': '0x0'}}
            for tid, coin, trade, ts in [(10, 'xyz:GOLD', 1, 100002), (20, 'BTC', 1, 100003), (20, 'BTC', 2, 100001)]]
    store.ingest_fills('other', rows, 101000)
    assert store.fills('a', job['id'])['total'] == 0
    store.ingest_fills('a', rows + [rows[0]], 101000)
    store.ingest_fills('a', rows, 101001)
    result = store.fills('a', job['id'], limit=2)
    assert result['total'] == 3 and len(result['items']) == 2
    assert result['items'][0]['time'] == 100003
    assert store.fill_keys('a') == {('xyz:GOLD', '1'), ('BTC', '1'), ('BTC', '2')}
    assert store.get('a', job['id'])['legs'][1]['executed_size'] == .2
    assert store.fills('other', job['id']) is None


def test_immediate_pending_blocks_reserve_and_native_helper_blocks_immediate(tmp_path):
    store = NativeTwapStore(tmp_path / 'db')
    conn = trade_journal.connect(store.path)
    attempt = trade_journal.begin(conn, 'a', 'p', 'Aumentar', ORDERS)
    with pytest.raises(RuntimeError):
        store.reserve('a', 'p', 'Aumentar', 30, False, ORDERS)
    trade_journal.finish(conn, attempt, 'complete')
    store.reserve('a', 'p', 'Aumentar', 30, False, ORDERS)
    conn.execute('BEGIN IMMEDIATE')
    assert overlap_sql(conn, 'a', ['BTC'])
    conn.rollback()
    conn.close()


def test_cancel_failure_remains_blocking_and_never_resends_unknown_order(tmp_path):
    store, ex, job = execute(tmp_path, [ack(10), TimeoutError(), TimeoutError()])
    assert job['status'] == 'uncertain'
    assert job['legs'][0]['status'] == 'uncertain'
    assert len(ex.posts) == 3
    ex.responses = [{'status': 'ok', 'response': {'data': {'status': 'success'}}}]
    result = cancel_pair(store, 'a', job['id'], 'unused', exchange_factory=lambda *_: ex, clock=lambda: 102000)
    assert result['status'] == 'uncertain'  # Unknown second submission persists.
    assert len(ex.posts) == 4 and ex.posts[-1][0]['type'] == 'twapCancel'
    assert store.overlap('a', ['BTC'])


def test_cumulative_observations_never_reduce_known_fill_totals(tmp_path):
    store, _, job = execute(tmp_path, [ack(10), ack(20)])
    store.ingest_state('a', '', [[20, {'coin': 'BTC', 'executedSz': '.8', 'executedNtl': '80'}]], 101000)
    store.ingest_state('a', '', [[20, {'coin': 'BTC', 'executedSz': '.2', 'executedNtl': '20'}]], 102000)
    assert store.get('a', job['id'])['legs'][1]['executed_size'] == .8
    store.ingest_history('a', [{'twapId': 20, 'state': {'coin': 'BTC', 'executedSz': '.3'},
                              'status': {'status': 'terminated'}, 'time': 103000}], 103000)
    assert store.get('a', job['id'])['legs'][1]['executed_size'] == .8


def test_fill_key_filter_and_private_database_permissions(tmp_path):
    store, _, job = execute(tmp_path, [ack(10), ack(20)])
    store.ingest_fills('a', [{'twapId': 20, 'fill': {'coin': 'BTC', 'tid': 1, 'sz': '.1', 'px': '2', 'time': 100001}}], 101000)
    assert store.fill_keys('a', job_ids=[]) == set()
    assert store.fill_keys('a', job_ids=['other']) == set()
    assert store.fill_keys('a', job_ids=[job['id']]) == {('BTC', '1')}
    assert store.path.stat().st_mode & 0o777 == 0o600


def _reserve_process(path, queue):
    store = NativeTwapStore(path)
    try:
        store.reserve('a', 'p', 'Aumentar', 30, False, ORDERS)
        queue.put('reserved')
    except RuntimeError:
        queue.put('blocked')


def test_independent_processes_cannot_double_reserve_shared_assets(tmp_path):
    import multiprocessing
    ctx = multiprocessing.get_context('fork')
    queue = ctx.Queue()
    path = tmp_path / 'db'
    NativeTwapStore(path)
    workers = [ctx.Process(target=_reserve_process, args=(path, queue)) for _ in range(2)]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join(timeout=10)
        assert worker.exitcode == 0
    assert sorted(queue.get(timeout=2) for _ in workers) == ['blocked', 'reserved']


def test_active_jobs_precede_terminal_history(tmp_path):
    store, _, job = execute(tmp_path, [ack(10), ack(20)])
    # Another account cannot pollute the displayed account's history.
    store.reserve('b', 'other', 'Aumentar', 30, False, ORDERS, now_ms=999999)
    assert store.list('a', limit=1)[0]['id'] == job['id']
    with store._connect() as c:
        c.execute("UPDATE native_twap_jobs SET status='complete' WHERE id=?", (job['id'],))
    next_job = store.reserve('a', 'other', 'Aumentar', 30, False, ORDERS, now_ms=1)
    assert store.list('a', limit=1)[0]['id'] == next_job['id']


def test_delayed_terminal_history_resolves_absent_snapshot_after_exchange_finish(tmp_path):
    store, _, job = execute(tmp_path, [ack(10), ack(20)])
    store.ingest_state('a', '', [], 105000)
    assert store.get('a', job['id'])['legs'][1]['status'] == 'uncertain'
    store.ingest_history('a', [{'twapId': 20, 'state': {'coin': 'BTC', 'executedSz': '1'},
                              'status': {'status': 'finished'}, 'time': 104000}], 106000)
    assert store.get('a', job['id'])['legs'][1]['status'] == 'finished'
    # An old activation cannot replace a newer observation that found no active order.
    store.ingest_state('a', 'xyz', [], 107000)
    store.ingest_history('a', [{'twapId': 10, 'state': {'coin': 'xyz:GOLD'},
                              'status': {'status': 'activated'}, 'time': 104000}], 108000)
    assert store.get('a', job['id'])['legs'][0]['status'] == 'uncertain'


def test_constructing_store_does_not_touch_disk(tmp_path):
    path = tmp_path / 'new' / 'db'
    store = NativeTwapStore(path)
    assert not path.exists()
    assert store.list('a') == []
    assert path.exists()


def test_signer_preflights_both_legs_before_any_post(tmp_path, monkeypatch):
    import pairs_desk.native_twap as native
    store, ex = NativeTwapStore(tmp_path / 'db'), FakeExchange([])
    original = native._sign
    calls = []
    def broken_sign(exchange, action, nonce):
        calls.append(action)
        if len(calls) == 2:
            raise ValueError('synthetic invalid signer')
        return original(exchange, action, nonce)
    monkeypatch.setattr(native, '_sign', broken_sign)
    with pytest.raises(ValueError):
        submit_pair(store, 'a', 'p', 'Aumentar', ORDERS, 30, False, 'unused', exchange_factory=lambda *_: ex)
    assert len(calls) == 2 and ex.posts == [] and store.list('a') == []


def test_cancel_claim_is_atomic_and_cannot_cancel_twice_without_observation(tmp_path):
    store, _, job = execute(tmp_path, [ack(10), ack(20)])
    assert store._claim_cancel(job['id'], 0, 101000)
    assert not NativeTwapStore(store.path)._claim_cancel(job['id'], 0, 101001)


def test_unknown_id_recovery_requires_exact_reduce_only_and_account(tmp_path):
    store = NativeTwapStore(tmp_path / 'db')
    job = store.reserve('a', 'p', 'Aumentar', 30, False, ORDERS, now_ms=100000)
    store._claim_submission(job['id'], 0, 100000)
    state = dict(coin='BTC', side='B', sz='1', minutes=30, randomize=False,
                 reduceOnly=True, user='a', timestamp=100000, executedSz='1')
    for wrong in [state, dict(state, reduceOnly=0), dict(state, reduceOnly=False, user='other')]:
        store.ingest_state('a', '', [[999, wrong]], 101000)
        store.ingest_history('a', [dict(state=wrong, status={'status': 'finished'}, time=101000)], 101000)
        assert store.get('a', job['id'])['legs'][0]['twap_id'] is None
        assert store.get('a', job['id'])['legs'][0]['status'] == 'uncertain'
    store.ingest_state('a', '', [[999, dict(state, reduceOnly=False, user='A')]], 102000)
    assert store.get('a', job['id'])['legs'][0]['twap_id'] == 999


def test_cancel_after_first_ack_prevents_second_native_order_cross_store(tmp_path, monkeypatch):
    store, ex = NativeTwapStore(tmp_path / 'db'), FakeExchange([ack(10),
        {'status': 'ok', 'response': {'data': {'status': 'success'}}}])
    other_process_store = NativeTwapStore(store.path)
    original = store._leg
    cancelled = []
    def after_ack(job_id, index, now, **fields):
        original(job_id, index, now, **fields)
        if fields.get('twap_id') == 10 and not cancelled:
            cancelled.append(cancel_pair(other_process_store, 'a', job_id, 'unused',
                exchange_factory=lambda *_: ex, clock=lambda: 100001))
    monkeypatch.setattr(store, '_leg', after_ack)
    result = submit_pair(store, 'a', 'p', 'Aumentar', ORDERS, 30, False, 'unused',
                         exchange_factory=lambda *_: ex, clock=lambda: 100000)
    assert [p[0]['type'] for p in ex.posts] == ['twapOrder', 'twapCancel']
    assert result['legs'][1]['status'] == 'cancelled'
    assert result['legs'][1]['twap_id'] is None
    assert result['status'] != 'complete'
    assert store.overlap('a', ['BTC'])


def test_cancel_during_inflight_claim_remains_uncertain_then_cancels_ack(tmp_path, monkeypatch):
    store, ex = NativeTwapStore(tmp_path / 'db'), FakeExchange([ack(10),
        {'status': 'ok', 'response': {'data': {'status': 'success'}}}])
    original, observed = store._claim_submission, []
    def before_network(job_id, index, now):
        claimed = original(job_id, index, now)
        if index == 0 and claimed:
            observed.append(cancel_pair(NativeTwapStore(store.path), 'a', job_id, 'unused',
                exchange_factory=lambda *_: ex, clock=lambda: 100001))
        return claimed
    monkeypatch.setattr(store, '_claim_submission', before_network)
    result = submit_pair(store, 'a', 'p', 'Aumentar', ORDERS, 30, False, 'unused',
                         exchange_factory=lambda *_: ex, clock=lambda: 100000)
    assert observed[0]['status'] == 'uncertain'
    assert [p[0]['type'] for p in ex.posts] == ['twapOrder', 'twapCancel']
    assert result['legs'][1]['status'] == 'cancelled'


def test_cancel_before_any_send_claim_records_intent_and_stops_all_posts(tmp_path):
    store = NativeTwapStore(tmp_path / 'db')
    job = store.reserve('a', 'p', 'Aumentar', 30, False, ORDERS, now_ms=100000)
    def no_exchange(*_):
        raise AssertionError('No native ids, no network needed')
    result = cancel_pair(NativeTwapStore(store.path), 'a', job['id'], 'unused', exchange_factory=no_exchange)
    assert result['status'] == 'cancelled'
    assert not store._claim_submission(job['id'], 0, 100001)
    assert not store._claim_submission(job['id'], 1, 100001)


def test_restart_first_ack_then_finished_with_unsent_second_stays_uncertain_and_blocked(tmp_path):
    store = NativeTwapStore(tmp_path / 'db')
    job = store.reserve('a', 'p', 'Aumentar', 30, False, ORDERS, now_ms=100000)
    store._claim_submission(job['id'], 0, 100000)
    store._leg(job['id'], 0, 100001, status='running', twap_id=10)
    restarted = NativeTwapStore(store.path)
    assert restarted.get('a', job['id'])['status'] == 'uncertain'  # Expired submission lease.
    restarted.ingest_history('a', [{'twapId': 10, 'state': {'coin': 'BTC', 'executedSz': '1'},
                                  'status': {'status': 'finished'}, 'time': 101000}], 101001)
    assert restarted.get('a', job['id'])['status'] == 'uncertain'
    assert restarted.get('a', job['id'])['legs'][1]['status'] == 'pending'
    assert restarted.overlap('a', ['BTC'])
    assert not restarted._claim_submission(job['id'], 0, 102000)  # Never resend first.


def test_terminal_native_history_arriving_before_http_ack_cannot_be_regressed(tmp_path):
    store, ex = NativeTwapStore(tmp_path / 'db'), FakeExchange([ack(10), ack(20)])
    original = ex._post_action
    def observed_before_ack(action, signature, nonce):
        answer = original(action, signature, nonce)
        if action['twap']['a'] == 100001:
            store.ingest_history('a', [{'state': dict(coin='xyz:GOLD', side='A', sz='2', minutes=30,
                randomize=False, reduceOnly=False, timestamp=100000, executedSz='2'),
                'status': {'status': 'finished'}, 'time': 100001}], 100001)
        return answer
    ex._post_action = observed_before_ack
    job = submit_pair(store, 'a', 'p', 'Aumentar', ORDERS, 30, False, 'unused',
                      exchange_factory=lambda *_: ex, clock=lambda: 100000)
    assert job['legs'][0]['status'] == 'finished'
    assert job['legs'][0]['twap_id'] == 10
    assert job['legs'][0]['executed_size'] == 2


def test_http_timeout_cannot_erase_native_id_already_recovered_by_snapshot(tmp_path):
    store = NativeTwapStore(tmp_path / 'db')
    job = store.reserve('a', 'p', 'Aumentar', 30, False, ORDERS, now_ms=100000)
    store._claim_submission(job['id'], 0, 100000)
    state = dict(coin='BTC', side='B', sz='1', minutes=30, randomize=False,
                 reduceOnly=False, timestamp=100000)
    store.ingest_state('a', '', [[99, state]], 100001)
    store._leg(job['id'], 0, 100002, status='uncertain', twap_id=None, error='submission_outcome_unknown')
    leg = store.get('a', job['id'])['legs'][0]
    assert leg['twap_id'] == 99 and leg['status'] == 'running'


def test_native_minimum_preflights_both_legs_before_any_post(tmp_path):
    orders = [dict(o, mark=20) for o in ORDERS]
    store, ex = NativeTwapStore(tmp_path / 'db'), FakeExchange([ack(10), ack(20)])
    with pytest.raises(ValueError, match='100 USD por pata'):
        submit_pair(store, 'a', 'p', 'Aumentar', orders, 180, False, 'unused',
                    exchange_factory=lambda *_: ex)
    assert ex.posts == []
    assert store.list('a') == []


def test_rejection_keeps_safe_reason_without_raw_data(tmp_path):
    response = {'status': 'ok', 'response': {'type': 'twapOrder', 'data': {
        'status': {'error': 'TWAP order must have minimum notional value of $100. SECRET key'}}}}
    store, ex, job = execute(tmp_path, [response])
    assert job['legs'][0]['error'] == 'twap_min_notional'
    assert job['legs'][1]['error'] == 'not_submitted'
    assert 'SECRET' not in str(job)
    assert len(ex.posts) == 1


def test_native_signature_uses_canonical_sdk_size_wire(tmp_path, monkeypatch):
    from hyperliquid.utils.signing import float_to_wire, sign_l1_action
    original = FakeExchange._post_action
    captured = []
    def capture(self, action, signature, nonce):
        captured.append((self, action, signature, nonce))
        return original(self, action, signature, nonce)
    monkeypatch.setattr(FakeExchange, '_post_action', capture)
    execute(tmp_path, [ack(10), ack(20)])
    for ex, action, signature, nonce in captured:
        canonical = dict(action, twap=dict(action['twap'], s=float_to_wire(float(action['twap']['s']))))
        assert action == canonical, 'size must match official SDK wire, without .0/trailing zeroes'
        assert signature == sign_l1_action(ex.wallet, canonical, None, nonce, None, True)


@pytest.mark.parametrize('message,code', [
    ('L1 error: User or API Wallet 0x'+'a'*40+' does not exist.', 'signer_not_found'),
    ('Must deposit before performing actions. User: 0x'+'b'*40, 'account_not_funded'),
    ('Invalid TWAP duration: 600 min(s)', 'twap_invalid_duration'),
])
def test_known_exchange_errors_explain_rejection_without_addresses(tmp_path, message, code):
    _,_,job=execute(tmp_path,[{'status':'err','response':message}])
    assert job['legs'][0]['error']==code
    assert '0x' not in str(job)


@pytest.mark.parametrize('minutes',[2880,10080])
def test_multi_day_native_duration_persists_without_truncating(tmp_path, minutes):
    store,ex=NativeTwapStore(tmp_path/'db'),FakeExchange([ack(10),ack(20)])
    job=submit_pair(store,'a','pair','Aumentar',ORDERS,minutes,False,'unused',exchange_factory=lambda *_:ex,clock=lambda:100000)
    assert job['minutes']==minutes
    assert job['planned_end_ms']-job['created_ms']==minutes*60000
    assert all(action['twap']['m']==minutes for action,_ in ex.posts)
    assert NativeTwapStore(store.path).get('a',job['id'])['minutes']==minutes


def test_unknown_rejection_retains_bounded_safe_exchange_reason(tmp_path):
    error='Maximum number of active TWAPs reached for user 0x'+'a'*40
    store,ex,job=execute(tmp_path,[{'status':'ok','response':{'type':'twapOrder','data':{'status':{'error':error}}}}])
    detail=job['legs'][0].get('error_detail')
    assert detail and 'Maximum number of active TWAPs' in detail
    assert '0x' not in detail
    assert len(ex.posts)==1
    assert job['legs'][1]['error']=='not_submitted'
    assert NativeTwapStore(store.path).get('a',job['id'])['legs'][0]['error_detail']==detail


@pytest.mark.parametrize('value',[
    'SECRET key', 'private_key='+'a'*64, 'Authorization: Bearer abcdef',
    'seed phrase: example', '<script>alert(1)</script>',
])
def test_error_diagnostic_drops_credentials_and_markup(tmp_path,value):
    _,_,job=execute(tmp_path,[{'status':'err','response':value}])
    assert not job['legs'][0].get('error_detail')


def test_error_diagnostic_is_bounded_and_redacts_long_tokens(tmp_path):
    from pairs_desk.native_twap import _safe_error_detail
    response={'status':'err','response':'Unsupported request '+'b'*64+' '+('size '*150)}
    detail=_safe_error_detail(response)
    assert len(detail)<=320
    assert 'b'*64 not in detail


def test_error_detail_migration_preserves_existing_active_job(tmp_path):
    import sqlite3
    path=tmp_path/'db'
    store=NativeTwapStore(path)
    job=store.reserve('a','pair','Aumentar',30,False,ORDERS,now_ms=100000)
    with sqlite3.connect(path) as conn:
        conn.execute('ALTER TABLE native_twap_legs DROP COLUMN error_detail')
    migrated=NativeTwapStore(path).get('a',job['id'])
    assert migrated['status']==job['status']
    assert [leg['size'] for leg in migrated['legs']]==[leg['size'] for leg in job['legs']]
    assert all(leg['error_detail'] is None for leg in migrated['legs'])


def test_entry_fill_view_is_account_scoped_and_uses_native_leg_side(tmp_path):
    store,ex,job=execute(tmp_path,[ack(10),ack(20)])
    store.ingest_fills('a',[{'twapId':10,'fill':{'coin':'xyz:GOLD','tid':1,'sz':'1','px':'10','time':100001}}],100002)
    rows=store.entry_fills('a',['xyz:GOLD'])
    assert len(rows)==1 and rows[0]['side']=='A' and rows[0]['sz']==1
    assert store.entry_fills('b',['xyz:GOLD'])==[]
    assert store.entry_fills('a',['BTC'])==[]
    assert store.entry_fills('a',[])==[]
    assert not any(key in rows[0] for key in ['account','fee','closedPnl'])
