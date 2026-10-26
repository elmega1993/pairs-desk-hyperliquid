import json
import subprocess
import sys


def test_cli_writes_private_local_report_without_raw_address(tmp_path):
    settings = tmp_path / 'settings.json'
    settings.write_text(json.dumps({
        'address': '0xprivate', 'pairs': [], 'closed_pairs': [{
            'id': 'A|B', 'long': 'A', 'short': 'B', 'opened_at': 1000,
            'closed_at': 2000, 'realized': 1, 'fees': 0.1,
            'funding': 0, 'funding_complete': True, 'total_pnl': 0.9,
        }],
    }))
    output = tmp_path / 'report'
    result = subprocess.run([
        sys.executable, 'scripts/analyze_operations.py',
        '--settings', str(settings), '--output', str(output),
        '--skip-live',
    ], capture_output=True, text=True)

    assert result.returncode == 0, result.stderr
    assert {path.name for path in output.iterdir()} == {'operations.csv', 'summary.json', 'summary.md', 'reconciliation.json'}
    assert '0xprivate' not in (output / 'summary.json').read_text()
    assert 'payload' not in (output / 'summary.json').read_text()
