import tempfile,json,shutil,sqlite3
from pathlib import Path
from mutagen.id3 import ID3,TXXX,TALB,TPOS
import music,music_art_worker as art,music_bulk as bulk
inventory=json.loads(Path('/mnt/data/projects/maha-library/music-inventory.json').read_text())['files']
sample=Path(min((r for r in inventory if r['status']=='include'),key=lambda r:r['bytes'])['path'])
assert art.norm('東京')!=art.norm('大阪')
assert art.norm('東京') and art.norm('Álbum')==art.norm('Album')
with tempfile.TemporaryDirectory() as directory:
 root=Path(directory);music.ROOT=root/'library'
 first=music.add_file(sample,sample.name,1)
 variant=root/'variant.mp3';shutil.copyfile(sample,variant)
 tags=ID3(variant);tags.add(TXXX(encoding=3,desc='MAHA audit fixture',text='different metadata'));tags.save(variant)
 assert music.add_file(variant,sample.name,1)['status']=='skipped'
 tags=ID3(variant);tags.add(TALB(encoding=3,text='Separate release for audit'));tags.save(variant)
 assert music.add_file(variant,sample.name,1)['status']=='added','Separate albums must retain membership'
 tags=ID3(variant);tags.add(TPOS(encoding=3,text='2'));tags.save(variant)
 assert music.add_file(variant,sample.name,1)['status']=='added','Identical audio on another disc must remain'
 import music_tag_worker
 with music.connect() as db:db.execute("UPDATE tracks SET removedAt='removed',tagState='queued'")
 assert music_tag_worker.process_one() is False,'Removed tracks must not consume AI work'
 with music.connect() as db:db.execute("UPDATE tracks SET removedAt=''")
 with music.connect() as db:
  row=db.execute('SELECT * FROM tracks WHERE id=?',(first['id'],)).fetchone()
  music.inferred_compilation(row) # sqlite3.Row is the real upload API type.
 rows=[{'id':'one','audioSha256':'same','album':'Release','artist':'Beatles','albumArtist':'The Beatles','title':'Song','track':'1','disc':''}, {'id':'two','audioSha256':'same','album':'Release','artist':'Beatles','albumArtist':'Beatles','title':'Song','track':'1','disc':''}]
 assert len(music.collapse_audio_duplicates(rows))==1 and rows[1]['duplicateOf']=='one'
 assert len(rows)==2,'Both files must remain accessible'
 changed=[dict(r) for r in rows];changed[1]['track']='2'
 assert len(music.collapse_audio_duplicates(changed))==2,'Repeated audio at another track position must remain'
 changed[1]['track']='1';changed[1]['title']='Another track'
 assert len(music.collapse_audio_duplicates(changed))==2
 admin={'id':1,'role':'super'};preview=bulk.preview({'ids':[first['id']]},admin)
 with music.connect() as db:db.execute('UPDATE tracks SET title=? WHERE id=?',('Changed after preview',first['id']))
 try:bulk.execute({'action':'delete','token':preview['token'],'confirmation':'DELETE 1'},admin)
 except ValueError:pass
 else:raise AssertionError('A stale deletion preview was accepted')
 assert (music.ROOT/'tracks'/(first['id']+'.mp3')).exists()
 # Simultaneous confirmations can consume a preview only once.
 from concurrent.futures import ThreadPoolExecutor
 import threading
 preview=bulk.preview({'ids':[first['id']]},admin);calls=[];guard=threading.Lock()
 original_delete=music.delete_file
 def fake_delete(data,user):
  with guard:calls.append(data['id'])
  return {'bytesRemoved':0}
 music.delete_file=fake_delete
 def confirm(_):
  try:return bulk.execute({'action':'delete','token':preview['token'],'confirmation':'DELETE 1'},admin)
  except ValueError:return 'used'
 with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(confirm,range(2)))
 music.delete_file=original_delete
 assert len(calls)==1 and results.count('used')==1

print('Audit regressions: Unicode artwork, separate releases, metadata duplicates, SQLite rows, accessible duplicates, repeat positions and stale deletion previews: passed')

with tempfile.TemporaryDirectory() as directory:
 music.ROOT=Path(directory);(music.ROOT/'covers').mkdir()
 rows=[{'id':'a','album':'Release','artist':'Main Artist','albumArtist':'Main Artist','compilation':0,'cover':'cover','artKind':''},{'id':'b','album':'Release','artist':'Main Artist','albumArtist':'Various Artists','compilation':0,'cover':'cover','artKind':''}]
 for row in rows:(music.ROOT/'covers'/(row['id']+'.jpg')).write_bytes(b'identical embedded artwork fixture')
 music.annotate_compilations(rows)
 music.wait_for_cover_fingerprints()
 music.annotate_compilations(rows)
 assert all(r.get('resolvedAlbumArtist')=='Main Artist' for r in rows)
 assert not any(r.get('inferredCompilation') for r in rows)
 # Compilation flags and genuine different artists must not be reversed.
 rows[1]['compilation']=1;rows[1].pop('resolvedAlbumArtist',None)
 music.annotate_compilations(rows)
 music.wait_for_cover_fingerprints()
 music.annotate_compilations(rows)
 assert not rows[1].get('resolvedAlbumArtist')
 rows[1]['compilation']=0;rows[1]['artist']='Another Artist';rows[1]['albumArtist']='Another Artist'
 music.annotate_compilations(rows)
 music.wait_for_cover_fingerprints()
 music.annotate_compilations(rows)
 assert all(r.get('inferredCompilation') for r in rows)
print('Shared-cover single-artist reconciliation, explicit compilation protection and multi-artist inference: passed')
