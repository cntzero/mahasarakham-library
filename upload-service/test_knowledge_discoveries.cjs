const fs=require('fs'),vm=require('vm'),assert=require('assert');
class Element{
 constructor(){this.children=[];this.style={setProperty(){}};this.scrollLeft=0;this.clientWidth=400;this.scrollWidth=1200;this.attributes={};}
 append(...nodes){this.children.push(...nodes);}replaceChildren(){this.children=[];}setAttribute(k,v){this.attributes[k]=v;}addEventListener(){}scrollBy(options){this.scrollLeft+=options.left;}
}
const nodes={};const context={document:{getElementById:id=>nodes[id]??=(new Element()),createElement:()=>new Element()},window:{addEventListener(){}},requestAnimationFrame:fn=>fn(),setInterval(){},matchMedia:()=>({matches:true})};vm.createContext(context);
vm.runInContext(fs.readFileSync('dist/knowledge-discoveries.js','utf8'),context);
const rows=Array.from({length:20},(_,i)=>({id:'site-'+i,title:'Site '+i,url:'/kiwix/site-'+i,collection:'Wikipedia',cover:'/icon.png'}));
context.window.MAHA_KNOWLEDGE_DISCOVER(rows);const shelf=nodes['knowledge-discovery-shelf'];const titles=()=>shelf.children.map(n=>n.title).join(',');const first=titles();assert.equal(shelf.children.length,8);assert(shelf.children.every(n=>n.href.startsWith('archive-reader.html?url=')));
context.window.MAHA_KNOWLEDGE_DISCOVER(rows);assert.equal(titles(),first);shelf.scrollLeft=300;nodes['knowledge-discover-surprise'].onclick();assert.notEqual(titles(),first);assert.equal(shelf.scrollLeft,0);
context.window.MAHA_KNOWLEDGE_DISCOVER([]);assert.equal(nodes['knowledge-discover-surprise'].disabled,true);assert.equal(shelf.children.length,1);
console.log('Knowledge discoveries: stable daily choices, local reader links, reshuffle, scroll reset and empty state: passed');
