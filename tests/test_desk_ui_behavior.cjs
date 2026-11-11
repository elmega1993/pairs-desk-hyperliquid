const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const ts=require(require.resolve('typescript',{paths:[path.join(__dirname,'../react_frontend')]}));
function harness(){
 const states=[],refs=[],effects=[];let cursor=0,dirty=true,tree,queued=[],chat,createCalls=0;
 const calls=[];
 const React={
  useState(initial){const i=cursor++;if(!(i in states))states[i]=typeof initial==='function'?initial():initial;return [states[i],value=>{states[i]=typeof value==='function'?value(states[i]):value;dirty=true}]},
  useRef(initial){const i=cursor++;return refs[i]||(refs[i]={current:initial})},
  useEffect(fn,deps){const i=cursor++;if(!effects[i]||!deps||deps.some((x,j)=>x!==effects[i].deps?.[j])){queued.push(()=>{effects[i]?.cleanup?.();effects[i]={deps,cleanup:fn()}})}}
 };
 const deskApi={
  conversations:async()=>({items:[{id:'old',title:'Vecina'},{id:'long',title:'Chat largo'}],total:2,limit:20,offset:0}),
  conversation:async id=>({id,title:id==='long'?'Chat largo':'Vecina',message_count:id==='long'?95:1}),
  messages:async(id,limit,offset)=>{calls.push({op:'messages',id,limit,offset});return {items:id==='long'?[{id:'m95',role:'assistant',content:'Respuesta anterior',status:'complete'}]:[{id:'m1',role:'user',content:'Otro chat'}],total:id==='long'?95:1,limit,offset}},
  createConversation:async title=>{calls.push({op:'create',title});createCalls++;return {id:'created',title}},
  deleteConversation:async()=>{},
 };
 const api={deskApi,advisorStatus:async()=>({available:true,model:'local',processor:'GPU'}),askAdvisor:(message,history,onEvent,signal,options)=>{calls.push({op:'ask',message,history,options});return new Promise((resolve,reject)=>{chat={onEvent,resolve,reject,signal};signal.addEventListener('abort',()=>reject(new Error('Abortado')),{once:true})})}};
 const runtime={jsx:(type,props,key)=>({type,props:props||{},key}),jsxs:(type,props,key)=>({type,props:props||{},key})};
 const mod={exports:{}};
 const code=ts.transpileModule(fs.readFileSync(path.join(__dirname,'../react_frontend/src/components/Advisor.tsx'),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX}}).outputText;
 vm.runInNewContext(code,{module:mod,exports:mod.exports,require:name=>name==='react'?React:name==='react/jsx-runtime'?runtime:name==='../advisorApi'?api:{DeskPanels:()=>null,MemoryEvidence:()=>null},AbortController,Date,Error,window:{setInterval:()=>1,clearInterval(){},confirm:()=>true}});
 const render=()=>{cursor=0;dirty=false;tree=mod.exports.Advisor({active:true});const pending=queued;queued=[];pending.forEach(fn=>fn());return tree};
 async function flush(){for(let i=0;i<16;i++){await Promise.resolve();if(dirty)render()}}
 const walk=(node,predicate)=>{if(!node||typeof node!=='object')return null;if(predicate(node))return node;const children=node.props?.children;for(const child of Array.isArray(children)?children:[children]){if(Array.isArray(child)){for(const nested of child){const found=walk(nested,predicate);if(found)return found}}else{const found=walk(child,predicate);if(found)return found}}return null};
 const text=node=>node==null?'':Array.isArray(node)?node.map(text).join(''):typeof node==='object'?text(node.props?.children):String(node);
 const button=label=>walk(tree,n=>n.type==='button'&&text(n)===label);
 render();
 return {flush,button,find:predicate=>walk(tree,predicate),calls,text:()=>text(tree),get chat(){return chat},get creates(){return createCalls},unmount(){effects.forEach(e=>e?.cleanup?.())}};
}
(async()=>{
 const h=harness();await h.flush();
 h.find(n=>n.type==='textarea').props.onChange({target:{value:'Hola sin datos de cuenta'}});await h.flush();
 assert.equal(h.button('Consultar ↗').props.disabled,false,'Casual chat must remain available without account snapshot');
 h.find(n=>n.type==='form').props.onSubmit({preventDefault(){}});await h.flush();
 assert.equal(h.creates,1);assert.equal(h.calls.findIndex(x=>x.op==='create')<h.calls.findIndex(x=>x.op==='ask'),true);
 const sent=h.calls.find(x=>x.op==='ask');assert.equal(sent.options.conversation_id,'created');assert.equal(sent.options.mode,'auto');assert.equal(sent.history.length,0);
 h.chat.onEvent({type:'token',text:'Partial old conversation'});await h.flush();
 const oldChat=h.chat;
 h.button('Chat largo').props.onClick();await h.flush();
 assert.equal(oldChat.signal.aborted,true);assert.ok(h.calls.some(c=>c.op==='messages'&&c.id==='long'&&c.limit===30&&c.offset===65),'Newest page must be loaded by message_count');
 oldChat.onEvent({type:'token',text:'SHOULD NOT LEAK'});await h.flush();
 assert.equal(h.text().includes('SHOULD NOT LEAK'),false);assert.equal(h.text().includes('Partial old conversation'),false);
 h.button('Cargar mensajes anteriores (65)').props.onClick();await h.flush();
 assert.ok(h.calls.some(c=>c.op==='messages'&&c.id==='long'&&c.limit===30&&c.offset===35));
 h.find(n=>n.type==='textarea').props.onChange({target:{value:'Seguir el chat'}});await h.flush();
 h.find(n=>n.type==='select').props.onChange({target:{value:'research'}});await h.flush();
 h.find(n=>n.type==='form').props.onSubmit({preventDefault(){}});await h.flush();
 assert.equal(h.creates,1,'Existing chat must not create another conversation');assert.equal(h.calls.at(-1).options.mode,'research');
 const last=h.chat;h.unmount();assert.equal(last.signal.aborted,true);await h.flush();
 const limited=harness();await limited.flush();
 limited.find(n=>n.type==='textarea').props.onChange({target:{value:'Analizá el par'}});await limited.flush();
 limited.find(n=>n.type==='form').props.onSubmit({preventDefault(){}});await limited.flush();
 limited.chat.onEvent({type:'token',text:'Respuesta parcial'});
 limited.chat.onEvent({type:'done',truncated:true,stop_reason:'length'});limited.chat.resolve();await limited.flush();
 assert.ok(limited.text().includes('límite de extensión'),'Length stop must explain why response is incomplete');
 limited.unmount();
 console.log('OK: Desk conversation persistence, modes, newest/older pagination, stale chat, switch isolation, unmount cancellation');
})().catch(e=>{console.error(e);process.exitCode=1});
