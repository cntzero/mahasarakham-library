'use strict';
(()=>{
 const byId=id=>document.getElementById(id),params=new URLSearchParams(location.search),frame=byId('content');
 let target;try{target=new URL(params.get('url')||'',location.origin);}catch{}
 if(!target||target.origin!==location.origin||!/^\/(?:kiwix\/content\/|archive\/askaprepper\/)/.test(target.pathname)){byId('status').textContent='This local archive link is not valid. Return to MAHA and choose an archive.';frame.hidden=true;return;}
 const captured=target.pathname.startsWith('/archive/');
 const archiveId=target.pathname.match(/^\/kiwix\/content\/([^/]+)/)?.[1];
 if(archiveId){byId('archive-search').hidden=false;byId('archive-search').onsubmit=event=>{event.preventDefault();const query=byId('query').value.trim();if(!query)return;byId('status').textContent='Searching this offline archive…';frame.src='/kiwix/search?'+new URLSearchParams({content:archiveId,pattern:query});};}
 byId('title').textContent=params.get('title')||'Offline archive';document.title=byId('title').textContent+' · MAHA';
 byId('back').href=captured?'archives.html':'knowledge.html';byId('back').textContent=captured?'← MAHA archived websites':'← MAHA knowledge';
 byId('original').href=target.pathname+target.search+target.hash;byId('original').hidden=false;
 let simplified=false;
 frame.addEventListener('load',()=>{
  try{
   const doc=frame.contentDocument;simplified=false;byId('readable').textContent='Simple reading view';
   if(!doc){byId('status').textContent='This page could not be displayed. Return to the catalog or try the original view.';return;}
   if(doc.getElementById('login-form')){location.replace('/login.html?return='+encodeURIComponent(location.pathname+location.search));return;}
   // The sandbox disables captured scripts and forms. Keep external links from
   // silently taking the reader out of the local collection.
   doc.addEventListener('click',event=>{const link=event.target.closest?.('a[href]');if(!link)return;const url=new URL(link.href,doc.baseURI);if(url.origin!==location.origin){event.preventDefault();byId('status').textContent='That link leaves the offline collection. Use the original view if you want to browse it separately.';}},true);
   const images=[...doc.images];let remaining=images.filter(img=>!img.complete).length;
   const report=()=>{const missing=images.filter(img=>img.complete&&!img.naturalWidth).length;byId('status').textContent=(captured?'Historical capture. ':'Offline archive. ')+(missing?missing+' image'+(missing===1?' is':'s are')+' unavailable in this capture. ':'')+'Original files are preserved; scripts and forms are disabled in this reader.';};
   for(const image of images.filter(img=>!img.complete)){image.addEventListener('load',()=>{remaining--;report();},{once:true});image.addEventListener('error',()=>{remaining--;report();},{once:true});}report();
   const article=doc.querySelector('.entry-content .content-inner')||doc.querySelector('.entry-content')||doc.querySelector('.mw-parser-output')||doc.querySelector('main')||[...doc.querySelectorAll('article')].sort((a,b)=>b.textContent.length-a.textContent.length)[0];byId('readable').hidden=!article;
   byId('readable').onclick=()=>{if(simplified){simplified=false;byId('readable').textContent='Simple reading view';frame.src=target.href;return;}const clean=article.cloneNode(true);clean.querySelectorAll('script,style,iframe,object,embed,form,nav,aside,.sharedaddy,.comments-area').forEach(node=>node.remove());clean.querySelectorAll('*').forEach(node=>{for(const attr of [...node.attributes])if(/^on/i.test(attr.name)||attr.name==='style')node.removeAttribute(attr.name);});doc.head.querySelectorAll('link[rel=stylesheet],style').forEach(node=>node.remove());doc.body.replaceChildren(clean);const style=doc.createElement('style');style.textContent='body{max-width:780px;margin:24px auto;padding:0 20px;font:18px/1.7 Georgia,serif;background:#fffdf7;color:#22392e}img,video,table{max-width:100%;height:auto}a{color:#22392e}';doc.head.append(style);simplified=true;byId('readable').textContent='Full captured layout';};
  }catch{byId('status').textContent='This archive cannot be inspected here. Use the original view or return to MAHA.';}
 });
 frame.src=target.href;
})();
