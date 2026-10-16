"""Safely archive flat pair cycles from the independent frontend.

Never discard unverified pairs. Read-only Hyperliquid queries may write local
settings history, but cannot place orders or modify remote positions.
"""
from __future__ import annotations

import threading
import time
from pathlib import Path

from .lifecycle import archive_closed_pairs
from .metrics import closed_pair_trade_events, archived_pair_entry_ratio
from .storage import load_settings, save_settings

_LOCK = threading.RLock()
_SEEN: dict[tuple[str, str], tuple[float, int, str | None]] = {}


def archive_frontend(settings_path: Path, account: str, positions: dict, fills: list,
                     fills_complete: bool, xyz_ok: bool = True, now: float | None = None,
                     min_separation: float = 5.0, ledger=None, snapshot_token: str | None = None):
    """Require two distinct successful reads separated in time, then persist.

    Re-read settings under a lock immediately before committing, preserving
    changes made by other routes and the original backup chain.
    """
    now = time.time() if now is None else now
    with _LOCK:
        cfg, err = load_settings(settings_path)
        if err or cfg.get('address', '').lower() != account.lower():
            return cfg, False
        if not fills_complete:
            # A failed read invalidates any pending flat confirmation.
            for key in list(_SEEN):
                if key[0] == account.lower():
                    _SEEN.pop(key, None)
            return cfg, False
        for p in cfg.get('pairs', []):
            pair_id = f"{p['long']}|{p['short']}"
            key = (account.lower(), pair_id)
            if p['long'] in positions or p['short'] in positions or (not xyz_ok and 'xyz:' in pair_id):
                _SEEN.pop(key, None)
                continue
            first, count, previous_token = _SEEN.get(key, (now, 0, None))
            if count == 0:
                _SEEN[key] = (now, 1, snapshot_token)
            elif (now - first >= min_separation
                  and (snapshot_token is None or snapshot_token != previous_token)):
                _SEEN[key] = (first, 2, snapshot_token)
        confirmations = {}
        for p in cfg.get('pairs', []):
            pair_id = f"{p['long']}|{p['short']}"
            if _SEEN.get((account.lower(), pair_id), (0, 0, None))[1] >= 2:
                confirmations[pair_id] = {'count': 1, 'snapshot_token': 'first'}
        updated, changed, _ = archive_closed_pairs(
            cfg, positions, fills,
            {'core_ok': True, 'xyz_ok': xyz_ok, 'fills_ok': fills_complete,
             'snapshot_token': f'second:{now}'},
            confirmations, required_confirmations=2)
        if ledger is not None:
            from .ledger import closed_accounting
            reconciled = [closed_accounting(ledger, account, item, fills, fills_complete)
                          for item in updated.get('closed_pairs', [])]
            if reconciled != updated.get('closed_pairs', []):
                updated['closed_pairs'] = reconciled
                changed = True
        if changed:
            for closed in updated.get('closed_pairs', []):
                if closed.get('events') is None:
                    opened = int(closed.get('opened_at') or 0)
                    closed_at = int(closed.get('closed_at') or 0)
                    closed['events'] = closed_pair_trade_events(
                        closed['long'], closed['short'], fills, opened, closed_at)
                    closed['entry_ratio'] = archived_pair_entry_ratio(
                        closed['long'], closed['short'], fills, opened)
            save_settings(settings_path, updated)
            for p in cfg.get('pairs', []):
                if p not in updated.get('pairs', []):
                    _SEEN.pop((account.lower(), f"{p['long']}|{p['short']}"), None)
        return updated, changed
