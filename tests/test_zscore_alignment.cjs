const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const ts=require(require.resolve('typescript',{paths:[path.join(__dirname,'../react_frontend')]}));
const loaded={exports:{}};
const source=fs.readFileSync(path.join(__dirname,'../react_frontend/src/RatioChart.tsx'),'utf8')+'\nmodule.exports.registerZScore=registerZScore;';
vm.runInNewContext(ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.React}}).outputText,{module:loaded,exports:loaded.exports,require:()=>({}),Math,Number,Set});
let indicator;loaded.exports.registerZScore({registerIndicator:value=>indicator=value});
const bars=Array.from({length:120},(_,i)=>({close:100+i}));
const result=indicator.calc(bars,{calcParams:[60]});
assert.equal(result.length,bars.length,'warmup must preserve every candle index on the shared chart axis');
assert.ok(result.slice(0,59).every(point=>point.z===undefined));
for(const i of [59,60,119]){const window=bars.slice(i-59,i+1).map(row=>row.close);const mean=window.reduce((a,b)=>a+b,0)/60;const std=Math.sqrt(window.reduce((sum,x)=>sum+(x-mean)**2,0)/60);assert.ok(Math.abs(result[i].z-(bars[i].close-mean)/std)<1e-12);}
assert.equal(indicator.figures[0].key,'z');
console.log('OK: native Z-score preserves candle domain and rolling values');
