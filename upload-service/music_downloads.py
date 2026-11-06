"""Authenticated music downloads. ZIP files stream without temporary disk copies."""
import json,re,secrets,time,zipfile,shutil
from urllib.parse import quote
import music

def connect():
    db=music.connect()
    db.execute('CREATE TABLE IF NOT EXISTS music_downloads(token TEXT PRIMARY KEY,owner INTEGER,ids TEXT,title TEXT,expires REAL)')
    return db

def create(data,user):
    if not user:raise PermissionError('Please sign in to download music.')
    ids=data.get('ids');title=data.get('title','Album')
    if not isinstance(ids,list) or not 0<len(ids)<=1000 or any(not isinstance(i,str) or not re.fullmatch('[a-f0-9]{32}',i) for i in ids):raise ValueError('Choose an album to download.')
    if not isinstance(title,str) or not title.strip() or len(title)>500:raise ValueError('Invalid album title.')
    with connect() as db:
        rows=db.execute('SELECT id FROM tracks WHERE id IN ('+','.join('?' for _ in ids)+") AND removedAt='' AND purgedAt=''",ids).fetchall()
        if len(rows)!=len(set(ids)):raise ValueError('Some recordings are unavailable. Refresh the library.')
        token=secrets.token_hex(24)
        db.execute('DELETE FROM music_downloads WHERE expires<?',(time.time(),))
        db.execute('INSERT INTO music_downloads VALUES(?,?,?,?,?)',(token,user['id'],json.dumps(list(dict.fromkeys(ids))),title,time.time()+600))
    return {'url':'/api/library/music/download/'+token}

def safe_name(text):return re.sub(r'[\x00-\x1f<>:"/\\|?*]','_',text).strip(' .')[:150] or 'Recording'

def stream(handler):
    user=handler.user()
    if not user:return handler.reply(401,{'error':'Please sign in.'})
    token=handler.path.rsplit('/',1)[-1]
    if not re.fullmatch('[a-f0-9]{48}',token):return handler.reply(404,{'error':'Download not found.'})
    with connect() as db:
        ticket=db.execute('SELECT * FROM music_downloads WHERE token=? AND owner=? AND expires>?',(token,user['id'],time.time())).fetchone()
        if not ticket:return handler.reply(404,{'error':'Download expired. Please select Download album again.'})
        ids=json.loads(ticket['ids']);rows=[]
        for ident in ids:
            row=db.execute("SELECT * FROM tracks WHERE id=? AND removedAt='' AND purgedAt=''",(ident,)).fetchone()
            path=music.ROOT/'tracks'/(ident+'.mp3')
            if not row or not path.is_file() or not path.resolve().is_relative_to(music.ROOT.resolve()):return handler.reply(404,{'error':'A recording is no longer available.'})
            rows.append((dict(row),path))
    handler.send_response(200);handler.send_header('Content-Type','application/zip');handler.send_header('Content-Disposition',"attachment; filename=\"MAHA-album.zip\"; filename*=UTF-8''"+quote(safe_name(ticket['title'])+'.zip',safe=''))
    handler.send_header('Cache-Control','no-store');handler.send_header('X-Content-Type-Options','nosniff');handler.send_header('X-Accel-Buffering','no');handler.send_header('Connection','close');handler.end_headers();handler.close_connection=True
    try:
        with zipfile.ZipFile(handler.wfile,'w',compression=zipfile.ZIP_STORED,allowZip64=True) as archive:
            for index,(row,path) in enumerate(rows,1):
                name=str(index).zfill(3)+' - '+safe_name(row['artist']+' - '+row['title'])+'.mp3'
                with path.open('rb') as source,archive.open(name,'w',force_zip64=True) as dest:shutil.copyfileobj(source,dest,1024*256)
    except (BrokenPipeError,ConnectionResetError):pass
