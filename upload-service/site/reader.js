/* EPUB.js and JSZip are bundled locally. Original book scripts are disabled. */
'use strict';
const element=id=>document.getElementById(id);
let book,rendition,fontSize=110,currentId;
function notice(message){element('status').textContent=message;}
function save(key,value){try{localStorage.setItem(key,value);}catch{/* Reading works without browser storage. */}}
function load(key){try{return localStorage.getItem(key);}catch{return null;}}
function contentsOpen(open){element('contents').hidden=!open;element('contents-toggle').setAttribute('aria-expanded',String(open));}
async function start(){
 try{
  currentId=new URLSearchParams(location.search).get('id');
  let response=await fetch('/api/library/books').catch(()=>null);if(response?.status===401){location.replace('/login.html?return='+encodeURIComponent(location.pathname+location.search));return;}if(!response?.ok)response=await fetch('catalog.json');if(!response.ok)throw Error('The catalog could not be loaded.');
  const catalog=await response.json(),entry=catalog.find(b=>b.id===currentId),source=entry?.sources.find(s=>s.format==='EPUB');
  if(!entry)throw Error('Book not found. It may have been removed or this link is out of date. Return to the library to search again.');
  if(!source)throw Error('This title has no EPUB edition. Return to the library to see its available formats.');
  element('title').textContent=entry.title;element('author').textContent=entry.author;document.title=entry.title+' · MAHA';
  const download=element('download');download.href=source.url;download.setAttribute('download','');download.hidden=false;
  book=ePub(source.url,{openAs:'epub'});
  rendition=book.renderTo('viewer',{width:'100%',height:'100%',spread:'none',flow:'paginated',allowScriptedContent:false,allowPopups:false});
  // Block outbound hyperlinks inside book pages; the original download remains unmodified.
  rendition.hooks.content.register(contents=>{
   contents.document.querySelectorAll('script').forEach(s=>s.remove());
   contents.document.addEventListener('click',event=>{const a=event.target.closest?.('a[href]');if(a&&/^https?:\/\//i.test(a.getAttribute('href'))){event.preventDefault();notice('This is an external link. Internet browsing is not part of the offline reader.');}},true);
  });
  fontSize=Number(load('maha-font-size'))||110;rendition.themes.fontSize(fontSize+'%');
  rendition.themes.default({'body':{'color':'#22392e','background':'#fffdf7','line-height':'1.65'},'img':{'max-width':'100%','height':'auto'},'table':{'max-width':'100%'}});
  const locationKey='maha-location-'+currentId;
  try{await rendition.display(load(locationKey)||undefined);}catch{await rendition.display();}
  notice('');for(const id of ['contents-toggle','smaller','larger'])element(id).disabled=false;element('prev').disabled=false;element('next').disabled=false;
  book.loaded.navigation.then(navigation=>{
   function add(items,depth=0){items.forEach(item=>{const a=document.createElement('a');a.textContent=item.label.trim()||'Section';a.href='#';a.style.paddingLeft=(5+depth*14)+'px';a.onclick=event=>{event.preventDefault();rendition.display(item.href).then(()=>contentsOpen(false)).catch(()=>notice('This section could not be opened. Try the next-page control or download the original.'));};element('toc').append(a);if(item.subitems)add(item.subitems,depth+1);});}
   add(navigation.toc);if(!navigation.toc.length)element('toc').textContent='No contents list provided. Use Previous and Next.';
  });
  rendition.on('relocated',location=>{if(location.start?.cfi)save(locationKey,location.start.cfi);element('prev').disabled=!!location.atStart;element('next').disabled=!!location.atEnd;const n=location.start?.displayed;element('position').textContent=n?`Section page ${n.page} of ${n.total}`:'Original illustrated EPUB';});
  rendition.on('displayError',()=>notice('A page could not be displayed. Try another section or download the original EPUB.'));
  function keys(event){if(event.target?.matches?.('input,textarea,select'))return;if(event.key==='ArrowRight')rendition.next();if(event.key==='ArrowLeft')rendition.prev();}
  document.addEventListener('keydown',keys);rendition.on('keyup',keys);
  let resizeTimer;window.addEventListener('resize',()=>{clearTimeout(resizeTimer);resizeTimer=setTimeout(()=>rendition.resize('100%','100%'),150);});
 }catch(error){notice('Unable to open this book: '+error.message);element('title').textContent='Book reader';}
}
element('contents-toggle').onclick=()=>contentsOpen(element('contents').hidden);
element('prev').onclick=()=>rendition?.prev().catch(()=>notice('Previous page unavailable.'));
element('next').onclick=()=>rendition?.next().catch(()=>notice('Next page unavailable.'));
function size(delta){fontSize=Math.min(180,Math.max(80,fontSize+delta));save('maha-font-size',String(fontSize));rendition?.themes.fontSize(fontSize+'%');}
element('smaller').onclick=()=>size(-10);element('larger').onclick=()=>size(10);
start();
