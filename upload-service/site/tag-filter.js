'use strict';
(()=>{
  const selected=new Set();window.MAHA_SELECTED_TAGS=()=>[...selected];window.MAHA_RESTORE_TAGS=tags=>{selected.clear();for(const tag of tags)if(typeof tag==='string')selected.add(tag);};
  window.MAHA_CLEAR_TAG_FILTER=()=>selected.clear();
  const tagsFor=book=>[...new Set((book.tags||[]).map(t=>t.trim().toLowerCase()).filter(Boolean))];
  window.MAHA_TAG_FILTER=book=>[...selected].every(tag=>tagsFor(book).includes(tag));
  const area=document.createElement('div');area.className='tag-filter';
  const picker=document.createElement('details');picker.className='tag-picker';
  const summary=document.createElement('summary');summary.textContent='Filter by tags';
  const panel=document.createElement('div');panel.className='tag-panel';
  const search=document.createElement('input');search.type='search';search.placeholder='Find a tag';search.setAttribute('aria-label','Find a tag');
  const explanation=document.createElement('p');explanation.textContent='Match all selected tags. Counts reflect the current category, search, and selected tags.';
  const choices=document.createElement('div');choices.className='tag-choices';choices.setAttribute('role','group');choices.setAttribute('aria-label','Book tags');
  const status=document.createElement('p');status.className='tag-status';status.setAttribute('role','status');
  panel.append(search,explanation,choices,status);picker.append(summary,panel);
  const chips=document.createElement('div');chips.className='selected-tags';chips.setAttribute('aria-label','Selected tags');
  area.append(picker,chips);document.querySelector('.chips').after(area);
  function change(tag){selected.has(tag)?selected.delete(tag):selected.add(tag);limit=24;document.getElementById('books').scrollTop=0;render();}
  function update(){
    const text=document.getElementById('search').value.trim().toLowerCase();
    const base=catalog.filter(b=>(topic==='All books'||b.topic===topic)&&(window.MAHA_ADDED_FILTER?.(b)!==false)&&(!text||(b.title+' '+(b.originalName||'')+' '+b.author+' '+b.topic+' '+(b.tags||[]).join(' ')).toLowerCase().includes(text)));
    const counts=new Map();
    for(const book of base){const tags=tagsFor(book);for(const tag of tags){if([...selected].every(s=>s===tag||tags.includes(s)))counts.set(tag,(counts.get(tag)||0)+1);}}
    for(const tag of selected)if(!counts.has(tag))counts.set(tag,0);
    const query=search.value.trim().toLowerCase();
    const matches=[...counts].filter(([tag])=>!query||tag.includes(query)).sort((a,b)=>Number(selected.has(b[0]))-Number(selected.has(a[0]))||b[1]-a[1]||a[0].localeCompare(b[0]));
    const focused=document.activeElement?.dataset.tag;
    choices.replaceChildren();
    for(const [tag,count] of matches.slice(0,80)){const label=document.createElement('label'),input=document.createElement('input'),name=document.createElement('span'),number=document.createElement('small');input.type='checkbox';input.checked=selected.has(tag);input.dataset.tag=tag;input.setAttribute('aria-label',tag+' ('+count+' books)');input.onchange=()=>change(tag);input.disabled=count===0&&!selected.has(tag);name.textContent=tag;number.textContent=String(count);label.append(input,name,number);choices.append(label);if(focused===tag)input.focus({preventScroll:true});}
    status.textContent=matches.length>80?'Showing 80 of '+matches.length+' tags. Type to narrow the list.':matches.length?matches.length+' matching tags':catalog.length?'No tags match these filters.':'Tags will appear as books are sorted.';
    summary.textContent=selected.size?'Tags ('+selected.size+')':'Filter by tags';
    chips.replaceChildren();
    area.hidden=selected.size===0;
    for(const tag of selected){const button=document.createElement('button');button.className='selected-tag';button.textContent=tag+' \u00d7';button.setAttribute('aria-label','Remove tag filter: '+tag);button.onclick=()=>change(tag);chips.append(button);}
    if(selected.size){const clear=document.createElement('button');clear.className='clear-tags';clear.textContent='Clear tags';clear.onclick=()=>{selected.clear();limit=24;render();};chips.append(clear);}
  }
  search.oninput=update;
  document.addEventListener('click',event=>{if(!event.composedPath().includes(picker))picker.open=false;});
  picker.addEventListener('keydown',event=>{if(event.key==='Escape'){picker.open=false;summary.focus();}});
  const previous=render;render=function(){previous();update();};
  render();
})();
