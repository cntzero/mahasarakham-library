'use strict';
window.MAHA_CAN_MANAGE=false;
let categorySuggestions=[];
fetch('/api/library/categories').then(r=>r.ok?r.json():{}).then(data=>categorySuggestions=data.categories||[]).catch(()=>{});
async function refreshLibrary(){const response=await fetch('/api/library/books');if(!response.ok)throw Error('Could not refresh the library.');const updated=await response.json();const order=new Map(catalog.map((b,i)=>[b.id,i]));catalog=updated.sort((a,b)=>(order.get(a.id)??999999)-(order.get(b.id)??999999));render();}
function renderCategories(){const group=document.querySelector('.chips'),backwoods=document.getElementById('search').value==='Backwoods Home Magazine';const categories=['All books','Backwoods magazine',...new Set(catalog.map(b=>b.topic).filter(t=>t&&t!=='To be sorted').sort()),'To be sorted'];group.replaceChildren();for(const category of categories){const button=document.createElement('button');button.textContent=category;button.className=(category==='Backwoods magazine'?backwoods:!backwoods&&topic===category)?'active':'';button.onclick=()=>{if(category==='Backwoods magazine'){window.MAHA_SHOW_BACKWOODS();return;}if(backwoods){document.getElementById('search').value='';document.getElementById('shelf-title').textContent='Find your next useful thing.';}topic=category;limit=24;render();};group.append(button);}}

const baseRender=render;
render=function(){renderCategories();baseRender();document.querySelectorAll('#books>.book').forEach(button=>{const book=catalog.find(b=>b.id===button.dataset.bookId);if(!book)return;const card=document.createElement('div');card.className='book-entry';button.replaceWith(card);card.append(button);const note=document.createElement('div');note.className='book-meta';const pending=['queued','running'].includes(book.classification?.state);note.textContent=pending?'To be sorted \u00b7 sorting in background':book.topic+(book.tags?.length?' \u00b7 '+book.tags.slice(0,3).join(', '):'');card.append(note);const favoriteItem={kind:'book',id:book.id,title:book.title,subtitle:book.author,url:book.sources?.length===1?bookUrl(book,book.sources[0]):'index.html?view=library&book='+encodeURIComponent(book.id)};if(window.MAHA_PERSONAL?.has(favoriteItem))card.append(window.MAHA_PERSONAL.button(favoriteItem));if(window.MAHA_PERSONAL||window.MAHA_CAN_MANAGE){const actions=document.createElement('div');actions.className='book-actions';actions.id='actions-'+book.id;const toggle=document.createElement('button');toggle.className='book-options';toggle.textContent='...';toggle.setAttribute('aria-label','Options for '+book.title);toggle.setAttribute('aria-expanded','false');toggle.setAttribute('aria-controls',actions.id);toggle.onclick=()=>{const open=card.classList.toggle('options-open');toggle.setAttribute('aria-expanded',String(open));};card.append(toggle);if(window.MAHA_PERSONAL)actions.append(window.MAHA_PERSONAL.saveButton(favoriteItem));if(window.MAHA_CAN_MANAGE){const edit=document.createElement('button');edit.className='text-btn book-edit';edit.textContent='Edit book details';edit.onclick=()=>editClassification(book);actions.append(edit);const remove=document.createElement('button');remove.className='text-btn book-edit';remove.textContent='Remove from library';remove.onclick=()=>removeBook(book);actions.append(remove);}card.append(actions);}});};
const editor=document.createElement('dialog');editor.className='classification-editor';editor.setAttribute('aria-labelledby','book-editor-heading');document.body.append(editor);
function editClassification(book){
  editor.replaceChildren();
  const heading=document.createElement('h2');heading.id='book-editor-heading';heading.textContent=book.title;
  const titleLabel=document.createElement('label');titleLabel.textContent='Title';const titleInput=document.createElement('input');titleInput.value=book.title;titleInput.maxLength=500;titleLabel.append(titleInput);
  const addedInfo=document.createElement('p');const addedDate=Date.parse(book.importedAt||book.addedAt||'');addedInfo.textContent='Added: '+(Number.isFinite(addedDate)?new Date(addedDate).toLocaleString():'Date unknown (older catalog entry)');if(book.originalName)addedInfo.textContent+=' · Original file: '+book.originalName;
  const authorLabel=document.createElement('label');authorLabel.textContent='Author';const authorInput=document.createElement('input');authorInput.value=book.author||'';authorInput.maxLength=500;authorLabel.append(authorInput);
  const categoryLabel=document.createElement('label');categoryLabel.textContent='Category';
  const category=document.createElement('input');category.value=book.topic||'To be sorted';category.maxLength=80;category.setAttribute('list','book-categories');
  const datalist=document.createElement('datalist');datalist.id='book-categories';
  for(const value of [...new Set(['To be sorted',...categorySuggestions,...catalog.map(b=>b.topic)])]){const option=document.createElement('option');option.value=value;datalist.append(option);}
  categoryLabel.append(category,datalist);
  const tagsLabel=document.createElement('label');tagsLabel.textContent='Tags, separated by commas';
  const tags=document.createElement('input');tags.value=(book.tags||[]).join(', ');tagsLabel.append(tags);
  const note=document.createElement('p');note.setAttribute('role','status');note.setAttribute('aria-live','polite');note.textContent=book.classification?.note||'Your changes take priority over automatic sorting.';
  const actions=document.createElement('div');actions.className='editor-actions';
  const save=document.createElement('button');save.className='action';save.textContent='Save changes';
  const retry=document.createElement('button');retry.className='action secondary';retry.textContent='Try AI sorting';
  const close=document.createElement('button');close.className='text-btn';close.textContent='Cancel';close.onclick=()=>editor.close();
  let timer=null,watching=false,revision=null;
  function busy(value){save.disabled=retry.disabled=titleInput.disabled=authorInput.disabled=category.disabled=tags.disabled=value;editor.setAttribute('aria-busy',String(value));}
  function stop(){watching=false;clearTimeout(timer);busy(false);}
  editor.addEventListener('close',stop,{once:true});
  async function post(path,payload){const response=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json','X-Maha-Upload':'1'},body:JSON.stringify(payload)});const data=await response.json();if(!response.ok)throw Error(data.error||'Could not save.');return data;}
  async function checkProgress(){
    if(!watching||!editor.open)return;
    try{
      await refreshLibrary();if(!watching||!editor.open)return;
      const updated=catalog.find(b=>b.id===book.id);if(!updated)throw Error('This book is no longer in the library.');
      const state=updated.classification||{};
      if(revision&&state.revision!==revision){stop();note.textContent='The classification changed in another session. Close and reopen this book to see the latest settings.';close.textContent='Close';return;}
      if(['queued','running'].includes(state.state)){note.textContent=state.state==='queued'?'AI sorting is queued. Waiting for the local AI to become available...':'AI sorting... Reading a sample and choosing a category and tags. This may take a minute.';timer=setTimeout(checkProgress,2000);return;}
      stop();retry.textContent='Try AI sorting';retry.onclick=startSorting;category.value=updated.topic||'To be sorted';tags.value=(updated.tags||[]).join(', ');close.textContent='Close';
      if(state.state==='sorted')note.textContent='AI sorting finished and saved. Category: '+category.value+'. Tags: '+(tags.value||'none')+'. You can edit these below.';
      else note.textContent='AI sorting needs review. '+(state.note||'No confident category was found.')+(state.suggestedTopic?' Suggested category: '+state.suggestedTopic+'.':'')+' The book remains readable in To be sorted.';
    }catch(error){if(!watching||!editor.open)return;stop();note.textContent='Could not check AI sorting: '+error.message+' The background job may still be running.';retry.textContent='Check progress';retry.onclick=()=>watch(revision);close.textContent='Close';}
  }
  function watch(jobRevision){revision=jobRevision;watching=true;busy(true);close.textContent='Continue in background';checkProgress();}
  save.onclick=async()=>{busy(true);try{await post('/api/library/metadata',{id:book.id,title:titleInput.value,author:authorInput.value});await post('/api/library/classification',{id:book.id,topic:category.value,tags:tags.value.split(',').map(t=>t.trim()).filter(Boolean)});await refreshLibrary();editor.close();}catch(error){note.textContent=error.message;}finally{busy(false);}};
  async function startSorting(){busy(true);note.textContent='Requesting AI sorting...';try{const job=await post('/api/library/classify',{id:book.id});retry.textContent='Try AI sorting';watch(job.revision);}catch(error){busy(false);note.textContent='Could not start AI sorting: '+error.message;}}
  retry.onclick=startSorting;
  actions.append(save,retry,close);editor.append(heading,titleLabel,authorLabel,addedInfo,categoryLabel,tagsLabel,note,actions);editor.showModal();
  if(['queued','running'].includes(book.classification?.state))watch(book.classification.revision);
}

document.addEventListener('maha-session',()=>render());
setInterval(()=>{if(!editor.open&&catalog.some(b=>['queued','running'].includes(b.classification?.state)))refreshLibrary().catch(()=>{});},10000);
render();

async function visibility(kind,id,hidden){const response=await fetch('/api/library/visibility',{method:'POST',headers:{'Content-Type':'application/json','X-Maha-Upload':'1'},body:JSON.stringify({kind,id,hidden})});const data=await response.json();if(!response.ok)throw Error(data.error||'Could not update this item.');}
async function removeBook(book){if(!await (window.MAHA_CONFIRM||confirm)('Remove “'+book.title+'” from the library? Original files will be kept. You can restore it under Removed books.'))return;try{await visibility('book',book.id,true);await refreshLibrary();}catch(e){alert(e.message)}}
const removedButton=document.createElement('button');removedButton.className='text-btn';removedButton.textContent='Removed books';removedButton.hidden=true;document.getElementById('browse-all').before(removedButton);
removedButton.onclick=async()=>{try{const response=await fetch('/api/library/removed-books');if(!response.ok)throw Error('Could not load removed books.');const rows=await response.json();editor.replaceChildren();const heading=document.createElement('h2');heading.id='book-editor-heading';heading.textContent='Removed books';editor.append(heading);if(!rows.length){const empty=document.createElement('p');empty.textContent='No removed books.';editor.append(empty)}for(const book of rows){const row=document.createElement('p'),restore=document.createElement('button');row.textContent=book.title+' ';restore.className='text-btn';restore.textContent='Restore';restore.onclick=async()=>{try{await visibility('book',book.id,false);await refreshLibrary();row.remove()}catch(e){alert(e.message)}};row.append(restore);editor.append(row)}const close=document.createElement('button');close.className='action';close.textContent='Close';close.onclick=()=>editor.close();editor.append(close);editor.showModal()}catch(e){alert(e.message)}};
document.addEventListener('maha-session',()=>removedButton.hidden=!window.MAHA_CAN_MANAGE);

let personalBookOpened=false;
const personalBookRender=render;
render=function(){personalBookRender();const ref=window.MAHA_PERSONAL_BOOK_REF||new URLSearchParams(location.search).get('book');if(ref&&!personalBookOpened){const book=catalog.find(b=>b.id===ref);if(book){personalBookOpened=true;openBook(book);}}};
const bookFavorites=document.createElement('button');bookFavorites.className='favorite-filter';bookFavorites.textContent='Favorites';bookFavorites.setAttribute('aria-pressed','false');bookFavorites.onclick=()=>{window.MAHA_BOOK_FAVORITES=!window.MAHA_BOOK_FAVORITES;bookFavorites.setAttribute('aria-pressed',String(!!window.MAHA_BOOK_FAVORITES));render();};document.getElementById('books').before(bookFavorites);
window.addEventListener('maha-personal-change',()=>render());
