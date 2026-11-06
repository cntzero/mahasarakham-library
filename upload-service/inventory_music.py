"""Read-only MP3 inventory. Nothing is moved or published by this script."""
from pathlib import Path
import os,json,time,collections
from mutagen.mp3 import MP3
ROOT=Path('/mnt/data');OUT=Path('/mnt/data/projects/maha-library/music-inventory.json')
EXCLUDED={'program files','program files (x86)','programs','appdata','application data','windows','$recycle.bin','node_modules','.cache','cache','caches','steamapps','gog galaxy'}
rows=[];errors=[];started=time.time();seen=0
def error(exc):errors.append(str(exc))
for base,dirs,files in os.walk(ROOT,onerror=error,followlinks=False):
 dirs[:]=[d for d in dirs if (Path(base)/d) not in {ROOT/'survival-library',ROOT/'projects'} and not Path(base,d).is_symlink()]
 for name in files:
  if not name.lower().endswith('.mp3'):continue
  p=Path(base)/name;seen+=1;parts={s.casefold() for s in p.parts}
  if parts&EXCLUDED:rows.append({'path':str(p),'status':'excluded','reason':'application/game/cache directory'});continue
  try:
   audio=MP3(p);tags=audio.tags
   def tag(key):
    frame=tags.get(key) if tags else None
    return str(frame.text[0]).strip()[:500] if frame and frame.text else ''
   artist,album,title,genre=tag('TPE1'),tag('TALB'),tag('TIT2'),tag('TCON')
   duration=round(audio.info.length,2);music_folder=bool(parts&{'music','artists','albums','itunes','itunes media','itunes music','my music','mp3','mp3s'})
   status='include' if (music_folder and duration>=20) or (artist and album and duration>=45) else 'review'
   reason='music collection' if music_folder else 'tagged music' if status=='include' else 'short or unclassified audio; review before sharing'
   if genre.casefold() in {'sound effect','sound effects','sfx'}:status='excluded';reason='sound-effect genre'
   rows.append({'path':str(p),'status':status,'reason':reason,'bytes':p.stat().st_size,'duration':duration,'title':title,'artist':artist,'album':album,'genre':genre})
  except Exception as exc:rows.append({'path':str(p),'status':'review','reason':'Could not validate MP3: '+type(exc).__name__})
 if seen and seen%500==0:print('Scanned',seen,flush=True)
summary={'counts':dict(collections.Counter(r['status'] for r in rows)),'includedBytes':sum(r.get('bytes',0) for r in rows if r['status']=='include'),'errors':errors,'elapsed':round(time.time()-started),'root':str(ROOT)}
OUT.write_text(json.dumps({'summary':summary,'files':rows},ensure_ascii=False,indent=2));print(json.dumps(summary),flush=True)
