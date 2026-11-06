import tempfile,json
from pathlib import Path
import music,music_bulk as bulk
admin={'id':1,'role':'super'};owner={'id':2,'role':'user'};other={'id':3,'role':'user'}
def fails(fn,kind):
 try:fn()
 except kind:return
 raise AssertionError('Expected '+kind.__name__)
with tempfile.TemporaryDirectory() as temp:
 music.ROOT=Path(temp)
 ids=['a'*32,'b'*32]
 with music.connect() as db:
  for i,ident in enumerate(ids):
   db.execute("INSERT INTO tracks(id,sha256,title,artist,owner,tags) VALUES(?,?,?,?,?,?)",(ident,ident,'Fixture '+str(i),'Artist',2,'[]'))
   (music.ROOT/'tracks'/(ident+'.mp3')).write_bytes(b'fixture audio')
 fails(lambda:bulk.execute({'action':'tag','ids':ids,'tags':['podcast']},other),PermissionError)
 bulk.execute({'action':'tag','ids':ids,'tags':['podcast','Podcast']},owner)
 with music.connect() as db:assert all(json.loads(r['tags'])==['podcast'] for r in db.execute('SELECT tags FROM tracks'))
 bulk.execute({'action':'untag','ids':ids,'tags':['PODCAST']},owner)
 fails(lambda:bulk.preview({'ids':ids},owner),PermissionError)
 preview=bulk.preview({'ids':ids},admin)
 assert preview['count']==2 and preview['bytes']==26
 fails(lambda:bulk.execute({'action':'delete','token':preview['token'],'confirmation':'wrong'},admin),ValueError)
 assert all((music.ROOT/'tracks'/(ident+'.mp3')).exists() for ident in ids)
 fails(lambda:bulk.execute({'action':'delete','token':preview['token'],'confirmation':'DELETE 2'},other),ValueError)
 bulk.execute({'action':'remove','ids':[ids[0]]},owner)
 fails(lambda:bulk.execute({'action':'delete','token':preview['token'],'confirmation':'DELETE 2'},admin),ValueError)
 preview=bulk.preview({'ids':ids},admin)
 result=bulk.execute({'action':'delete','token':preview['token'],'confirmation':'DELETE 2'},admin)
 assert len(result['completed'])==2 and not result['errors']
 assert not any((music.ROOT/'tracks'/(ident+'.mp3')).exists() for ident in ids)
 fails(lambda:bulk.execute({'action':'delete','token':preview['token'],'confirmation':'DELETE 2'},admin),ValueError)
 db.close()
 import gc;gc.collect()
print('Bulk ownership, tag deduplication, tag removal, deletion preview, confirmation, changed selections and token reuse: passed')
