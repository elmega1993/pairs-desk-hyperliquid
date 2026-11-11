#!/usr/bin/env python3
"""Audit the historical account DB offline, without market/trading requests."""
import json
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from pairs_desk.historical_account import HistoricalAccount
from pairs_desk.history_audit import audit_history

if __name__=='__main__':
    store=HistoricalAccount(Path.home()/'.local/share/crypto-pairs-desk/historical_account.sqlite3')
    try:
        account=store.db.execute("SELECT value FROM metadata WHERE key='account'").fetchone()[0]
        print(json.dumps(audit_history(store,account),indent=2))
    finally:
        store.db.close()
