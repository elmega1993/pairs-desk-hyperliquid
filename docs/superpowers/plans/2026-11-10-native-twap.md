# Native Hyperliquid TWAP

Implement selected native TWAP in existing pair trading/chart. Keep immediate tickets. No live order or arming during verification. No local schedule.

Official twapOrder/twapCancel signed with installed SDK. Native duration 5–1440 whole minutes, default30, randomize optional. Slices30s and slippage3% belong to the exchange. Show native constraints, don't reuse immediate slippage slider.

Two independent native TWAPs, same duration. Persist per-leg intent before POST. Never blindly resend uncertain response. If second definitively rejects, cancel first and track actual fills/unknown outcome.

Reuse orders.sqlite3 with new tables. Block overlapping assets and existing uncertain immediate attempts with atomic SQL reservation. Recovery retains native IDs and unknown states. Time elapsed alone never means filled.

Observe WS twapStates/userTwapHistory/userTwapSliceFills without keys. Account/dex scoped and timestamped. Reconnect restores current state and deduplicated fills. UI marks stale observations.

GET /api/trade/twaps -> {items:[job],as_of_ms}
POST /api/trade/twaps/{id}/cancel -> CSRF+confirmation CONFIRMAR, allowed while new orders disarmed.
GET /api/trade/twaps/{id}/fills -> paginated details.

Existing preview/execute immutable tickets bind execution mode, minutes, randomize, quantities. SDK preflights both sizes/lot precision/signer before any POST. Close/reduce reduceOnly. Increase long-buy/short-sell.

Chart one time span per group with executed amounts by leg. Native slice fills are hidden from generic ADD/RED markers when matched by exact native fill IDs. Short intervals on daily chart collapse into one marker. Ratio of slice prices is never presented as simultaneous execution or actual average entry.

## Shared API
Job {id,pair_id,operation,minutes,randomize,created_ms,planned_end_ms,status,updated_ms,legs:[{coin,is_buy,reduce_only,size,asset,twap_id,status,executed_size,executed_notional,updated_ms}],error?}.
Group statuses running/complete/incomplete/cancelled/partial/uncertain/submitting/rejected.
Per-leg pending/submitting/running/finished/cancelled/rejected/uncertain/cancel_requested.
Unknown executed size is null, finished with partial quantity is incomplete.
No account or keys in UI. pair.twaps is Job[]; pair.twap_fill_keys contains exact coin+tid to suppress matched native fills if possible.

## Tasks
- [x] Engine/store native_twap.py and test_native_twap.py. Agent owns these. Durable store, SDK preflight/submit/cancel, idempotent state/fill ingestion, aggregation.
- [x] UI/chart. Agent owns PairActions.tsx, new TwapOrders.tsx and twapModel.ts, RatioChart.tsx, new JS tests; append CSS only. Existing Pair index signature supports pair.twaps. Fetch /trade/twaps?pair_id while modal open. No App edits.
- [x] Controller owns secure_trade_routes.py, trade_journal.py, native_twap_monitor.py, read_only_server.py, route/monitor tests.
- [x] Review, regression, build and synthetic visual smoke. Record limits and outstanding testnet verification.

Working in active checkout with prior uncommitted source. Preserve all unrelated changes. No bulk commit/reset.

Verified offline and synthetic browser only. Exchange end-to-end validation remains pending explicit authorized order. See docs/current/NATIVE_TWAP.md.
