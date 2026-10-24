from __future__ import annotations

from copy import deepcopy
from typing import Any

from .metrics import latest_closed_cycle
from .closed_ratio import close_ratio_from_fills


def archive_closed_pairs(
    cfg: dict[str, Any],
    positions: dict[str, dict[str, Any]],
    fills: list[dict[str, Any]],
    health: dict[str, Any],
    confirmations: dict[str, Any] | None = None,
    required_confirmations: int = 2,
) -> tuple[dict[str, Any], bool, dict[str, Any]]:
    """Archive verified flat pairs only after distinct healthy snapshots.

    Re-running Streamlit against the same cached payload must not count as a
    second confirmation. ``health['snapshot_token']`` therefore identifies the
    underlying network read, not the render.
    """
    out = deepcopy(cfg)
    counts = deepcopy(confirmations or {})
    changed = False
    closed_history = out.setdefault('closed_pairs', [])
    existing_ids = {str(item.get('id')) for item in closed_history if isinstance(item, dict)}

    if not health.get('core_ok', False) or not health.get('fills_ok', False):
        return out, False, counts
    snapshot_token = str(health.get('snapshot_token') or '')
    if not snapshot_token:
        return out, False, counts

    archived: list[dict[str, Any]] = []
    for pair_cfg in list(out.get('pairs', [])):
        long_sym, short_sym = pair_cfg['long'], pair_cfg['short']
        pair_id = f'{long_sym}|{short_sym}'
        needs_xyz = long_sym.startswith('xyz:') or short_sym.startswith('xyz:')
        if needs_xyz and not health.get('xyz_ok', False):
            counts.pop(pair_id, None)
            continue
        if long_sym in positions or short_sym in positions:
            counts.pop(pair_id, None)
            continue

        prev = counts.get(pair_id)
        if isinstance(prev, int):
            prev = {'count': prev, 'snapshot_token': None}
        if not isinstance(prev, dict):
            prev = {'count': 0, 'snapshot_token': None}
        if prev.get('snapshot_token') == snapshot_token:
            count = int(prev.get('count') or 0)
        else:
            count = int(prev.get('count') or 0) + 1
            counts[pair_id] = {'count': count, 'snapshot_token': snapshot_token}
        if count < required_confirmations:
            continue

        lc = latest_closed_cycle(fills, long_sym, current_szi=0.0)
        sc = latest_closed_cycle(fills, short_sym, current_szi=0.0)
        if not lc or not sc:
            continue

        closed_at = max(int(lc['closed_at'] or 0), int(sc['closed_at'] or 0))
        opened_at = min(int(lc['opened_at'] or 0), int(sc['opened_at'] or 0))
        archive_id = f'{long_sym}|{short_sym}|{closed_at}'
        if archive_id not in existing_ids:
            realized = float(lc['realized']) + float(sc['realized'])
            fees = float(lc['fees']) + float(sc['fees'])
            close_ratio = close_ratio_from_fills(long_sym, short_sym, fills, opened_at, closed_at)
            closed_history.append({
                'id': archive_id,
                'long': long_sym,
                'short': short_sym,
                'opened_at': opened_at,
                'closed_at': closed_at,
                'realized': realized,
                'fees': fees,
                'net_realized': realized - fees,
                **({'close_ratio': close_ratio} if close_ratio is not None else {}),
            })
            existing_ids.add(archive_id)
        archived.append(pair_cfg)
        counts.pop(pair_id, None)
        changed = True

    if archived:
        out['pairs'] = [p for p in out.get('pairs', []) if p not in archived]
    return out, changed, counts


def reset_management_on_reopen(pair_cfg: dict[str, Any], opened_at: int | None) -> bool:
    """Reset TP/ADD state when a newly opened trading cycle is detected."""
    if not opened_at:
        return False
    current = int(pair_cfg.get('management_cycle_opened_at') or 0)
    opened_at = int(opened_at)
    if current == opened_at:
        return False
    if current == 0:
        # Upgrade/first observation: remember the cycle without erasing existing
        # management state or moving an already established reference ratio.
        pair_cfg['management_cycle_opened_at'] = opened_at
        return False
    pair_cfg['management_cycle_opened_at'] = opened_at
    pair_cfg.pop('management_entry_ratio', None)
    pair_cfg.pop('executed_tp', None)
    pair_cfg.pop('executed_add', None)
    return True


def pair_is_live(pair: dict[str, Any], positions: dict[str, dict[str, Any]]) -> bool:
    """A saved pair reserves its legs only while both sides are actually open."""
    try:
        long_size = float(positions.get(pair['long'], {}).get('szi') or 0)
        short_size = float(positions.get(pair['short'], {}).get('szi') or 0)
    except (KeyError, TypeError, ValueError):
        return False
    return long_size > 0 and short_size < 0


def pair_leg_conflict(
    long_sym: str, short_sym: str, pairs: list[dict[str, Any]], positions: dict[str, dict[str, Any]]
) -> bool:
    """Ignore incomplete old pairs; do not silently delete their saved history."""
    wanted = {long_sym, short_sym}
    return any(pair_is_live(pair, positions) and bool(wanted & {pair['long'], pair['short']}) for pair in pairs)
