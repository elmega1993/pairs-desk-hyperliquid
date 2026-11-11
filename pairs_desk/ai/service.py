"""Persistent orchestration around the existing Advisor, without market polling."""
from __future__ import annotations
import threading
from datetime import datetime, timezone
from .context import ContextBuilder, clip
from .acquisition import acquire, conversation_summary
from pairs_desk.local_advisor import AdvisorError


class DeskService:
    def __init__(self, advisor, store, scope_provider, account_provider=None, identity_provider=None):
        self.advisor, self.store, self.scope_provider = advisor, store, scope_provider
        self.account_provider = account_provider
        self.identity_provider = identity_provider
        self.builder = ContextBuilder()
        self.busy = threading.Lock()

    def scope(self):
        return self.scope_provider()

    def context_for(self, scope, question, history, conversation, mode, expected_account=None):
        settings=self.store.get_settings(scope)
        memories=self.store.search(scope, question, limit=8)
        # Durable corrections/rules apply across wording changes. Explicit preference questions
        # can retrieve stable preferences even without matching the original vocabulary.
        from .context import normalized
        q=normalized(question)
        generic=any(word in q for word in ('prefier','preferenc','criterios uso','recordas','recuerd','mis reglas'))
        stable=self.store.list_memories(scope,status='active',limit=50)['items']
        now=datetime.now(timezone.utc).isoformat()
        relevant=[m for m in stable if (m['type']=='procedural' or generic and m['type']=='semantic')
                  and (not m['valid_until'] or m['valid_until']>now)]
        known={m['id'] for m in memories}
        for m in relevant:
            if m['id'] not in known:
                m['retrieval_explanation']='Regla/corrección vigente' if m['type']=='procedural' else 'Consulta sobre preferencias duraderas'
                memories.append(m)
        memories=sorted(memories,key=lambda m:(m['category']=='correction',m['type']=='procedural',m.get('score',0)),reverse=True)[:8]
        context=self.builder.build(question,history,memories=memories,summary=conversation.get('summary',''),settings=settings,mode=mode)
        if expected_account is not None:
            context['expected_account']=expected_account
        context['memory_tool']=lambda name,args:self.memory_tool(scope,name,args)
        return context

    def memory_tool(self, scope, name, args):
        if name=='search_memories':
            return {'memories':self.store.search(scope,args.get('query',''),limit=min(args.get('limit',5),8)), 'source':'Memoria local de Desk'}
        if name=='get_trading_rules':
            return {'identity_rules':self.builder.identity, 'personal_rules':self.store.get_settings(scope)['personal_rules'], 'source':'Reglas versionadas y reglas personales'}
        if name=='save_memory':
            memory=self.store.remember(scope,args['content'],type=args.get('type','semantic'),category='model_proposal',
                source='model_proposal',confidence=.4,status='pending',metadata={'confirmed':False})
            return {'memory':memory,'message':'Propuesta pendiente de revisión del usuario'}
        raise AdvisorError('Herramienta de memoria no permitida')

    def stream(self, question, *, conversation_id=None, mode='auto', allow_codex_context=False):
        self.advisor.check_consent(allow_codex_context)
        if not self.busy.acquire(blocking=False):
            raise AdvisorError('Desk está ocupado con otra consulta',429)
        iterator=None; conversation=None; answer=''; completed=False; metadata={}; summary=''; user_row=None; persisted=False; scope=None
        try:
            scope, expected_account = (self.identity_provider() if self.identity_provider else
                                       (self.scope(), self.account_provider() if self.account_provider else None))
            if self.scope()!=scope:
                raise AdvisorError('La cuenta cambió. Reabrí la conversación.',409)
            conversation=(self.store.get_conversation(scope,conversation_id) if conversation_id else self.store.create_conversation(scope,clip(question,20)))
            cid=conversation['id']
            total=conversation.get('message_count',0)
            # Server-owned history only. Never trust browser history when persistence is active.
            rows=self.store.messages(scope,cid,limit=12,offset=max(0,total-12))['items']
            history=[{'role':r['role'],'content':r['content']} for r in rows if r['status']=='complete']
            user_row=self.store.add_message(scope,cid,'user',question)
            settings=self.store.get_settings(scope)
            acquired=acquire(self.store,scope,question,user_row['id']) if settings['acquisition_enabled'] else []
            summary=conversation_summary(conversation.get('summary',''),question)
            self.store.set_summary(scope,cid,summary)
            context=self.context_for(scope,question,history,conversation,mode,expected_account=expected_account)
            context['allow_codex_context'] = allow_codex_context
            # Pin scope and snapshot: an account switch cannot send another account into this request.
            iterator=self.advisor.stream(question,history,context=context)
            for event in iterator:
                if self.scope()!=scope:
                    raise AdvisorError('La cuenta cambió durante la consulta. Reabrí el chat.',409)
                event=dict(event)
                if event['type']=='start':
                    event.update(conversation_id=cid,mode=context['mode'])
                if event['type']=='token':answer+=event.get('text','')
                if event['type']=='done':
                    completed=not event.get('truncated',False)
                    event.update(conversation_id=cid,mode=context['mode'],memories_used=context['memories_used'],memories_saved=[m['id'] for m in acquired])
                    metadata={k:v for k,v in event.items() if k!='type'}
                    # Commit before signaling successful completion to the browser.
                    self.store.add_message(scope,cid,'assistant',answer,status='complete' if completed else 'incomplete',metadata=metadata)
                    persisted=True
                yield event
        finally:
            try:
                if iterator:iterator.close()
                if conversation and user_row and not persisted:
                    try:
                        self.store.add_message(scope,conversation['id'],'assistant',answer,status='incomplete',metadata={'error':'Generación interrumpida'})
                    except ValueError:
                        self.store.add_message(scope,conversation['id'],'assistant','Contenido no persistido por la política de privacidad.',status='incomplete',metadata={'error':'Persistencia rechazada'})
            finally:self.busy.release()
