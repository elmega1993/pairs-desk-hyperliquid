"""Behavior tests for the private, scope-bound Desk store."""
import copy
import os
import sqlite3

import pytest

from pairs_desk.ai.memory import MemoryStore


@pytest.fixture
def store(tmp_path):
    result = MemoryStore(tmp_path / 'private' / 'desk.sqlite3')
    yield result
    result.close()


def test_persistence_dedup_and_scope_isolation(store):
    row = store.remember('alan', 'Prefiero respuestas breves', metadata={'tag': 'idioma'})
    assert store.remember('alan', '  PREFIERO respuestas breves ')['id'] == row['id']
    assert store.list_memories('alan')['total'] == 1
    assert store.search('otra', 'respuestas') == []
    with pytest.raises(KeyError):
        store.get_memory('otra', row['id'])
    with pytest.raises(KeyError):
        store.update_memory('otra', row['id'], {'content': 'changed'})
    with pytest.raises(KeyError):
        store.delete_memory('otra', row['id'])
    again = MemoryStore(store.path)
    assert again.get_memory('alan', row['id'])['metadata'] == {'tag': 'idioma'}
    assert again.get_memory('alan', row['id'])['namespace'] == 'personal'
    again.close()


def test_retrieval_filters_expiry_pending_and_superseded(store):
    first = store.remember('s', 'Prefiero detalle en respuestas')
    replacement = store.remember('s', 'Prefiero respuestas breves', supersedes_id=first['id'])
    store.remember('s', 'respuestas pendientes', status='pending')
    store.remember('s', 'respuestas vencidas', valid_until='2020-01-01T00:00:00Z')
    found = store.search('s', 'respuestas')
    assert [m['id'] for m in found] == [replacement['id']]
    assert found[0]['retrieval_explanation']
    assert store.get_memory('s', first['id'])['status'] == 'superseded'


def test_update_reindexes_and_delete_removes_revisions(store):
    row = store.remember('s', 'Prefiero respuestas breves')
    store.update_memory('s', row['id'], {'content': 'Prefiero tablas legibles', 'importance': .9})
    assert store.search('s', 'breves') == []
    assert store.search('s', 'tablas')[0]['importance'] == .9
    with sqlite3.connect(store.path) as con:
        assert con.execute('select count(*) from memory_revisions').fetchone()[0] == 1
    store.delete_memory('s', row['id'])
    assert store.search('s', 'tablas') == []
    with sqlite3.connect(store.path) as con:
        assert con.execute('select count(*) from memory_revisions').fetchone()[0] == 0


@pytest.mark.parametrize('kwargs', [
    {'content': ''}, {'content': 'api_key=sk-secret-value'},
    {'content': 'private_key: ' + 'a' * 64}, {'content': 'BTC price is 70000 USD'},
    {'content': 'válido', 'importance': 2}, {'content': 'válido', 'status': 'bad'},
    {'content': 'válido', 'valid_until': 'tomorrow'},
])
def test_invalid_memories_are_rejected(store, kwargs):
    with pytest.raises(ValueError):
        store.remember('s', **kwargs)
    assert store.list_memories('s')['total'] == 0


def test_conversations_paginate_chronologically_and_cascade(store):
    c = store.create_conversation('s', 'Mi conversación')
    for i in range(5):
        store.add_message('s', c['id'], 'user', str(i))
    assert [m['content'] for m in store.messages('s', c['id'], limit=2)['items']] == ['0', '1']
    assert [m['content'] for m in store.messages('s', c['id'], limit=2, offset=2)['items']] == ['2', '3']
    store.set_summary('s', c['id'], 'El usuario prefiere concisión')
    assert store.get_conversation('s', c['id'])['summary'].startswith('El usuario')
    with pytest.raises(KeyError):
        store.add_message('other', c['id'], 'user', 'intruso')
    assert store.list_conversations('s')['total'] == 1
    store.delete_conversation('s', c['id'])
    with pytest.raises(KeyError):
        store.messages('s', c['id'])


def test_export_import_atomic_scope_and_settings(store, tmp_path):
    store.remember('s', 'Prefiero español')
    c = store.create_conversation('s')
    store.add_message('s', c['id'], 'assistant', 'incompleto', status='incomplete')
    store.update_settings('s', {'personal_rules': 'Usá español', 'temperature': .3})
    exported = store.export_data('s')
    other = MemoryStore(tmp_path / 'other.sqlite3')
    other.import_data('new', exported)
    assert other.list_memories('new')['total'] == 1
    assert other.list_conversations('new')['total'] == 1
    assert other.get_settings('new')['temperature'] == .3
    assert other.list_memories('s')['total'] == 0
    malformed = copy.deepcopy(exported)
    malformed['memories'].append({'content': 'api_key=secret'})
    with pytest.raises(ValueError):
        other.import_data('new', malformed)
    assert other.list_memories('new')['total'] == 1
    other.delete_data('new')
    assert other.list_conversations('new')['total'] == 0
    assert other.get_settings('new')['temperature'] == .2
    assert store.list_memories('s')['total'] == 1
    other.close()


def test_private_permissions_and_backup_survives_delete(store):
    store.remember('s', 'Prefiero español')
    backup = store.backup()
    assert os.stat(store.path).st_mode & 0o777 == 0o600
    assert os.stat(backup).st_mode & 0o777 == 0o600
    store.delete_data('s')
    restored = MemoryStore(backup)
    assert restored.list_memories('s')['total'] == 1
    restored.close()


def test_payload_cannot_replace_scope_or_ids(store):
    row = store.remember('s', 'Prefiero español')
    for patch in ({'scope': 'other'}, {'id': 'other'}, {'created_at': 'fake'}):
        with pytest.raises(ValueError):
            store.update_memory('s', row['id'], patch)
    with pytest.raises(ValueError):
        store.update_settings('s', {'scope': 'other'})
    with pytest.raises(ValueError):
        store.list_memories('s', limit=0)


def test_optional_local_embeddings_retrieve_without_lexical_match(tmp_path):
    class LocalEmbedder:
        def embed(self, text):
            return [1., 0.] if 'conciso' in text or 'breves' in text else [0., 1.]
    s = MemoryStore(tmp_path / 'vectors.sqlite3', embedder=LocalEmbedder())
    row = s.remember('s', 'Prefiero respuestas breves')
    assert s.search('s', 'conciso')[0]['id'] == row['id']
    s.delete_memory('s', row['id'])
    assert s.search('s', 'conciso') == []
    s.close()


def test_nested_confidential_metadata_and_messages_are_rejected(store):
    with pytest.raises(ValueError):
        store.remember('s', 'Prefiero español', metadata={'credentials': {'api_key': 'sensitive-value'}})
    c = store.create_conversation('s')
    with pytest.raises(ValueError):
        store.add_message('s', c['id'], 'user', 'Mi private key es ' + 'a' * 64)
    assert store.messages('s', c['id'])['total'] == 0


def test_explicit_supersession_via_update_removes_conflicting_retrieval(store):
    old = store.remember('s', 'Prefiero respuestas largas')
    new = store.remember('s', 'Prefiero respuestas breves')
    store.update_memory('s', new['id'], {'supersedes_id': old['id']})
    assert store.get_memory('s', old['id'])['status'] == 'superseded'
    assert [row['id'] for row in store.search('s', 'respuestas')] == [new['id']]
    with pytest.raises(ValueError):
        store.update_memory('s', old['id'], {'supersedes_id': new['id']})


def test_import_preserves_validated_dates_and_rejects_malformed_ids(store):
    original = store.remember('s', 'Prefiero español')
    c = store.create_conversation('s')
    message = store.add_message('s', c['id'], 'user', 'Recordá mis preferencias')
    exported = store.export_data('s')
    store.import_data('other', exported)
    assert store.list_memories('other')['items'][0]['created_at'] == original['created_at']
    conversation = store.list_conversations('other')['items'][0]
    assert conversation['created_at'] == c['created_at']
    assert store.messages('other', conversation['id'])['items'][0]['created_at'] == message['created_at']
    invalid = copy.deepcopy(exported)
    invalid['memories'][0]['id'] = []
    with pytest.raises(ValueError):
        store.import_data('broken', invalid)
    assert store.list_memories('broken')['total'] == 0
    invalid = copy.deepcopy(exported)
    invalid['memories'][0]['created_at'] = 'not-a-date'
    with pytest.raises(ValueError):
        store.import_data('broken', invalid)
    assert store.list_memories('broken')['total'] == 0


def test_conversations_expose_count_for_tail_pagination(store):
    c = store.create_conversation('s')
    for i in range(35):
        store.add_message('s', c['id'], 'user', str(i))
    assert store.get_conversation('s', c['id'])['message_count'] == 35
    assert store.list_conversations('s')['items'][0]['message_count'] == 35
    assert [r['content'] for r in store.messages('s', c['id'], offset=32)['items']] == ['32', '33', '34']


def test_knowledge_conversation_types_and_revision_provenance(store):
    row = store.remember('s', 'El diario agrupa fechas locales', type='knowledge')
    store.remember('s', 'El usuario comentó sus preferencias', type='conversation')
    store.update_memory('s', row['id'], {'content': 'El diario usa Buenos Aires'})
    revisions = store.memory_revisions('s', row['id'])
    assert revisions['total'] == 1
    assert revisions['items'][0]['snapshot']['content'] == 'El diario agrupa fechas locales'
    with pytest.raises(KeyError):
        store.memory_revisions('other', row['id'])
    with pytest.raises(ValueError):
        store.remember('s', 'BTC price is 70000 USD', type='operational')


def test_explicit_ollama_embedder_is_loopback_only_and_validates_response():
    import json
    from http.server import BaseHTTPRequestHandler, HTTPServer
    import threading
    from pairs_desk.ai.embeddings import OllamaLocalEmbedder

    with pytest.raises(ValueError):
        OllamaLocalEmbedder('local-model', endpoint='https://example.com')
    with pytest.raises(ValueError):
        OllamaLocalEmbedder('')

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            if self.path == '/api/show':
                response = b'{"details":{"family":"nomic-bert"}}'
                self.send_response(200)
                self.send_header('Content-Length', str(len(response)))
                self.end_headers()
                self.wfile.write(response)
                return
            if self.path != '/api/embed' or body.get('model') != 'local-model' or body.get('input') != 'breve':
                self.send_error(400)
                return
            response = json.dumps({'embeddings': [[3., 4.]]}).encode()
            self.send_response(200)
            self.send_header('Content-Length', str(len(response)))
            self.end_headers()
            self.wfile.write(response)
        def log_message(self, *args):
            pass

    server = HTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        embedder = OllamaLocalEmbedder('local-model', endpoint=f'http://127.0.0.1:{server.server_port}')
        assert embedder.embed('breve') == pytest.approx([.6, .8])
        with pytest.raises(ValueError):
            embedder.embed('unrecognized request')
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


@pytest.mark.parametrize('patch', [{'type': []}, {'status': []}, {'metadata': []}])
def test_invalid_field_types_reject_without_silent_coercion(store, patch):
    with pytest.raises(ValueError):
        store.remember('s', 'Prefiero español', **patch)
    assert store.list_memories('s')['total'] == 0


def test_common_stopwords_do_not_retrieve_unrelated_memory(store):
    store.remember('s', 'El usuario prefiere respuestas breves')
    assert store.search('s', 'cuál es el funding actual') == []


def test_dedup_does_not_merge_different_memory_kinds(store):
    first = store.remember('s', 'Prefiero respuestas breves', category='preference')
    other_category = store.remember('s', 'Prefiero respuestas breves', category='rule')
    other_type = store.remember('s', 'Prefiero respuestas breves', type='procedural')
    assert len({first['id'], other_category['id'], other_type['id']}) == 3


def test_duplicate_proposals_and_explicit_consolidation_keep_provenance(store):
    keep = store.remember('s', 'Prefiero respuestas breves y claras')
    duplicate = store.remember('s', 'Prefiero respuestas breves claras', source_id='message-123')
    store.remember('s', 'No prefiero respuestas breves y claras')
    store.remember('other', 'Prefiero respuestas breves claras')
    candidates = store.find_duplicates('s', keep['id'])
    assert [r['id'] for r in candidates] == [duplicate['id']]
    assert candidates[0]['score'] > 0
    assert store.get_memory('s', duplicate['id'])['status'] == 'active'
    merged = store.consolidate('s', keep['id'], [duplicate['id']])
    assert merged['content'] == 'Prefiero respuestas breves y claras'
    assert merged['metadata']['consolidated_from'][0]['source_id'] == 'message-123'
    old = store.get_memory('s', duplicate['id'])
    assert old['status'] == 'superseded'
    assert old['content'] == 'Prefiero respuestas breves claras'
    assert old['metadata']['consolidated_into'] == keep['id']
    assert store.memory_revisions('s', keep['id'])['total'] == 1
    assert store.memory_revisions('s', duplicate['id'])['total'] == 1


def test_consolidation_rejects_cross_scope_kinds_and_empty_lists_atomically(store):
    keep = store.remember('s', 'Prefiero respuestas breves')
    foreign = store.remember('other', 'Prefiero respuestas claras')
    wrong_kind = store.remember('s', 'Prefiero respuestas claras', type='knowledge')
    first = store.remember('s', 'Prefiero respuestas breves claras')
    with pytest.raises(KeyError):
        store.consolidate('s', keep['id'], [first['id'], foreign['id']])
    with pytest.raises(ValueError):
        store.consolidate('s', keep['id'], [wrong_kind['id']])
    with pytest.raises(ValueError):
        store.consolidate('s', keep['id'], [])
    assert store.get_memory('s', first['id'])['status'] == 'active'
    assert store.memory_revisions('s', first['id'])['total'] == 0


@pytest.mark.parametrize('patch', [
    {'temperature': 1.1}, {'max_tokens': 99}, {'max_tokens': 1401},
    {'memory_budget': 2401}, {'history_budget': 119},
    {'history_budget': 2401}, {'personal_rules': 'x' * 6001},
])
def test_import_cannot_bypass_api_settings_limits(store, patch):
    data = store.export_data('s')
    data['settings'].update(patch)
    with pytest.raises(ValueError):
        store.import_data('s', data)
    assert store.get_settings('s')['max_tokens'] == 1400


def test_remote_ollama_metadata_blocks_embedding_text():
    import json
    from http.server import BaseHTTPRequestHandler, HTTPServer
    import threading
    from pairs_desk.ai.embeddings import OllamaLocalEmbedder
    with pytest.raises(ValueError):
        OllamaLocalEmbedder('nomic-cloud')
    requests_seen = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            requests_seen.append(self.path)
            self.rfile.read(int(self.headers['Content-Length']))
            response = json.dumps({'remote_host': 'https://remote.example', 'remote_model': 'nomic'}).encode()
            self.send_response(200)
            self.send_header('Content-Length', str(len(response)))
            self.end_headers()
            self.wfile.write(response)
        def log_message(self, *args):
            pass
    server = HTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        adapter = OllamaLocalEmbedder('aliased-model', endpoint=f'http://127.0.0.1:{server.server_port}')
        with pytest.raises(ValueError):
            adapter.embed('private memory must never leave this machine')
        assert requests_seen == ['/api/show']
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_embeddings_reject_text_and_normalize_large_finite_vectors():
    from pairs_desk.ai.embeddings import normalize_vector
    with pytest.raises(ValueError):
        normalize_vector('123')
    assert normalize_vector([1e308, 1e308]) == pytest.approx([.7071067811865475, .7071067811865475])
