"""Run the Node test suites (*.cjs) from pytest so a single command covers everything."""
import shutil
import subprocess
from pathlib import Path

import pytest

BASE = Path(__file__).resolve().parents[1]
NODE = shutil.which('node')
SUITES = sorted(Path(__file__).parent.glob('*.cjs'))


@pytest.mark.skipif(NODE is None, reason='Node.js no está instalado')
@pytest.mark.parametrize('suite', SUITES, ids=lambda p: p.name)
def test_node_suite(suite):
    if suite.name == 'test_react_sort_behavior.cjs' and not (BASE / 'react_frontend/node_modules/typescript').exists():
        pytest.skip('Falta react_frontend/node_modules (ejecutar npm ci en react_frontend)')
    result = subprocess.run([NODE, str(suite)], capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
