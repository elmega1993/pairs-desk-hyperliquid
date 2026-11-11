const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const ts=require(require.resolve('typescript',{paths:[path.join(__dirname,'../react_frontend')]}));
const root=path.join(__dirname,'../react_frontend/src');
function transpile(file,extra='',require=()=>({})){const loaded={exports:{}};vm.runInNewContext(ts.transpileModule(fs.readFileSync(path.join(root,file),'utf8')+'\n'+extra,{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.React}}).outputText,{module:loaded,exports:loaded.exports,require,Number,Math,Date,Set});return loaded.exports}
const model=transpile('twapModel.ts');
const chart=transpile('RatioChart.tsx','module.exports.testRegister=register;module.exports.testLevels=renderLevels;module.exports.percentagePair=percentagePair;',name=>name==='./twapModel'?model:name==='./overlayLifecycle'?{clearTrackedOverlays:()=>{},rememberOverlay:()=>{}}:{});
const definitions={};chart.testRegister({registerOverlay:d=>definitions[d.name]=d});
const twap=definitions.react_twap;assert.ok(twap);const create=coordinates=>twap.createPointFigures({coordinates:coordinates.map(x=>({x,y:9999})),bounding:{width:800,height:400},overlay:{extendData:{label:'TWAP BTC 50%',color:'#abc'}}});
const tiny=create([40,40.3,40.6]);assert.ok(tiny.some(f=>f.type==='circle'),'sub-candle daily span collapses to one marker');assert.equal(tiny.filter(f=>f.type==='text').length,1);assert.ok(tiny.every(f=>!f.attrs.y||f.attrs.y<400),'timeline ignores price coordinate');
const wide=create([40,100,200]);assert.ok(wide.some(f=>f.type==='line'&&f.styles.style==='dashed'));assert.ok(wide.some(f=>f.type==='line'&&f.styles.style==='solid'));assert.equal(create([-50,-40,-10]).length,0);
const created=[];const instance={createOverlay:o=>{created.push(o);return String(created.length)},removeOverlay:()=>{}};
const job={id:'native',operation:'Aumentar',created_ms:1000,planned_end_ms:31000,updated_ms:16000,status:'running',legs:[{coin:'BTC',size:10,executed_size:5}]};
const bars=[{timestamp:1000,open:1,high:2,low:.5,close:1},{timestamp:61000,open:1,high:2,low:.5,close:1}];
const levels={average:false,initial:false,targets:false,events:true};
chart.testLevels(instance,{twaps:[job],events:[{time:1000,kind:'add'},{time:1000,kind:'reduce',twap_group_id:'native'}]},bars,levels,null,new Set(),true);
assert.equal(created.filter(o=>o.name==='react_event').length,1,'keep unmatched ordinary event at same time');assert.equal(created.filter(o=>o.name==='react_twap').length,1);assert.equal(created.find(o=>o.name==='react_twap').points[2].dataIndex,.5,'actual sub-candle endpoint');
created.length=0;chart.testLevels(instance,{twaps:[job],events:[{time:1000,kind:'add'}],chart_events:[]},bars,levels,null,new Set(),true);assert.equal(created.filter(o=>o.name==='react_event').length,0,'empty verified chart_events must stay empty');
created.length=0;chart.testLevels(instance,{twaps:[job],events:[]},bars,{...levels,events:false},null,new Set(),true);assert.equal(created.length,0,'operations layer controls spans as well as generic markers');
console.log('OK: native timeline geometry, collapse, exact event suppression, operations layer');

created.length=0;chart.testLevels(instance,{twaps:[{...job,status:'rejected',legs:[{coin:'BTC',status:'rejected',error:'exchange_rejected',twap_id:null,executed_size:null}]}],events:[]},bars,levels,null,new Set(),true);assert.equal(created.length,0,'definitively rejected unsent TWAP must not appear as an executed operation');

const averagePair=chart.percentagePair({entry_ratio:1.92,entry_history:{available:true,initial_ratio:2,steps:[{time:1000,ratio:2},{time:2000,ratio:1.92}]}},1.92);assert.equal(averagePair.entry_ratio,0);assert.equal(averagePair.entry_history.steps.at(-1).ratio,0);assert.ok(averagePair.entry_history.steps[0].ratio>0,'old average must be shown relative to updated live average');
