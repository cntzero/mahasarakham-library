import tempfile
from pathlib import Path
import music,music_bulk as bulk
admin={'id':1,'role':'super'};owner={'id':2,'role':'user'}
def fails(fn,kind):
 try:fn()
 except kind:return
 raise AssertionError('Expected '+kind.__name__)
with tempfile.TemporaryDirectory() as temporary:
 root=Path(temporary);music.ROOT=root/'library';original=root/'original.mp3';original.write_bytes(b'original')
 ids=[c*32 for c in 'abcd']
 def add(ident,album,removed=''):
  with music.connect() as db:db.execute("INSERT INTO tracks(id,sha256,title,artist,album,albumArtist,owner,tags,bytes,removedAt) VALUES(?,?,?,?,?,?,?,?,?,?)",(ident,ident,'Track '+ident[0],'Artist',album,'Artist',2,'[]',5,removed))
  (music.ROOT/'tracks'/(ident+'.mp3')).write_bytes(b'audio');(music.ROOT/'covers'/(ident+'.jpg')).write_bytes(b'art')
 add(ids[0],'Album');add(ids[1],'Album','removed');add(ids[2],'Other Album')
 fails(lambda:bulk.preview({'albumId':ids[0]},owner),PermissionError)
 preview=bulk.preview({'albumId':ids[0]},admin)
 assert preview['count']==2 and preview['removedCount']==1 and preview['bytes']==16
 fails(lambda:bulk.execute({'action':'delete','token':preview['token'],'confirmation':'DELETE 1'},admin),ValueError)
 add(ids[3],'Album')
 fails(lambda:bulk.execute({'action':'delete','token':preview['token'],'confirmation':'DELETE 2'},admin),ValueError)
 assert (music.ROOT/'tracks'/(ids[0]+'.mp3')).exists()
 preview=bulk.preview({'albumId':ids[0]},admin);assert preview['count']==3
 result=bulk.execute({'action':'delete','token':preview['token'],'confirmation':'DELETE 3'},admin)
 assert len(result['completed'])==3 and not result['errors'] and result['bytesRemoved']==24
 assert all(not (music.ROOT/'tracks'/(ident+'.mp3')).exists() for ident in (ids[0],ids[1],ids[3]))
 assert (music.ROOT/'tracks'/(ids[2]+'.mp3')).exists() and original.read_bytes()==b'original'
print('Album deletion: super-user restriction, all album files including removed tracks, artwork size, changed membership, typed confirmation and preservation of other albums/source originals: passed')
