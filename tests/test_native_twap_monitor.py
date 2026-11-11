from pairs_desk.native_twap_monitor import NativeTwapMonitor


class Store:
    def __init__(self):
        self.calls = []

    def ingest_state(self, *args):
        self.calls.append(("state", args))

    def ingest_history(self, *args):
        self.calls.append(("history", args))

    def ingest_fills(self, *args):
        self.calls.append(("fills", args))


def test_monitor_filters_other_accounts_and_preserves_dex_scope():
    store = Store()
    assert not NativeTwapMonitor.ingest("a", store, {
        "channel": "twapStates", "data": {"user": "b", "states": []},
    }, 100)
    assert store.calls == []
    assert NativeTwapMonitor.ingest("a", store, {
        "channel": "twapStates", "data": {"user": "A", "dex": "xyz", "states": [[12, {"coin": "xyz:USAR"}]]},
    }, 100)
    assert store.calls[0] == ("state", ("a", "xyz", [[12, {"coin": "xyz:USAR"}]], 100))


def test_fill_and_history_snapshots_are_usable_after_reconnect():
    store = Store()
    assert NativeTwapMonitor.ingest("a", store, {
        "channel": "userTwapSliceFills", "data": {"user": "a", "isSnapshot": True, "twapSliceFills": [{"twapId": 3}]},
    }, 200)
    assert NativeTwapMonitor.ingest("a", store, {
        "channel": "userTwapHistory", "data": {"user": "a", "isSnapshot": True, "history": [{"state": {}, "status": {"status": "finished"}}]},
    }, 201)
    assert [kind for kind, _ in store.calls] == ["fills", "history"]
    assert NativeTwapMonitor().status("another")["as_of_ms"] is None


def test_fresh_core_traffic_cannot_mask_stale_xyz_observation():
    monitor = NativeTwapMonitor()
    monitor._account = 'a'
    monitor._status = {'connected':True,'as_of_ms':10000,'error':None}
    monitor._dex_as_of = {'':10000,'xyz':100}
    assert monitor.status('a',dexes={'','xyz'})['as_of_ms'] == 100
    assert monitor.status('a',dexes={''})['as_of_ms'] == 10000
    assert monitor.status('a',dexes={'other'})['as_of_ms'] is None
