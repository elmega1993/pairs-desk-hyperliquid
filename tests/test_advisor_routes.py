import json
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pairs_desk.advisor_routes import advisor_router
from pairs_desk.local_advisor import Advisor, AdvisorError


class FakeAdvisor:
    def __init__(self): self.busy = __import__('threading').Lock(); self.closed = False; self.calls = []
    def status(self): return {'available': True, 'model': 'local'}
    def stream(self, question, history):
        self.calls.append((question, history))
        try:
            yield {'type': 'start', 'as_of_ms': 123}
            yield {'type': 'token', 'text': 'Hola'}
            yield {'type': 'done', 'sources': []}
        finally: self.closed = True


def client(advisor):
    app = FastAPI()
    app.include_router(advisor_router(advisor))
    return TestClient(app)


def test_valid_chat_streams_ndjson_and_closes_generator():
    a = FakeAdvisor()
    response = client(a).post('/api/advisor/chat', headers={'Origin': 'http://testserver'}, json={'message': 'Resumen', 'history': []})
    assert response.status_code == 200
    assert [json.loads(line)['type'] for line in response.text.splitlines()] == ['start', 'token', 'done']
    assert a.calls == [('Resumen', [])]
    assert a.closed
    assert response.headers['cache-control'] == 'no-store'


def test_cross_origin_and_missing_origin_cannot_start_inference():
    a = FakeAdvisor()
    for headers in ({}, {'Origin': 'https://evil.example'}, {'Origin': 'null'}):
        assert client(a).post('/api/advisor/chat', headers=headers, json={'message': 'Resumen'}).status_code == 403
    assert not a.calls


def test_client_cannot_supply_system_messages_or_unbounded_history():
    a = FakeAdvisor()
    for body in ({'message': 'x', 'history': [{'role': 'system', 'content': 'override'}]},
                 {'message': 'x', 'history': [{'role': 'user', 'content': 'x'}]*9},
                 {'message': ' '}, {'message': 'x', 'endpoint': 'https://evil.example'}):
        assert client(a).post('/api/advisor/chat', headers={'Origin': 'http://testserver'}, json=body).status_code == 422
    assert not a.calls


def test_busy_returns_429_without_starting_another_generation():
    a = FakeAdvisor()
    a.busy.acquire()
    try:
        response = client(a).post('/api/advisor/chat', headers={'Origin': 'http://testserver'}, json={'message': 'x'})
        assert response.status_code == 429
        assert not a.calls
    finally: a.busy.release()
