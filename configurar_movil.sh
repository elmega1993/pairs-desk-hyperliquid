#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

if [ "$(id -u)" -eq 0 ]; then
  echo 'Ejecutá este archivo como Alan, sin sudo delante de bash.' >&2
  exit 1
fi

if ! command -v tailscale >/dev/null 2>&1; then
  . /etc/os-release
  if [ "${ID:-}" != ubuntu ] || [ "${VERSION_CODENAME:-}" != noble ]; then
    echo 'Este instalador está preparado para Ubuntu 24.04 (noble).' >&2
    exit 1
  fi
  echo 'Se instalará Tailscale desde su repositorio oficial para Ubuntu 24.04.'
  echo 'Ingresá tu contraseña de Ubuntu cuando sudo la solicite.'
  sudo -v
  setup_dir=$(mktemp -d /tmp/pairs-desk-tailscale.XXXXXXXX)
  curl --fail --silent --show-error --location --output "$setup_dir/key.gpg" https://pkgs.tailscale.com/stable/ubuntu/noble.noarmor.gpg
  curl --fail --silent --show-error --location --output "$setup_dir/repository.list" https://pkgs.tailscale.com/stable/ubuntu/noble.tailscale-keyring.list
  for target in /usr/share/keyrings/tailscale-archive-keyring.gpg /etc/apt/sources.list.d/tailscale.list; do
    source_file="$setup_dir/key.gpg"
    if [ "$target" = /etc/apt/sources.list.d/tailscale.list ]; then source_file="$setup_dir/repository.list"; fi
    if [ -e "$target" ] && ! cmp --silent "$source_file" "$target"; then
      echo "Existe una configuración distinta en $target. Revisarla antes de continuar." >&2
      exit 1
    fi
    sudo install -m 0644 "$source_file" "$target"
  done
  sudo apt-get update
  sudo apt-get install tailscale
fi

echo 'Iniciá sesión en el enlace que muestre Tailscale, con la misma cuenta que usarás en Android.'
sudo tailscale up
python3 scripts/configure_mobile_host.py

# Fail closed rather than replace an existing private/public service on HTTPS 443.
sudo tailscale serve status --json | python3 -c '
import json,sys
s=json.load(sys.stdin)
if s.get("AllowFunnel") and any(s["AllowFunnel"].values()):
    raise SystemExit("Hay una configuración Funnel existente: revisar antes de continuar.")
for host, web in s.get("Web",{}).items():
    if host.endswith(":443"):
        handlers=web.get("Handlers",{})
        if handlers != {"/":{"Proxy":"http://127.0.0.1:8510"}}:
            raise SystemExit("El puerto 443 ya sirve otra aplicación; no se reemplazó.")
tcp=s.get("TCP",{}).get("443",{})
if tcp and not tcp.get("HTTPS"):
    raise SystemExit("El puerto TCP 443 tiene otra configuración; no se reemplazó.")
'

sudo tailscale serve --bg --https=443 http://127.0.0.1:8510
echo 'Acceso privado preparado. Si aparece un enlace para habilitar HTTPS, completalo.'
echo 'Reiniciá Pair Desk para que acepte el nombre privado y abrí desde Android la URL anterior.'
echo 'Para comprobarlo fuera de casa: activá Tailscale en Android y probá con Wi-Fi apagado.'
