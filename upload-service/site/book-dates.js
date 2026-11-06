'use strict';
(()=>{
 const row=document.createElement('div');row.className='book-date-filters catalog-controls';
 function control(label,id,options){const wrapper=document.createElement('label');wrapper.textContent=label;const select=document.createElement('select');select.id=id;for(const [value,text] of options){const option=document.createElement('option');option.value=value;option.textContent=text;select.append(option);}wrapper.append(select);row.append(wrapper);return select;}
 const sort=control('Sort by','book-sort',[['title','Title A–Z'],['newest','Recently added'],['oldest','Oldest added']]);
 const added=control('Date added','book-added',[['all','Any time'],['7','Last 7 days'],['30','Last 30 days'],['90','Last 90 days'],['unknown','Date unknown']]);
 document.querySelector('.tag-filter').before(row);
 row.append(document.querySelector('.tag-picker'));
 const timestamp=book=>{const date=Date.parse(book.importedAt||book.addedAt||'');return Number.isFinite(date)?date:null;};
 window.MAHA_ADDED_FILTER=book=>{const date=timestamp(book);return added.value==='all'||(added.value==='unknown'?date===null:date!==null&&date>=Date.now()-Number(added.value)*86400000);};
 window.MAHA_BOOK_SORT=(a,b)=>{if(sort.value==='title')return a.title.localeCompare(b.title);const x=timestamp(a),y=timestamp(b);if(x===null||y===null)return x===y?0:x===null?1:-1;return sort.value==='newest'?y-x:x-y;};
 for(const select of [sort,added])select.onchange=()=>{limit=24;render();document.getElementById('books').scrollTop=0;};
 render();
})();
