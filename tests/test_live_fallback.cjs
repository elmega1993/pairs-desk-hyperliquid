const serverSource=require('node:fs').readFileSync(require('node:path').join(__dirname,'../read_only_server.py'),'utf8');
require('node:assert/strict').match(serverSource,/connect-src 'self' wss:\/\/api\.hyperliquid\.xyz;/);
const vm=require('node:vm'),fs=require('node:fs'),assert=require('node:assert/strict');
let now=100000,requests=0,pendingResolve;
const ctx=vm.createContext({Date:{now:()=>now},AbortController,setInterval:()=>1,clearInterval:()=>{},setTimeout:()=>1,clearTimeout:()=>{},fetch:async()=>{requests++;return await new Promise(resolve=>pendingResolve=resolve);}});
vm.runInContext(fs.readFileSync(require('node:path').join(__dirname,'../frontend/live-ratios.js'),'utf8')+'\nglobalThis.Client=LiveRatios;',ctx);
(async()=>{
 const client=new ctx.Client(()=>{},()=>{}),pair={long:'ZK',short:'STRK'};
 client.coins=new Set(['ZK','STRK']);
 const pending=client.poll();await client.poll();assert.equal(requests,1);
 pendingResolve({ok:true,json:async()=>({prices:{ZK:{price:.15,time:now},STRK:{price:1,time:now}}})});await pending;
 assert.equal(client.quote(pair).source,'http');assert.equal(client.ratio(pair),.15);
 client.prices.set('ZK',{price:.16,time:now});assert.equal(client.quote(pair).source,'http');
 client.prices.set('STRK',{price:1,time:now});assert.equal(client.quote(pair).source,'ws');
 now+=16000;assert.equal(client.quote(pair),null);
 const failed=client.poll();pendingResolve({ok:false,status:503});await failed;assert(client.httpError.includes('503'));assert.equal(client.quote(pair),null);
 client.ws={readyState:1,close(){this.closed=true;}};client.connectedAt=now-16000;client.lastPrice=0;client.lastPoll=now;client.lastMessage=now;client.tick();assert(client.ws.closed);
 client.stop();console.log('OK: fallback, no overlapping fetch, no mixed sources, expiry, HTTP error, silent WebSocket watchdog');
})().catch(e=>{console.error(e);process.exitCode=1});
