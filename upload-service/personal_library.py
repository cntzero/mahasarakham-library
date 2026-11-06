"""Per-account favorites and ordered playlists. Never modifies media."""
import json,sqlite3,uuid,time,contextlib,os
from urllib.parse import urlsplit,parse_qs
import accounts,music
KINDS={'song','album','book','site','knowledge','game'}
@contextlib.contextmanager
def connect():
 db=sqlite3.connect(accounts.DB.with_name('personal-library.sqlite'),timeout=20);db.row_factory=sqlite3.Row
 try:
  db.executescript("CREATE TABLE IF NOT EXISTS favorites(owner INTEGER,kind TEXT,ref TEXT,payload TEXT,created REAL,PRIMARY KEY(owner,kind,ref)); CREATE TABLE IF NOT EXISTS playlists(id TEXT PRIMARY KEY,owner INTEGER,name TEXT,tracks TEXT,revision INTEGER,created REAL); CREATE UNIQUE INDEX IF NOT EXISTS playlist_names ON playlists(owner,name COLLATE NOCASE);")
  os.chmod(accounts.DB.with_name('personal-library.sqlite'),0o600)
  yield db;db.commit()
 except Exception:db.rollback();raise
 finally:db.close()
def initialize():
 with connect():pass

def user_id(user):
 if not user:raise PermissionError('Please sign in to save your favorites and playlists.')
 return user['id']
def track_rows(ids):
 result={}
 with music.connect() as db:
  for i in range(0,len(ids),800):
   batch=ids[i:i+800]
   for r in db.execute("SELECT t.id,t.title,t.artist,t.removedAt,t.purgedAt,COALESCE(NULLIF(c.cover,''),t.cover) AS cover FROM tracks t LEFT JOIN tracks c ON c.id=t.manualAlbumCoverId WHERE t.id IN ("+','.join('?' for _ in batch)+')',batch):result[r['id']]=dict(r)
 return result
def track_ids(value):
 if not isinstance(value,list) or len(value)>1000 or any(not isinstance(i,str) or len(i)!=32 or any(c not in '0123456789abcdef' for c in i) for i in value):raise ValueError('Choose up to 1,000 recordings.')
 return list(dict.fromkeys(value))
def available(ids):
 rows=track_rows(ids)
 if any(i not in rows or rows[i]['removedAt'] or rows[i]['purgedAt'] for i in ids):raise ValueError('Some recordings are no longer available. Refresh and review your selection.')
def read(user):
 owner=user_id(user)
 with connect() as db:
  favorites=[json.loads(r['payload']) for r in db.execute('SELECT payload FROM favorites WHERE owner=? ORDER BY created DESC',(owner,))]
  playlists=[dict(r) for r in db.execute('SELECT id,name,tracks,revision FROM playlists WHERE owner=? ORDER BY name COLLATE NOCASE',(owner,))]
 album_anchors={i['id']:parse_qs(urlsplit(i['url']).query).get('albumTrack',[''])[0] for i in favorites if i['kind']=='album'}
 ids=list(dict.fromkeys([i for p in playlists for i in json.loads(p['tracks'])]+[i['id'] for i in favorites if i['kind']=='song']+[i for i in album_anchors.values() if i]))
 rows=track_rows(ids) if ids else {}
 for item in favorites:
  if item['kind']=='song':
   row=rows.get(item['id']);item['available']=bool(row and not row['removedAt'] and not row['purgedAt'])
   if row:item['title']=row['title'];item['subtitle']=row['artist'];item['cover']=row.get('cover') or ''
  elif item['kind']=='album':
   row=rows.get(album_anchors.get(item['id']));item['cover']=(row.get('cover') or '') if row else ''
 for p in playlists:
  p['tracks']=[{'id':i,'title':rows.get(i,{}).get('title','Unavailable recording'),'artist':rows.get(i,{}).get('artist',''),'available':i in rows and not rows[i]['removedAt'] and not rows[i]['purgedAt']} for i in json.loads(p['tracks'])]
 return {'favorites':favorites,'playlists':playlists}
def text(value,limit,label):
 if not isinstance(value,str) or not value.strip() or len(value)>limit:raise ValueError('Enter '+label+'.')
 return value.strip()
def save(data,user):
 owner=user_id(user);action=data.get('action')
 if action=='favorite':
  item=data.get('item')
  if not isinstance(item,dict) or item.get('kind') not in KINDS:raise ValueError('Choose a library item.')
  kind=item['kind'];ref=text(item.get('id'),2048,'a valid library reference');wanted=data.get('saved')
  if not isinstance(wanted,bool):raise ValueError('Choose favorite or unfavorite.')
  if wanted:
   title=text(item.get('title'),500,'a title');url=text(item.get('url'),8192,'a local library address');parts=urlsplit(url)
   if parts.scheme or parts.netloc or '\\' in url or any(ord(c)<32 for c in url) or url.startswith('//') or not (url.startswith('/') or url.startswith(('music.html?','reader.html?','archive-reader.html?','index.html?'))):raise ValueError('Use a local library address.')
   if kind=='song':available(track_ids([ref]))
   payload={'kind':kind,'id':ref,'title':title,'url':url,'subtitle':str(item.get('subtitle',''))[:500]}
   with connect() as db:db.execute('INSERT INTO favorites VALUES(?,?,?,?,?) ON CONFLICT(owner,kind,ref) DO UPDATE SET payload=excluded.payload',(owner,kind,ref,json.dumps(payload),time.time()))
  else:
   with connect() as db:db.execute('DELETE FROM favorites WHERE owner=? AND kind=? AND ref=?',(owner,kind,ref))
 elif action=='create':
  name=text(data.get('name'),100,'a playlist name of up to 100 characters');ids=track_ids(data.get('ids',[]));available(ids)
  with connect() as db:
   if db.execute('SELECT count(*) FROM playlists WHERE owner=?',(owner,)).fetchone()[0]>=100:raise ValueError('You can create up to 100 playlists.')
   try:db.execute('INSERT INTO playlists VALUES(?,?,?,?,?,?)',(uuid.uuid4().hex,owner,name,json.dumps(ids),1,time.time()))
   except sqlite3.IntegrityError:raise ValueError('You already have a playlist with that name.')
 elif action in ('append','reorder','rename','delete'):
  with connect() as db:
   db.execute('BEGIN IMMEDIATE');row=db.execute('SELECT * FROM playlists WHERE owner=? AND id=?',(owner,data.get('id'))).fetchone()
   if not row:raise LookupError('Playlist not found.')
   if data.get('revision')!=row['revision']:raise ValueError('This playlist changed on another device. Refresh and try again.')
   if action=='delete':db.execute('DELETE FROM playlists WHERE owner=? AND id=?',(owner,row['id']))
   elif action=='rename':
    try:db.execute('UPDATE playlists SET name=?,revision=revision+1 WHERE id=?',(text(data.get('name'),100,'a playlist name of up to 100 characters'),row['id']))
    except sqlite3.IntegrityError:raise ValueError('You already have a playlist with that name.')
   else:
    old=json.loads(row['tracks']);new=track_ids(data.get('ids'))
    if action=='append':
     available(new);new=list(dict.fromkeys(old+new))
    elif not set(new).issubset(set(old)):raise ValueError('Use Add tracks to add recordings to a playlist.')
    if len(new)>1000:raise ValueError('Playlists hold up to 1,000 recordings.')
    db.execute('UPDATE playlists SET tracks=?,revision=revision+1 WHERE id=?',(json.dumps(new),row['id']))
 else:raise ValueError('Choose a favorites or playlist action.')
 return read(user)
def handle(handler):
 user=handler.user()
 if not user:return handler.reply(401,{'error':'Please sign in.'})
 try:
  if handler.command=='GET':return handler.reply(200,read(user))
  size=int(handler.headers.get('Content-Length','0'))
  if not 0<size<=128*1024:raise ValueError('Request is too large.')
  data=json.loads(handler.rfile.read(size))
  if not isinstance(data,dict):raise ValueError('Invalid request.')
  return handler.reply(200,save(data,user))
 except PermissionError as e:return handler.reply(403,{'error':str(e)})
 except LookupError as e:return handler.reply(404,{'error':str(e)})
 except (ValueError,TypeError) as e:return handler.reply(422,{'error':str(e)})
