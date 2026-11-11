export type AdvisorSource={name:string;as_of_ms:number};
export type DeskMode='auto'|'chat'|'analyze'|'research';
export type DeskMemory={id:string;content:string;type:string;status:string;importance?:number;confidence?:number;category?:string;source?:string;source_id?:string;retrieval_reason?:string;retrieval_explanation?:string|Record<string,number>;why_used?:string;explanation?:string};
export type AdvisorEvent={type:'start'|'stage'|'token'|'done'|'error';text?:string;message?:string;model?:string;as_of_ms?:number;sources?:AdvisorSource[];truncated?:boolean;stop_reason?:string;conversation_id?:string;mode?:DeskMode;memories_used?:DeskMemory[]};
export type AdvisorTurn={role:'user'|'assistant';content:string};
export type AdvisorStatus={available:boolean;model:string;processor:string;provider?:'codex';busy:boolean;reason?:string|null};
export type DeskConversation={id:string;title:string;summary?:string;message_count?:number;created_at?:string;updated_at?:string};
export type DeskMessage=AdvisorTurn&{id:string;status?:string;metadata?:{as_of_ms?:number;sources?:AdvisorSource[];memories_used?:DeskMemory[];truncated?:boolean};created_at?:string};
export type DeskMemoryRevision={id?:number;snapshot:Partial<DeskMemory>;created_at:string};
export type DeskPage<T>={items:T[];total:number;limit:number;offset:number};
export type DeskSettings={personal_rules:string;temperature:number;max_tokens:number;memory_budget:number;history_budget:number;acquisition_enabled:boolean};

export function advisorHistory(messages:AdvisorTurn[]):AdvisorTurn[]{
 return messages.filter(m=>m.content.trim()).slice(-6).map(m=>({role:m.role,content:m.content.slice(0,1000)}));
}
async function jsonRequest<T>(path:string,method='GET',data?:unknown,signal?:AbortSignal):Promise<T>{
 const response=await fetch('/api/advisor'+path,{method,cache:'no-store',headers:data===undefined?undefined:{'Content-Type':'application/json'},body:data===undefined?undefined:JSON.stringify(data),signal});
 if(!response.ok){let detail='No se pudo completar la operación';try{const body=await response.json();if(typeof body.detail==='string')detail=body.detail;else if(Array.isArray(body.detail))detail=body.detail.map((x:{msg?:string})=>x.msg||'Dato inválido').join('; ')}catch{}throw new Error(detail)}
 if(response.status===204)return undefined as T;
 return response.json();
}
const key=encodeURIComponent;
export const deskApi={
 conversations:(limit=20,offset=0)=>jsonRequest<DeskPage<DeskConversation>>(`/conversations?limit=${limit}&offset=${offset}`),
 createConversation:(title='Nueva conversación')=>jsonRequest<DeskConversation>('/conversations','POST',{title}),
 conversation:(id:string)=>jsonRequest<DeskConversation>(`/conversations/${key(id)}`),
 deleteConversation:(id:string)=>jsonRequest(`/conversations/${key(id)}`,'DELETE'),
 messages:(id:string,limit=30,offset=0)=>jsonRequest<DeskPage<DeskMessage>>(`/conversations/${key(id)}/messages?limit=${limit}&offset=${offset}`),
 memories:(limit=20,offset=0)=>jsonRequest<DeskPage<DeskMemory>>(`/memories?limit=${limit}&offset=${offset}`),
 createMemory:(data:Partial<DeskMemory>)=>jsonRequest<DeskMemory>('/memories','POST',data),
 updateMemory:(id:string,data:Partial<DeskMemory>)=>jsonRequest<DeskMemory>(`/memories/${key(id)}`,'PATCH',data),
 memoryDuplicates:(id:string,limit=5)=>jsonRequest<{items:(DeskMemory&{score?:number})[];total:number}>(`/memories/${key(id)}/duplicates?limit=${limit}`),
 consolidateMemory:(id:string,duplicate_ids:string[])=>jsonRequest<DeskMemory>(`/memories/${key(id)}/consolidate`,'POST',{duplicate_ids}),
 memoryRevisions:(id:string,limit=20,offset=0)=>jsonRequest<DeskPage<DeskMemoryRevision>>(`/memories/${key(id)}/revisions?limit=${limit}&offset=${offset}`),
 deleteMemory:(id:string)=>jsonRequest(`/memories/${key(id)}`,'DELETE'),
 settings:()=>jsonRequest<DeskSettings>('/settings'),
 updateSettings:(data:DeskSettings)=>jsonRequest<DeskSettings>('/settings','PATCH',data),
 export:()=>jsonRequest<unknown>('/export'),
 import:(data:unknown)=>jsonRequest('/import','POST',{data}),
 backup:()=>jsonRequest('/backup','POST'),
 erase:(confirmation:string)=>jsonRequest('/data','DELETE',{confirmation}),
};
export function advisorStatus():Promise<AdvisorStatus>{return jsonRequest<AdvisorStatus>('/status')}

export async function askAdvisor(message:string,history:AdvisorTurn[],onEvent:(event:AdvisorEvent)=>void,signal?:AbortSignal,options?:{conversation_id?:string;mode?:DeskMode;allow_codex_context?:boolean}):Promise<void>{
 const body=options?{message,...options}:{message,history:advisorHistory(history)};
 const response=await fetch('/api/advisor/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body),signal});
 if(!response.ok){let detail='No se pudo iniciar la consulta';try{const data=await response.json();if(typeof data.detail==='string')detail=data.detail}catch{}throw new Error(detail)}
 if(!response.body)throw new Error('El navegador no pudo abrir la respuesta progresiva');
 const reader=response.body.getReader(),decoder=new TextDecoder();let buffer='',done=false;
 const consume=(line:string)=>{if(!line.trim())return;const event=JSON.parse(line) as AdvisorEvent;if(event.type==='error')throw new Error(event.message||'Se interrumpió la consulta');if(event.type==='done')done=true;onEvent(event)};
 try{
  while(true){const chunk=await reader.read();if(chunk.done)break;buffer+=decoder.decode(chunk.value,{stream:true});let end:number;while((end=buffer.indexOf('\n'))>=0){consume(buffer.slice(0,end));buffer=buffer.slice(end+1)}}
  buffer+=decoder.decode();if(buffer.trim())consume(buffer);
  if(!done)throw new Error('La respuesta se interrumpió antes de completarse. Volvé a intentar.');
 }finally{try{await reader.cancel()}finally{reader.releaseLock()}}
}
