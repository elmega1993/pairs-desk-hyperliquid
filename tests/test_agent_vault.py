import sys
from types import SimpleNamespace
import pytest
from pairs_desk.agent_vault import save_agent, load_agent, delete_agent

ADDR = '0x' + 'a' * 40
KEY = '0x' + 'b' * 64

def test_vault_persistence_and_deletion(monkeypatch):
    db = {}
    def delete(service, account):
        db.pop((service, account), None)
    fake = SimpleNamespace(get_password=lambda s, a: db.get((s, a)),
                           set_password=lambda s, a, k: db.__setitem__((s, a), k),
                           delete_password=delete, errors=SimpleNamespace(PasswordDeleteError=KeyError))
    monkeypatch.setitem(sys.modules, 'keyring', fake)
    save_agent(ADDR, KEY)
    assert load_agent(ADDR) == KEY
    delete_agent(ADDR)
    assert load_agent(ADDR) is None

def test_vault_rejects_invalid_key(monkeypatch):
    with pytest.raises(ValueError):
        save_agent(ADDR, 'not-a-key')
