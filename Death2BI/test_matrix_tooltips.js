const assert=require('node:assert/strict'),I=require('./chart-interactions'),E=require('./report-engine');
const col=(table,column)=>({field:{Column:{Expression:{SourceRef:{Entity:table}},Property:column}}});
const hierarchy={HierarchyLevel:{Expression:{Hierarchy:{Expression:{SourceRef:{Entity:'Dates'}},Hierarchy:'Calendar'}},Level:'Year'}};
const matrix={definition:{query:{queryState:{Rows:{projections:[col('KPI_Config','Category'),{...col('KPI_Config','KPI_Name'),active:false}]},Columns:{projections:[{field:hierarchy},col('Sites','Site')]},Values:{projections:[{field:{Measure:{Property:'Latest Value'}}}]}}}}};
const parent=I.matrixTooltipIdentity(matrix,['Financial']),child=I.matrixTooltipIdentity(matrix,['Financial',"O'Brien"],[2026,'West']);
assert.equal(parent.fields.length,1);assert.equal(child.fields.length,4);assert.deepEqual(child.fields[2].field,hierarchy);
const filter=E.tooltipPointFilters(matrix,{_rowIdentity:child})[0].filter.Where[0].Condition.In;
assert.deepEqual(filter.Expressions,[matrix.definition.query.queryState.Rows.projections[0].field,matrix.definition.query.queryState.Rows.projections[1].field,hierarchy,matrix.definition.query.queryState.Columns.projections[1].field]);
assert.deepEqual(filter.Values[0].map(v=>v.Literal.Value),["'Financial'","'O''Brien'",'2026',"'West'"]);
assert.equal(I.matrixTooltipIdentity(matrix,['Financial'],[2026]).fields.length,2); // Column subtotal retains ancestors only.
assert.deepEqual(E.tooltipPointFilters(matrix,{_rowIdentity:I.matrixTooltipIdentity(matrix)}),[]); // Grand total retains the current report context.
assert.equal(I.matrixTooltipIdentity(matrix,['Financial',Infinity]),null);
const measuresOnly={definition:{query:{queryState:{Rows:{projections:[{field:{Measure:{Property:'Value'}}}]}}}}};assert.equal(I.matrixTooltipIdentity(measuresOnly,[42]),null);
const cells=[{},{}],scroll={},focus={},row={cells,tabIndex:-1,addEventListener:(name,fn)=>focus[name]=fn,removeAttribute:name=>assert.equal(name,'title'),contains:x=>x===cells[0],getBoundingClientRect:()=>({left:10,top:20,width:100,height:40})};
const table={querySelectorAll:()=>[row]},el={querySelector:selector=>selector==='table'?table:{addEventListener:(name,fn)=>scroll[name]=fn}},seen=[];
I.bindRowTooltips(el,[[parent,child]],{onHover:(datum,event)=>seen.push({datum,event}),onLeave:()=>seen.push('leave')});
const target=cell=>({closest:selector=>selector==='td,th'?cell:null});
row.onmousemove({target:target(cells[1]),clientX:35,clientY:45});assert.equal(seen[0].datum._rowIdentity,child);assert.equal(seen[0].event.clientX,35);assert.equal(row.tabIndex,0);
focus.focusin({target:row});assert.equal(seen[1].datum._rowIdentity,parent);assert.deepEqual(seen[1].event,{clientX:60,clientY:40});
row.onmousemove({target:{closest:selector=>selector==='td,th'?cells[0]:{}}});assert.equal(seen.at(-1),'leave'); // Expansion buttons do not start a tooltip.
row.onmouseleave();scroll.scroll();assert.equal(seen.at(-1),'leave');
focus.focusout({relatedTarget:cells[0]});const before=seen.length;focus.focusout({relatedTarget:null});assert.equal(seen.length,before+1);
I.bindRowTooltips({querySelector:()=>({querySelectorAll:()=>assert.fail('Disabled tooltip bound events')})},[parent],{});
const tableIdentity=I.rowIdentity({definition:{query:{queryState:{Values:{projections:[col('KPI_Config','KPI_Name'),{field:{Measure:{Property:'Value'}}}]}}}}},['Revenue',10]);
I.bindRowTooltips(el,[tableIdentity],{onHover:d=>assert.equal(d._rowIdentity,tableIdentity)});row.onmousemove({target:target(cells[0]),clientX:10,clientY:20});
const hierarchyTable={definition:{query:{queryState:{Values:{projections:[{field:hierarchy},{field:{Measure:{Property:'Value'}}}]},Formatting:{projections:[col('KPI_Config','Color')]}}}}};
const hierarchyIdentity=I.compoundIdentity(hierarchyTable,[2026,10,'#123456']);assert.equal(hierarchyIdentity.fields.length,1);assert.deepEqual(E.tooltipPointFilters(hierarchyTable,{_rowIdentity:hierarchyIdentity})[0].filter.Where[0].Condition.In.Expressions,[hierarchy]);
assert.deepEqual(E.tooltipPointFilters(measuresOnly,{_rowIdentity:I.compoundIdentity(measuresOnly,[10])||{fields:[],datum:{}}}),[]);
console.log('PASS matrix row/column/hierarchy/total tooltip filters, cell-specific hover, keyboard focus, leave/scroll cleanup, disabled tooltips and ordinary table rows');
