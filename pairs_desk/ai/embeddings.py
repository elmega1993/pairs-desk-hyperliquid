"""Optional, explicitly supplied local embeddings; never downloads models."""
from __future__ import annotations

import math
import http.client
import json
from typing import Protocol, Sequence
from urllib.parse import urlsplit


class LocalEmbedder(Protocol):
    def embed(self, text: str) -> Sequence[float]:
        """Return a finite local vector for text without external network calls."""
        ...


def normalize_vector(value: Sequence[float]) -> list[float]:
    if isinstance(value, (str, bytes, dict)):
        raise ValueError('Invalid embedding')
    try:
        result = [float(x) for x in value]
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError('Invalid embedding') from exc
    if not result or len(result) > 16384 or not all(math.isfinite(x) for x in result):
        raise ValueError('Invalid embedding')
    length = math.hypot(*result)
    if not length or not math.isfinite(length):
        raise ValueError('Embedding must be nonzero')
    return [x / length for x in result]


def cosine(left: Sequence[float], right: Sequence[float]) -> float:
    if len(left) != len(right):
        return 0.0
    return sum(a * b for a, b in zip(left, right))


class OllamaLocalEmbedder:
    """Explicit-model adapter for an existing Ollama installation on loopback.

    Does not discover or download models. No proxy, redirects, remote hostnames,
    or unbounded response bodies are accepted. Failures let the store use FTS.
    """

    def __init__(self, model: str, endpoint='http://127.0.0.1:11434', timeout=5.):
        if not isinstance(model, str) or not model.strip() or len(model) > 200:
            raise ValueError('An explicit local embedding model is required')
        if 'cloud' in model.casefold():
            raise ValueError('Remote embedding models are not allowed')
        try:
            parsed = urlsplit(endpoint)
            port = parsed.port or 11434
        except (ValueError, TypeError) as exc:
            raise ValueError('Invalid Ollama endpoint') from exc
        if (parsed.scheme != 'http' or parsed.hostname not in {'127.0.0.1', 'localhost', '::1'}
                or parsed.username or parsed.password or parsed.path not in {'', '/'} or parsed.query or parsed.fragment):
            raise ValueError('Ollama embeddings must use a loopback HTTP endpoint')
        if isinstance(timeout, bool) or not isinstance(timeout, (float, int)) or not math.isfinite(timeout) or not .1 <= timeout <= 30:
            raise ValueError('Invalid embedding timeout')
        self.model = model.strip()
        self.host = '127.0.0.1' if parsed.hostname == 'localhost' else parsed.hostname
        self.port, self.timeout = port, timeout

    def _request(self, path, payload):
        connection = http.client.HTTPConnection(self.host, self.port, timeout=self.timeout)
        try:
            connection.request('POST', path, body=json.dumps(payload), headers={'Content-Type': 'application/json'})
            response = connection.getresponse()
            if response.status != 200:
                raise ValueError('Local embedding model unavailable')
            body = response.read(1_000_001)
            if len(body) > 1_000_000:
                raise ValueError('Embedding response too large')
            result = json.loads(body)
            if not isinstance(result, dict):
                raise ValueError('Invalid local model response')
            return result
        except (OSError, http.client.HTTPException, TypeError, KeyError, json.JSONDecodeError) as exc:
            raise ValueError('Local embedding request failed') from exc
        finally:
            connection.close()

    def embed(self, text: str) -> list[float]:
        if not isinstance(text, str) or not text.strip() or len(text) > 32000:
            raise ValueError('Invalid embedding input')
        # Check immediately before every embedding, since a local model alias
        # may have changed since construction. Never send private text first.
        metadata = self._request('/api/show', {'model': self.model})
        if metadata.get('remote_host') or metadata.get('remote_model'):
            raise ValueError('Remote embedding models are not allowed')
        data = self._request('/api/embed', {'model': self.model, 'input': text})
        if not isinstance(data.get('embeddings'), list) or len(data['embeddings']) != 1:
            raise ValueError('Invalid local embedding response')
        return normalize_vector(data['embeddings'][0])
