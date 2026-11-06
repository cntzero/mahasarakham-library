"""Super-user artwork queue. Network work runs in a separate, constrained service."""
import base64,hashlib,io,json,re,time,uuid,os
from pathlib import Path
import music

def connect():
    db=music.connect()
    columns={r[1] for r in db.execute('PRAGMA table_info(tracks)')}
    for name in ('artKind','artSource'):
        if name not in columns:db.execute('ALTER TABLE tracks ADD COLUMN '+name+" TEXT DEFAULT ''")
    db.execute('CREATE TABLE IF NOT EXISTS artwork_jobs(id TEXT PRIMARY KEY, targets TEXT, album TEXT, artist TEXT, state TEXT, message TEXT, candidates TEXT, updated REAL, replaceExisting INTEGER DEFAULT 0)')
    if 'expected' not in {r[1] for r in db.execute('PRAGMA table_info(artwork_jobs)')}:db.execute("ALTER TABLE artwork_jobs ADD COLUMN expected TEXT DEFAULT '{}'")
    columns={r[1] for r in db.execute('PRAGMA table_info(artwork_jobs)')}
    for name,definition in [('attempts','INTEGER DEFAULT 0'),('nextAttempt','REAL DEFAULT 0'),('lastError',"TEXT DEFAULT ''")]:
        if name not in columns:db.execute('ALTER TABLE artwork_jobs ADD COLUMN '+name+' '+definition)
    return db

def targets(ids,db):
    if not isinstance(ids,list) or not 0<len(ids)<=1000 or any(not isinstance(i,str) or not re.fullmatch('[a-f0-9]{32}',i) for i in ids):raise ValueError('Choose a valid album.')
    rows=[dict(r) for r in db.execute('SELECT * FROM tracks WHERE id IN ('+','.join('?' for _ in ids)+") AND removedAt='' AND purgedAt=''",ids)]
    if len(rows)!=len(set(ids)):raise ValueError('Some recordings are no longer available. Refresh the library.')
    return rows

def enqueue(data):
    album=data.get('album');artist=data.get('artist')
    if not isinstance(album,str) or not album.strip() or len(album)>500 or not isinstance(artist,str) or len(artist)>500:raise ValueError('Enter an album and artist.')
    with connect() as db:
        rows=targets(data.get('ids'),db)
        previous=db.execute("SELECT id,state FROM artwork_jobs WHERE targets=? AND album=? AND artist=? AND state IN ('queued','running','waiting')",(json.dumps(sorted(r['id'] for r in rows)),album.strip(),artist.strip())).fetchone()
        if previous:
            if previous['state']=='waiting':db.execute("UPDATE artwork_jobs SET state='queued',nextAttempt=0,updated=? WHERE id=?",(time.time(),previous['id']))
            return {'id':previous['id'],'queued':True}
        ident=uuid.uuid4().hex
        db.execute('INSERT INTO artwork_jobs(id,targets,album,artist,state,message,candidates,updated,replaceExisting,expected) VALUES(?,?,?,?,?,?,?,?,?,?)',(ident,json.dumps(sorted(r['id'] for r in rows)),album.strip(),artist.strip(),'queued','Waiting for artwork lookup.','[]',time.time(),int(data.get('replaceExisting') is True),json.dumps({r['id']:r['cover'] for r in rows})))
    return {'id':ident,'queued':True}

def normalized_jpeg(raw):
    from PIL import Image,ImageOps
    if len(raw)>5*1024**2:raise ValueError('Choose a JPEG or PNG up to 5 MB.')
    try:
        with Image.open(io.BytesIO(raw)) as image:
            if image.format not in ('JPEG','PNG') or image.width*image.height>20_000_000:raise ValueError('Choose a JPEG or PNG smaller than 20 megapixels.')
            image=ImageOps.exif_transpose(image).convert('RGB');image.thumbnail((600,600));out=io.BytesIO();image.save(out,format='JPEG',quality=88);return out.getvalue()
    except (OSError,SyntaxError):raise ValueError('This image could not be read.')

def cache_image(raw):
    raw=normalized_jpeg(raw);name='art-'+hashlib.sha256(raw).hexdigest()[:24]+'.jpg';path=music.ROOT/'covers'/name
    temporary=path.with_suffix('.'+uuid.uuid4().hex+'.tmp');temporary.write_bytes(raw);os.replace(temporary,path)
    return '/music-media/covers/'+name

def apply_image(ids,url,kind,source,replace=False,expected=None):
    name=url.rsplit('/',1)[-1]
    if not re.fullmatch(r'art-[a-f0-9]{24}\.jpg',name):raise ValueError('Invalid artwork.')
    raw=(music.ROOT/'covers'/name).read_bytes();changed=0
    with music.LOCK,connect() as db:
        rows=targets(ids,db)
        for row in rows:
            if expected is not None and row['cover']!=expected.get(row['id']):continue
            if row['cover'] and row['artKind']!='generated' and not replace:continue
            dest=music.ROOT/'covers'/(row['id']+'.jpg')
            if not dest.parent.resolve().is_relative_to(music.ROOT.resolve()):raise ValueError('Invalid artwork storage.')
            temporary=dest.with_suffix('.'+uuid.uuid4().hex+'.tmp');temporary.write_bytes(raw);os.replace(temporary,dest)
            cover='/music-media/covers/'+row['id']+'.jpg?v='+hashlib.sha256(raw).hexdigest()[:12]
            db.execute('UPDATE tracks SET cover=?,artKind=?,artSource=? WHERE id=?',(cover,kind,source,row['id']));changed+=1
    return changed

def status():
    with connect() as db:
        rows=[dict(r) for r in db.execute('SELECT id,album,artist,state,message,candidates,updated,attempts,nextAttempt,lastError FROM artwork_jobs ORDER BY updated DESC LIMIT 100')]
        counts={r[0]:r[1] for r in db.execute('SELECT state,count(*) FROM artwork_jobs GROUP BY state')}
    for row in rows:row['candidates']=json.loads(row['candidates'])
    return {'jobs':rows,'counts':counts}

def handle(handler):
    if not handler.allowed(True):return
    user=handler.user()
    if not user or user.get('role')!='super':return handler.reply(403,{'error':'Artwork management requires a super user.'})
    try:
        length=int(handler.headers.get('Content-Length','0'))
        if not 0<length<=8*1024**2:raise ValueError('Artwork request is too large.')
        data=json.loads(handler.rfile.read(length))
        if not isinstance(data,dict):raise ValueError('Invalid request.')
        action=handler.path.rsplit('/',1)[-1]
        if action=='status':return handler.reply(200,status())
        if action=='lookup':return handler.reply(200,enqueue(data))
        if action=='upload':
            with connect() as db:targets(data.get('ids'),db)
            raw=base64.b64decode(data.get('image',''),validate=True);url=cache_image(raw)
            return handler.reply(200,{'changed':apply_image(data['ids'],url,'uploaded','User-supplied artwork',True)})
        if action=='apply':
            with connect() as db:
                row=db.execute('SELECT * FROM artwork_jobs WHERE id=?',(data.get('job'),)).fetchone()
            if not row:raise ValueError('Artwork lookup not found.')
            candidates=json.loads(row['candidates']);index=data.get('candidate')
            if type(index) is not int or not 0<=index<len(candidates):raise ValueError('Choose a suggested cover.')
            candidate=candidates[index]
            changed=apply_image(json.loads(row['targets']),candidate['url'],'archive',candidate['source'],bool(row['replaceExisting']),json.loads(row['expected']))
            with connect() as db:db.execute("UPDATE artwork_jobs SET state='applied',message=?,updated=? WHERE id=?",('Artwork saved to '+str(changed)+' recordings.',time.time(),row['id']))
            return handler.reply(200,{'changed':changed})
        return handler.reply(404,{'error':'Not found.'})
    except (ValueError,TypeError,KeyError) as exc:return handler.reply(422,{'error':str(exc)})
