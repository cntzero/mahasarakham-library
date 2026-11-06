"""Local MP3 library. Immutable media, editable catalog, owner-aware writes."""
from pathlib import Path
from functools import lru_cache
import queue
import os,json,sqlite3,time,hashlib,shutil,tempfile,threading,re,uuid
from urllib.parse import unquote
import music_grouping
ROOT=Path(os.environ.get('MAHA_MUSIC_ROOT','/mnt/data/survival-library/music'))
LOCK=threading.Lock();MAX_BYTES=200*1024**2
def connect():
 ROOT.mkdir(parents=True,exist_ok=True)
 for folder in ('tracks','covers','staging'):(ROOT/folder).mkdir(exist_ok=True)
 db=sqlite3.connect(ROOT/'catalog.sqlite',timeout=30);db.row_factory=sqlite3.Row
 db.execute('CREATE TABLE IF NOT EXISTS tracks(id TEXT PRIMARY KEY,sha256 TEXT UNIQUE,title TEXT,artist TEXT,album TEXT,genre TEXT,year TEXT,track TEXT,duration REAL,addedAt TEXT,owner INTEGER,originalName TEXT,tags TEXT,cover TEXT)')
 db.execute('CREATE TABLE IF NOT EXISTS sources(track_id TEXT,path TEXT,UNIQUE(track_id,path))')
 columns={row[1] for row in db.execute('PRAGMA table_info(tracks)')}
 for name,definition in [('tagState',"TEXT DEFAULT 'queued'"),('tagRevision',"TEXT DEFAULT ''"),('tagStarted','REAL DEFAULT 0'),('removedAt',"TEXT DEFAULT ''"),('bytes','INTEGER DEFAULT 0'),('purgedAt',"TEXT DEFAULT ''"),('albumArtist',"TEXT DEFAULT ''"),('disc',"TEXT DEFAULT ''"),('compilation','INTEGER DEFAULT 0'),('albumMetadataVersion','INTEGER DEFAULT 0'),('artKind',"TEXT DEFAULT ''"),('artSource',"TEXT DEFAULT ''"),('audioSha256',"TEXT DEFAULT ''"),('manualAlbumGroup',"TEXT DEFAULT ''"),('manualAlbumTitle',"TEXT DEFAULT ''"),('manualAlbumArtist',"TEXT DEFAULT ''"),('manualAlbumCoverId',"TEXT DEFAULT ''")]:
  if name not in columns:db.execute('ALTER TABLE tracks ADD COLUMN '+name+' '+definition)
 db.execute('CREATE INDEX IF NOT EXISTS tracks_duration ON tracks(duration)')
 db.execute('CREATE INDEX IF NOT EXISTS tracks_audio_sha ON tracks(audioSha256)')
 return db
def inspect(path,name):
 from mutagen.mp3 import MP3
 from mutagen import MutagenError
 try:audio=MP3(path)
 except (MutagenError,OSError,ValueError):raise ValueError('This is not a readable MP3 audio file.')
 if audio.info.length<=0:raise ValueError('This MP3 contains no playable audio.')
 def tag(key):
  frame=audio.tags.get(key) if audio.tags else None
  return str(frame.text[0]).strip()[:500] if frame and frame.text else ''
 result={'title':tag('TIT2') or re.sub(r'[_]+',' ',Path(name).stem),'artist':tag('TPE1') or 'Unknown artist','album':tag('TALB') or 'Unknown album','genre':tag('TCON'),'year':tag('TDRC')[:10],'track':tag('TRCK')[:20],'duration':round(audio.info.length,2)}
 art=next(iter(audio.tags.getall('APIC')),None) if audio.tags else None
 return result,art.data if art and len(art.data)<=12*1024**2 else None
def album_metadata(path):
 from mutagen.mp3 import MP3
 audio=MP3(path)
 def tag(key):
  frame=audio.tags.get(key) if audio.tags else None
  return str(frame.text[0]).strip()[:500] if frame and frame.text else ''
 return tag('TPE2'),tag('TPOS')[:20],int(tag('TCMP').lower() in ('1','true','yes'))

def digest(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as source:
  for chunk in iter(lambda:source.read(1024**2),b''):h.update(chunk)
 return h.hexdigest()
def audio_digest(path):
 from mutagen.mp3 import MP3
 path=Path(path);start=MP3(path).info.frame_offset;end=path.stat().st_size
 with path.open('rb') as source:
  if end>=128:
   source.seek(end-128)
   if source.read(3)==b'TAG':end-=128
  # APEv2 footer/tags can also trail MP3 audio.
  if end>=32:
   source.seek(end-32);footer=source.read(32)
   if footer[:8]==b'APETAGEX':
    size=int.from_bytes(footer[12:16],'little')
    if 32<=size<=end-start:end-=size
  if end<=start:raise ValueError('No MP3 audio frames found.')
  source.seek(start);remaining=end-start;result=hashlib.sha256()
  while remaining:
   chunk=source.read(min(1024**2,remaining))
   if not chunk:raise ValueError('Audio read interrupted.')
   result.update(chunk);remaining-=len(chunk)
 return result.hexdigest()

def artist_identity(value):
 value=re.sub(r'\s+(?:featuring|feat\.?|ft\.?)\s+.+$','',value or '',flags=re.I)
 value=re.sub(r'\.(?=\s|$)','',value).casefold()
 return re.sub(r'^the\s+','',' '.join(value.split()))

def collapse_audio_duplicates(rows):
 groups={};result=[]
 for row in rows:
  audio=row.get('audioSha256')
  if not audio:result.append(row);continue
  key=(audio,row.get('groupKey') or (row.get('album') or '').strip().casefold(),artist_identity(row.get('artist')),(row.get('title') or '').strip().casefold(),row.get('track') or '',row.get('disc') or '',bool(row.get('removedAt')))
  if key not in groups:groups[key]=row;result.append(row)
  else:
   primary=groups[key]
   primary['duplicateCount']=primary.get('duplicateCount',0)+1
   row['duplicateOf']=primary['id']
 return result

def add_file(path,name,owner=None,source_path=None):
 path=Path(path);sha=digest(path);ident=sha[:32]
 with LOCK:
  with connect() as db:
   old=db.execute('SELECT id,title FROM tracks WHERE sha256=?',(sha,)).fetchone()
   if old:
    if source_path:db.execute('INSERT OR IGNORE INTO sources VALUES(?,?)',(old['id'],str(source_path)))
    return {'status':'skipped','id':old['id'],'title':old['title'],'message':'Exact duplicate already in the library'}
   info,art=inspect(path,name)
   audio_sha=audio_digest(path)
   new_album_artist,new_disc,new_compilation=album_metadata(path)
   candidates=db.execute("SELECT * FROM tracks WHERE duration BETWEEN ? AND ? AND purgedAt='' ",(info['duration']-.05,info['duration']+.05)).fetchall()
   for candidate in candidates:
    # The same audio may legitimately appear on a different release or track.
    if (candidate['album'] or '').strip().casefold()!=info['album'].strip().casefold() or artist_identity(candidate['artist'])!=artist_identity(info['artist']) or (candidate['title'] or '').strip().casefold()!=info['title'].strip().casefold() or (candidate['track'] or '')!=info['track'] or (candidate['disc'] or '')!=new_disc:continue
    fingerprint=candidate['audioSha256']
    if not fingerprint:
     try:fingerprint=audio_digest(ROOT/'tracks'/(candidate['id']+'.mp3'))
     except (OSError,ValueError):continue
     db.execute('UPDATE tracks SET audioSha256=? WHERE id=?',(fingerprint,candidate['id']))
    if fingerprint==audio_sha:
     if source_path:db.execute('INSERT OR IGNORE INTO sources VALUES(?,?)',(candidate['id'],str(source_path)))
     return {'status':'skipped','id':candidate['id'],'message':'Identical MP3 audio already in the library; metadata differs'}
   dest=ROOT/'tracks'/(ident+'.mp3')
   if shutil.disk_usage(ROOT).free<path.stat().st_size+1024**3:raise ValueError('Not enough free disk space for this song.')
   # Copy via a temporary file and verify before publishing the catalog entry.
   with tempfile.NamedTemporaryFile(dir=ROOT/'staging',delete=False) as f:temporary=Path(f.name)
   try:
    shutil.copyfile(path,temporary)
    if digest(temporary)!=sha:raise ValueError('Copied audio failed verification. Original retained.')
    os.replace(temporary,dest)
   finally:temporary.unlink(missing_ok=True)
   cover=''
   if art:
    try:
     from PIL import Image,ImageOps
     import io
     with Image.open(io.BytesIO(art)) as image:
      if image.width*image.height>25_000_000:raise ValueError('Artwork too large')
      image=ImageOps.exif_transpose(image).convert('RGB');image.thumbnail((500,500));image.save(ROOT/'covers'/(ident+'.jpg'),quality=85)
     cover='/music-media/covers/'+ident+'.jpg'
    except Exception:pass
   db.execute('INSERT INTO tracks(id,sha256,title,artist,album,genre,year,track,duration,addedAt,owner,originalName,tags,cover,tagState,tagRevision) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(ident,sha,info['title'],info['artist'],info['album'],info['genre'],info['year'],info['track'],info['duration'],time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),owner,name,json.dumps([info['genre']] if info['genre'] else []),cover,'queued',uuid.uuid4().hex))
   album_artist,disc,compilation=new_album_artist,new_disc,new_compilation
   db.execute('UPDATE tracks SET bytes=?,albumArtist=?,disc=?,compilation=?,albumMetadataVersion=1 WHERE id=?',(dest.stat().st_size,album_artist,disc,compilation,ident))
   db.execute('UPDATE tracks SET audioSha256=? WHERE id=?',(audio_sha,ident))
   if source_path:db.execute('INSERT OR IGNORE INTO sources VALUES(?,?)',(ident,str(source_path)))
   return {'status':'added','id':ident,'title':info['title'],'message':'Song added and verified'}
# Artwork inference must never perform disk reads on a catalog request.
_COVER_REVISION=0;_CATALOG_EPOCH=uuid.uuid4().hex
_COVER_CACHE={};_COVER_PENDING=set();_COVER_QUEUE=queue.Queue();_COVER_THREAD=None;_COVER_LOCK=threading.Lock()

def _cover_worker():
 global _COVER_REVISION
 while True:
  key,path=_COVER_QUEUE.get()
  try:
   try:value=digest(path)
   except OSError:value=None
   with _COVER_LOCK:_COVER_CACHE[key]=value;_COVER_PENDING.discard(key);_COVER_REVISION+=1
  finally:_COVER_QUEUE.task_done()

def cover_evidence(row):
 global _COVER_THREAD
 key=(str(ROOT),row['id'],row['cover'])
 with _COVER_LOCK:
  if key in _COVER_CACHE:return _COVER_CACHE[key],False
  if _COVER_THREAD is None:
   _COVER_THREAD=threading.Thread(target=_cover_worker,daemon=True,name='cover-evidence');_COVER_THREAD.start()
  if key not in _COVER_PENDING:
   _COVER_PENDING.add(key);_COVER_QUEUE.put((key,ROOT/'covers'/(row['id']+'.jpg')))
 return None,True

def wait_for_cover_fingerprints():
 # Test/diagnostic helper. Catalog requests never call this.
 _COVER_QUEUE.join()

def annotate_compilations(rows):
 # Identical real embedded/archive artwork plus album title corroborates a shared release.
 albums={}
 for row in rows:
  for key in ('groupingPending','inferredCompilation','resolvedAlbumArtist'):row.pop(key,None)
  if (not row.get('albumArtist') or artist_identity(row['albumArtist']) in (artist_identity(row['artist']),'various artists')) and not row.get('compilation') and (row.get('album') or '').strip().casefold() not in ('','unknown','unknown album','album unknown','album','title'):
   albums.setdefault(row['album'].strip().casefold(),[]).append(row)
 for group in albums.values():
  if len(group)<2:continue
  identities={artist_identity(r['artist']) for r in group}
  # Single-artist albums need no image reads unless a Various Artists tag conflicts.
  if len(identities)<2 and not (any(artist_identity(r.get('albumArtist'))=='various artists' for r in group) and any(r.get('albumArtist') and artist_identity(r['albumArtist']) in identities for r in group)):continue
  images={}
  for row in group:
   if not row.get('cover') or row.get('artKind') not in ('','archive'):continue
   fingerprint,pending=cover_evidence(row)
   if pending:row['groupingPending']=True
   if not fingerprint:continue
   images.setdefault(fingerprint,[]).append(row)
  for matching in images.values():
   identities={artist_identity(r['artist']) for r in matching}
   if len(identities)>=2:
    for row in matching:row['inferredCompilation']=True
   elif len(matching)>=2 and identities and 'unknown artist' not in identities:
    # A stray Various Artists tag must not split a corroborated single-artist release.
    corroborated=[r for r in matching if r.get('albumArtist') and artist_identity(r['albumArtist'])==artist_identity(r['artist'])]
    if corroborated:
     resolved=corroborated[0]['albumArtist']
     for row in matching:row['resolvedAlbumArtist']=resolved

def catalog_etag(user):
 parts=[_CATALOG_EPOCH,str(_COVER_REVISION),str(user.get('id') if user else ''),str(user.get('role') if user else '')]
 for path in (ROOT/'catalog.sqlite',ROOT/'catalog.sqlite-wal'):
  try:
   stat=path.stat();parts.append(str(stat.st_mtime_ns)+':'+str(stat.st_size))
  except OSError:parts.append('missing')
 return '"'+hashlib.sha256('|'.join(parts).encode()).hexdigest()+'"'

def catalog(user):
 with connect() as db:
  rows=[dict(row) for row in db.execute("SELECT * FROM tracks WHERE purgedAt=''"+("" if user and user.get("role")=="super" else " AND removedAt=''")+" ORDER BY title COLLATE NOCASE")]
  for row in rows:
   if not row['albumMetadataVersion']:
    try:row['albumArtist'],row['disc'],row['compilation']=album_metadata(ROOT/'tracks'/(row['id']+'.mp3'))
    except (OSError,ValueError):pass
    db.execute('UPDATE tracks SET albumArtist=?,disc=?,compilation=?,albumMetadataVersion=1 WHERE id=?',(row['albumArtist'],row['disc'],row['compilation'],row['id']))
   if not row['bytes']:
    try:row['bytes']=(ROOT/'tracks'/(row['id']+'.mp3')).stat().st_size
    except OSError:row['bytes']=0
    if row['bytes']:db.execute('UPDATE tracks SET bytes=? WHERE id=?',(row['bytes'],row['id']))
 annotate_compilations(rows)
 music_grouping.annotate(rows,inferred_compilation)
 # Keep every stored file accessible; only the browser's default view collapses copies.
 collapse_audio_duplicates(rows)
 for row in rows:
  row['tags']=json.loads(row['tags']);row['url']='/music-media/tracks/'+row['id']+'.mp3'
  row['canEdit']=bool(user and (user.get('role')=='super' or row['owner']==user.get('id')))
  row['canDelete']=bool(user and user.get('role')=='super')
  row['isMine']=bool(user and row['owner']==user.get('id'))
  row.pop('owner');row.pop('sha256');row.pop('tagRevision');row.pop('tagStarted')
 return rows
def inferred_compilation(row):
 row=dict(row)
 return bool(row.get('inferredCompilation') or row['compilation']) or bool(re.match(r'^(?:(?:19|20)\d{2}|\d{2}[\x27’]?s)\s+(?:classic\s+rock|alternative|mellow|dance|techno|pop|rock|country|jazz|blues|classical|r[&n]b|hip[ -]?hop|rap|reggae|disco|electronic|trance|house|metal|soul|funk|folk|hits)(?:\b|\s*[-–:])',row['album'] or '',re.I))

def discovery_candidates():
 # Small representatives let the hero load independently of the full track list.
 with connect() as db:
  rows=[dict(r) for r in db.execute("SELECT id,title,artist,album,albumArtist,disc,compilation,year,originalName,cover,artKind,duration,bytes,track,audioSha256,manualAlbumGroup,manualAlbumTitle,manualAlbumArtist,manualAlbumCoverId FROM tracks WHERE removedAt='' AND purgedAt=''")]
 annotate_compilations(rows)
 music_grouping.annotate(rows,inferred_compilation)
 rows=collapse_audio_duplicates(rows)
 groups={}
 for row in rows:
  key=row['groupKey']
  if key not in groups or (row['cover'] and not groups[key]['cover']):groups[key]=row
 day=time.strftime('%Y-%m-%d',time.localtime())
 ordered=sorted(groups.values(),key=lambda r:hashlib.sha256((day+r['id']).encode()).hexdigest())
 illustrated=[r for r in ordered if r['cover']]
 return (illustrated if len(illustrated)>=8 else ordered)[:64]

def edit(data,user):
 if not user:raise PermissionError('Please sign in.')
 ident=data.get('id')
 if not isinstance(ident,str) or not re.fullmatch('[a-f0-9]{32}',ident):raise ValueError('Choose a valid song.')
 with LOCK,connect() as db:
  row=db.execute('SELECT * FROM tracks WHERE id=?',(ident,)).fetchone()
  if not row:raise LookupError('Song not found.')
  if user.get('role')!='super' and row['owner']!=user.get('id'):raise PermissionError('You can edit only songs you uploaded.')
  fields={}
  for key in ('title','artist','album','genre','year','track'):
   value=data.get(key,row[key])
   if not isinstance(value,str) or len(value)>500:raise ValueError('Use text of 500 characters or fewer.')
   fields[key]=value.strip()
  if not fields['title']:raise ValueError('Enter a song title.')
  tags=data.get('tags',json.loads(row['tags']))
  if not isinstance(tags,list) or len(tags)>30 or any(not isinstance(t,str) or not t.strip() or len(t)>60 for t in tags):raise ValueError('Use up to 30 tags of 60 characters each.')
  fields['tags']=json.dumps(list(dict.fromkeys(t.strip() for t in tags)))
  fields['tagState']='manual';fields['tagRevision']=uuid.uuid4().hex
  db.execute('UPDATE tracks SET '+','.join(key+'=?' for key in fields)+' WHERE id=?',(*fields.values(),ident))
 return {'saved':True}
def queue_tags(ident,user):
 if not isinstance(ident,str) or not re.fullmatch('[a-f0-9]{32}',ident):raise ValueError('Choose a valid song.')
 with connect() as db:
  row=db.execute('SELECT owner FROM tracks WHERE id=?',(ident,)).fetchone()
  if not row:raise LookupError('Song not found.')
  if not user or (user.get('role')!='super' and row['owner']!=user.get('id')):raise PermissionError('You can edit only songs you uploaded.')
  db.execute("UPDATE tracks SET tagState='queued',tagRevision=?,tagStarted=0 WHERE id=?",(uuid.uuid4().hex,ident))
 return {'queued':True}
def remove(ident,user):
 if not isinstance(ident,str) or not re.fullmatch('[a-f0-9]{32}',ident):raise ValueError('Choose a valid song.')
 with LOCK,connect() as db:
  row=db.execute('SELECT owner FROM tracks WHERE id=?',(ident,)).fetchone()
  if not row:raise LookupError('Song not found.')
  if not user or (user.get('role')!='super' and row['owner']!=user.get('id')):raise PermissionError('You can remove only songs you uploaded.')
  db.execute("UPDATE tracks SET removedAt=?,tagState='manual',tagRevision=? WHERE id=?",(time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),uuid.uuid4().hex,ident))
 return {'removed':True,'id':ident}

def delete_file(data,user):
 if not user or user.get('role')!='super':raise PermissionError('Only super users can permanently delete files.')
 ident=data.get('id')
 if not isinstance(ident,str) or not re.fullmatch('[a-f0-9]{32}',ident):raise ValueError('Choose a valid song.')
 with LOCK,connect() as db:
  row=db.execute('SELECT * FROM tracks WHERE id=?',(ident,)).fetchone()
  if not row:raise LookupError('Song not found.')
  if data.get('confirmTitle')!=row['title']:raise ValueError('Enter the exact recording title to confirm deletion.')
  paths=[ROOT/'tracks'/(ident+'.mp3'),ROOT/'covers'/(ident+'.jpg')]
  root=ROOT.resolve()
  for path in paths:
   if not path.parent.resolve().is_relative_to(root):raise ValueError('Managed storage path is invalid.')
  freed=0
  for path in paths:
   if path.exists() or path.is_symlink():
    size=path.lstat().st_size;path.unlink();freed+=size
  now=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())
  db.execute("UPDATE tracks SET removedAt=?,purgedAt=?,bytes=0,cover='',tagState='manual',tagRevision=? WHERE id=?",(now,now,uuid.uuid4().hex,ident))
 return {'deleted':True,'id':ident,'bytesRemoved':freed}

def post(handler):
 if not handler.allowed():return
 user=handler.user()
 if not user:return handler.reply(401,{'error':'Music uploads require a signed-in account.'})
 try:
  length=int(handler.headers.get('Content-Length','0'))
  if handler.path.endswith(('/metadata','/classify','/remove','/delete')):
   if not 0<length<=16384:raise ValueError('Invalid metadata request.')
   data=json.loads(handler.rfile.read(length))
   if not isinstance(data,dict):raise ValueError('Invalid metadata request.')
   if handler.path.endswith('/delete'):return handler.reply(200,delete_file(data,user))
   if handler.path.endswith('/remove'):return handler.reply(200,remove(data.get('id'),user))
   return handler.reply(200,queue_tags(data.get('id'),user) if handler.path.endswith('/classify') else edit(data,user))
  if handler.path!='/api/library/music/upload':return handler.reply(404,{'error':'Not found'})
  if not 0<length<=MAX_BYTES:return handler.reply(413,{'error':'Choose an MP3 up to 200 MB.'})
  name=unquote(handler.headers.get('X-File-Name','')).replace('\\','/').rsplit('/',1)[-1][:240]
  if not name.lower().endswith('.mp3'):return handler.reply(415,{'error':'Choose MP3 audio files.'})
  with connect():pass
  if shutil.disk_usage(ROOT).free<length*2+1024**3:return handler.reply(507,{'error':'Not enough disk space.'})
  handler.connection.settimeout(180)
  with tempfile.NamedTemporaryFile(dir=ROOT/'staging',suffix='.mp3') as f:
   left=length
   while left:
    chunk=handler.rfile.read(min(left,1024**2))
    if not chunk:raise ValueError('Upload interrupted. Choose this file again to retry.')
    f.write(chunk);left-=len(chunk)
   f.flush();result=add_file(Path(f.name),name,user['id'])
  if result.get('status')=='added':
   try:
    import music_art
    with music_art.connect() as db:row=db.execute('SELECT * FROM tracks WHERE id=?',(result['id'],)).fetchone()
    if row and not row['cover']:music_art.enqueue({'ids':[row['id']],'album':row['album'],'artist':row['albumArtist'] or ('Various Artists' if inferred_compilation(row) else row['artist'])})
   except Exception:pass
  return handler.reply(200,result)
 except PermissionError as exc:return handler.reply(403,{'error':str(exc)})
 except LookupError as exc:return handler.reply(404,{'error':str(exc)})
 except (ValueError,json.JSONDecodeError) as exc:return handler.reply(422,{'error':str(exc)})
