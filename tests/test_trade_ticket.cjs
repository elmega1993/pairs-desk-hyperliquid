const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const ts=require(require.resolve('typescript',{paths:[path.join(__dirname,'../react_frontend')]}));

const source=fs.readFileSync(path.join(__dirname,'../react_frontend/src/tradeTicket.ts'),'utf8');
const out=ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}}).outputText;
const loaded={exports:{}};
vm.runInNewContext(out,{module:loaded,exports:loaded.exports,Math,Number});
const {remainingTicketSeconds,isTicketExpired}=loaded.exports;

assert.equal(remainingTicketSeconds(30,1000,1000),30);
assert.equal(remainingTicketSeconds(30,1000,11000),20);
assert.equal(remainingTicketSeconds(30,1000,31000),0);
assert.equal(isTicketExpired(30,1000,30999),false);
assert.equal(isTicketExpired(30,1000,31000),true);
console.log('OK: vencimiento determinista de tickets');
