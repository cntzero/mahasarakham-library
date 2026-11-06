import tempfile
from pathlib import Path
import music,music_grouping,music_merges as albums
owner={'id':2,'role':'user'};other={'id':3,'role':'user'}
def fails(fn,kind):
 try:fn()
 except kind:return
 raise AssertionError('Expected '+kind.__name__)
with tempfile.TemporaryDirectory() as directory:
 music.ROOT=Path(directory);ids=[c*32 for c in 'abcdefg']
 with music.connect() as db:
  rows=[('Single A','A','Unknown album'),('Single B','B','Unknown album'),('Multi 1','C','Unknown album'),('Multi 2','C','Unknown album'),('Known 1','D','Vintage Goons 03'),('Known 2','D','Vintage Goons 03'),('Manual','E','Unknown album')]
  for ident,(title,artist,album) in zip(ids,rows):db.execute("INSERT INTO tracks(id,sha256,title,artist,album,owner,tags,bytes,albumMetadataVersion) VALUES(?,?,?,?,?,?,?,?,?)",(ident,ident,title,artist,album,2,'[]',4,1))
  db.execute("UPDATE tracks SET manualAlbumGroup='manual-fixture',manualAlbumTitle='Explicit unknown',manualAlbumArtist='E' WHERE id=?",(ids[-1],))
 def read():
  with music.connect() as db:data=[dict(r) for r in db.execute('SELECT * FROM tracks')]
  music_grouping.annotate(data,music.inferred_compilation);return {r['id']:r for r in data}
 data=read();assert data[ids[0]]['groupKey']==data[ids[1]]['groupKey']=='collection:unknown-album-singles'
 assert not data[ids[2]].get('unknownSingles') and data[ids[2]]['groupKey']==data[ids[3]]['groupKey']
 assert data[ids[-1]]['groupLabel']=='Explicit unknown'
 source=data[ids[4]];request={'id':source['id'],'name':'Goon Shows','expectedGroup':source['groupKey'],'expectedTitle':source['groupLabel']}
 fails(lambda:albums.rename(request,other),PermissionError)
 result=albums.rename(request,owner);assert result['count']==2
 data=read();assert all(data[i]['album']=='Goon Shows' and data[i]['groupLabel']=='Goon Shows' for i in ids[4:6])
 assert data[ids[4]]['groupKey']==data[ids[5]]['groupKey']
 assert data[ids[0]]['album']=='Unknown album' and data[ids[4]]['title']=='Known 1'
 fails(lambda:albums.rename(request,owner),ValueError)
 # Hidden copies of the same recording should still behave as a single-track group.
 duplicate=dict(data[ids[0]],id='f'*32);duplicate['audioSha256']='audio';original=dict(data[ids[0]],audioSha256='audio')
 music_grouping.annotate([original,duplicate],music.inferred_compilation)
 assert original.get('unknownSingles') and duplicate.get('unknownSingles')
print('Album organization: unknown singles consolidate; multi-track/manual groups retained; duplicate variants counted once; album-wide rename, permissions and stale-name protection: passed')
