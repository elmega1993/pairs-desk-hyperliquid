import hashlib
import importlib.util
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]


def _installer():
    spec = importlib.util.spec_from_file_location('install_klinechart', BASE / 'install_klinechart.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_vendored_klinecharts_matches_pinned_hash():
    module = _installer()
    blob = (BASE / 'pairs_desk/vendor/klinecharts.min.js').read_bytes()
    assert hashlib.sha256(blob).hexdigest() == module.pinned_hash()


def test_installer_rejects_tampered_file(tmp_path, monkeypatch):
    module = _installer()
    tampered = tmp_path / 'klinecharts.min.js'
    tampered.write_bytes(b'x' * 200_000)
    monkeypatch.setattr(module, 'DEST', tampered)
    assert module.main() == 2
    assert tampered.read_bytes() == b'x' * 200_000  # never overwritten or deleted
