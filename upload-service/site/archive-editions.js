'use strict';
// Keep subjects and languages distinct; merge only snapshot/packaging variants.
function archiveFamily(book){
  const stem=(book.edition||book.id).replace(/_\d{4}-\d{2}(?:-\d{2})?$/,'').replace(/_(?:maxi|nopic|mini|nodet|orig)$/,'');
  return [book.collection||'',book.language||'',stem].join('|');
}
function archiveQuality(book){
  const stem=book.edition||'';
  return /_maxi_/.test(stem)?4:/_orig_/.test(stem)?3:/_nopic_/.test(stem)?1:/_(?:mini|nodet)_/.test(stem)?0:2;
}
function latestArchives(rows){
  const groups=new Map();
  for(const book of rows){const key=archiveFamily(book),old=groups.get(key);
    const order=old?(book.date||'').localeCompare(old.date||'')||archiveQuality(book)-archiveQuality(old)||(book.size||0)-(old.size||0)||String(book.id).localeCompare(String(old.id)):1;
    if(order>0)groups.set(key,book);
  }
  return [...groups.values()];
}
