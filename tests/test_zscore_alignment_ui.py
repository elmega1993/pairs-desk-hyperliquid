from pathlib import Path
import shutil
import subprocess
import pytest

BASE = Path(__file__).resolve().parents[1]


def test_zscore_keeps_the_same_full_x_domain_as_ratio_bars():
    if not shutil.which('node') or not (BASE / 'react_frontend/node_modules/typescript').exists():
        pytest.skip('Node/TypeScript unavailable')
    subprocess.run(['node', str(BASE / 'tests/test_zscore_alignment.cjs')], cwd=BASE, check=True)
