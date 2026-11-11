import {useEffect,useRef,useState} from 'react';
import type {FormEvent,KeyboardEvent} from 'react';
import {advisorStatus,askAdvisor,deskApi} from '../advisorApi';
import type {AdvisorStatus,DeskConversation,DeskMessage,DeskMode,DeskPage} from '../advisorApi';
import {DeskPanels,MemoryEvidence} from './DeskPanels';
const time=(ms:number)=>new Date(ms).toLocaleString('es-AR',{timeZone:'America/Argentina/Buenos_Aires',day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit',second:'2-digit'});
const sourceName:Record<string,string>={'cuenta y posiciones':'Cuenta y posiciones',positions:'Posiciones',pair_review:'Análisis del par',strategy:'Estrategia / costos',closed_pairs:'Pares cerrados',analytics:'Indicadores del par',pair_candles:'Velas del ratio',ledger:'Operaciones y funding'};
const failure=(e:unknown)=>e instanceof Error?e.message:String(e);

export function Advisor({active,updatedAt,pairId}:{active:boolean;updatedAt?:number;pairId?:string}){
 const [status,setStatus]=useState<AdvisorStatus|null>(null),[statusError,setStatusError]=useState('');
 const [messages,setMessages]=useState<DeskMessage[]>([]),[input,setInput]=useState(''),[busy,setBusy]=useState(false),[stage,setStage]=useState(''),[error,setError]=useState('');
 const [conversation,setConversation]=useState<DeskConversation|null>(null),[conversations,setConversations]=useState<DeskPage<DeskConversation>|null>(null),[listOffset,setListOffset]=useState(0),[listError,setListError]=useState(''),[listLoading,setListLoading]=useState(false),[listRevision,setListRevision]=useState(0),[messageOffset,setMessageOffset]=useState(0),[loading,setLoading]=useState(false),[mode,setMode]=useState<DeskMode>('auto'),[showManagement,setShowManagement]=useState(false);
 const abort=useRef<AbortController|null>(null),generation=useRef(0),tail=useRef<HTMLDivElement|null>(null),alive=useRef(true);
 const [allowCodexContext,setAllowCodexContext]=useState(false);
 const requiresConsent=status?.provider==='codex'&&!allowCodexContext;
 const loadStatus=async()=>{try{const data=await advisorStatus();if(alive.current){setStatus(data);setStatusError('')}}catch(e){if(alive.current){setStatus(null);setStatusError(failure(e))}}};
 useEffect(()=>{alive.current=true;return()=>{alive.current=false;generation.current++;abort.current?.abort()}},[]);
 useEffect(()=>{if(!active)return;void loadStatus();const timer=window.setInterval(()=>void loadStatus(),20000);return()=>window.clearInterval(timer)},[active]);
 useEffect(()=>{if(!active)return;let current=true;setListLoading(true);deskApi.conversations(20,listOffset).then(data=>{if(current){setConversations(data);setListError('')}}).catch(e=>{if(current)setListError(failure(e))}).finally(()=>{if(current)setListLoading(false)});return()=>{current=false}},[active,listOffset,listRevision]);
 useEffect(()=>{if(active&&busy)tail.current?.scrollIntoView({block:'nearest'})},[messages,active,busy]);
 const refreshList=()=>setListRevision(n=>n+1);
 const reset=()=>{generation.current++;abort.current?.abort();abort.current=null;setBusy(false);setStage('');setConversation(null);setMessages([]);setMessageOffset(0);setInput('');setError('');setLoading(false)};
 const selectConversation=async(id:string)=>{
  reset();const current=generation.current;setLoading(true);
  try{const row=await deskApi.conversation(id);if(current!==generation.current)return;const offset=Math.max(0,(row.message_count||0)-30);const page=await deskApi.messages(id,30,offset);if(current!==generation.current)return;setConversation(row);setMessages(page.items);setMessageOffset(offset)}catch(e){if(current===generation.current)setError(failure(e))}finally{if(current===generation.current)setLoading(false)}
 };
 const olderMessages=async()=>{if(!conversation||loading||messageOffset===0)return;const current=generation.current;const offset=Math.max(0,messageOffset-30);setLoading(true);try{const page=await deskApi.messages(conversation.id,messageOffset-offset,offset);if(current===generation.current){setMessages(old=>[...page.items,...old]);setMessageOffset(offset)}}catch(e){if(current===generation.current)setError(failure(e))}finally{if(current===generation.current)setLoading(false)}};
 const removeConversation=async()=>{if(!conversation||!window.confirm('¿Eliminar esta conversación y sus mensajes? Las memorias adquiridas y las copias independientes se administran por separado.'))return;const id=conversation.id;reset();try{await deskApi.deleteConversation(id);refreshList()}catch(e){if(alive.current)setError(failure(e))}};
 const submit=async(question=input)=>{
  const prompt=question.trim();if(!prompt||busy||loading||requiresConsent)return;
  const current=++generation.current,request=new AbortController();abort.current=request;
  const replyId=`reply-${current}`;
  setInput('');setError('');setBusy(true);setStage('Preparando conversación…');
  try{
   let row=conversation;
   if(!row){row=await deskApi.createConversation(prompt.slice(0,100));if(current!==generation.current)return;setConversation(row);setListOffset(0);refreshList()}
   if(current!==generation.current)return;
   setMessages(prev=>[...prev,{id:`user-${current}`,role:'user',content:prompt,status:'complete'},{id:replyId,role:'assistant',content:'',status:'incomplete'}]);
   setStage(status?.provider==='codex'?'Conectando con Codex…':'Conectando con Ollama…');
   await askAdvisor(prompt,[],event=>{
    if(current!==generation.current)return;
    if(event.type==='stage')setStage(event.text||'Consultando herramientas…');
    if(event.type==='start'){setStage(`Modo ${event.mode||mode} · ${event.model||'modelo local'}`);setMessages(prev=>prev.map(m=>m.id===replyId?{...m,metadata:{...m.metadata,as_of_ms:event.as_of_ms}}:m))}
    if(event.type==='token')setMessages(prev=>prev.map(m=>m.id===replyId?{...m,content:m.content+(event.text||'')}:m));
    if(event.type==='done')setMessages(prev=>prev.map(m=>m.id===replyId?{...m,status:event.truncated?'incomplete':'complete',metadata:{sources:event.sources,as_of_ms:event.as_of_ms,memories_used:event.memories_used,truncated:event.truncated}}:m));
   },request.signal,{conversation_id:row.id,mode,...(status?.provider==='codex'?{allow_codex_context:allowCodexContext}:{})});
  }catch(e){
   if(current===generation.current){setError(request.signal.aborted?'Consulta cancelada. La respuesta puede quedar incompleta; el servidor conserva lo recibido.':failure(e));setMessages(prev=>prev.map(m=>m.id===replyId?{...m,status:'incomplete'}:m));setInput(prompt)}
  }finally{if(current===generation.current){setBusy(false);setStage('');abort.current=null;refreshList();void loadStatus()}}
 };
 const onSubmit=(event:FormEvent)=>{event.preventDefault();void submit()};
 const onKey=(event:KeyboardEvent<HTMLTextAreaElement>)=>{if(event.key==='Enter'&&!event.shiftKey&&!event.nativeEvent.isComposing){event.preventDefault();void submit()}};
 const stale=!updatedAt||Date.now()-updatedAt>90000;
 const questions=['Recordá que prefiero respuestas breves y con fuentes.','Revisá los riesgos actuales de mi cuenta y qué merece atención primero.',pairId?`Analizá ${pairId.replace('|',' / ')}: situación actual, riesgos y escenarios.`:'¿Qué activos me generan más costos y cómo influye el funding?'];
 return <section className="advisor-page" aria-label="Asesor Desk">
  <div className="advisor-heading"><div><span className="eyebrow">ASESOR IA</span><h2>Desk</h2><p>Conversaciones y preferencias guardadas localmente, con fuentes para revisar cada análisis.</p></div><span className="advisor-readonly">Sin órdenes</span></div>
  <div className="advisor-statusbar"><span className={'advisor-model '+(status?.available?'ready':'')}><i/>{status?.model||'Ollama local'} · {status?.available?status.processor:'No disponible'}</span><span>Datos de cuenta: {updatedAt?time(updatedAt):'sin lectura'}{stale?' · requieren actualización para analizar la cuenta':''}{status?.busy&&!busy?' · otra consulta en curso':''}</span><button type="button" onClick={()=>void loadStatus()}>Comprobar conexión</button></div>
  {(statusError||status?.reason)&&<div className="warning" role="status">{statusError||status?.reason}</div>}
  <div className="desk-toolbar"><button type="button" onClick={reset}>Nueva conversación</button><button type="button" aria-expanded={showManagement} onClick={()=>setShowManagement(v=>!v)}>Memorias y preferencias</button><label>Modo<select value={mode} onChange={e=>setMode(e.target.value as DeskMode)} disabled={busy}>{([['auto','Automático'],['chat','Conversar'],['analyze','Analizar'],['research','Investigar']] as const).map(([value,label])=><option key={value} value={value}>{label}</option>)}</select></label></div>
  {showManagement&&<DeskPanels refreshToken={listRevision} onDataChanged={()=>{reset();setListOffset(0);refreshList()}}/>}
  <div className="desk-layout"><aside className="panel desk-conversations" aria-label="Conversaciones guardadas"><h3>Conversaciones</h3>{listError&&<p className="warning" role="alert">{listError}<button onClick={refreshList}>Reintentar</button></p>}{listLoading&&<p role="status">Cargando…</p>}{!listLoading&&conversations?.total===0&&<p className="desk-muted">Todavía no hay conversaciones guardadas.</p>}<div className="desk-conversation-list">{conversations?.items.map(row=><button key={row.id} type="button" aria-current={conversation?.id===row.id?'true':undefined} onClick={()=>void selectConversation(row.id)}>{row.title||'Conversación sin título'}</button>)}</div><div className="desk-actions"><button disabled={listLoading||listOffset===0} onClick={()=>setListOffset(n=>Math.max(0,n-20))}>Anterior</button><button disabled={listLoading||!conversations||listOffset+conversations.items.length>=conversations.total} onClick={()=>setListOffset(n=>n+20)}>Más</button></div>{conversations&&<small>{conversations.total} guardadas</small>}</aside>
  <div className="panel advisor-chat"><div className="advisor-chat-top"><h3>{conversation?.title||'Conversá con Desk'}</h3>{conversation&&<button onClick={()=>void removeConversation()}>Eliminar chat</button>}</div>
   {conversation?.summary&&<details className="desk-summary"><summary>Resumen guardado</summary><p>{conversation.summary}</p></details>}
   <div className="advisor-messages" aria-live="polite" aria-relevant="additions" aria-busy={loading}>
    {loading&&<p role="status">Cargando mensajes…</p>}{messageOffset>0&&<button disabled={loading||busy} onClick={()=>void olderMessages()}>Cargar mensajes anteriores ({messageOffset})</button>}
    {!messages.length&&!loading&&<div className="advisor-empty"><div className="advisor-symbol" aria-hidden="true">◈</div><h3>¿Qué querés conversar o analizar?</h3><p>Podés guardar preferencias y revisar qué memorias y fuentes se usaron. Para consultar datos de cuenta, Desk necesita una lectura vigente.</p><div className="advisor-suggestions">{questions.map(q=><button key={q} disabled={busy||!status?.available||requiresConsent} onClick={()=>void submit(q)}>{q}<span aria-hidden="true">↗</span></button>)}</div></div>}
    {messages.map(message=><article className={'advisor-message '+message.role} key={message.id}><div className="advisor-author">{message.role==='user'?'Vos':'Desk'}{message.metadata?.as_of_ms?<span>Datos: {time(message.metadata.as_of_ms)}</span>:null}</div>
     <div className="advisor-answer">{message.content||(busy?stage:'Sin respuesta completa')}</div>
     {(message.status==='incomplete'||message.metadata?.truncated)&&<span className="advisor-incomplete">{message.metadata?.truncated?'Alcanzó el límite de extensión · respuesta incompleta. Pedí una versión más breve o dividí el análisis en partes.':'Respuesta interrumpida · no usar como conclusión'}</span>}
     {!!message.metadata?.sources?.length&&<div className="advisor-sources" aria-label="Fuentes consultadas">{message.metadata.sources.filter((s,i,a)=>a.findIndex(x=>x.name===s.name&&x.as_of_ms===s.as_of_ms)===i).map(s=><span key={s.name+s.as_of_ms}>{sourceName[s.name]||s.name} · {s.as_of_ms?time(s.as_of_ms):'fecha no informada'}</span>)}</div>}
     {!!message.metadata?.memories_used?.length&&<MemoryEvidence memories={message.metadata.memories_used}/>}
    </article>)}<div ref={tail}/>
   </div>
   {error&&<div className="warning advisor-error" role="alert">{error}</div>}
   {busy&&<p className="advisor-progress" role="status"><span/>{stage} {status?.provider!=='codex'&&' La primera consulta puede tardar al cargar el modelo.'}</p>}
   <form className="advisor-compose" onSubmit={onSubmit}>{status?.provider==='codex'&&<label className="desk-check"><input type="checkbox" checked={allowCodexContext} disabled={busy} onChange={e=>setAllowCodexContext(e.target.checked)}/>Enviar la consulta y el contexto seleccionado a OpenAI (historial, recuerdos y datos de cuenta cuando correspondan)</label>}<label htmlFor="advisor-question">Tu consulta</label><textarea id="advisor-question" value={input} onChange={e=>setInput(e.target.value)} onKeyDown={onKey} maxLength={2000} rows={3} placeholder="Consultá, indicá una preferencia o pedí un análisis" disabled={busy||loading}/><div><span>Enter para enviar · Shift + Enter para nueva línea</span>{busy?<button type="button" onClick={()=>abort.current?.abort()}>Cancelar consulta</button>:<button className="advisor-send" disabled={!input.trim()||loading||!status?.available||requiresConsent} type="submit">Consultar ↗</button>}</div></form>
  </div></div>
  <p className="advisor-footnote">{status?.provider==='codex'?'Codex usa el cupo de tu cuenta de ChatGPT.':'Ollama procesa las consultas en esta PC.'} Desk guarda conversaciones y memorias en el servidor local. Revisá las fechas, fuentes y memorias utilizadas antes de decidir. Las respuestas no ejecutan operaciones.</p>
 </section>;
}
