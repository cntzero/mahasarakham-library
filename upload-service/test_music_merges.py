import tempfile,json,threading
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import music,music_grouping,music_merges as merges
u={'id':2,'role':'user'};other={'id':3,'role':'user'};admin={'id':1,'role':'super'}
def fails(fn,kind):
 try:fn()
 except kind:return
 raise AssertionError('Expected '+kind.__name__)
with tempfile.TemporaryDirectory() as directory:
 music.ROOT=Path(directory);ids=[c*32 for c in 'abcd']
 with music.connect() as db:
  for index,ident in enumerate(ids):
   db.execute("INSERT INTO tracks(id,sha256,title,artist,album,albumArtist,owner,tags,bytes) VALUES(?,?,?,?,?,?,?,?,?)",(ident,ident,'Track '+str(index),'Artist','Source' if index<2 else 'Destination' if index==2 else 'Third','Artist',2,'[]',4))
   (music.ROOT/'tracks'/(ident+'.mp3')).write_bytes(b'MP3!')
 before_files={p.name:p.read_bytes() for p in (music.ROOT/'tracks').iterdir()}
 fails(lambda:merges.preview({'source':ids[0],'target':ids[2]},other),PermissionError)
 preview=merges.preview({'source':ids[0],'target':ids[2]},u);assert preview['sourceCount']==2 and preview['targetCount']==1
 fails(lambda:merges.confirm({'token':preview['token']},other),ValueError)
 result=merges.confirm({'token':preview['token']},u)
 with music.connect() as db:
  rows=[dict(r) for r in db.execute('SELECT * FROM tracks')]
 music_grouping.annotate(rows,music.inferred_compilation)
 assert len({r['groupKey'] for r in rows[:3]})==1 and rows[0]['groupLabel']=='Destination'
 assert rows[0]['album']=='Source','Original catalog metadata must be retained'
 assert len(merges.history(u))==1 and not merges.history(other)
 fails(lambda:merges.confirm({'token':preview['token']},u),ValueError)
 # Undo after a later merge must refuse until the later merge is reversed.
 second=merges.confirm({'token':merges.preview({'source':ids[0],'target':ids[3]},u)['token']},u)
 fails(lambda:merges.undo({'id':result['id']},u),ValueError)
 merges.undo({'id':second['id']},u);merges.undo({'id':result['id']},u)
 with music.connect() as db:assert all(not r[0] for r in db.execute('SELECT manualAlbumGroup FROM tracks'))
 # A changed membership invalidates an old preview.
 preview=merges.preview({'source':ids[0],'target':ids[2]},u)
 with music.connect() as db:db.execute('UPDATE tracks SET title=? WHERE id=?',('Changed',ids[0]))
 fails(lambda:merges.confirm({'token':preview['token']},u),ValueError)
 # Mixed ownership cannot be changed by an ordinary user.
 with music.connect() as db:db.execute('UPDATE tracks SET owner=3 WHERE id=?',(ids[1],))
 fails(lambda:merges.preview({'source':ids[0],'target':ids[2]},u),PermissionError)
 preview=merges.preview({'source':ids[0],'target':ids[2]},admin)
 def confirm(_):
  try:return merges.confirm({'token':preview['token']},admin)
  except ValueError:return 'used'
 with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(confirm,range(2)))
 assert results.count('used')==1
 assert {p.name:p.read_bytes() for p in (music.ROOT/'tracks').iterdir()}==before_files
print('Album merges: full membership, permissions, atomic confirmation, original tags/media, stale previews, chained undo and actor isolation: passed')
