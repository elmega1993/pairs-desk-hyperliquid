const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const roots=[path.join(__dirname,'../react_frontend')],ts=require(require.resolve('typescript',{paths:roots}));
const React=require(require.resolve('react',{paths:roots})),{renderToStaticMarkup}=require(require.resolve('react-dom/server',{paths:roots}));
const mod={exports:{}};
const code=ts.transpileModule(fs.readFileSync(path.join(roots[0],'src/components/DeskPanels.tsx'),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX}}).outputText;
vm.runInNewContext(code,{module:mod,exports:mod.exports,require:name=>name==='../advisorApi'?{deskApi:{}}:require(require.resolve(name,{paths:roots}))});
const html=renderToStaticMarkup(React.createElement(mod.exports.MemoryEvidence,{memories:[{id:'m1',content:'Respuestas breves',source:'user',source_id:'chat1',retrieval_explanation:{lexical:1.23456,importance:.7}}]}));
assert.match(html,/Respuestas breves/);assert.match(html,/Coincidencia textual/);assert.match(html,/1.235/);assert.match(html,/chat1/);
console.log('OK: memory retrieval explanation object renders with source and relevance scores');
