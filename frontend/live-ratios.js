'use strict';
// Public mark-price stream. Never sends account data or trading requests.
class LiveRatios {
 constructor(onUpdate, onStatus) {
  this.onUpdate=onUpdate; this.onStatus=onStatus; this.coins=new Set();
  this.prices=new Map(); this.httpPrices=new Map(); this.lastPoll=0; this.httpError=""; this.retry=1000; this.stopped=false;
  this.timer=setInterval(()=>this.tick(),1000);
 }
 sync(pairs) {
  const next=new Set(pairs.flatMap(p=>[p.long,p.short]));
  if(this.ws?.readyState===1){
   for(const coin of this.coins)if(!next.has(coin))this.send('unsubscribe',coin);
   for(const coin of next)if(!this.coins.has(coin))this.send('subscribe',coin);
  }
  for(const coin of this.coins)if(!next.has(coin))this.prices.delete(coin);
  this.coins=next;
  if(next.size&&!this.ws&&!this.reconnect)this.connect();
 }
 send(method,coin){this.ws.send(JSON.stringify({method,subscription:{type:'activeAssetCtx',coin}}));}
 connect(){
  if(this.stopped)return;
  this.prices.clear(); this.lastMessage=Date.now(); this.connectedAt=Date.now(); this.lastPrice=0; this.lastPing=0;
  this.onStatus('conectando');
  let ws;
  try{ws=new WebSocket('wss://api.hyperliquid.xyz/ws');}catch(e){this.schedule();return;}
  this.ws=ws;
  ws.onopen=()=>{if(this.ws!==ws)return;this.onStatus('esperando precios');for(const coin of this.coins)this.send('subscribe',coin);};
  ws.onmessage=event=>{
   if(this.ws!==ws)return;
   this.lastMessage=Date.now();
   let msg;try{msg=JSON.parse(event.data);}catch(e){return;}
   if(msg.channel==='error'){this.streamError=typeof msg.data==='string'?msg.data:JSON.stringify(msg.data);this.onStatus('suscripción rechazada; usando respaldo');return;}
   if(msg.channel!=='activeAssetCtx')return;
   const coin=msg.data?.coin,price=Number(msg.data?.ctx?.markPx);
   if(!this.coins.has(coin)||!Number.isFinite(price)||price<=0)return;
   this.retry=1000;this.lastPrice=Date.now();this.onStatus('recibiendo');this.prices.set(coin,{price,time:Date.now()});this.onUpdate();
  };
  ws.onerror=()=>ws.close();
  ws.onclose=()=>{if(this.ws!==ws)return;this.ws=null;this.prices.clear();this.onUpdate();this.onStatus('reconectando');this.schedule();};
 }
 schedule(){if(this.stopped||this.reconnect)return;this.onStatus('reconectando');this.reconnect=setTimeout(()=>{this.reconnect=null;this.connect();},this.retry);this.retry=Math.min(30000,this.retry*2);}
 quote(pair){
  const now=Date.now();
  for(const [map,source] of [[this.prices,'ws'],[this.httpPrices,'http']]){
   const a=map.get(pair.long),b=map.get(pair.short);
   if(!a||!b||now-a.time>15000||now-b.time>15000)continue;
   const ratio=a.price/b.price;
   if(Number.isFinite(ratio)&&ratio>0)return {ratio,source};
  }
  return null;
 }
 ratio(pair){return this.quote(pair)?.ratio??null;}
 async poll(){
  if(this.polling||this.stopped)return;
  this.polling=true;this.lastPoll=Date.now();
  const controller=new AbortController();this.pollController=controller;
  const timeout=setTimeout(()=>controller.abort(),18000);
  try{
   const response=await fetch('/api/live-prices',{cache:'no-store',signal:controller.signal});
   if(!response.ok)throw Error('HTTP '+response.status+' en consulta de precios');
   const data=await response.json();
   if(this.stopped)return;
   for(const [coin,value] of Object.entries(data.prices||{})){
    const price=Number(value.price),time=Number(value.time);
    if(this.coins.has(coin)&&Number.isFinite(price)&&price>0&&Number.isFinite(time))this.httpPrices.set(coin,{price,time});
   }
   this.httpError=(data.errors||[]).join('; ');
  }catch(e){this.httpError=e.name==='AbortError'?'La consulta de precios tardó demasiado':e.message;}
  finally{clearTimeout(timeout);this.polling=false;this.pollController=null;if(!this.stopped)this.onUpdate();}
 }
 tick(){
  const ws=this.ws,now=Date.now();
  const missing=[...this.coins].some(coin=>!this.prices.has(coin)||now-this.prices.get(coin).time>10000);
  if(missing&&now-this.lastPoll>=5000)this.poll();
  if(ws?.readyState===1&&now-(this.lastPrice||this.connectedAt)>15000){this.onStatus('sin precios; usando respaldo');ws.close();return;}
  if(ws&&(ws.readyState===0||ws.readyState===1)&&now-this.lastMessage>45000){ws.close();return;}
  if(ws?.readyState===1&&now-this.lastPing>20000){ws.send(JSON.stringify({method:'ping'}));this.lastPing=now;}
  this.onUpdate();
 }
 stop(){this.stopped=true;clearInterval(this.timer);clearTimeout(this.reconnect);this.pollController?.abort();this.ws?.close();}
}
