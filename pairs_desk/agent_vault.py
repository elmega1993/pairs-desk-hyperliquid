"""Persistent Agent credentials using the OS keyring, never settings.json."""
from __future__ import annotations

import re

SERVICE = 'crypto-pairs-desk-hyperliquid-agent'
KEY_PATTERN = re.compile(r'(?:0x)?[a-fA-F0-9]{64}\Z')


def _account(address: str) -> str:
    if not re.fullmatch(r'0x[a-fA-F0-9]{40}', address):
        raise ValueError('Guardá primero una dirección pública válida.')
    return address.lower()


def load_agent(address: str) -> str | None:
    import keyring
    return keyring.get_password(SERVICE, _account(address))


def save_agent(address: str, secret: str) -> None:
    value = secret.strip()
    if not KEY_PATTERN.fullmatch(value):
        raise ValueError('La clave del Agent debe tener 64 caracteres hexadecimales.')
    import keyring
    keyring.set_password(SERVICE, _account(address), value)


def delete_agent(address: str) -> None:
    import keyring
    try:
        keyring.delete_password(SERVICE, _account(address))
    except keyring.errors.PasswordDeleteError:
        pass
