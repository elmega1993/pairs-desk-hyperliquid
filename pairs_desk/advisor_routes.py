"""HTTP boundary for the local read-only advisor; never mounts trade tools."""
from typing import Literal
from urllib.parse import urlsplit
import json

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from starlette.background import BackgroundTask
from starlette.responses import StreamingResponse

from pairs_desk.local_advisor import AdvisorError


class ChatTurn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    role: Literal['user', 'assistant']
    content: str = Field(min_length=1, max_length=1200)


class ChatInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    message: str = Field(min_length=1, max_length=2000)
    conversation_id: str | None = Field(default=None, min_length=1, max_length=64)
    allow_codex_context: bool = Field(default=False, strict=True)
    mode: Literal['auto', 'chat', 'analyze', 'research'] = 'auto'
    history: list[ChatTurn] = Field(default_factory=list, max_length=8)

    @field_validator('message')
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError('Escribí una consulta')
        return value.strip()

    @model_validator(mode='after')
    def bounded_history(self):
        if sum(len(t.content) for t in self.history) > 6500:
            raise ValueError('Historial demasiado extenso')
        return self


def same_origin(request):
    origin = request.headers.get('origin', '')
    parsed = urlsplit(origin)
    if parsed.scheme not in ('http', 'https') or parsed.netloc != request.url.netloc or parsed.path or parsed.query or parsed.fragment:
        raise HTTPException(403, 'La consulta debe iniciarse desde Pair Desk')
    if parsed.scheme != request.url.scheme:
        raise HTTPException(403, 'Origen de consulta inválido')


def advisor_router(advisor, desk=None):
    router = APIRouter(prefix='/api/advisor')

    @router.get('/status')
    def status():
        return advisor.status()

    @router.post('/chat')
    def chat(request: Request, data: ChatInput):
        same_origin(request)
        if advisor.busy.locked():
            raise HTTPException(429, 'El asesor está ocupado con otra consulta')
        iterator = (desk.stream(data.message, conversation_id=data.conversation_id, mode=data.mode,
                                allow_codex_context=data.allow_codex_context) if desk is not None
                    else advisor.stream(data.message, [t.model_dump() for t in data.history]))
        try:
            first = next(iterator)
        except KeyError:
            raise HTTPException(404, 'Conversación no encontrada en este ámbito') from None
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None
        except AdvisorError as exc:
            raise HTTPException(getattr(exc, 'status_code', 503), str(exc)) from exc

        def events():
            try:
                yield json.dumps(first, ensure_ascii=False)+'\n'
                for event in iterator:
                    yield json.dumps(event, ensure_ascii=False)+'\n'
            except AdvisorError as exc:
                yield json.dumps({'type': 'error', 'message': str(exc)}, ensure_ascii=False)+'\n'
            except Exception:
                yield json.dumps({'type': 'error', 'message': 'La consulta se interrumpió. Volvé a intentar.'})+'\n'
            finally:
                iterator.close()

        return StreamingResponse(events(), media_type='application/x-ndjson',
                                 headers={'Cache-Control': 'no-store', 'X-Accel-Buffering': 'no'},
                                 background=BackgroundTask(iterator.close))

    return router
