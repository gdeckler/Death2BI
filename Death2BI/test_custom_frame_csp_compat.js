const assert=require('node:assert/strict'),vm=require('node:vm'),Frame=require('./custom-frame');
const factory='function(t){var e;try{(e=new Function("d","return "+t+";"))(1)}catch(t){console.log(t),e=new Function("d","return d;")}return e}';
function format(expression,value,pkg={guid:'wishyoulizationwalkers',version:'1.0.2'}){
 const context=vm.createContext({}, {codeGeneration:{strings:false,wasm:false}});
 const js='globalThis.result=('+factory+')('+JSON.stringify(expression)+')('+JSON.stringify(value)+');';
 new vm.Script(Frame.compatibleScript({...pkg,js})).runInContext(context);
 return context.result;
}
assert.equal(format("Math.round(d) + '%'",42.9),'43%');
assert.equal(format('d',42.9),42.9);
assert.equal(format("'$' + d.toFixed(2) + 'M'",1.246),'$1.25M');
assert.equal(format('Math.floor(d)',42.9),42);
assert.equal(format('Math.ceil(d)',42.1),43);
assert.equal(format('Math.trunc(d)',-42.9),-42);
assert.equal(format('Math.abs(d)',-42.9),42.9);
assert.equal(format('d.toFixed(99)',42.9),42.9,'unsupported formats retain the legacy identity fallback');
assert.equal(format('globalThis.stolen=true;d',42.9),42.9,'a setting cannot execute JavaScript');
assert.equal(format("d + '\\x25'",42.9),42.9,'escape sequences cannot widen the bounded literal grammar');
assert.equal(format('Math.random()',42.9),42.9);
assert.throws(()=>format('d',42.9,{guid:'UnrelatedVisual',version:'1.0.2'}),/Code generation from strings disallowed/,'unrelated visual scripts must not be rewritten');
assert.throws(()=>format('d',42.9,{guid:'wishyoulizationwalkers',version:'9.0.0'}),/Code generation from strings disallowed/,'unknown versions keep their code untouched');
for(const probe of ['Function("return this")()',"new Function('return this')()",'new Function("return this")()']){
 const context=vm.createContext({}, {codeGeneration:{strings:false,wasm:false}});
 new vm.Script(Frame.compatibleScript({guid:'LegacyGlobalProbe',js:'globalThis.matches=('+probe+')===globalThis;'})).runInContext(context);
 assert.equal(context.matches,true,'the complete optional-new global probe must be replaced');
}
const document=Frame.documentFor({guid:'wishyoulizationwalkers',version:'1.0.2',js:'globalThis.formatter='+factory+';'},'walkersNonce');
const csp=document.match(/Content-Security-Policy" content="([^"]+)/)[1];
assert(!csp.includes('unsafe-eval'));
assert(csp.includes("script-src 'nonce-walkersNonce'"));
assert(csp.includes("connect-src 'none'"));
assert(csp.includes("frame-src 'none'"));
console.log('PASS: legacy numeric formatters and global-object probes run with string code generation disabled; unknown code stays untouched and sandbox CSP remains strict');
