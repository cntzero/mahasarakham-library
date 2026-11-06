"""Previewed, owner-aware album grouping overrides with conflict-checked undo."""
import json,re,time,uuid,secrets,hashlib
import music,music_grouping
FIELDS=('manualAlbumGroup','manualAlbumTitle','manualAlbumArtist','manualAlbumCoverId')
def connect():
 db=music.connect()
 db.execute('CREATE TABLE IF NOT EXISTS album_merge_previews(token TEXT PRIMARY KEY,owner INTEGER,payload TEXT,expires REAL)')
 db.execute('CREATE TABLE IF NOT EXISTS album_merge_history(id TEXT PRIMARY KEY,owner INTEGER,before TEXT,after TEXT,created REAL,undone INTEGER DEFAULT 0)')
 return db
def user_id(user):
 if not user:raise PermissionError('Please sign in.')
 return user['id']
def authorize(rows,user):
 user_id(user)
 if user.get('role')!='super' and any(r['owner']!=user['id'] for r in rows):raise PermissionError('You can merge only albums whose recordings you uploaded. A super user can merge shared albums.')
def anchor(value):
 if not isinstance(value,str) or not re.fullmatch('[a-f0-9]{32}',value):raise ValueError('Choose an album from the library.')
 return value
def groups(db,source,target):
 source=anchor(source);target=anchor(target)
 rows=[dict(r) for r in db.execute("SELECT * FROM tracks WHERE removedAt='' AND purgedAt=''")]
 music.annotate_compilations(rows);music_grouping.annotate(rows,music.inferred_compilation);index={r['id']:r for r in rows}
 if source not in index or target not in index:raise LookupError('An album is no longer available. Refresh and try again.')
 if index[source]['groupKey']==index[target]['groupKey']:raise ValueError('These recordings already belong to the same album.')
 left=[r for r in rows if r['groupKey']==index[source]['groupKey']];right=[r for r in rows if r['groupKey']==index[target]['groupKey']]
 if len(left)+len(right)>2000:raise ValueError('Merge up to 2,000 recordings at a time.')
 return left,right,index[target]
def snapshot(rows):
 fields=('id','sha256','owner','album','albumArtist','artist','title','compilation','disc','track','cover','artKind','removedAt','purgedAt',*FIELDS)
 return hashlib.sha256(json.dumps(sorted(tuple(r[k] for k in fields) for r in rows),ensure_ascii=False).encode()).hexdigest()
def preview(data,user):
 owner=user_id(user)
 with connect() as db:
  left,right,target=groups(db,data.get('source'),data.get('target'));rows=left+right;authorize(rows,user)
  token=secrets.token_hex(24);payload={'source':data['source'],'target':data['target'],'ids':sorted(r['id'] for r in rows),'snapshot':snapshot(rows)}
  db.execute('DELETE FROM album_merge_previews WHERE expires<?',(time.time(),));db.execute('INSERT INTO album_merge_previews VALUES(?,?,?,?)',(token,owner,json.dumps(payload),time.time()+600))
 return {'token':token,'sourceTitle':left[0]['groupLabel'],'targetTitle':target['groupLabel'],'targetArtist':target['displayAlbumArtist'],'sourceCount':len(left),'targetCount':len(right),'count':len(rows),'bytes':sum(r['bytes'] or 0 for r in rows),'tracks':[{'title':r['title'],'artist':r['artist']} for r in rows[:30]]}
def confirm(data,user):
 owner=user_id(user)
 with connect() as db:
  db.execute('BEGIN IMMEDIATE');ticket=db.execute('SELECT * FROM album_merge_previews WHERE token=? AND owner=? AND expires>?',(data.get('token'),owner,time.time())).fetchone()
  if not ticket:raise ValueError('Merge preview expired or already used. Review the albums again.')
  payload=json.loads(ticket['payload']);left,right,target=groups(db,payload['source'],payload['target']);rows=left+right;authorize(rows,user)
  if sorted(r['id'] for r in rows)!=payload['ids'] or snapshot(rows)!=payload['snapshot']:raise ValueError('These albums changed. Preview the merge again.')
  before={r['id']:{k:r[k] for k in FIELDS} for r in rows};ident=uuid.uuid4().hex
  after=dict(zip(FIELDS,(ident,target['groupLabel'],target['displayAlbumArtist'],target.get('manualAlbumCoverId') or target['id'])))
  db.executemany('UPDATE tracks SET '+','.join(k+'=?' for k in FIELDS)+' WHERE id=?',[(*after.values(),r['id']) for r in rows])
  db.execute('INSERT INTO album_merge_history VALUES(?,?,?,?,?,0)',(ident,owner,json.dumps(before),json.dumps(after),time.time()));db.execute('DELETE FROM album_merge_previews WHERE token=?',(data['token'],))
 return {'merged':True,'id':ident,'count':len(rows),'title':target['groupLabel']}
def undo(data,user):
 owner=user_id(user)
 with connect() as db:
  db.execute('BEGIN IMMEDIATE');event=db.execute('SELECT * FROM album_merge_history WHERE id=? AND owner=? AND undone=0',(data.get('id'),owner)).fetchone()
  if not event:raise LookupError('Merge not found or already undone.')
  before=json.loads(event['before']);after=json.loads(event['after']);ids=list(before)
  rows=[dict(r) for r in db.execute('SELECT * FROM tracks WHERE id IN ('+','.join('?' for _ in ids)+')',ids)];authorize(rows,user)
  if len(rows)!=len(ids) or any(any(r[k]!=after[k] for k in FIELDS) for r in rows):raise ValueError('This group changed after the merge. Undo its later merges first.')
  db.executemany('UPDATE tracks SET '+','.join(k+'=?' for k in FIELDS)+' WHERE id=?',[(*(before[r['id']][k] for k in FIELDS),r['id']) for r in rows]);db.execute('UPDATE album_merge_history SET undone=1 WHERE id=?',(event['id'],))
 return {'undone':True}
def history(user):
 owner=user_id(user)
 with connect() as db:return [{'id':r['id'],'title':json.loads(r['after'])['manualAlbumTitle'],'created':r['created']} for r in db.execute('SELECT * FROM album_merge_history WHERE owner=? AND undone=0 ORDER BY created DESC LIMIT 30',(owner,))]

def rename(data,user):
 user_id(user);ident=anchor(data.get('id'));name=data.get('name')
 if not isinstance(name,str) or not name.strip() or len(name)>500:raise ValueError('Enter an album name of up to 500 characters.')
 with connect() as db:
  db.execute('BEGIN IMMEDIATE');rows=[dict(r) for r in db.execute("SELECT * FROM tracks WHERE purgedAt=''")]
  music.annotate_compilations(rows);music_grouping.annotate(rows,music.inferred_compilation);source=next((r for r in rows if r['id']==ident),None)
  if not source:raise LookupError('Album no longer available.')
  if source.get('unknownSingles'):raise ValueError('The shared Unknown album collection is not an individual album. Edit or identify a track to assign its album first.')
  if source['groupKey']!=data.get('expectedGroup') or source['groupLabel']!=data.get('expectedTitle'):raise ValueError('The album changed. Close and reopen it before renaming.')
  group=[r for r in rows if r['groupKey']==source['groupKey']];authorize(group,user)
  group_id=source['manualAlbumGroup'] or uuid.uuid4().hex;cover=source['manualAlbumCoverId'] or source['id']
  db.executemany("UPDATE tracks SET album=?,manualAlbumGroup=?,manualAlbumTitle=?,manualAlbumArtist=?,manualAlbumCoverId=?,tagState='manual',tagRevision=? WHERE id=?",[(name.strip(),group_id,name.strip(),source['displayAlbumArtist'],cover,uuid.uuid4().hex,r['id']) for r in group])
 return {'renamed':True,'title':name.strip(),'count':len(group)}

def handle(handler):
 user=handler.user()
 if not user:return handler.reply(401,{'error':'Please sign in.'})
 try:
  if handler.command=='GET':return handler.reply(200,history(user))
  size=int(handler.headers.get('Content-Length','0'))
  if not 0<size<=8192:raise ValueError('Invalid merge request.')
  data=json.loads(handler.rfile.read(size))
  if not isinstance(data,dict):raise ValueError('Invalid merge request.')
  action=data.get('action');fn={'preview':preview,'merge':confirm,'undo':undo,'rename':rename}.get(action)
  if not fn:raise ValueError('Choose a merge action.')
  return handler.reply(200,fn(data,user))
 except PermissionError as e:return handler.reply(403,{'error':str(e)})
 except LookupError as e:return handler.reply(404,{'error':str(e)})
 except (ValueError,TypeError) as e:return handler.reply(422,{'error':str(e)})
