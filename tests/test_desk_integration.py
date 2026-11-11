import json
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pairs_desk.local_advisor import Advisor, AdvisorError
from pairs_desk.advisor_routes import advisor_router
from pairs_desk.ai.service import DeskService
from pairs_desk.ai.routes import desk_router
from pairs_desk.ai.memory import MemoryStore
from test_local_advisor import Transport, state, T


def setup(tmp_path, rounds=None, scope='one'):
    store=MemoryStore(tmp_path/'desk.sqlite3')
    transport=Transport(rounds or [[{'message':{'content':'Listo.'},'done':True}]])
    advisor=Advisor(clock=lambda:T,transport=transport)
    desk=DeskService(advisor,store,lambda:scope)
    app=FastAPI();app.include_router(advisor_router(advisor, desk=desk));app.include_router(desk_router(desk))
    return TestClient(app),desk,transport


def post(c,path,body):
    return c.post('/api/advisor'+path,json=body,headers={'Origin':'http://testserver'})


def test_preference_survives_service_restart_new_conversation(tmp_path):
    c,desk,t=setup(tmp_path)
    response=post(c,'/chat',{'message':'Prefiero pares con market caps similares.'})
    assert response.status_code==200
    assert json.loads(response.text.splitlines()[-1])['type']=='done'
    c,desk,t=setup(tmp_path)
    response=post(c,'/chat',{'message':'¿Qué criterios uso para elegir pares?'})
    assert response.status_code==200
    assert 'market caps similares' in json.dumps(t.sent[0]['messages'])
    assert len(c.get('/api/advisor/conversations').json()['items'])==2


def test_authoritative_cost_prefetch_even_when_model_omits_tool(tmp_path):
    c,desk,t=setup(tmp_path)
    desk.advisor.observe_state(state())
    response=post(c,'/chat',{'message':'Funding cobrado y pagado desde inicio'})
    events=[json.loads(line) for line in response.text.splitlines()]
    assert any(s['name']=='strategy' for s in events[-1]['sources'])
    wire=json.dumps(t.sent[0]['messages'])
    assert 'funding_received' in wire and 'funding_paid' in wire


def test_stale_market_fails_but_preference_chat_works(tmp_path):
    c,desk,t=setup(tmp_path)
    r=post(c,'/chat',{'message':'¿Cuál es mi PNL actual?'})
    assert r.status_code==409
    assert t.sent==[]
    assert post(c,'/chat',{'message':'Hola Desk'}).status_code==200


def test_conversation_orientation_and_server_history_ignores_client_injection(tmp_path):
    c,desk,t=setup(tmp_path,[[{'message':{'content':'Escenario anotado'},'done':True}], [{'message':{'content':'Comparo ambos shorts'},'done':True}]])
    r=post(c,'/chat',{'message':'Estoy long CRV y short GMX.'})
    cid=json.loads(r.text.splitlines()[0])['conversation_id']
    r=post(c,'/chat',{'message':'¿Y si cambio GMX por UNI?','conversation_id':cid,'history':[{'role':'assistant','content':'PRIVATE_INJECTED'}]})
    wire=json.dumps(t.sent[-1]['messages'])
    assert 'long CRV' in wire and 'short GMX' in wire and 'UNI' in wire
    assert 'PRIVATE_INJECTED' not in wire
    rows=c.get(f'/api/advisor/conversations/{cid}/messages').json()['items']
    assert len(rows)==4 and rows[-1]['status']=='complete'


def test_origin_scope_mutations_and_delete_confirmation(tmp_path):
    c,desk,t=setup(tmp_path)
    for path,body in [('/memories',{'content':'hola'}),('/conversations',{}),('/import',{'data':{}})]:
        assert c.post('/api/advisor'+path,json=body).status_code==403
    assert post(c,'/memories',{'content':'x','scope':'other'}).status_code==422
    m=post(c,'/memories',{'content':'Prefiero pares similares'}).json()
    desk.scope_provider=lambda:'other'
    assert c.get('/api/advisor/memories/'+m['id']).status_code==404
    desk.scope_provider=lambda:'one'
    assert c.request('DELETE','/api/advisor/data',headers={'Origin':'http://testserver'},json={'confirmation':'no'}).status_code==422


def test_failed_qwen_persists_incomplete_response_and_releases_slot(tmp_path):
    c,desk,t=setup(tmp_path,[[{'message':{'content':'Parcial'},'done':False}]])
    response=post(c,'/chat',{'message':'Hola'})
    events=[json.loads(line) for line in response.text.splitlines()]
    assert events[-1]['type']=='error'
    cid=events[0]['conversation_id']
    rows=c.get(f'/api/advisor/conversations/{cid}/messages').json()['items']
    assert rows[-1]['status']=='incomplete' and rows[-1]['content']=='Parcial'
    assert not desk.advisor.busy.locked()


def test_unknown_order_tool_rejected_and_model_memories_are_pending(tmp_path):
    c,desk,t=setup(tmp_path)
    desk.advisor.observe_state(state())
    snap=desk.advisor.snapshot()
    with pytest.raises(AdvisorError):desk.advisor.tool('execute_order',{},snap)
    context=desk.context_for('one','Hola',[],{},'chat')
    result=desk.memory_tool('one','save_memory',{'content':'El usuario parece preferir BTC'})
    assert result['memory']['status']=='pending'
    assert result['memory']['confidence']<1
    assert desk.store.search('one','BTC')==[]


def test_explicit_correction_retrieved_new_conversation_and_no_old_quotes(tmp_path):
    c,desk,t=setup(tmp_path,[[{'message':{'content':'Corregido'},'done':True}],[{'message':{'content':'Aplico corrección'},'done':True}]])
    post(c,'/chat',{'message':'Te corrijo: no sumes nominales de pares con activos compartidos.'})
    desk.advisor.observe_state(state())
    post(c,'/chat',{'message':'¿Cuál es mi PNL actual?'})
    assert 'no sumes nominales' in json.dumps(t.sent[-1]['messages'])


def test_get_memory_expiry_uses_iso_and_large_requests_rejected(tmp_path):
    c,desk,t=setup(tmp_path)
    r=post(c,'/memories',{'content':'Prefiero pares similares','valid_until':'2000-01-01T00:00:00+00:00'})
    assert r.status_code==200
    assert desk.store.search('one','pares similares')==[]
    r=post(c,'/chat',{'message':'x'*2001})
    assert r.status_code==422


def test_request_account_mismatch_fails_before_model(tmp_path):
    c,desk,t=setup(tmp_path)
    desk.account_provider=lambda:'new-account'
    desk.advisor.observe_state(state(),account='old-account')
    r=post(c,'/chat',{'message':'Mis posiciones actuales'})
    assert r.status_code==409
    assert t.sent==[]


def test_settings_cannot_disable_system_safety_and_tools_typed(tmp_path):
    c,desk,t=setup(tmp_path)
    headers={'Origin':'http://testserver'}
    assert c.patch('/api/advisor/settings',headers=headers,json={'execute_orders':True}).status_code==422
    assert c.patch('/api/advisor/settings',headers=headers,json={'max_tokens':999999}).status_code==422
    snap=None
    for name,args in [('positions',{'offset':1}),('save_memory',{}),('search_memories',{'query':'test','limit':True}),('pair_ratio',{})]:
        with pytest.raises(AdvisorError):desk.advisor.tool(name,args,snap)


def test_identity_is_pinned_when_account_changes_between_scope_and_context(tmp_path):
    c,desk,t=setup(tmp_path)
    desk.store.remember('one','Prefiero datos privados de cuenta A')
    desk.identity_provider=lambda:('one','account-A')
    desk.account_provider=lambda:'account-B'
    desk.advisor.observe_state(state(),account='account-B')
    r=post(c,'/chat',{'message':'Mis posiciones actuales'})
    assert r.status_code==409
    assert t.sent==[]


def test_mode_chat_does_not_include_operational_tools_or_old_market_data(tmp_path):
    c,desk,t=setup(tmp_path)
    desk.advisor.observe_state(state())
    post(c,'/chat',{'message':'Hola Desk','mode':'chat'})
    names={tool['function']['name'] for tool in t.sent[0]['tools']}
    assert names <= {'search_memories','save_memory','get_trading_rules'}
    assert 'net_pnl' not in json.dumps(t.sent[0]['messages'])


def test_acquisition_keeps_unrelated_preferences_and_replaces_actual_contradiction(tmp_path):
    from pairs_desk.ai.acquisition import acquire
    c,desk,t=setup(tmp_path)
    first=acquire(desk.store,'one','Prefiero respuestas breves y con fuentes.','message-1')[0]
    second=acquire(desk.store,'one','Ahora prefiero pares con market caps similares.','message-2')[0]
    assert desk.store.get_memory('one',first['id'])['status']=='active'
    third=acquire(desk.store,'one','Prefiero respuestas extensas.','message-3')[0]
    assert desk.store.get_memory('one',first['id'])['status']=='superseded'
    assert desk.store.get_memory('one',second['id'])['status']=='active'
    assert third['supersedes_id']==first['id'] and third['source_id']=='message-3'


def test_aggregate_maximum_context_is_trimmed_before_inference(tmp_path):
    c,desk,t=setup(tmp_path)
    desk.store.update_settings('one',{'memory_budget':2400,'history_budget':2400,'personal_rules':'regla '*1000})
    desk.store.remember('one','Prefiero respuestas breves. '+'detalle '*490,category='preference')
    desk.store.remember('one','Prefiero respuestas con fuentes. '+'fuente '*550,category='preference')
    row=desk.store.create_conversation('one')
    for _ in range(4):
        desk.store.add_message('one',row['id'],'user','contexto '*150)
        desk.store.add_message('one',row['id'],'assistant','respuesta '*130)
    desk.store.set_summary('one',row['id'],'resumen '*500)
    response=post(c,'/chat',{'message':'¿Qué preferencias recordás? '+'x'*1900,'conversation_id':row['id']})
    assert json.loads(response.text.splitlines()[-1])['type']=='done'
    assert t.sent and len(json.dumps(t.sent[0]['messages'],ensure_ascii=False))<=20000


def test_editor_memory_accepts_empty_optional_category_and_revisions_are_paginated(tmp_path):
    c,desk,t=setup(tmp_path)
    r=post(c,'/memories',{'content':'Prefiero pares con market caps similares.','category':''})
    assert r.status_code==200
    mid=r.json()['id']
    response=c.patch('/api/advisor/memories/'+mid,headers={'Origin':'http://testserver'},json={'content':'Prefiero pares con capitalizaciones similares.'})
    assert response.status_code==200
    revisions=c.get('/api/advisor/memories/'+mid+'/revisions?limit=1&offset=0').json()
    assert revisions['total']==1 and revisions['items'][0]['snapshot']['content'].startswith('Prefiero pares con market caps')


def test_qwen_timeout_never_leaves_generation_slot_locked(tmp_path):
    import requests
    c,desk,t=setup(tmp_path)
    original=t.post
    def timeout(url,**kwargs):
        if url.endswith('/api/chat'):raise requests.Timeout('PRIVATE_TRANSPORT_ERROR')
        return original(url,**kwargs)
    t.post=timeout
    r=post(c,'/chat',{'message':'Hola Desk'})
    assert 'PRIVATE_TRANSPORT_ERROR' not in r.text
    assert json.loads(r.text.splitlines()[-1])['type']=='error'
    assert not desk.busy.locked() and not desk.advisor.busy.locked()


def test_model_cannot_execute_tools_outside_mode_or_approve_own_memories(tmp_path):
    rounds=[
        [{'message':{'tool_calls':[{'function':{'name':'execute_order','arguments':{'coin':'BTC'}}}]},'done':True}],
        [{'message':{'content':'No puedo enviar órdenes.'},'done':True}],
    ]
    c,desk,t=setup(tmp_path,rounds)
    r=post(c,'/chat',{'message':'Hola Desk','mode':'chat'})
    assert json.loads(r.text.splitlines()[-1])['type']=='done'
    assert 'no habilitada' in t.sent[-1]['messages'][-1]['content']
    assert desk.store.list_memories('one')['total']==0


def test_portfolio_changes_are_read_fresh_in_same_conversation(tmp_path):
    rounds=[[{'message':{'content':'42'},'done':True}],[{'message':{'content':'99'},'done':True}]]
    c,desk,t=setup(tmp_path,rounds)
    desk.advisor.observe_state(state())
    r=post(c,'/chat',{'message':'¿Cuál es mi PNL actual?'})
    cid=json.loads(r.text.splitlines()[0])['conversation_id']
    changed=state();changed['strategy']['net_pnl']=99
    desk.advisor.observe_state(changed)
    r=post(c,'/chat',{'message':'¿Cuál es mi PNL actual?','conversation_id':cid})
    evidence=json.loads(t.sent[-1]['messages'][-1]['content'].split('\n',1)[1])
    assert evidence['data']['net_pnl']==99
    assert desk.store.list_memories('one')['total']==0


def test_identity_resolution_failure_releases_service_lock(tmp_path):
    c,desk,t=setup(tmp_path)
    def unavailable():raise ValueError('Configuration unavailable')
    desk.identity_provider=unavailable
    with pytest.raises(ValueError):list(desk.stream('Hola'))
    assert not desk.busy.locked()


def test_failed_reply_persistence_is_never_saved_as_complete(tmp_path):
    c,desk,t=setup(tmp_path,[[{'message':{'content':'password=NOT_A_REAL_SECRET'},'done':True}]])
    r=post(c,'/chat',{'message':'Hola'})
    events=[json.loads(line) for line in r.text.splitlines()]
    assert events[-1]['type']=='error'
    cid=events[0]['conversation_id']
    rows=desk.store.messages('one',cid)['items']
    assert rows[-1]['role']=='assistant' and rows[-1]['status']=='incomplete'


def test_checksum_case_of_same_wallet_does_not_block_current_data(tmp_path):
    c,desk,t=setup(tmp_path)
    checksummed='0x'+('aB'*20)
    desk.identity_provider=lambda:('one',checksummed.lower())
    desk.advisor.observe_state(state(),account=checksummed)
    r=post(c,'/chat',{'message':'Funding cobrado y pagado'})
    assert r.status_code==200 and t.sent


def test_full_portfolio_prefetch_fits_context_without_losing_any_position(tmp_path):
    c,desk,t=setup(tmp_path)
    portfolio=state()
    portfolio['pairs']=[dict(id=f'L{i}|S{i}',long=f'L{i}',short=f'S{i}',pnl=-i*.123456789,long_usd=123.123456789,
        short_usd=122.123456789,ratio=1.234567891,ratio_change=1.123456789,entry_ratio=1.123456789,liq=12.123456789,
        funding=-.123456789,realized=2.123456789,fees=1.123456789,total_pnl=3.123456789) for i in range(17)]
    holdings={f'A{i}':dict(szi='-1.12345678901234',entryPx='12.12345678901234',positionValue='123.12345678901234',
        unrealizedPnl='-1.12345678901234',liquidationPx='25.12345678901234',marginUsed='100.12345678901234') for i in range(34)}
    desk.advisor.observe_state(portfolio,positions=holdings)
    r=post(c,'/chat',{'message':'Usá positions y resumí mis posiciones actuales.'})
    assert json.loads(r.text.splitlines()[-1])['type']=='done'
    wire=json.dumps(t.sent[0]['messages'],ensure_ascii=False)
    assert 'L16|S16' in wire and 'A33' in wire and 'pair_count' in wire
    assert len(wire)<=20000


def test_analysis_default_budget_allows_complete_longer_answer_and_persists_stop_reason(tmp_path):
    c,desk,t=setup(tmp_path,[[{'message':{'content':'Análisis completo.'},'done':True,'done_reason':'stop'}]])
    desk.advisor.observe_state(state())
    r=post(c,'/chat',{'message':'Analizá mis posiciones: riesgos y escenarios.'})
    events=[json.loads(line) for line in r.text.splitlines()]
    assert t.sent[0]['options']['num_predict']==1400
    assert events[-1]['stop_reason']=='stop' and events[-1]['truncated'] is False
    assert desk.store.messages('one',events[0]['conversation_id'])['items'][-1]['status']=='complete'


def test_output_length_limit_explains_incomplete_in_stream_and_saved_history(tmp_path):
    c,desk,t=setup(tmp_path,[[{'message':{'content':'Texto a mitad de'},'done':True,'done_reason':'length'}]])
    r=post(c,'/chat',{'message':'Hola Desk'})
    events=[json.loads(line) for line in r.text.splitlines()]
    assert events[-1]['truncated'] is True and events[-1]['stop_reason']=='length'
    stored=desk.store.messages('one',events[0]['conversation_id'])['items'][-1]
    assert stored['metadata']['stop_reason']=='length' and stored['status']=='incomplete'


def test_explicit_lower_output_limit_is_still_respected(tmp_path):
    c,desk,t=setup(tmp_path)
    desk.store.update_settings('one',{'max_tokens':300})
    post(c,'/chat',{'message':'Hola Desk'})
    assert t.sent[0]['options']['num_predict']==300


def test_named_pair_analysis_prefetches_pair_specific_evidence_before_answer(tmp_path):
    c,desk,t=setup(tmp_path)
    desk.advisor.observe_state(state())
    r=post(c,'/chat',{'message':'Analizá BTC / ETH: situación actual, riesgos y escenarios.'})
    events=[json.loads(line) for line in r.text.splitlines()]
    assert 'pair_review' in {s['name'] for s in events[-1]['sources']}
    assert 'ratio_change_since_entry_pct' in t.sent[0]['messages'][-1]['content']
    assert desk.context_for('one','Analizá BTC / ETH',[],{},'auto')['requires_state']


def test_pair_review_resolves_unambiguous_venue_alias_without_loading_whole_portfolio(tmp_path):
    c,desk,t=setup(tmp_path)
    data=state();data['pairs']=[{'id':'xyz:USAR|xyz:NATGAS','long':'xyz:USAR','short':'xyz:NATGAS',
        'long_usd':647,'short_usd':772,'ratio_change':-10.79,'funding':-158}]
    desk.advisor.observe_state(data)
    r=post(c,'/chat',{'message':'Analiza USAR/NATGAS'})
    events=[json.loads(line) for line in r.text.splitlines()]
    assert events[-1]['type']=='done'
    assert 'pair_review' in {s['name'] for s in events[-1]['sources']}
    assert '"historical_funding_net_usd":-158.0' in t.sent[0]['messages'][-1]['content']
    assert all(s['name']!='positions' for s in events[-1]['sources'])


def test_pair_alias_ambiguity_or_reversed_orientation_cannot_pick_arbitrary_pair(tmp_path):
    c,desk,t=setup(tmp_path)
    data=state();data['pairs']=[{'id':'xyz:A|xyz:B','long':'xyz:A','short':'xyz:B'},
        {'id':'abc:A|abc:B','long':'abc:A','short':'abc:B'}]
    desk.advisor.observe_state(data)
    for pair in ['A|B','B|A']:
        with pytest.raises(AdvisorError):desk.advisor.tool('pair_review',{'pair_id':pair},desk.advisor.snapshot())
    assert desk.advisor.tool('pair_review',{'pair_id':'xyz:A|xyz:B'},desk.advisor.snapshot())['pair']['id']=='xyz:A|xyz:B'


def test_lowercase_pair_analysis_still_requires_verified_pair_evidence(tmp_path):
    c,desk,t=setup(tmp_path)
    data=state();data['pairs']=[{'id':'xyz:USAR|xyz:NATGAS','long':'xyz:USAR','short':'xyz:NATGAS'}]
    desk.advisor.observe_state(data)
    r=post(c,'/chat',{'message':'Analiza usar/natgas'})
    events=[json.loads(line) for line in r.text.splitlines()]
    assert 'pair_review' in {s['name'] for s in events[-1]['sources']}


def test_pair_review_rejects_closed_position_instead_of_offering_live_adjustments(tmp_path):
    c,desk,t=setup(tmp_path)
    data=state();data['closed_pairs']=data['pairs'];data['pairs']=[]
    desk.advisor.observe_state(data)
    with pytest.raises(AdvisorError,match='cerrado'):
        desk.advisor.tool('pair_review',{'pair_id':'BTC|ETH'},desk.advisor.snapshot())


def test_codex_requires_consent_before_reading_or_saving_context(tmp_path):
    c, desk, _ = setup(tmp_path)

    class ForbiddenProvider:
        def answer(self, messages):
            pytest.fail('Codex must not receive context without explicit consent')

    desk.advisor.codex = ForbiddenProvider()
    response = post(c, '/chat', {'message': 'Analizá BTC / ETH'})
    assert response.status_code == 403
    assert desk.store.list_conversations('one')['total'] == 0


def test_codex_receives_verified_pair_evidence_and_keeps_existing_chat_contract(tmp_path):
    c, desk, _ = setup(tmp_path)

    class Provider:
        model = 'fixture-codex'

        def answer(self, messages):
            assert messages[0]['role'] == 'system'
            assert 'ratio_change_since_entry_pct' in messages[-1]['content']
            assert '_account' not in json.dumps(messages)
            return 'Conclusión verificada.'

    desk.advisor.codex = Provider()
    desk.advisor.observe_state(state(), account='private-account-identifier')
    response = post(c, '/chat', {'message': 'Analizá BTC / ETH. ¿Qué riesgo agrega el hedge?', 'allow_codex_context': True})
    events = [json.loads(line) for line in response.text.splitlines()]
    assert events[-1]['type'] == 'done'
    assert events[-1]['model'] == 'fixture-codex'
    assert any(source['name'] == 'pair_review' for source in events[-1]['sources'])
    rows = desk.store.messages('one', events[0]['conversation_id'])['items']
    assert rows[-1]['content'] == 'Conclusión verificada.'
