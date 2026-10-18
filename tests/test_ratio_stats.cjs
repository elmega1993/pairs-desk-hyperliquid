const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const ts=require(require.resolve('typescript',{paths:[path.join(__dirname,'../react_frontend')]}));
const code=fs.readFileSync(path.join(__dirname,'../react_frontend/src/ratioStats.ts'),'utf8');
const compiled=ts.transpileModule(code,{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}}).outputText;
const moduleObject={exports:{}};
vm.runInNewContext(compiled,{module:moduleObject,exports:moduleObject.exports});
const {buildRatioStats}=moduleObject.exports;

const bars=Array.from({length:20},(_,i)=>({timestamp:i,close:i+1}));
const stats=buildRatioStats(bars,10,4);
assert.equal(stats.current,20);
assert.equal(stats.sampleSize,10);
assert.equal(stats.percentile,100);
assert.equal(stats.percentiles.p10,11.9);
assert.equal(stats.percentiles.p25,13.25);
assert.equal(stats.percentiles.p50,15.5);
assert.equal(stats.percentiles.p75,17.75);
assert.equal(stats.percentiles.p90,19.1);
assert.equal(stats.zScore,1.5667);
assert.equal(stats.forward?.sampleSize,6);
assert.equal(stats.forward?.up,100);

const invalid=buildRatioStats([{timestamp:1,close:0},{timestamp:2,close:NaN}],90,14);
assert.equal(invalid,null);

const longBars=Array.from({length:220},(_,i)=>({timestamp:i,close:i+1}));
const longStats=buildRatioStats(longBars,undefined,14);
assert.equal(longStats.sampleSize,180);
assert.equal(longStats.forward.sampleSize,166);
console.log('OK: ratio stats percentiles, z-score and forward outcomes');
