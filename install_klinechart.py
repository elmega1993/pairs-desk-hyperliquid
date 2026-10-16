"""Install KLineChart 9.8.12 as a *local* JS file, verified against a pinned SHA-256.

Exit codes:
  0  local file present and verified (or downloaded and verified)
  1  no verified copy available (offline); non-fatal for the legacy Plotly chart
  2  integrity failure: a local file exists but does not match the pinned hash
"""
from pathlib import Path
import hashlib
import sys
import urllib.request

VERSION = '9.8.12'
ROOT = Path(__file__).resolve().parent
DEST = ROOT / 'pairs_desk' / 'vendor' / 'klinecharts.min.js'
HASH_FILE = ROOT / 'pairs_desk' / 'vendor' / 'klinecharts.sha256'
URLS = (
    f'https://unpkg.com/klinecharts@{VERSION}/dist/umd/klinecharts.min.js',
    f'https://cdn.jsdelivr.net/npm/klinecharts@{VERSION}/dist/umd/klinecharts.min.js',
)


def pinned_hash() -> str:
    """Return the expected SHA-256 from klinecharts.sha256 ("<hash>  <file>")."""
    text = HASH_FILE.read_text(encoding='utf-8').split()
    if not text or len(text[0]) != 64 or any(c not in '0123456789abcdef' for c in text[0].lower()):
        raise ValueError(f'{HASH_FILE.name} no contiene un SHA-256 válido')
    return text[0].lower()


def sha256(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def valid(blob: bytes) -> bool:
    return (100_000 < len(blob) < 3_000_000 and
            b'klinecharts' in blob[:5000].lower() and
            b'createOverlay' in blob and b'applyNewData' in blob)


def main() -> int:
    try:
        expected = pinned_hash()
    except (OSError, ValueError) as error:
        print(f'ERROR de integridad: no se pudo leer el hash fijado ({error}).', file=sys.stderr)
        return 2
    if DEST.exists():
        if sha256(DEST.read_bytes()) == expected:
            print('KLineChart local instalado y verificado (SHA-256).')
            return 0
        print(f'ERROR de integridad: {DEST.name} no coincide con el SHA-256 fijado.\n'
              f'Esperado: {expected}\nNo se usará. Restaurá el archivo original o eliminá '
              'el local para que se descargue de nuevo.', file=sys.stderr)
        return 2
    for url in URLS:
        try:
            request = urllib.request.Request(url, headers={'User-Agent': 'PairsDesk/1.0'})
            with urllib.request.urlopen(request, timeout=15) as response:
                data = response.read(3_000_001)
            if not valid(data) or sha256(data) != expected:
                print('Descarga de KLineChart no coincide con el SHA-256 fijado; descartada.', file=sys.stderr)
                continue
            DEST.parent.mkdir(parents=True, exist_ok=True)
            tmp = DEST.with_suffix('.js.tmp')
            tmp.write_bytes(data)
            tmp.replace(DEST)
            print('KLineChart descargado, verificado (SHA-256) e instalado localmente.')
            return 0
        except Exception as error:
            print('No se pudo instalar desde este servidor:', type(error).__name__, file=sys.stderr)
    print('KLineChart verificado no disponible: se conservará el gráfico alternativo si existe.', file=sys.stderr)
    return 1


if __name__ == '__main__':
    sys.exit(main())
