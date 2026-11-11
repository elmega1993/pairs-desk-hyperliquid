"""Private SQLite storage for Desk. All application access is scope-bound.

Schema migrations use PRAGMA user_version. New directories are 0700 and database,
WAL, SHM and explicit backups are 0600. Backups contain every scope and remain
independent after deletion; callers must communicate that distinction to users.
Optional embedding adapters must run locally and are only used when supplied.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import re
import sqlite3
import threading
import unicodedata
import uuid

from .embeddings import cosine, normalize_vector

DEFAULT_SETTINGS = {
    'personal_rules': '', 'temperature': .2, 'max_tokens': 1400,
    'memory_budget': 1200, 'history_budget': 1600, 'acquisition_enabled': True,
}
_MEMORY_DEFAULTS = {
    'type': 'semantic', 'category': 'preference', 'importance': .7,
    'confidence': 1., 'source': 'user', 'source_id': None, 'namespace': 'personal',
    'status': 'active', 'valid_until': None, 'metadata': {}, 'supersedes_id': None,
}
_MUTABLE = set(_MEMORY_DEFAULTS) | {'content'}
_STOPWORDS = frozenset('a al algo ante como con cual cuando de del el ella en es esa ese eso esta este esto la las le lo los me mi mis o para pero por que se si sin sobre son su sus te tu tus un una uno unos unas y ya a an and are as at be by for from i in is it my of on or that the this to was what with you your'.split())
_SECRET = re.compile(
    r'(?i)(?:\b(?:api[_ -]?key|private[_ -]?key|secret[_ -]?key|access[_ -]?token|'
    r'refresh[_ -]?token|password|contrase[ñn]a|seed[_ -]?phrase|mnemonic)[\s\"\']*'
    r'(?:[=:]|\bes\b|\bis\b)[\s\"\']*\S+'
    r'|\b(?:sk-[A-Za-z0-9_-]{8,}|gh[pousr]_[A-Za-z0-9]{15,})\b'
    r'|\bBearer\s+[A-Za-z0-9_.-]{8,}|\b0x[a-f0-9]{64}\b'
    r'|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)'
)
_QUOTE = re.compile(
    r'(?i)(?:\b(?:price|precio|cotizaci[oó]n|mark[_ ]?price|pnl|funding|saldo|balance)'
    r'\s*(?:actual|is|es|de|=|:)?\s*[$€]?\s*-?\d'
    r'|\b[A-Z]{2,10}\s+(?:price|precio)\s+(?:is|es)?\s*\d)'
)


def _now():
    return datetime.now(timezone.utc).isoformat()


def _text(value, maximum=8000, *, empty=False):
    if not isinstance(value, str) or len(value) > maximum or (not empty and not value.strip()):
        raise ValueError('Invalid text')
    if _SECRET.search(value):
        raise ValueError('Confidential credentials cannot be stored')
    return value.strip()


def _json(value):
    try:
        result = json.dumps(value, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError('Invalid JSON data') from exc
    if len(result) > 32000:
        raise ValueError('Metadata too large')
    if _SECRET.search(result):
        raise ValueError('Confidential credentials cannot be stored')
    return result


def _import_identity(raw):
    if not isinstance(raw, dict):
        raise ValueError('Import row must be an object')
    identifier = _text(raw.get('id'), 256)
    dates = {}
    for field in ('created_at', 'updated_at', 'last_accessed_at'):
        if field in raw:
            dates[field] = _date(raw[field])
            if field != 'last_accessed_at' and dates[field] is None:
                raise ValueError('Missing imported date')
    if 'access_count' in raw:
        count = raw['access_count']
        if type(count) is not int or not 0 <= count <= 2**53:
            raise ValueError('Invalid access count')
        dates['access_count'] = count
    return identifier, dates


def _date(value):
    if value is None:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if parsed.tzinfo is None:
            raise ValueError('Timezone required')
        return parsed.astimezone(timezone.utc).isoformat()
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValueError('Invalid timestamp') from exc


def _number(value, minimum, maximum):
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value) or not minimum <= value <= maximum:
        raise ValueError('Number outside allowed range')
    return value


def _normalized(text):
    return ' '.join(unicodedata.normalize('NFKC', text).casefold().split())


def _terms(text):
    return set(re.findall(r'\w+', _normalized(text)))


def _polarity(text):
    words = _terms(text)
    axes = (
        ({'no', 'not', 'nunca', 'jamás', 'never', 'sin', 'without'}, set()),
        ({'breve', 'breves', 'corto', 'cortos', 'conciso', 'concisos', 'short'},
         {'largo', 'largos', 'larga', 'largas', 'extenso', 'extensos', 'detallado', 'detailed', 'long'}),
        ({'similar', 'similares', 'same', 'igual', 'iguales'}, {'diferente', 'diferentes', 'different', 'distinto', 'distintos'}),
    )
    return tuple((bool(words & positive), bool(words & negative)) for positive, negative in axes)


def _page(limit, offset, maximum=200):
    if type(limit) is not int or type(offset) is not int or not 1 <= limit <= maximum or offset < 0:
        raise ValueError('Invalid pagination')


class MemoryStore:
    def __init__(self, path, embedder=None):
        self.path = Path(path).expanduser()
        if not self.path.parent.exists():
            self.path.parent.mkdir(mode=0o700, parents=True)
        if not self.path.exists():
            fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.close(fd)
        os.chmod(self.path, 0o600)
        self.embedder = embedder
        self._lock = threading.RLock()
        self._depth = 0
        self._db = sqlite3.connect(str(self.path), check_same_thread=False, timeout=15)
        self._db.row_factory = sqlite3.Row
        self._db.execute('PRAGMA foreign_keys=ON')
        self._db.execute('PRAGMA secure_delete=ON')
        self._db.execute('PRAGMA journal_mode=WAL')
        self._migrate()
        self._permissions()

    def _permissions(self):
        for suffix in ('', '-wal', '-shm'):
            path = Path(str(self.path) + suffix)
            if path.exists():
                os.chmod(path, 0o600)

    def _migrate(self):
        version = self._db.execute('PRAGMA user_version').fetchone()[0]
        if version > 1:
            raise ValueError('Unsupported future Desk schema')
        if version == 0:
            self._db.executescript('''
            BEGIN;
            CREATE TABLE memories (
                id TEXT PRIMARY KEY, scope TEXT NOT NULL, content TEXT NOT NULL,
                type TEXT NOT NULL, category TEXT NOT NULL, importance REAL NOT NULL,
                confidence REAL NOT NULL, source TEXT NOT NULL, source_id TEXT,
                namespace TEXT NOT NULL, status TEXT NOT NULL, valid_until TEXT,
                metadata TEXT NOT NULL, supersedes_id TEXT, normalized TEXT NOT NULL,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                last_accessed_at TEXT, access_count INTEGER NOT NULL DEFAULT 0
            );
            CREATE INDEX memories_scope_status ON memories(scope,status,updated_at);
            CREATE INDEX memories_dedup ON memories(scope,namespace,normalized);
            CREATE TABLE memory_revisions (
                id INTEGER PRIMARY KEY, memory_id TEXT NOT NULL REFERENCES memories(id) ON DELETE CASCADE,
                scope TEXT NOT NULL, snapshot TEXT NOT NULL, created_at TEXT NOT NULL
            );
            CREATE INDEX revisions_scope ON memory_revisions(scope,memory_id);
            CREATE VIRTUAL TABLE memory_fts USING fts5(id UNINDEXED, scope UNINDEXED, content, tokenize='unicode61 remove_diacritics 2');
            CREATE TABLE memory_vectors (
                memory_id TEXT PRIMARY KEY REFERENCES memories(id) ON DELETE CASCADE,
                scope TEXT NOT NULL, vector TEXT NOT NULL
            );
            CREATE INDEX vectors_scope ON memory_vectors(scope);
            CREATE TABLE conversations (
                id TEXT PRIMARY KEY, scope TEXT NOT NULL, title TEXT NOT NULL,
                summary TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL, updated_at TEXT NOT NULL
            );
            CREATE INDEX conversations_scope ON conversations(scope,updated_at);
            CREATE TABLE messages (
                seq INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT NOT NULL UNIQUE,
                scope TEXT NOT NULL, conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
                role TEXT NOT NULL, content TEXT NOT NULL, status TEXT NOT NULL,
                metadata TEXT NOT NULL, created_at TEXT NOT NULL
            );
            CREATE INDEX messages_scope_conversation ON messages(scope,conversation_id,seq);
            CREATE TABLE settings (scope TEXT PRIMARY KEY, data TEXT NOT NULL);
            PRAGMA user_version=1;
            COMMIT;
            ''')

    @contextmanager
    def _transaction(self):
        with self._lock:
            outer = self._depth == 0
            if outer:
                self._db.execute('BEGIN IMMEDIATE')
            self._depth += 1
            try:
                yield
            except BaseException:
                if outer:
                    self._db.rollback()
                raise
            else:
                if outer:
                    self._db.commit()
            finally:
                self._depth -= 1
                self._permissions()

    def close(self):
        with self._lock:
            self._db.close()

    @staticmethod
    def _scope(scope):
        return _text(scope, 256)

    @staticmethod
    def _row(row):
        result = dict(row)
        result.pop('scope', None)
        result.pop('normalized', None)
        result.pop('seq', None)
        if 'metadata' in result:
            result['metadata'] = json.loads(result['metadata'])
        return result

    def _get(self, table, scope, identifier):
        row = self._db.execute(f'SELECT * FROM {table} WHERE scope=? AND id=?', (self._scope(scope), identifier)).fetchone()
        if row is None:
            raise KeyError('Record not found')
        return self._row(row)

    def _validate_memory(self, values):
        if set(values) - _MUTABLE:
            raise ValueError('Unknown memory fields')
        data = {**_MEMORY_DEFAULTS, **values}
        data['content'] = _text(data.get('content'))
        if not isinstance(data['type'], str) or data['type'] not in {'semantic', 'episodic', 'procedural', 'knowledge', 'conversation'}:
            raise ValueError('Invalid memory type')
        if not isinstance(data['status'], str) or data['status'] not in {'active', 'pending', 'inactive', 'superseded', 'rejected', 'expired'}:
            raise ValueError('Invalid memory status')
        if data['type'] == 'semantic' and _QUOTE.search(data['content']):
            raise ValueError('Operational quotes are not durable semantic memories')
        for field in ('category', 'namespace', 'source'):
            data[field] = _text(data[field], 100)
        for field in ('source_id', 'supersedes_id'):
            if data[field] is not None:
                data[field] = _text(data[field], 256)
        for field in ('importance', 'confidence'):
            data[field] = _number(data[field], 0, 1)
        if not isinstance(data['metadata'], dict):
            raise ValueError('Metadata must be an object')
        _json(data['metadata'])
        data['valid_until'] = _date(data['valid_until'])
        return data

    def _index(self, scope, row):
        self._db.execute('DELETE FROM memory_fts WHERE scope=? AND id=?', (scope, row['id']))
        self._db.execute('INSERT INTO memory_fts(id,scope,content) VALUES (?,?,?)', (row['id'], scope, row['content']))
        self._db.execute('DELETE FROM memory_vectors WHERE scope=? AND memory_id=?', (scope, row['id']))
        if self.embedder is not None:
            try:
                vector = normalize_vector(self.embedder.embed(row['content']))
            except Exception:
                return  # lexical search stays available when the optional adapter fails
            self._db.execute('INSERT INTO memory_vectors VALUES (?,?,?)', (row['id'], scope, json.dumps(vector)))

    def remember(self, scope, content, *, type='semantic', category='preference', importance=.7,
                 confidence=1, source='user', source_id=None, namespace='personal', status='active',
                 valid_until=None, metadata=None, supersedes_id=None):
        scope = self._scope(scope)
        values = self._validate_memory(dict(content=content, type=type, category=category,
            importance=importance, confidence=confidence, source=source, source_id=source_id,
            namespace=namespace, status=status, valid_until=valid_until, metadata={} if metadata is None else metadata,
            supersedes_id=supersedes_id))
        with self._transaction():
            previous = None
            if supersedes_id:
                previous = self.get_memory(scope, supersedes_id)
            duplicate = self._db.execute('''SELECT * FROM memories WHERE scope=? AND namespace=?
                AND type=? AND category=? AND normalized=? AND status IN ('active','pending')
                AND (valid_until IS NULL OR valid_until>?)''',
                (scope, values['namespace'], values['type'], values['category'], _normalized(values['content']), _now())).fetchone()
            if duplicate is not None:
                return self._row(duplicate)
            if previous is not None:
                self.update_memory(scope, previous['id'], {'status': 'superseded'})
            now, identifier = _now(), uuid.uuid4().hex
            data = {**values, 'metadata': _json(values['metadata']), 'id': identifier, 'scope': scope,
                    'normalized': _normalized(values['content']), 'created_at': now, 'updated_at': now}
            columns = ','.join(data)
            self._db.execute(f'INSERT INTO memories ({columns}) VALUES ({",".join("?" for _ in data)})', tuple(data.values()))
            row = self.get_memory(scope, identifier)
            self._index(scope, row)
            return row

    def get_memory(self, scope, id):
        with self._lock:
            return self._get('memories', scope, id)

    def memory_revisions(self, scope, id, limit=20, offset=0):
        scope = self._scope(scope)
        _page(limit, offset)
        with self._lock:
            self.get_memory(scope, id)
            args = (scope, id)
            total = self._db.execute('SELECT count(*) FROM memory_revisions WHERE scope=? AND memory_id=?', args).fetchone()[0]
            rows = self._db.execute('SELECT id,memory_id,snapshot,created_at FROM memory_revisions WHERE scope=? AND memory_id=? ORDER BY id DESC LIMIT ? OFFSET ?', (*args, limit, offset)).fetchall()
            items = [{**dict(row), 'snapshot': json.loads(row['snapshot'])} for row in rows]
            return {'items': items, 'total': total, 'offset': offset, 'limit': limit}

    def list_memories(self, scope, query='', limit=20, offset=0, status=None):
        scope = self._scope(scope)
        _page(limit, offset)
        query = _text(query, 2000, empty=True)
        where, args = 'scope=?', [scope]
        if query:
            where += " AND content LIKE ? ESCAPE '\\'"
            args.append('%' + query.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_') + '%')
        if status is not None:
            if not isinstance(status, str) or status not in {'active', 'pending', 'inactive', 'superseded', 'rejected', 'expired'}:
                raise ValueError('Invalid status')
            where += ' AND status=?'
            args.append(status)
        with self._lock:
            total = self._db.execute(f'SELECT count(*) FROM memories WHERE {where}', args).fetchone()[0]
            rows = self._db.execute(f'SELECT * FROM memories WHERE {where} ORDER BY updated_at DESC,id LIMIT ? OFFSET ?', [*args, limit, offset]).fetchall()
        return {'items': [self._row(r) for r in rows], 'total': total, 'offset': offset, 'limit': limit}

    def search(self, scope, query, limit=8):
        scope = self._scope(scope)
        _page(limit, 0, 50)
        query = _text(query, 2000, empty=True)
        if not query:
            return []
        tokens = [t for t in re.findall(r'\w+', query.casefold(), flags=re.UNICODE) if t not in _STOPWORDS][:40]
        if not tokens:
            return []
        expression = ' OR '.join('"' + word.replace('"', '""') + '"' for word in tokens)
        with self._transaction():
            lexical = self._db.execute('''SELECT m.*,bm25(memory_fts) AS lexical_rank FROM memory_fts
                JOIN memories m ON m.id=memory_fts.id AND m.scope=memory_fts.scope
                WHERE memory_fts MATCH ? AND m.scope=? AND m.status='active'
                AND (m.valid_until IS NULL OR m.valid_until>?) ORDER BY lexical_rank LIMIT 200''',
                (expression, scope, _now())).fetchall()
            candidates = {r['id']: (self._row(r), 1. / (1. + i), 0.) for i, r in enumerate(lexical)}
            if self.embedder is not None:
                try:
                    query_vector = normalize_vector(self.embedder.embed(query))
                except Exception:
                    query_vector = None
                if query_vector:
                    rows = self._db.execute('''SELECT m.*,v.vector FROM memory_vectors v JOIN memories m ON m.id=v.memory_id
                        AND m.scope=v.scope WHERE m.scope=? AND m.status='active'
                        AND (m.valid_until IS NULL OR m.valid_until>?) ORDER BY m.updated_at DESC LIMIT 2000''', (scope, _now())).fetchall()
                    for raw in rows:
                        similarity = cosine(query_vector, json.loads(raw['vector']))
                        if similarity >= .35:
                            existing = candidates.get(raw['id'])
                            row = self._row(raw)
                            row.pop('vector', None)
                            candidates[raw['id']] = (row, existing[1] if existing else 0., similarity)
            ranked = []
            for row, lexical_score, semantic_score in candidates.values():
                row.pop('lexical_rank', None)
                age = max(0., (datetime.now(timezone.utc) - datetime.fromisoformat(row['updated_at'])).total_seconds() / 86400)
                recency = 1 / (1 + age / 30)
                row['score'] = round(.55 * max(lexical_score, semantic_score) + .2 * row['importance'] + .15 * row['confidence'] + .1 * recency, 6)
                row['retrieval_explanation'] = {'lexical': round(lexical_score, 4), 'semantic': round(semantic_score, 4),
                    'importance': row['importance'], 'confidence': row['confidence'], 'recency': round(recency, 4)}
                ranked.append(row)
            ranked.sort(key=lambda r: (-r['score'], r['id']))
            result = ranked[:limit]
            for row in result:
                self._db.execute('UPDATE memories SET last_accessed_at=?,access_count=access_count+1 WHERE scope=? AND id=?', (_now(), scope, row['id']))
            return result

    def update_memory(self, scope, id, patch):
        scope = self._scope(scope)
        if not isinstance(patch, dict) or set(patch) - _MUTABLE:
            raise ValueError('Unknown memory fields')
        with self._transaction():
            old = self.get_memory(scope, id)
            data = self._validate_memory({**{k: old[k] for k in _MUTABLE}, **patch})
            if data['supersedes_id']:
                if data['supersedes_id'] == id:
                    raise ValueError('Cannot supersede itself')
                target = self.get_memory(scope, data['supersedes_id'])
                seen = {id}
                while target is not None:
                    if target['id'] in seen:
                        raise ValueError('Cyclic supersession')
                    seen.add(target['id'])
                    target = self.get_memory(scope, target['supersedes_id']) if target['supersedes_id'] else None
                if data['supersedes_id'] != old['supersedes_id']:
                    self.update_memory(scope, data['supersedes_id'], {'status': 'superseded'})
            self._db.execute('INSERT INTO memory_revisions(memory_id,scope,snapshot,created_at) VALUES (?,?,?,?)', (id, scope, _json(old), _now()))
            data['metadata'] = _json(data['metadata'])
            data.update(updated_at=_now(), normalized=_normalized(data['content']))
            self._db.execute(f'UPDATE memories SET {",".join(k+"=?" for k in data)} WHERE scope=? AND id=?', [*data.values(), scope, id])
            row = self.get_memory(scope, id)
            self._index(scope, row)
            return row

    def find_duplicates(self, scope, id, limit=5):
        """Propose consolidation candidates; never automatically merge meaning.

        Embedding proximity can hide opposing preferences. Only explicit
        consolidation changes records; proposals reject mismatched polarity.
        """
        scope = self._scope(scope)
        _page(limit, 0, 50)
        with self._lock:
            target = self.get_memory(scope, id)
            rows = self._db.execute('''SELECT m.*,v.vector FROM memories m
                LEFT JOIN memory_vectors v ON v.memory_id=m.id AND v.scope=m.scope
                WHERE m.scope=? AND m.id<>? AND m.type=? AND m.category=? AND m.namespace=?
                AND m.status IN ('active','pending') AND (m.valid_until IS NULL OR m.valid_until>?)
                ORDER BY m.updated_at DESC LIMIT 2000''',
                (scope, id, target['type'], target['category'], target['namespace'], _now())).fetchall()
            vector = self._db.execute('SELECT vector FROM memory_vectors WHERE scope=? AND memory_id=?', (scope, id)).fetchone()
            target_vector = json.loads(vector['vector']) if vector else None
            terms = _terms(target['content']) - _STOPWORDS
            candidates = []
            for raw in rows:
                if _polarity(raw['content']) != _polarity(target['content']):
                    continue
                other_terms = _terms(raw['content']) - _STOPWORDS
                union = terms | other_terms
                lexical = len(terms & other_terms) / len(union) if union else 0.
                semantic = cosine(target_vector, json.loads(raw['vector'])) if target_vector and raw['vector'] else 0.
                if lexical < .45 and semantic < .85:
                    continue
                candidate = self._row(raw)
                candidate.pop('vector', None)
                candidate.update(score=round(max(lexical, semantic), 6), lexical_similarity=round(lexical, 6), semantic_similarity=round(semantic, 6))
                candidates.append(candidate)
            candidates.sort(key=lambda row: (-row['score'], row['id']))
            return candidates[:limit]

    def consolidate(self, scope, keep_id, duplicate_ids):
        """Explicitly consolidate same-kind records, retaining all originals."""
        scope = self._scope(scope)
        if not isinstance(duplicate_ids, list) or not 1 <= len(duplicate_ids) <= 50:
            raise ValueError('Supply between one and fifty duplicate ids')
        identifiers = [_text(id, 256) for id in duplicate_ids]
        if len(set(identifiers)) != len(identifiers) or keep_id in identifiers:
            raise ValueError('Duplicate ids must be distinct from the retained memory')
        with self._transaction():
            keep = self.get_memory(scope, keep_id)
            duplicates = [self.get_memory(scope, id) for id in identifiers]
            for row in [keep, *duplicates]:
                if any(row[field] != keep[field] for field in ('type', 'category', 'namespace')):
                    raise ValueError('Only memories of the same kind can be consolidated')
                if row['status'] not in {'active', 'pending'} or (row['valid_until'] and row['valid_until'] <= _now()):
                    raise ValueError('Only current memories can be consolidated')
            metadata = dict(keep['metadata'])
            provenance = metadata.get('consolidated_from', [])
            if not isinstance(provenance, list):
                raise ValueError('Invalid consolidation provenance')
            provenance = list(provenance)
            for row in duplicates:
                provenance.append({'id': row['id'], 'source': row['source'], 'source_id': row['source_id']})
                self.update_memory(scope, row['id'], {'status': 'superseded',
                    'metadata': {**row['metadata'], 'consolidated_into': keep_id}})
            metadata['consolidated_from'] = provenance
            return self.update_memory(scope, keep_id, {'metadata': metadata})

    def delete_memory(self, scope, id):
        scope = self._scope(scope)
        with self._transaction():
            self.get_memory(scope, id)
            self._db.execute('DELETE FROM memory_fts WHERE scope=? AND id=?', (scope, id))
            self._db.execute('UPDATE memories SET supersedes_id=NULL WHERE scope=? AND supersedes_id=?', (scope, id))
            self._db.execute('DELETE FROM memories WHERE scope=? AND id=?', (scope, id))

    def create_conversation(self, scope, title='Nueva conversación'):
        scope, title = self._scope(scope), _text(title, 300)
        with self._transaction():
            id, now = uuid.uuid4().hex, _now()
            self._db.execute('INSERT INTO conversations VALUES (?,?,?,?,?,?)', (id, scope, title, '', now, now))
            return self.get_conversation(scope, id)

    def get_conversation(self, scope, id):
        with self._lock:
            result = self._get('conversations', scope, id)
            result['message_count'] = self._db.execute('SELECT count(*) FROM messages WHERE scope=? AND conversation_id=?', (scope, id)).fetchone()[0]
            return result

    def list_conversations(self, scope, limit=20, offset=0):
        scope = self._scope(scope)
        _page(limit, offset)
        with self._lock:
            total = self._db.execute('SELECT count(*) FROM conversations WHERE scope=?', (scope,)).fetchone()[0]
            rows = self._db.execute('''SELECT c.*,(SELECT count(*) FROM messages m WHERE m.scope=c.scope AND m.conversation_id=c.id) AS message_count
                FROM conversations c WHERE c.scope=? ORDER BY c.updated_at DESC,c.id LIMIT ? OFFSET ?''', (scope, limit, offset)).fetchall()
            return {'items': [self._row(r) for r in rows], 'total': total, 'offset': offset, 'limit': limit}

    def delete_conversation(self, scope, id):
        scope = self._scope(scope)
        with self._transaction():
            self.get_conversation(scope, id)
            self._db.execute('DELETE FROM conversations WHERE scope=? AND id=?', (scope, id))

    def add_message(self, scope, conversation_id, role, content, status='complete', metadata=None):
        scope = self._scope(scope)
        content = _text(content, 64000, empty=status == 'incomplete')
        if not isinstance(role, str) or not isinstance(status, str) or role not in {'user', 'assistant'} or status not in {'complete', 'incomplete'}:
            raise ValueError('Invalid message role or status')
        if metadata is not None and not isinstance(metadata, dict):
            raise ValueError('Invalid message metadata')
        metadata = _json(metadata or {})
        with self._transaction():
            self.get_conversation(scope, conversation_id)
            id, now = uuid.uuid4().hex, _now()
            self._db.execute('''INSERT INTO messages(id,scope,conversation_id,role,content,status,metadata,created_at)
                VALUES (?,?,?,?,?,?,?,?)''', (id, scope, conversation_id, role, content, status, metadata, now))
            self._db.execute('UPDATE conversations SET updated_at=? WHERE scope=? AND id=?', (now, scope, conversation_id))
            return self._get('messages', scope, id)

    def messages(self, scope, id, limit=30, offset=0):
        scope = self._scope(scope)
        _page(limit, offset)
        with self._lock:
            self.get_conversation(scope, id)
            total = self._db.execute('SELECT count(*) FROM messages WHERE scope=? AND conversation_id=?', (scope, id)).fetchone()[0]
            rows = self._db.execute('SELECT * FROM messages WHERE scope=? AND conversation_id=? ORDER BY seq LIMIT ? OFFSET ?', (scope, id, limit, offset)).fetchall()
            return {'items': [self._row(r) for r in rows], 'total': total, 'offset': offset, 'limit': limit}

    def set_summary(self, scope, id, summary):
        scope, summary = self._scope(scope), _text(summary, 12000, empty=True)
        with self._transaction():
            self.get_conversation(scope, id)
            self._db.execute('UPDATE conversations SET summary=?,updated_at=? WHERE scope=? AND id=?', (summary, _now(), scope, id))

    def get_settings(self, scope):
        scope = self._scope(scope)
        with self._lock:
            row = self._db.execute('SELECT data FROM settings WHERE scope=?', (scope,)).fetchone()
            return {**DEFAULT_SETTINGS, **(json.loads(row[0]) if row else {})}

    def update_settings(self, scope, patch):
        scope = self._scope(scope)
        if not isinstance(patch, dict) or set(patch) - set(DEFAULT_SETTINGS):
            raise ValueError('Unknown settings')
        for field, value in patch.items():
            if field == 'personal_rules':
                _text(value, 6000, empty=True)
            elif field == 'acquisition_enabled':
                if type(value) is not bool:
                    raise ValueError('Acquisition flag must be boolean')
            elif field == 'temperature':
                _number(value, 0, 1)
            else:
                if type(value) is not int:
                    raise ValueError('Token budgets must be integers')
                bounds = {'max_tokens': (100, 1400), 'memory_budget': (0, 2400), 'history_budget': (120, 2400)}
                _number(value, *bounds[field])
        with self._transaction():
            data = {**self.get_settings(scope), **patch}
            self._db.execute('INSERT INTO settings VALUES (?,?) ON CONFLICT(scope) DO UPDATE SET data=excluded.data', (scope, _json(data)))
            return data

    def export_data(self, scope):
        scope = self._scope(scope)
        with self._transaction():
            def rows(table, order='created_at,id'):
                return [self._row(r) for r in self._db.execute(f'SELECT * FROM {table} WHERE scope=? ORDER BY {order}', (scope,))]
            return {'version': 1, 'exported_at': _now(), 'memories': rows('memories'),
                'conversations': rows('conversations'), 'messages': rows('messages', 'seq'), 'settings': self.get_settings(scope)}

    def import_data(self, scope, data):
        """Validate and merge an export atomically, remapping IDs into this scope."""
        scope = self._scope(scope)
        try:
            encoded = json.dumps(data, allow_nan=False)
        except (TypeError, ValueError) as exc:
            raise ValueError('Invalid import') from exc
        if len(encoded) > 8_000_000 or not isinstance(data, dict) or data.get('version') != 1:
            raise ValueError('Unsupported or oversized import')
        if set(data) - {'version', 'exported_at', 'memories', 'conversations', 'messages', 'settings'}:
            raise ValueError('Unknown import fields')
        for key in ('memories', 'conversations', 'messages'):
            if not isinstance(data.get(key), list) or len(data[key]) > 10000:
                raise ValueError('Invalid import collections')
        with self._transaction():
            self.update_settings(scope, data.get('settings', {}))
            memory_ids = {}
            pending_links = []
            for raw in data['memories']:
                original_id, dates = _import_identity(raw)
                if not isinstance(raw, dict) or 'id' not in raw or set(raw) - (_MUTABLE | {'id','created_at','updated_at','last_accessed_at','access_count'}):
                    raise ValueError('Invalid imported memory')
                if original_id in memory_ids:
                    raise ValueError('Duplicate imported memory id')
                values = {k: raw[k] for k in _MUTABLE if k in raw}
                supersedes = values.pop('supersedes_id', None)
                if 'content' not in values:
                    raise ValueError('Missing memory content')
                created = self.remember(scope, **values)
                memory_ids[original_id] = created['id']
                if dates:
                    self._db.execute(f'UPDATE memories SET {",".join(k+"=?" for k in dates)} WHERE scope=? AND id=?', [*dates.values(), scope, created['id']])
                if supersedes:
                    pending_links.append((created['id'], supersedes))
            for id, supersedes in pending_links:
                if supersedes not in memory_ids or memory_ids[supersedes] == id:
                    raise ValueError('Invalid supersession link')
                self.update_memory(scope, id, {'supersedes_id': memory_ids[supersedes]})
            conversations = {}
            conversation_dates = {}
            for raw in data['conversations']:
                original_id, dates = _import_identity(raw)
                if not isinstance(raw, dict) or set(raw) - {'id','title','summary','created_at','updated_at'} or not isinstance(raw.get('id'), str) or raw['id'] in conversations:
                    raise ValueError('Invalid imported conversation')
                created = self.create_conversation(scope, raw.get('title', 'Nueva conversación'))
                conversations[original_id] = created['id']
                conversation_dates[created['id']] = dates
                self.set_summary(scope, created['id'], raw.get('summary', ''))
            for raw in data['messages']:
                _, dates = _import_identity(raw)
                if not isinstance(raw, dict) or set(raw) - {'id','conversation_id','role','content','status','metadata','created_at'}:
                    raise ValueError('Invalid imported message')
                original_conversation_id = _text(raw.get('conversation_id'), 256)
                conversation_id = conversations.get(original_conversation_id)
                if not conversation_id:
                    raise ValueError('Unknown imported conversation')
                created = self.add_message(scope, conversation_id, raw.get('role'), raw.get('content'), raw.get('status', 'complete'), raw.get('metadata'))
                if dates:
                    self._db.execute('UPDATE messages SET created_at=? WHERE scope=? AND id=?', (dates['created_at'], scope, created['id']))
            for id, dates in conversation_dates.items():
                if dates:
                    self._db.execute(f'UPDATE conversations SET {",".join(k+"=?" for k in dates)} WHERE scope=? AND id=?', [*dates.values(), scope, id])
        return {'memories': len(data['memories']), 'conversations': len(data['conversations']), 'messages': len(data['messages'])}

    def backup(self):
        """Create a private full-database snapshot; independent of later deletions."""
        with self._lock:
            directory = self.path.parent / 'backups'
            directory.mkdir(mode=0o700, exist_ok=True)
            os.chmod(directory, 0o700)
            path = directory / f'desk-{datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")}-{uuid.uuid4().hex[:8]}.sqlite3'
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.close(fd)
            destination = sqlite3.connect(path)
            try:
                self._db.backup(destination)
            finally:
                destination.close()
            return path

    def delete_data(self, scope):
        scope = self._scope(scope)
        with self._transaction():
            self._db.execute('DELETE FROM memory_fts WHERE scope=?', (scope,))
            self._db.execute('DELETE FROM memories WHERE scope=?', (scope,))
            self._db.execute('DELETE FROM conversations WHERE scope=?', (scope,))
            self._db.execute('DELETE FROM settings WHERE scope=?', (scope,))
        with self._lock:
            self._db.execute('PRAGMA wal_checkpoint(TRUNCATE)')
