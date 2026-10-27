const assert=require('node:assert/strict'),I=require('./chart-interactions'),T=require('./table-rendering'),S=require('./report-style');

// Small DOM fixture exercises real formatting/sorting rather than duplicating
// the cleanup implementation. SVG icon titles are parsed from actual markup.
class Element{
 constructor(tag){this.tagName=tag.toLowerCase();this.children=[];this.parentElement=null;this.attributes={};this.style={};this.dataset={};this.events={};this.tabIndex=-1;this._text=''}
 get title(){return this.attributes.title||''}set title(value){this.attributes.title=String(value)}
 get cells(){return this.children.filter(n=>['td','th'].includes(n.tagName))}
 get tHead(){return this.children.find(n=>n.tagName==='thead')}
 get firstChild(){return this.children[0]||null}
 get textContent(){return this._text+this.children.map(n=>n.textContent).join('')}
 set textContent(value){this._text=String(value??'');this.replaceChildren()}
 set innerHTML(value){this.replaceChildren();this._text='';if(!String(value).startsWith('<svg'))return;const svg=new Element('svg');svg.className=/class="([^"]*)"/.exec(value)?.[1]||'';svg.setAttribute('role','img');svg.setAttribute('aria-label',/aria-label="([^"]*)"/.exec(value)?.[1]||'');const title=new Element('title');title.textContent=/<title>(.*?)<\/title>/.exec(value)?.[1]||'';svg.appendChild(title);this.appendChild(svg)}
 setAttribute(name,value){this.attributes[name]=String(value)}getAttribute(name){return this.attributes[name]??null}removeAttribute(name){delete this.attributes[name]}
 appendChild(child){child.remove();this.children.push(child);child.parentElement=this;return child}
 prepend(child){child.remove();this.children.unshift(child);child.parentElement=this}
 replaceChildren(...nodes){for(const child of this.children)child.parentElement=null;this.children=[];nodes.forEach(n=>this.appendChild(n))}
 remove(){if(this.parentElement){const p=this.parentElement;p.children=p.children.filter(n=>n!==this);this.parentElement=null}}
 addEventListener(name,fn){(this.events[name]||=[]).push(fn)}
 removeEventListener(name,fn){this.events[name]=(this.events[name]||[]).filter(existing=>existing!==fn)}
 contains(node){return node===this||this.children.some(c=>c.contains(node))}
 getBoundingClientRect(){return {left:0,top:0,width:100,height:20}}
 matches(selector){const match=/^([\w-]+)?(?:\.([\w-]+))?(?:\[([\w-]+)="([^"]*)"\])?$/.exec(selector);return !!match&&(!match[1]||this.tagName===match[1])&&(!match[2]||String(this.className||'').split(/\s+/).includes(match[2]))&&(!match[3]||this.getAttribute(match[3])===match[4])}
 querySelectorAll(selector){const found=[];for(const branch of selector.split(',')){const direct=branch.startsWith(':scope > '),parts=branch.replace(/^:scope > /,'').trim().split(/\s+/);const visit=node=>{for(const child of node.children){if(child.matches(parts.at(-1))){let cursor=child.parentElement,index=parts.length-2;while(index>=0&&cursor&&cursor!==this){if(cursor.matches(parts[index]))index--;cursor=cursor.parentElement}if(index<0&&(!direct||child.parentElement===this))found.push(child)}visit(child)}};visit(this)}return [...new Set(found)]}
 querySelector(selector){return this.querySelectorAll(selector)[0]||null}
 closest(selector){return selector.split(',').some(s=>this.matches(s.trim()))?this:this.parentElement?.closest(selector)||null}
}
const make=tag=>new Element(tag),projection=(name)=>({field:{Column:{Expression:{SourceRef:{Entity:'Facts'}},Property:name}},queryRef:'Facts.'+name});
const visual={type:'tableEx',_footerRow:[3,30],definition:{query:{queryState:{Values:{projections:[projection('Status'),projection('Amount')]}}},objects:{columnFormatting:[{selector:{metadata:'Facts.Status'},properties:{icon:{value:'CircleHigh',layout:'IconOnly'}}},{selector:{metadata:'Facts.Amount'},properties:{dataBars:{}}}]}}};
const model={theme:{background:'#ffffff',foreground:'#222222'}},labels=['Status','Amount'],rows=[[1,10],[2,20]],identities=rows.map(row=>I.rowIdentity(visual,row));
function fixture(){const el=make('div'),wrap=make('div'),table=make('table'),head=make('thead'),headerRow=make('tr'),body=make('tbody'),foot=make('tfoot'),footerRow=make('tr');wrap.className='tablewrap';el.appendChild(wrap);wrap.appendChild(table);table.appendChild(head);head.appendChild(headerRow);for(const label of labels){const th=make('th');th.textContent=label;headerRow.appendChild(th)}table.appendChild(body);for(const row of rows){const tr=make('tr');tr.title='Source row hint';tr.setAttribute('aria-label','Accessible row');body.appendChild(tr);for(const value of row){const td=make('td');td.textContent=value;td.title='Source cell hint';tr.appendChild(td)}}table.appendChild(foot);foot.appendChild(footerRow);footerRow.title='Total row hint';for(const value of visual._footerRow){const td=make('td');td.textContent=value;td.title='Total cell hint';footerRow.appendChild(td)}return {el,table,head,body,foot,headers:headerRow.cells}}
const previousDocument=global.document;global.document={createElement:make};
function styled(){const f=fixture();S.styleTable(f.el,structuredClone(model),visual,labels,rows);return f}
function assertSuppressed(f){for(const row of f.table.querySelectorAll('tbody tr,tfoot tr')){assert.equal(row.getAttribute('title'),null);for(const cell of row.cells)assert.equal(cell.getAttribute('title'),null);assert.equal(row.querySelectorAll('svg title').length,0)}for(const th of f.headers)assert.match(th.title,/Sort loaded rows/);for(const svg of f.table.querySelectorAll('tbody svg,tfoot svg'))assert.equal(svg.getAttribute('aria-label'),'Green circle');for(const row of f.body.children)assert.equal(row.getAttribute('aria-label'),'Accessible row');for(const cell of f.table.querySelectorAll('tbody td,tfoot td').filter(c=>c.querySelector('.pbi-data-bar')))assert.ok(cell.getAttribute('aria-label'))}
try{
 const standard=styled();I.bindRowTooltips(standard.el,identities,{});I.attachRows(standard.el,identities,{onSelect(){}});assert.ok(standard.body.children[0].title);assert.ok(standard.body.children[0].cells[1].title);assert.equal(standard.table.querySelectorAll('svg title').length,3);standard.headers[1].onclick();assert.equal(standard.table.querySelectorAll('svg title').length,3,'ordinary tooltips retain SVG labels through sorts');

 for(const mode of [{onHover(){}},{tooltip:false},{onHover(){assert.fail('Disabled tooltips must not bind hover')},tooltip:false}]){
  const f=styled();I.bindRowTooltips(f.el,identities,mode);assertSuppressed(f);
  I.attachRows(f.el,identities,{onSelect(){}});assertSuppressed(f); // Binding order cannot restore selection help as a native tooltip.
  assert.equal(f.table.getAttribute('aria-multiselectable'),'true');assert.equal(f.body.children[0].getAttribute('aria-selected'),'false');
  f.headers[1].onclick();assertSuppressed(f);f.headers[1].onclick();assertSuppressed(f); // Icons and data bars are really repainted.
  S.styleTable(f.el,structuredClone(model),visual,labels,rows);assertSuppressed(f);
  if(mode.tooltip===false)assert.equal(f.body.children[0].onmousemove,undefined);
 }

 // A matrix expansion replaces its table. Binding the same mode suppresses
 // newly created row headers, totals and SVG icons even without identities.
 for(const options of [{onHover(){}},{tooltip:false}]){
  const f=fixture();f.body.children[0].cells[0].tagName='th';I.bindRowTooltips(f.el,[null],options);S.styleTable(f.el,structuredClone(model),visual,labels,rows);assertSuppressed(f);
  const expanded=styled();I.bindRowTooltips(expanded.el,[null,null],options);assertSuppressed(expanded);
 }
 const toggled=styled();I.bindRowTooltips(toggled.el,identities,{tooltip:false});I.bindRowTooltips(toggled.el,identities,{});toggled.headers[1].onclick();assert.ok(toggled.body.children[0].cells[1].title,'returning to standard mode permits its native tooltip on repaint');
 const rebound=styled();I.bindRowTooltips(rebound.el,identities,{onHover(){assert.fail('stale hover')},onLeave(){assert.fail('stale leave')}});assert.equal(rebound.body.children[0].events.focusin.length,1);I.bindRowTooltips(rebound.el,identities,{tooltip:false});assert.equal(rebound.body.children[0].onmousemove,null);assert.equal(rebound.body.children[0].onmouseleave,null);assert.equal(rebound.body.children[0].events.focusin.length,0);assert.equal(rebound.body.children[0].events.focusout.length,0);assert.equal(rebound.el.querySelector('.tablewrap').events.scroll.length,0);assertSuppressed(rebound);
 console.log('PASS table/matrix native tooltip suppression for external/disabled modes, SVG icons, data bars, footer totals, cached sorts/repaints, expansion/re-render, selection order and preserved accessibility/header help');
}finally{global.document=previousDocument}
