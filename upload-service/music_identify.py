"""Manual audio identification: private setup, queued review, explicit field application."""
import json,os,time,uuid,re,shutil,hashlib
from pathlib import Path
import music,music_grouping,music_art
SNAP=('title','artist','album','albumArtist','genre','year','track','disc','compilation','tags','cover','removedAt','purgedAt','tagRevision','manualAlbumGroup','manualAlbumTitle','manualAlbumArtist','manualAlbumCoverId')
def settings_path():return music.ROOT/'identification-settings.json'
def settings():
 try:return json.loads(settings_path().read_text())
 except (OSError,ValueError):return {}
def connect():
 db=music.connect();db.execute("CREATE TABLE IF NOT EXISTS identification_jobs(id TEXT PRIMARY KEY,owner INTEGER,source TEXT,targets TEXT,snapshot TEXT,state TEXT,message TEXT,candidates TEXT,chosen INTEGER DEFAULT -1,details TEXT DEFAULT '{}',created REAL,updated REAL)")
 db.execute('CREATE TABLE IF NOT EXISTS identification_status(id INTEGER PRIMARY KEY,online INTEGER,checked REAL,message TEXT)')
 return db
def snapshot(rows):return {r['id']:{k:r[k] for k in SNAP} for r in rows}
def permitted(rows,user):
 if not user:raise PermissionError('Please sign in.')
 if user.get('role')!='super' and any(r['owner']!=user['id'] for r in rows):raise PermissionError('You can apply changes only to recordings you uploaded. A super user can edit the shared library.')
def identifier(value):
 if not isinstance(value,str) or not re.fullmatch('[a-f0-9]{32}',value):raise ValueError('Choose a recording from this album.')
 return value
def status(user):
 with connect() as db:
  health=db.execute('SELECT * FROM identification_status WHERE id=1').fetchone();jobs=[dict(r) for r in db.execute('SELECT id,source,state,message,candidates,chosen,details,created FROM identification_jobs WHERE owner=? ORDER BY created DESC LIMIT 8',(user['id'],))]
 for job in jobs:
  job['candidates']=json.loads(job['candidates']);job['details']=json.loads(job['details'])
 fresh=bool(health and time.time()-health['checked']<100)
 return {'online':bool(fresh and health['online']),'checking':not fresh,'message':health['message'] if fresh else 'Checking online recognition services…','configured':bool(settings().get('client')),'fingerprinting':bool(shutil.which('fpcalc')),'canConfigure':user.get('role')=='super','jobs':jobs}
def start(data,user):
 ident=identifier(data.get('id'))
 scope=data.get('scope','album')
 if scope not in ('track','album'):raise ValueError('Choose track or album identification.')
 if not settings().get('client'):raise ValueError('Set an AcoustID application API key first.')
 if not shutil.which('fpcalc'):raise ValueError('The fingerprinting tool is not installed. Run the identification installer.')
 with connect() as db:
  health=db.execute('SELECT * FROM identification_status WHERE id=1').fetchone()
  if not health or not health['online'] or time.time()-health['checked']>100:raise ValueError('Online recognition is unavailable. Check MAHA’s internet connection and try again.')
  rows=[dict(r) for r in db.execute("SELECT * FROM tracks WHERE removedAt='' AND purgedAt=''")];index={r['id']:r for r in rows}
  if ident not in index:raise LookupError('Recording no longer available.')
  permitted([index[ident]],user)
  if scope=='track':group=[index[ident]]
  else:
   music.annotate_compilations(rows);music_grouping.annotate(rows,music.inferred_compilation);group=[index[ident]] if index[ident].get('unknownSingles') else [r for r in rows if r['groupKey']==index[ident]['groupKey']]
  if len(group)>1000:raise ValueError('This album has more than 1,000 recordings. Open a track’s actions and choose Identify this track instead.')
  previous=db.execute("SELECT id FROM identification_jobs WHERE owner=? AND state IN ('queued','running','details_queued','loading_details')",(user['id'],)).fetchone()
  if previous:raise ValueError('Your previous identification is still running. Wait for it to finish.')
  previous=db.execute("SELECT id FROM identification_jobs WHERE owner=? AND source=? AND snapshot=? AND state IN ('review','ready') AND created>? ORDER BY created DESC LIMIT 1",(user['id'],ident,json.dumps(snapshot(group)),time.time()-86400)).fetchone()
  if previous:return {'id':previous['id'],'cached':True}
  job=uuid.uuid4().hex;db.execute('INSERT INTO identification_jobs(id,owner,source,targets,snapshot,state,message,candidates,created,updated) VALUES(?,?,?,?,?,?,?,?,?,?)',(job,user['id'],ident,json.dumps([r['id'] for r in group]),json.dumps(snapshot(group)),'queued','Waiting for audio fingerprint lookup.','[]',time.time(),time.time()))
 return {'id':job}
def choose(data,user):
 with connect() as db:
  db.execute('BEGIN IMMEDIATE');job=db.execute('SELECT * FROM identification_jobs WHERE id=? AND owner=?',(data.get('id'),user['id'])).fetchone()
  if not job or job['state'] not in ('review','ready'):raise ValueError('Wait for recognition results or start a new lookup.')
  candidates=json.loads(job['candidates']);index=data.get('candidate')
  if type(index)!=int or not 0<=index<len(candidates):raise ValueError('Choose a matching release.')
  db.execute("UPDATE identification_jobs SET chosen=?,state='details_queued',message='Loading release tracks and artwork…',details='{}',updated=? WHERE id=?",(index,time.time(),job['id']))
 return {'queued':True}
def apply(data,user):
 fields=data.get('fields');allowed={'title','artist','track','disc','genre','album','albumArtist','year','compilation','tags'}
 if not isinstance(fields,list) or any(not isinstance(k,str) or k not in allowed for k in fields):raise ValueError('Choose which metadata fields to apply.')
 cover=data.get('artwork') is True
 if not fields and not cover:raise ValueError('Select at least one metadata field or artwork.')
 scope=data.get('scope');art_scope=data.get('artScope')
 if scope not in ('track','album') or art_scope not in ('track','album'):raise ValueError('Choose a track or album scope.')
 originals=[];changed=[]
 with music.LOCK:
  try:
   with connect() as db:
    db.execute('BEGIN IMMEDIATE');job=db.execute('SELECT * FROM identification_jobs WHERE id=? AND owner=?',(data.get('id'),user['id'])).fetchone()
    if not job or job['state']!='ready':raise ValueError('Load the matching release before applying changes.')
    detail=json.loads(job['details']);matches=detail['matches'];match_index=data.get('match',0)
    if type(match_index)!=int or not 0<=match_index<len(matches):raise ValueError('Choose the matching release track.')
    proposed={**detail['albumFields'],**matches[match_index]};target_ids=json.loads(job['targets']);rows=[dict(r) for r in db.execute('SELECT * FROM tracks WHERE id IN ('+','.join('?' for _ in target_ids)+')',target_ids)];by_id={r['id']:r for r in rows};source=by_id.get(job['source'])
    if not source:raise ValueError('Source recording is unavailable.')
    album_fields={'album','albumArtist','year','compilation'}
    metadata_ids=set(target_ids if scope=='album' and any(k in album_fields for k in fields) else [source['id']] if fields else [])
    artwork_ids=set(target_ids if art_scope=='album' else [source['id']]) if cover else set();ids=metadata_ids|artwork_ids
    if any(i not in by_id or by_id[i]['removedAt'] or by_id[i]['purgedAt'] for i in ids):raise ValueError('Some recordings are no longer available. Start a new lookup.')
    permitted([by_id[i] for i in ids],user);expected=json.loads(job['snapshot'])
    if any({k:by_id[i][k] for k in SNAP}!=expected[i] for i in ids):raise ValueError('Metadata or artwork changed since this lookup. Identify the recording again before applying.')
    prepared={}
    for ident in metadata_ids:
     row=by_id[ident];values={}
     for key in fields:
      if key not in album_fields and ident!=source['id']:continue
      value=proposed.get(key)
      if key=='tags':
       existing=json.loads(row['tags']);value=[];seen=set()
       for tag in existing+detail.get('suggestedTags',[]):
        if not isinstance(tag,str) or not tag.strip() or len(tag)>60:raise ValueError('A suggested tag is invalid.')
        if tag.strip().casefold() not in seen:value.append(tag.strip());seen.add(tag.strip().casefold())
       if len(value)>30:raise ValueError('Applying these genre tags would exceed 30 tags.')
       values['tags']=json.dumps(value);continue
      if key=='compilation':values[key]=int(bool(value));continue
      if not isinstance(value,str) or not value.strip() or len(value)>500:raise ValueError('The selected field '+key+' has no valid proposed value.')
      values[key]=value.strip()
     if row['manualAlbumGroup'] and any(k in values for k in ('album','albumArtist')):
      if scope=='album':
       if 'album' in values:values['manualAlbumTitle']=values['album']
       if 'albumArtist' in values:values['manualAlbumArtist']=values['albumArtist']
      else:values.update({k:'' for k in ('manualAlbumGroup','manualAlbumTitle','manualAlbumArtist','manualAlbumCoverId')})
     if values:values.update(tagState='manual',tagRevision=uuid.uuid4().hex)
     prepared[ident]=values
    image=None
    if cover:
     name=detail.get('cover','').rsplit('/',1)[-1]
     if not re.fullmatch(r'art-[a-f0-9]{24}\.jpg',name):raise ValueError('No artwork is available for this release.')
     image=(music.ROOT/'covers'/name).read_bytes()
    # Backups permit restoring filesystem writes if any later operation fails.
    backup=music.ROOT/'identification-backups'/job['id'];backup.mkdir(parents=True,exist_ok=True)
    (backup/'metadata-before.json').write_text(json.dumps({i:{k:by_id[i][k] for k in SNAP} for i in ids}),encoding='utf-8')
    for ident in artwork_ids:
     destination=music.ROOT/'covers'/(ident+'.jpg');original=destination.read_bytes() if destination.exists() else None;originals.append((destination,original));temporary=destination.with_suffix('.'+uuid.uuid4().hex+'.tmp');temporary.write_bytes(image);os.replace(temporary,destination)
     if original is not None:(backup/(ident+'.jpg')).write_bytes(original)
     values=prepared.setdefault(ident,{});values.update(cover='/music-media/covers/'+ident+'.jpg?v='+hashlib.sha256(image).hexdigest()[:12],artKind='archive',artSource=detail['source'])
    for ident,values in prepared.items():
     if values:db.execute('UPDATE tracks SET '+','.join(k+'=?' for k in values)+' WHERE id=?',(*values.values(),ident));changed.append(ident)
    db.execute("UPDATE identification_jobs SET state='applied',message=?,updated=? WHERE id=?",('Applied selected fields and artwork to '+str(len(ids))+' recordings.',time.time(),job['id']))
  except Exception:
   for path,original in originals:
    if original is None:path.unlink(missing_ok=True)
    else:path.write_bytes(original)
   raise
 return {'applied':True,'count':len(changed)}
def handle(handler):
 user=handler.user()
 if not user:return handler.reply(401,{'error':'Please sign in.'})
 try:
  if handler.command=='GET':return handler.reply(200,status(user))
  length=int(handler.headers.get('Content-Length','0'))
  if not 0<length<=16384:raise ValueError('Invalid identification request.')
  data=json.loads(handler.rfile.read(length))
  if not isinstance(data,dict):raise ValueError('Invalid request.')
  action=data.get('action')
  if action=='settings':
   if user.get('role')!='super':raise PermissionError('Only super users can configure recognition.')
   key=data.get('client')
   if not isinstance(key,str) or not re.fullmatch('[A-Za-z0-9_-]{6,128}',key):raise ValueError('Enter your AcoustID application API key.')
   path=settings_path();temporary=path.with_suffix('.tmp');temporary.write_text(json.dumps({'client':key}));os.chmod(temporary,0o600);os.replace(temporary,path);return handler.reply(200,{'saved':True})
  function={'start':start,'choose':choose,'apply':apply}.get(action)
  if not function:raise ValueError('Choose an identification action.')
  return handler.reply(200,function(data,user))
 except PermissionError as e:return handler.reply(403,{'error':str(e)})
 except LookupError as e:return handler.reply(404,{'error':str(e)})
 except (ValueError,TypeError) as e:return handler.reply(422,{'error':str(e)})
