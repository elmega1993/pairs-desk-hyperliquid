"""Same-origin personal Desk management. Scope is resolved only by the server."""
from typing import Literal
import json
from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator
from fastapi.responses import JSONResponse
from pairs_desk.advisor_routes import same_origin


class Strict(BaseModel):
    model_config=ConfigDict(extra='forbid',allow_inf_nan=False)

    @field_validator('category',check_fields=False)
    @classmethod
    def category_default(cls,value):
        return (value.strip() or 'preference') if isinstance(value,str) else value


class ConversationInput(Strict):
    title: str=Field(default='Nueva conversación',min_length=1,max_length=120)


class MemoryInput(Strict):
    content:str=Field(min_length=1,max_length=4000)
    type:Literal['semantic','procedural','episodic','conversation','knowledge']='semantic'
    category:str=Field(default='preference',max_length=80)
    namespace:str=Field(default='personal',max_length=80)
    importance:float=Field(default=.7,ge=0,le=1)
    confidence:float=Field(default=1,ge=0,le=1)
    status:Literal['active','pending','inactive']='active'
    valid_until:str|None=Field(default=None,max_length=40)
    supersedes_id:str|None=Field(default=None,max_length=64)

    @field_validator('content')
    @classmethod
    def content_nonblank(cls,v):
        if not v.strip():raise ValueError('Contenido vacío')
        return v.strip()


class MemoryPatch(Strict):
    content:str|None=Field(default=None,min_length=1,max_length=4000)
    category:str|None=Field(default=None,max_length=80)
    importance:float|None=Field(default=None,ge=0,le=1)
    confidence:float|None=Field(default=None,ge=0,le=1)
    status:Literal['active','pending','inactive']|None=None
    valid_until:str|None=Field(default=None,max_length=40)


class SettingsPatch(Strict):
    personal_rules:str|None=Field(default=None,max_length=6000)
    temperature:float|None=Field(default=None,ge=0,le=1)
    max_tokens:int|None=Field(default=None,ge=100,le=1400)
    memory_budget:int|None=Field(default=None,ge=0,le=2400)
    history_budget:int|None=Field(default=None,ge=120,le=2400)
    acquisition_enabled:bool|None=None


class ImportInput(Strict):
    data:dict


class ConsolidateInput(Strict):
    duplicate_ids:list[str]=Field(min_length=1,max_length=20)


class EraseInput(Strict):
    confirmation:Literal['DESK']


def desk_router(desk):
    router=APIRouter(prefix='/api/advisor')

    def call(fn,*args,**kwargs):
        try:return fn(desk.scope(),*args,**kwargs)
        except KeyError:raise HTTPException(404,'No se encontró en este ámbito') from None
        except ValueError as exc:raise HTTPException(422,str(exc)) from None

    @router.get('/conversations')
    def conversations(limit:int=Query(20,ge=1,le=50),offset:int=Query(0,ge=0)):
        return call(desk.store.list_conversations,limit=limit,offset=offset)

    @router.post('/conversations')
    def create_conversation(request:Request,data:ConversationInput):
        same_origin(request)
        return call(desk.store.create_conversation,title=data.title)

    @router.get('/conversations/{cid}')
    def conversation(cid:str):return call(desk.store.get_conversation,cid)

    @router.get('/conversations/{cid}/messages')
    def messages(cid:str,limit:int=Query(30,ge=1,le=60),offset:int=Query(0,ge=0)):
        return call(desk.store.messages,cid,limit=limit,offset=offset)

    @router.delete('/conversations/{cid}')
    def delete_conversation(cid:str,request:Request):
        same_origin(request)
        if desk.busy.locked():raise HTTPException(409,'Esperá que termine la consulta')
        call(desk.store.delete_conversation,cid)
        return {'deleted':True}

    @router.get('/memories')
    def memories(query:str=Query('',max_length=500),status:Literal['active','pending','inactive','superseded']|None=None,
                 limit:int=Query(20,ge=1,le=50),offset:int=Query(0,ge=0)):
        return call(desk.store.list_memories,query=query,status=status,limit=limit,offset=offset)

    @router.get('/memories/{mid}')
    def memory(mid:str):return call(desk.store.get_memory,mid)

    @router.get('/memories/{mid}/revisions')
    def revisions(mid:str,limit:int=Query(20,ge=1,le=50),offset:int=Query(0,ge=0)):
        return call(desk.store.memory_revisions,mid,limit=limit,offset=offset)

    @router.get('/memories/{mid}/duplicates')
    def duplicates(mid:str,limit:int=Query(5,ge=1,le=20)):
        items=call(desk.store.find_duplicates,mid,limit=limit)
        return {'items':items,'total':len(items)}

    @router.post('/memories/{mid}/consolidate')
    def consolidate(mid:str,request:Request,data:ConsolidateInput):
        same_origin(request)
        return call(desk.store.consolidate,mid,data.duplicate_ids)

    @router.post('/memories')
    def create_memory(request:Request,data:MemoryInput):
        same_origin(request)
        return call(desk.store.remember,source='user_editor',**data.model_dump())

    @router.patch('/memories/{mid}')
    def update_memory(mid:str,request:Request,data:MemoryPatch):
        same_origin(request)
        patch=data.model_dump(exclude_unset=True)
        if any(v is None for k,v in patch.items() if k!='valid_until'):raise HTTPException(422,'Campo vacío no permitido')
        return call(desk.store.update_memory,mid,patch)

    @router.delete('/memories/{mid}')
    def delete_memory(mid:str,request:Request):
        same_origin(request);call(desk.store.delete_memory,mid)
        return {'deleted':True}

    @router.get('/settings')
    def settings():return call(desk.store.get_settings)

    @router.patch('/settings')
    def update_settings(request:Request,data:SettingsPatch):
        same_origin(request)
        patch=data.model_dump(exclude_unset=True)
        if any(v is None for v in patch.values()):raise HTTPException(422,'Campo vacío no permitido')
        return call(desk.store.update_settings,patch)

    @router.get('/export')
    def export():
        return JSONResponse(call(desk.store.export_data),headers={'Cache-Control':'no-store','Content-Disposition':'attachment; filename="desk-memory.json"'})

    @router.post('/import')
    async def import_data(request:Request,data:ImportInput):
        same_origin(request)
        if len(json.dumps(data.data))>2_000_000:raise HTTPException(413,'Importación demasiado grande')
        if desk.busy.locked():raise HTTPException(409,'Esperá que termine la consulta')
        return call(desk.store.import_data,data.data)

    @router.post('/backup')
    def backup(request:Request):
        same_origin(request)
        path=desk.store.backup()
        return {'filename':path.name,'message':'Copia privada local. Borrar la memoria activa no borra backups anteriores.'}

    @router.delete('/data')
    def erase(request:Request,data:EraseInput):
        same_origin(request)
        if desk.busy.locked():raise HTTPException(409,'Esperá que termine la consulta')
        call(desk.store.delete_data)
        return {'deleted':True,'message':'Ámbito activo eliminado. Backups previos son copias independientes.'}

    return router
