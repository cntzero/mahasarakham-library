"use strict";
(()=>{
 const key='maha-catalog-state';
 window.MAHA_RESET_FILTERS=()=>{topic='All books';limit=24;document.getElementById('search').value='';window.MAHA_CLEAR_TAG_FILTER?.();document.getElementById('book-added').value='all';render();document.getElementById('books').scrollTop=0;};
 function remember(){try{sessionStorage.setItem(key,JSON.stringify({search:document.getElementById('search').value,topic,sort:document.getElementById('book-sort').value,added:document.getElementById('book-added').value,tags:window.MAHA_SELECTED_TAGS?.()||[],limit,jumpStart:window.MAHA_BOOK_JUMP_START||0,scroll:document.getElementById('books').scrollTop}));}catch{}}
 document.addEventListener('input',remember);document.addEventListener('change',remember);document.addEventListener('click',()=>queueMicrotask(remember));window.addEventListener('pagehide',remember);
 try{const saved=JSON.parse(sessionStorage.getItem(key)||'null');if(saved){window.MAHA_BOOK_JUMP_START=Math.max(0,Number(saved.jumpStart)||0);document.getElementById('search').value=saved.search||'';topic=saved.topic||'All books';document.getElementById('book-sort').value=['title','newest','oldest'].includes(saved.sort)?saved.sort:'title';document.getElementById('book-added').value=saved.added||'all';window.MAHA_RESTORE_TAGS?.(saved.tags||[]);const prior=render;render=function(){if(catalog.length)limit=Math.max(24,Math.min(10000,Number(saved.limit)||24));prior();if(catalog.length){document.getElementById('books').scrollTop=saved.scroll||0;render=prior;}};render();}}catch{}
})();
