from __future__ import annotations

import json
import os
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 2


def _empty_settings() -> dict[str, Any]:
    return {'schema_version': SCHEMA_VERSION, 'address': '', 'pairs': [], 'closed_pairs': []}


def load_settings(path: Path) -> tuple[dict[str, Any], str | None]:
    try:
        raw = json.loads(path.read_text())
    except FileNotFoundError:
        return _empty_settings(), None
    except (OSError, ValueError, TypeError) as exc:
        return _empty_settings(), str(exc)
    if not isinstance(raw, dict):
        return _empty_settings(), 'settings.json debe contener un objeto JSON'
    address = raw.get('address', '')
    pairs_raw = raw.get('pairs', [])
    closed_raw = raw.get('closed_pairs', [])
    if not isinstance(address, str):
        return _empty_settings(), 'address debe ser texto'
    if not isinstance(pairs_raw, list):
        return _empty_settings(), 'pairs debe ser una lista'
    if not isinstance(closed_raw, list):
        return _empty_settings(), 'closed_pairs debe ser una lista'

    valid_pairs = [p for p in pairs_raw if isinstance(p, dict) and isinstance(p.get('long'), str) and isinstance(p.get('short'), str)]
    valid_closed = [p for p in closed_raw if isinstance(p, dict) and isinstance(p.get('long'), str) and isinstance(p.get('short'), str)]
    malformed_pairs = [p for p in pairs_raw if p not in valid_pairs]
    malformed_closed = [p for p in closed_raw if p not in valid_closed]

    data = dict(raw)
    data['schema_version'] = SCHEMA_VERSION
    data['address'] = address
    data['pairs'] = valid_pairs
    data['closed_pairs'] = valid_closed
    if malformed_pairs or malformed_closed:
        # Keep invalid payloads visible in-memory for diagnostics, but expose only
        # valid rows to the UI and block every save so nothing on disk is lost.
        data['_invalid_pairs'] = malformed_pairs
        data['_invalid_closed_pairs'] = malformed_closed
        return data, 'settings.json contiene pares malformados; guardado bloqueado para no perder datos'
    # v1 -> v2 is additive: execution/rule fields are optional per pair and are
    # created only when the user uses them. Unknown keys remain untouched.
    return data, None


def _versioned_backup(path: Path) -> None:
    if not path.exists():
        return
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    backup = path.with_name(f'{path.stem}.{stamp}.bak{path.suffix}')
    shutil.copy2(path, backup)
    # Keep the legacy single-generation backup too for backwards compatibility.
    shutil.copy2(path, path.with_suffix(path.suffix + '.bak'))
    backups = sorted(path.parent.glob(f'{path.stem}.*.bak{path.suffix}'), key=lambda p: p.stat().st_mtime, reverse=True)
    for old in backups[10:]:
        try:
            old.unlink()
        except OSError:
            pass


def save_settings(path: Path, data: dict[str, Any], blocked: bool = False) -> None:
    if blocked:
        raise RuntimeError('Guardado bloqueado porque settings.json está corrupto o contiene datos inválidos.')
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        os.chmod(path.parent, 0o700)
    except OSError:
        pass
    _versioned_backup(path)
    payload = dict(data)
    payload['schema_version'] = SCHEMA_VERSION
    fd, tmp = tempfile.mkstemp(dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as fh:
            json.dump(payload, fh, indent=2)
            fh.flush()
            os.fsync(fh.fileno())
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
        try:
            dir_fd = os.open(path.parent, os.O_DIRECTORY)
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
        except (OSError, AttributeError):
            pass
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
