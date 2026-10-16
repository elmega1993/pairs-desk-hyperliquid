const vm=require('node:vm'),fs=require('node:fs'),assert=require('node:assert/strict');
let now=100000,scheduled=[],updates=0;
class Socket{constructor(url){this.url=url;this.readyState=0;this.sent=[];Socket.latest=this;}send(s){this.sent.push(JSON.parse(s));}close(){this.readyState=3;this.onclose?.();}open(){this.readyState=1;this.onopen();}price(coin,markPx){this.onmessage({data:JSON.stringify({channel:'activeAssetCtx',data:{coin,ctx:{markPx}}})});}}
const ctx=vm.createContext({WebSocket:Socket,Date:{now:()=>now},setInterval:()=>1,clearInterval:()=>{},setTimeout:f=>{scheduled.push(f);return 1;},clearTimeout:()=>{}});
vm.runInContext(fs.readFileSync(require('node:path').join(__dirname,'../frontend/live-ratios.js'),'utf8')+'\nglobalThis.Client=LiveRatios;',ctx);
const client=new ctx.Client(()=>updates++,()=>{}),pair={long:'xyz:ORCL',short:'xyz:QQQ'};
client.sync([pair]);const ws=Socket.latest;ws.open();assert.equal(ws.sent.length,2);assert.equal(ws.sent[0].subscription.coin,'xyz:ORCL');
ws.price(pair.long,'200');assert.equal(client.ratio(pair),null);ws.price(pair.short,'500');assert.equal(client.ratio(pair),.4);
ws.price(pair.short,'0');assert.equal(client.ratio(pair),.4);
now+=16000;assert.equal(client.ratio(pair),null);ws.price(pair.long,'210');assert.equal(client.ratio(pair),null);ws.price(pair.short,'500');assert.equal(client.ratio(pair),.42);
client.sync([{long:'BTC',short:'xyz:QQQ'}]);assert(ws.sent.some(x=>x.method==='unsubscribe'&&x.subscription.coin==='xyz:ORCL'));assert(ws.sent.some(x=>x.method==='subscribe'&&x.subscription.coin==='BTC'));
ws.close();assert.equal(client.prices.size,0);assert.equal(scheduled.length,1);scheduled.shift()();Socket.latest.open();assert.equal(Socket.latest.sent.length,2);
client.stop();assert(updates>0);console.log('OK: two-leg freshness, XYZ symbols, invalid prices, subscriptions and reconnect');
