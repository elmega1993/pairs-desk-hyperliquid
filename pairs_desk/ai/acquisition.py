"""Conservative explicit-user acquisition; model/external output cannot auto-approve itself."""
import re
from .context import normalized, clip


def candidates(text):
    q = normalized(text.strip())
    # Only first-person explicit statements at the beginning; never quoted source text.
    if len(text) > 2000 or re.search(r'\b(precio|cotiza|vale \d|estoy long|estoy short|api.?key|private.?key|seed|secret|contrase|0x[a-f0-9]{20})', q):
        return []
    patterns = [
        (r'^(te corrijo|correccion|recorda este error)\b', 'procedural', 'correction'),
        (r'^(?:ahora |ya no )?(prefiero|mi preferencia es)\b', 'semantic', 'preference'),
        (r'^(mi objetivo es|quiero recordar que)\b', 'semantic', 'goal'),
        (r'^(mi regla es|recorda que|no vuelvas a|a partir de ahora)\b', 'procedural', 'rule'),
        (r'^(aprendi que|la leccion es|decidi que)\b', 'episodic', 'lesson'),
    ]
    for pattern, kind, category in patterns:
        if re.search(pattern, q):
            return [{'type':kind, 'category':category, 'content':text.strip(), 'importance':.9 if kind=='procedural' else .75,
                     'confidence':1., 'status':'active', 'source':'explicit_user',
                     'metadata':{'acquisition':'explicit_prefix','confirmed':True}}]
    return []


def conversation_summary(previous, user_text):
    # Attributed extractive summary: reserve the first scenario AND recent context.
    statement = 'Usuario dijo: '+clip(user_text, 200)
    lines = (previous.splitlines() if previous else []) + [statement]
    if len(lines)==1:return clip(statement,500)
    first=clip(lines[0],120)
    remaining=1500-len((first+'\n').encode())
    tail=[]
    for line in reversed(lines[1:]):
        if remaining<=0:break
        part=line.encode()[:remaining].decode('utf-8',errors='ignore')
        tail.insert(0,part);remaining-=len((part+'\n').encode())
    return first+'\n'+'\n'.join(tail)


def _topic(text):
    q=normalized(text)
    if re.search(r'respuestas? (breve|corta|extensa|larga|detallada)',q):return 'response_length'
    if re.search(r'market caps?|capitalizaci',q):return 'pair_market_caps'
    if re.search(r'respuestas?.*(fuentes|citas)',q):return 'response_sources'
    if re.search(r'nominal|exposicion.*compart|pares.*compart',q):return 'shared_exposure'
    if re.search(r'funding|comision',q):return 'cost_accounting'
    return None


def acquire(store, scope, text, source_id):
    saved=[]
    for proposal in candidates(text):
        # Replace only explicit statements concerning the same narrow topic.
        # A broad lexical overlap such as "prefiero" is never a contradiction.
        topic=_topic(text)
        proposal['metadata']['topic']=topic
        if topic:
            active=store.list_memories(scope,status='active',limit=100)['items']
            prior=next((m for m in active if m['category']==proposal['category']
                        and _topic(m['content'])==topic and normalized(m['content'])!=normalized(text)),None)
            if prior:proposal['supersedes_id']=prior['id']
        saved.append(store.remember(scope, source_id=source_id, **proposal))
    return saved
