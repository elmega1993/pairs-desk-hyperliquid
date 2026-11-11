from pathlib import Path


BASE = Path(__file__).resolve().parents[1]


def test_launcher_uses_the_virtualenv_python_explicitly():
    launcher = (BASE / 'iniciar_frontend.sh').read_text()

    assert 'PYTHON_BIN=".venv_frontend/bin/python"' in launcher
    assert '"$PYTHON_BIN" -m pip' in launcher
    assert '"$PYTHON_BIN" -m uvicorn' in launcher
