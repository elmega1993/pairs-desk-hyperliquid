"""Explicit private Tailscale hostname; keep localhost binding and trade origins."""
import json
import re
from pathlib import Path

LOCAL_HOSTS = ['localhost','127.0.0.1','[::1]','testserver']


def validate_hostname(host):
    if not isinstance(host,str):
        raise ValueError('Nombre Tailscale inválido')
    host=host.lower().rstrip('.')
    labels=host.split('.')
    if len(host)>253 or len(labels)<4 or labels[-2:]!=['ts','net']:
        raise ValueError('Se requiere el nombre DNS completo de esta PC en Tailscale')
    if any(not re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?',label) for label in labels):
        raise ValueError('Nombre DNS inválido; no se permiten comodines, URLs ni puertos')
    return host


def allowed_hosts(path):
    try:
        host=validate_hostname(json.loads(Path(path).read_text())['tailscale_host'])
    except (OSError,ValueError,KeyError,TypeError):
        return list(LOCAL_HOSTS)
    return [*LOCAL_HOSTS,host]


def save_hostname(path,host):
    host=validate_hostname(host)
    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists():
        previous=json.loads(path.read_text())
        if previous.get('tailscale_host')!=host:
            raise ValueError('Ya existe otra configuración remota; revisar antes de reemplazarla')
        return host
    # Exclusive creation avoids overwriting concurrent or previous configuration.
    with path.open('x') as stream:
        path.chmod(0o600)
        json.dump({'tailscale_host':host},stream)
        stream.write('\n')
    return host
