const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const ts=require(require.resolve('typescript',{paths:[path.join(__dirname,'../react_frontend')]}));
const code=fs.readFileSync(path.join(__dirname,'../react_frontend/src/indicatorConfig.ts'),'utf8');
const compiled=ts.transpileModule(code,{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}}).outputText;
const moduleObject={exports:{}};
vm.runInNewContext(compiled,{module:moduleObject,exports:moduleObject.exports});
const {indicatorIsStacked,indicatorPaneId,indicatorPaneConfig}=moduleObject.exports;

assert.equal(indicatorIsStacked('MA'),false);
assert.equal(indicatorIsStacked('RSI'),true);
assert.equal(indicatorIsStacked('MACD'),true);
assert.equal(indicatorPaneId('MA'),'candle_pane');
assert.equal(indicatorPaneId('RSI'),'indicator_rsi');
assert.equal(indicatorPaneId('MACD'),'indicator_macd');
assert.equal(indicatorPaneConfig('MACD').id,'indicator_macd');
console.log('OK: indicator panes have stable lifecycle IDs');
