const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const ts=require(require.resolve('typescript',{paths:[path.join(__dirname,'../react_frontend')]}));
const code=fs.readFileSync(path.join(__dirname,'../react_frontend/src/ticks.ts'),'utf8');
const compiled=ts.transpileModule(code,{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}}).outputText;
const m={exports:{}};vm.runInNewContext(compiled,{module:m,exports:m.exports});
const {niceTicks,axisMoney}=m.exports;
// Rango típico con PNL positivo y cero incluido: marcas redondas y el 0 presente.
let r=niceTicks(-44.04,640,5);
assert.deepEqual(Array.from(r.ticks),[0,200,400,600]);assert.equal(r.step,200);
assert.ok(Array.from(r.ticks).every(t=>t>=-44.04&&t<=640));
// Rango negativo y positivo, pasos 1/2/2.5/5.
r=niceTicks(-1200,300,5);assert.ok(r.ticks.includes(0));assert.ok([250,500,100,200].includes(r.step));
r=niceTicks(-0.9,2.1,5);assert.ok(r.ticks.includes(0));assert.ok(r.step<=1);
// Nunca devuelve -0 ni valores con ruido de coma flotante.
assert.ok(Array.from(niceTicks(-0.3,0.6,5).ticks).every(t=>Object.is(t,-0)===false&&String(t).length<8));
// Rangos inválidos o degenerados no rompen.
assert.deepEqual(Array.from(niceTicks(5,5).ticks),[]);assert.deepEqual(Array.from(niceTicks(NaN,3).ticks),[]);
// Formato: sin decimales cuando el paso es entero; con decimales si hace falta.
assert.equal(axisMoney(1200,200),'$1,200');assert.equal(axisMoney(-400,200),'-$400');assert.equal(axisMoney(0.5,0.5),'$0.5');assert.equal(axisMoney(0.25,0.05),'$0.25');
console.log('OK: marcas redondas del eje PNL');
