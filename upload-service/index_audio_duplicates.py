import sqlite3,sys,collections,time
from pathlib import Path
sys.path.insert(0,'/opt/maha-library-api')
import music
with music.connect() as db:rows=[dict(r) for r in db.execute("SELECT id,title,duration,album,albumArtist,artist,audioSha256 FROM tracks WHERE purgedAt='' AND removedAt=''")]
groups=collections.defaultdict(list)
for row in rows:groups[round(row['duration'],2)].append(row)
candidates=[r for group in groups.values() if len(group)>1 for r in group if not r['audioSha256']]
print('Audio duplicate candidates:',len(candidates),flush=True)
for i,row in enumerate(candidates,1):
 try:
  fingerprint=music.audio_digest(music.ROOT/'tracks'/(row['id']+'.mp3'))
  with music.connect() as db:db.execute('UPDATE tracks SET audioSha256=? WHERE id=?',(fingerprint,row['id']))
 except Exception as e:print(row['id'],str(e),flush=True)
 if i%50==0:print('Indexed',i,'/',len(candidates),flush=True)
print('Audio duplicate indexing complete. No files deleted.',flush=True)
