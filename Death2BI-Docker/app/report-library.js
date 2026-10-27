(function(root){
class ReportLibrary {
 constructor(storage){this.models=new Map();this.storage=storage;this.active=null;this.views=new Map()}
 remember(id){this.active=id;try{this.storage?.setItem('modelbridge.activeReport',id)}catch{}}
 add(model){if(!model.id)throw Error('A saved report needs an import ID.');this.models.set(model.id,model);return model}
 list(){return [...this.models.values()].sort((a,b)=>(b.createdAt||'').localeCompare(a.createdAt||''))}
 load(models){this.models=new Map(models.map(m=>[m.id,m]));let preferred=this.active;try{preferred=preferred||this.storage?.getItem('modelbridge.activeReport')}catch{};const selected=this.models.get(preferred)||this.list()[0];if(selected)this.remember(selected.id);return selected}
 select(id){const selected=this.models.get(id);if(!selected)throw Error('Saved report no longer exists.');this.remember(id);return selected}
 remove(id){this.models.delete(id);this.views.delete(id);if(this.active===id)this.remember(this.list()[0]?.id||'demo');return this.models.get(this.active)}
}
if(typeof module!=='undefined')module.exports=ReportLibrary;root.ReportLibrary=ReportLibrary;
})(globalThis);
