import json

import pytest
from starlette.applications import Starlette
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.requests import Request
from starlette.responses import PlainTextResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from pairs_desk.mobile_access import allowed_hosts, save_hostname, validate_hostname, LOCAL_HOSTS


def test_exact_private_host_allowed_other_tailnet_hosts_rejected(tmp_path):
    path=tmp_path/'remote.json'
    save_hostname(path,'desk.tail123.ts.net.')
    app=Starlette(routes=[Route('/',lambda request:PlainTextResponse('ok'))])
    app.add_middleware(TrustedHostMiddleware,allowed_hosts=allowed_hosts(path))
    with TestClient(app) as client:
        assert client.get('/',headers={'Host':'desk.tail123.ts.net'}).status_code==200
        assert client.get('/',headers={'Host':'localhost:8510'}).status_code==200
        assert client.get('/',headers={'Host':'other.tail123.ts.net'}).status_code==400
        assert client.get('/',headers={'Host':'desk.tail123.ts.net.evil.example'}).status_code==400


@pytest.mark.parametrize('value',['*.ts.net','https://desk.tail.ts.net','desk.tail.ts.net:443','127.0.0.1','desk.ts.net/','x..tail.ts.net','foo.example.com'])
def test_invalid_remote_hosts_are_rejected(value):
    with pytest.raises(ValueError):validate_hostname(value)


def test_missing_or_corrupt_config_keeps_local_only(tmp_path):
    path=tmp_path/'remote.json'
    assert allowed_hosts(path)==LOCAL_HOSTS
    path.write_text('{bad json')
    assert allowed_hosts(path)==LOCAL_HOSTS


def test_configuration_is_private_idempotent_and_not_silently_replaced(tmp_path):
    path=tmp_path/'remote.json'
    save_hostname(path,'desk.tail123.ts.net')
    before=path.read_bytes()
    save_hostname(path,'desk.tail123.ts.net')
    assert path.read_bytes()==before
    assert path.stat().st_mode & 0o777 == 0o600
    with pytest.raises(ValueError):save_hostname(path,'another.tail123.ts.net')


def test_remote_origin_cannot_authorize_trades():
    from fastapi import HTTPException
    import secure_trade_routes as trade
    request=Request({'type':'http','method':'POST','path':'/api/trade/execute',
        'headers':[(b'host',b'desk.tail123.ts.net'),(b'origin',b'https://desk.tail123.ts.net')]})
    with pytest.raises(HTTPException) as error:trade._request_ok(request,trade._TOK)
    assert error.value.status_code==403
