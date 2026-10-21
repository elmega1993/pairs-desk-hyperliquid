const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const ts=require(require.resolve('typescript',{paths:[path.join(__dirname,'../react_frontend')]}));
function load(name){
  const code=fs.readFileSync(path.join(__dirname,'../react_frontend/src/'+name),'utf8');
  const out=ts.transpileModule(code,{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}}).outputText;
  const m={exports:{}};vm.runInNewContext(out,{module:m,exports:m.exports,Math,Number,Object,Array,Infinity,Map});return m.exports;
}
const {normalizePnlHistory,gapThreshold,toSegments,runningPeaks,pnlStats,gapTotal,includeZero,pickPnlSeries,drawdownSeries,drawdownDomain,groupPnlEvents,historicalComponent}=load('pnlModel.ts');
const {reconcile}=load('reconcile.ts');
const {buildAttention,statusMeta}=load('attention.ts');
const MIN=60000;
// --- segmentos: huecos y cambio de base ---
const rows=[];for(let i=0;i<10;i++)rows.push({time:1e12+i*MIN,pnl:i,basis:'gross'});
for(let i=0;i<5;i++)rows.push({time:1e12+(10+i)*MIN,pnl:100+i,basis:'net'});
for(let i=0;i<5;i++)rows.push({time:1e12+(300+i)*MIN,pnl:90+i,basis:'net'});
let r=toSegments(rows);
assert.equal(r.segments.length,3);
assert.deepEqual(Array.from(r.breaks,b=>b.kind),['basis','gap']);
assert.equal(r.segments.reduce((n,s)=>n+s.length,0),rows.length);
// sin cortes en una serie continua de una sola base
assert.equal(toSegments(rows.slice(0,10)).segments.length,1);
// el umbral nunca baja de 15 minutos
assert.equal(gapThreshold([{time:0,pnl:0},{time:1000,pnl:1}]),15*MIN);
// los huecos conservan los valores de ambos extremos (para el conector punteado) y se suman
const gapBreak=r.breaks.find(b=>b.kind==='gap');
assert.equal(gapBreak.fromPnl,104);assert.equal(gapBreak.pnl,90);
assert.equal(gapTotal(r.breaks),(300-14)*MIN);
// escala automática: cero solo si hay cruce o cercanía
assert.equal(includeZero(-40,300,'auto'),true);assert.equal(includeZero(2068,2674,'auto'),false);assert.equal(includeZero(2068,2674,'zero'),true);assert.equal(includeZero(50,300,'auto'),true);
// --- estadísticas: usan solo la última corrida con la misma base ---
let s=pnlStats(rows);
assert.equal(s.mixedBasis,true);assert.equal(s.first,100);assert.equal(s.max.pnl,104);assert.equal(s.min.pnl,90);
assert.equal(s.last,94);assert.equal(s.fromPeak,-10);assert.equal(s.delta,-6);
s=pnlStats([{time:1,pnl:0},{time:2,pnl:10},{time:3,pnl:4},{time:4,pnl:12},{time:5,pnl:6}]);
assert.equal(s.mixedBasis,false);assert.equal(s.maxDrawdown,-6);assert.equal(s.fromPeak,-6);assert.equal(pnlStats([]),null);
const d=drawdownSeries([{time:1,pnl:0},{time:2,pnl:10},{time:3,pnl:4},{time:4,pnl:12},{time:5,pnl:6}]);
assert.equal(d.summary.max,-6);assert.equal(d.summary.current,-6);assert.equal(d.summary.currentDuration,1);assert.equal(d.summary.recoveryMs,null);
assert.deepEqual(Array.from(drawdownSeries([{time:1,pnl:0},{time:2,pnl:10},{time:3,pnl:4},{time:4,pnl:12},{time:5,pnl:6}]),x=>x.drawdown),[0,0,-6,0,-6]);
assert.equal(drawdownSeries([{time:1,pnl:0},{time:2,pnl:10},{time:3,pnl:4},{time:4,pnl:10}]).summary.recoveryMs,2);
assert.equal(drawdownSeries([{time:1,pnl:100,basis:'gross'},{time:2,pnl:10,basis:'net'}])[1].drawdown,0);
const ddDomain=drawdownDomain([{time:1,pnl:0},{time:2,pnl:10},{time:3,pnl:4}]);
assert.equal(ddDomain.high,0);assert.ok(ddDomain.low<-6);
assert.equal(historicalComponent({realized:12},'realized',0,2,99),12);
assert.equal(historicalComponent({},'realized',0,2,99),null);
assert.equal(historicalComponent({},'realized',2,2,99),99);
const eventGroups=groupPnlEvents([{time:1e12,kind:'open',pair:'A/B'},{time:1e12+100,kind:'add',pair:'A/B'},{time:1e12+10000,kind:'close',pair:'C/D'}],2000);
assert.equal(eventGroups.length,2);assert.equal(eventGroups[0].count,2);assert.equal(eventGroups[0].label,'A/B · apertura + ADD');assert.equal(eventGroups[1].label,'C/D · cierre');
assert.equal(groupPnlEvents([{time:1e12,kind:'open',pair:'A/B'},{time:1e12+100,kind:'open',pair:'C/D'}],2000)[0].label,'2 pares · apertura');
// picos reiniciados en cambio de base
assert.deepEqual(Array.from(runningPeaks([{time:1,pnl:50,basis:'gross'},{time:2,pnl:10,basis:'net'},{time:3,pnl:20,basis:'net'}])),[50,10,20]);
// normalización: segundos→ms, orden y duplicados; conserva basis
const n=normalizePnlHistory([{time:200,pnl:2,basis:'net'},{time:100,pnl:1},{time:100,pnl:5},{time:NaN,pnl:1}]);
assert.deepEqual(Array.from(n,x=>x.pnl),[5,2]);assert.equal(n[0].time,100000);assert.equal(n[1].basis,'net');
// --- conciliación ---
let c=reconcile({realized:64.3,fees:2,funding:11.2,unrealized:-156.7,total:-83.2},{last:-83.2,basis:'net',source:'local'});
assert.equal(c.status,'ok');assert.ok(Math.abs(c.calc-(-83.2))<1e-9);assert.equal(c.notes.length,0);
// el caso visto en la captura: el neto no suma sus componentes
c=reconcile({realized:64.3,fees:0,funding:11.2,unrealized:-156.7,total:-156.7},null);
assert.equal(c.status,'mismatch');assert.ok(c.notes[0].includes('difiere'));
// gráfico vs KPI: +450 contra -156.70
c=reconcile({realized:64.3,fees:0,funding:11.2,unrealized:-156.7,total:-81.2},{last:450,basis:'net',source:'local'});
assert.equal(c.status,'mismatch');assert.ok(c.notes.some(t=>t.includes('gráfico')));
// otras definiciones del gráfico no se comparan como si fueran el neto
c=reconcile({realized:1,fees:0,funding:0,unrealized:1,total:2},{last:999,source:'hyperliquid'});
assert.equal(c.status,'ok');assert.ok(c.notes[0].includes('Hyperliquid'));
c=reconcile({realized:1,fees:0,funding:0,unrealized:1,total:2},{last:999,basis:'gross',source:'local'});
assert.equal(c.status,'ok');assert.ok(c.notes[0].includes('bruto'));
// datos faltantes: parcial, nunca "ok"
c=reconcile({realized:1,fees:null,funding:null,unrealized:1,total:null},null);
assert.equal(c.status,'partial');assert.equal(c.calc,null);assert.ok(c.notes[0].includes('comisiones'));
// --- cola de atención: error o falta de datos jamás equivale a "todo bien" ---
const pairs=[{id:'A|B',long:'A',short:'B'},{id:'C|D',long:'C',short:'D'},{id:'E|F',long:'E',short:'F'}];
const now=1e12;
let a=buildAttention(pairs,{},{loaded:false,error:'HTTP 503',now});
assert.equal(a.kind,'unavailable');
a=buildAttention([],{},{loaded:true,now});assert.equal(a.kind,'no-pairs');
a=buildAttention(pairs,{},{loaded:true,now,asOf:now});assert.equal(a.kind,'partial');assert.equal(a.unverified.length,3);
const ok={pair_status:'EN_TESIS'};
a=buildAttention(pairs,{'A|B':ok,'C|D':ok,'E|F':ok},{loaded:true,now,asOf:now-1000});assert.equal(a.kind,'ok');assert.equal(a.okCount,3);
// analítica vieja o con error de refresco: parcial aunque todo "esté en tesis"
a=buildAttention(pairs,{'A|B':ok,'C|D':ok,'E|F':ok},{loaded:true,now,asOf:now-400000});assert.equal(a.kind,'partial');assert.equal(a.stale,true);
a=buildAttention(pairs,{'A|B':ok,'C|D':ok,'E|F':ok},{loaded:true,now,asOf:now,error:'timeout'});assert.equal(a.kind,'partial');
// SIN_DATOS no cuenta como alerta ni como tranquilidad
a=buildAttention(pairs,{'A|B':ok,'C|D':{pair_status:'SIN_DATOS'},'E|F':ok},{loaded:true,now,asOf:now});
assert.equal(a.kind,'partial');assert.deepEqual(Array.from(a.nodata),['C/D']);assert.equal(a.items.length,0);
// orden por severidad y estados desconocidos visibles
a=buildAttention(pairs,{'A|B':{pair_status:'REVISAR_TP'},'C|D':{pair_status:'LIQUIDACION',pair_status_reason:'x'},'E|F':{pair_status:'ESTADO_NUEVO'}},{loaded:true,now,asOf:now});
assert.equal(a.kind,'alerts');assert.deepEqual(Array.from(a.items,i=>i.name),['C/D','E/F','A/B']);
assert.equal(statusMeta('ESTADO_NUEVO').sev,'warn');assert.equal(statusMeta(undefined),null);
// --- elección de fuente: Hyperliquid continuo; el local es alternativa o respaldo ---
const hlRows=[{time:1,pnl:0},{time:2,pnl:5}];const localRows=[{time:1e12-1000,pnl:3,basis:'net'},{time:1e12-500,pnl:4,basis:'net'}];
let pk=pickPnlSeries({'1d':hlRows},localRows,'1d','hl',1e12);
assert.equal(pk.source,'hyperliquid');assert.equal(pk.fallback,false);assert.equal(pk.rows.length,2);
pk=pickPnlSeries({'1d':hlRows},localRows,'1d','local',1e12);
assert.equal(pk.source,'local');assert.equal(pk.fallback,false);
pk=pickPnlSeries({},localRows,'1d','hl',1e12);
assert.equal(pk.source,'local');assert.equal(pk.fallback,true);
pk=pickPnlSeries({'7d':[{time:1,pnl:0}]},localRows,'7d','hl',1e12);
assert.equal(pk.fallback,true);
assert.equal(pickPnlSeries(undefined,[{time:1,pnl:1}],'all','local',1e12).rows.length,1);
assert.equal(pickPnlSeries(undefined,[{time:1,pnl:1},{time:1e12-10,pnl:2}],'1d','local',1e12).rows.length,1);
console.log('OK: serie PNL (huecos, bases, estadísticas), conciliación y cola de atención');
