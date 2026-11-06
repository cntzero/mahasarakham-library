/* Route MAHA documents into the persistent listening shell; never external sites. */
(()=>{const target=location.pathname+location.search+location.hash;const topLevel=window===window.top;function localPage(value){try{const u=new URL(value,location.href);return u.origin===location.origin&&(u.pathname.endsWith('.html')||/^\/(files|uploads\/readable|kiwix|archive)\//.test(u.pathname))?u:null;}catch{return null;}}
if(topLevel&&/\/(login|listen)\.html$/.test(location.pathname))return;if(topLevel){window.stop();location.replace('/listen.html?page='+encodeURIComponent(target));return;}
let shell;try{shell=parent.MAHA_LISTEN;}catch{}if(!shell)return;if(location.pathname.endsWith('/music.html')&&!shell.isEngine(window)){shell.navigate(target);return;}
function report(){const u=new URL(location.href);u.searchParams.delete('dock');shell.sync(u.pathname+u.search+u.hash,window);}
for(const method of ['pushState','replaceState']){const original=history[method].bind(history);history[method]=function(...args){const result=original(...args);report();return result;};}
addEventListener('hashchange',report);addEventListener('DOMContentLoaded',()=>{document.documentElement.classList.add('maha-listening-frame');report();});
document.addEventListener('click',event=>{if(event.defaultPrevented||event.button!==0||event.ctrlKey||event.metaKey||event.shiftKey||event.altKey)return;const a=event.target.closest('a[href]');if(!a||a.hasAttribute('download'))return;const raw=a.getAttribute('href');if(raw.startsWith('#'))return;const u=localPage(a.href);if(!u)return;if(u.pathname==='/access-procedure.html'){event.preventDefault();originalOpen(u.href,'_blank','noopener');return;}event.preventDefault();event.stopImmediatePropagation();shell.navigate(u.pathname+u.search+u.hash);},true);
const originalOpen=window.open.bind(window);window.open=function(url,...args){const u=localPage(url);if(u){shell.navigate(u.pathname+u.search+u.hash);return null;}return originalOpen(url,...args);};
})();
