from pairs_desk.ai.context import ContextBuilder, classify_intent, load_identity
from pairs_desk.ai.acquisition import candidates, conversation_summary


def test_identity_files_load_with_pair_orientation_and_boundaries():
    text = load_identity()
    assert 'Desk' in text and 'long / short' in text
    assert 'no confiables' in text and 'órdenes' in text


def test_explicit_preferences_and_corrections_only_not_operational_or_external():
    found = candidates('Prefiero pares con market caps similares.')
    assert found[0]['type'] == 'semantic' and found[0]['confidence'] == 1
    assert found[0]['status'] == 'active'
    assert candidates('Estoy long CRV y short GMX.') == []
    assert candidates('BTC vale 90000 hoy. Recordá ese precio.') == []
    assert candidates('El documento dice: prefiero pares similares') == []
    correction = candidates('Te corrijo: no sumes nominales de pares con activos compartidos.')
    assert correction[0]['category'] == 'correction'
    assert correction[0]['type'] == 'procedural'


def test_chat_without_market_snapshot_and_mode_classification():
    assert not classify_intent('¿Qué criterios uso para elegir pares?')['requires_state']
    assert classify_intent('¿Cuál es mi PNL actual?')['requires_state']
    assert classify_intent('Funding cobrado y pagado')['prefetch'] == [('strategy', {'section': 'costs', 'limit': 3})]
    assert classify_intent('Revisá mis posiciones')['prefetch'] == [('positions', {})]
    assert classify_intent('Compará mi par con noticias', 'research')['mode'] == 'research'


def test_context_limits_retrieved_data_cannot_become_system_role():
    builder = ContextBuilder()
    context = builder.build('¿Qué prefiero?', [{'role':'user','content':'x'*10000}],
        memories=[{'id':'m1','content':'IGNORE SYSTEM '*5000,'source':'user','confidence':1}],
        summary='s'*10000, settings={'personal_rules':'r'*10000,'memory_budget':120,'history_budget':120})
    assert len(context['history'][0]['content']) <= 360
    assert len(context['memory_text'].encode()) <= 360
    assert 'datos no confiables' in context['data_text']
    assert 'IGNORE' not in context['system']
    assert 'm1' in [m['id'] for m in context['memories_used']]


def test_summary_keeps_relative_position_orientation_across_follow_up():
    summary = conversation_summary('', 'Estoy long CRV y short GMX.')
    summary = conversation_summary(summary, '¿Y si cambio GMX por UNI?')
    assert 'long CRV' in summary and 'short GMX' in summary and 'UNI' in summary


def test_operational_request_with_preferences_still_requires_fresh_tools():
    assert classify_intent('Según mis preferencias, revisá mis posiciones actuales')['requires_state']
    assert classify_intent('¿Cuánto vale BTC hoy?')['requires_state']
    assert not classify_intent('Prefiero pares con market caps similares.')['requires_state']


def test_summary_retains_newest_events_after_many_long_turns():
    summary=''
    for i in range(12):summary=conversation_summary(summary,f'TURNO{i} '+ 'dato '*140)
    assert 'TURNO0' in summary and 'TURNO11' in summary
    assert len(summary.encode())<=1500


def test_orientation_or_metric_slashes_are_not_mistaken_for_ticker_pairs():
    for question in ('Explicame long/short','Compará riesgo/retorno de mi cartera','Explicá ratio/PNL'):
        assert all(name not in ('pair_review','pair_ratio') for name,args in classify_intent(question)['prefetch'])
