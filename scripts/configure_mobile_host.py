#!/usr/bin/env python3
"""Read the authenticated Tailscale node and prepare its exact app hostname."""
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from pairs_desk.mobile_access import save_hostname

if __name__=='__main__':
    result=subprocess.run(['tailscale','status','--json'],capture_output=True,text=True,check=True,timeout=15)
    status=json.loads(result.stdout)
    if status.get('BackendState')!='Running':
        raise SystemExit('Falta iniciar sesión: sudo tailscale up')
    host=save_hostname(Path.home()/'.config/crypto-pairs-desk/remote_access.json',status['Self']['DNSName'])
    print(f'https://{host}/react')
