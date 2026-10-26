import assert from 'node:assert/strict';
import {resolveOfficialPnl} from '../react_frontend/src/pnlSource.ts';

const hyperliquid = {
  official_pnl: {all: 476.13},
  hl_pnl: {all: [{time: 1, pnl: 0}, {time: 2, pnl: 476.13}]},
  summary: {total: 110.0},
  pnl_history: [{time: 2, pnl: 110.0}],
};
const resolved = resolveOfficialPnl(hyperliquid);
assert.equal(resolved.value, 476.13);
assert.equal(resolved.source, 'hyperliquid');
assert.equal(resolved.fallback, false);
assert.deepEqual(resolved.series.map(({time, pnl}) => ({time, pnl})), hyperliquid.hl_pnl.all);

const fallback = resolveOfficialPnl({summary: {total: 110.0}, pnl_history: [{time: 2, pnl: 110.0}]});
assert.equal(fallback.value, 110.0);
assert.equal(fallback.source, 'local');
assert.equal(fallback.fallback, true);
