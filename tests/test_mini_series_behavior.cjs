const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const ts=require(require.resolve('typescript',{paths:[path.join(__dirname,'../react_frontend')]}));
const vm=require('node:vm');
const code=fs.readFileSync(path.join(__dirname,'../react_frontend/src/miniSeries.ts'),'utf8');
const compiled=ts.transpileModule(code,{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}}).outputText;
const moduleObject={exports:{}};
vm.runInNewContext(compiled,{module:moduleObject,exports:moduleObject.exports,Math,Number,Map});
const {buildMiniSeries,windowSeries,spanLabel,nearestRow,gapThreshold,DAY_MS}=moduleObject.exports;
const NOW=1_800_000_000_000,MIN=60_000;
// 8 días de lecturas por minuto: pico absurdo al inicio y luego ~350 con ruido
const history=[];for(let i=8*24*60;i>=0;i--){history.push({time:NOW-i*MIN,pnl:i>8*24*60-3?900:350+Math.sin(i/37)*12})}
const windowed=windowSeries(history,NOW);
assert.ok(windowed.every(p=>p.time>=NOW-DAY_MS),'solo últimas 24 h');
assert.ok(windowed.length<=98,'agrupado en tramos de 15 min, no un punto por minuto');
assert.equal(windowed.at(-1).time,NOW,'el último punto conserva el valor actual');
const series=buildMiniSeries(history,NOW);
assert.ok(series.max<400,'el pico viejo no distorsiona la escala');
assert.equal(series.last,history.at(-1).pnl);
assert.equal(spanLabel(series.spanMs),'24 h');
// menos de 24 h de datos: se dice cuánto cubre en vez de aparentar 24 h
const short=buildMiniSeries(history.filter(p=>p.time>NOW-6*60*MIN),NOW);
assert.equal(spanLabel(short.spanMs),'6 h');
// sin datos suficientes: null (la card muestra aviso), nunca otra métrica
assert.equal(buildMiniSeries([{time:NOW,pnl:1}],NOW),null);
assert.equal(buildMiniSeries([],NOW),null);
assert.equal(buildMiniSeries([{time:NOW-3*DAY_MS,pnl:1},{time:NOW-2*DAY_MS,pnl:2}],NOW),null);
// un hueco largo corta la línea
const gap=buildMiniSeries([{time:NOW-5*60*MIN,pnl:10},{time:NOW-4.9*60*MIN,pnl:11},{time:NOW-20*MIN,pnl:12},{time:NOW,pnl:13}],NOW);
assert.equal(gap.segments.length,2);
// línea de cero solo si el rango cruza cero; delta = último - primero
const cross=buildMiniSeries([{time:NOW-2*60*MIN,pnl:-5},{time:NOW,pnl:7}],NOW);
assert.ok(cross.zeroY!==null&&cross.delta===12);
assert.equal(buildMiniSeries([{time:NOW-2*60*MIN,pnl:5},{time:NOW,pnl:7}],NOW).zeroY,null);
// serie plana: no se magnifica el ruido (rango mínimo)
const flat=buildMiniSeries([{time:NOW-20*MIN,pnl:362.1},{time:NOW,pnl:362.2}],NOW);
const ys=flat.segments[0].map(p=>p.y);assert.ok(Math.abs(ys[0]-ys[1])<2);
// Serie gruesa tipo Hyperliquid (1 punto por hora): debe dibujar UNA línea continua, no puntos sueltos
const hourly=[];for(let i=24;i>=0;i--)hourly.push({time:NOW-i*60*MIN,pnl:(24-i)*5-50});
const coarse=buildMiniSeries(hourly,NOW);
assert.equal(coarse.segments.length,1);assert.equal(coarse.segments[0].length,hourly.length);
assert.ok(gapThreshold(hourly.map(p=>p.time))>=4*60*MIN);
// y un corte real de varias horas sigue cortando incluso en una serie horaria
const cut=hourly.filter(p=>p.time<NOW-12*60*MIN||p.time>NOW-5*60*MIN);
assert.equal(buildMiniSeries(cut,NOW).segments.length,2);
// cursor: devuelve la lectura más cercana, con su fecha y su PNL
const hov=buildMiniSeries(hourly,NOW);
assert.equal(nearestRow(hov,0).time,hourly[0].time);
assert.equal(nearestRow(hov,1).time,NOW);
assert.equal(nearestRow(hov,0.5).pnl,hourly[12].pnl);
assert.equal(nearestRow(hov,-3).time,hourly[0].time);
console.log('OK: ventana 24 h, agrupado 15 min, escala sin pico viejo, huecos, cero, serie corta');
