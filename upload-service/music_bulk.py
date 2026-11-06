"""Owner-aware bulk tagging/removal and expiring, user-bound deletion previews."""
import json,re,time,secrets,hashlib,uuid
import music,music_grouping

def connect():
    db=music.connect()
    db.execute('CREATE TABLE IF NOT EXISTS music_bulk_previews(token TEXT PRIMARY KEY,owner INTEGER,ids TEXT,snapshot TEXT,expires REAL)')
    db.execute('CREATE TABLE IF NOT EXISTS music_bulk_album_context(token TEXT PRIMARY KEY,context TEXT)')
    return db

def selected(ids,user,db,delete=False,limit=1000):
    if not user:raise PermissionError('Please sign in.')
    if delete and user.get('role')!='super':raise PermissionError('Permanent deletion requires a super user.')
    if not isinstance(ids,list) or not 0<len(ids)<=limit or len(set(map(str,ids)))!=len(ids) or any(not isinstance(i,str) or not re.fullmatch('[a-f0-9]{32}',i) for i in ids):raise ValueError('Select between 1 and '+format(limit,',')+' recordings.')
    rows=[dict(r) for r in db.execute('SELECT * FROM tracks WHERE id IN ('+','.join('?' for _ in ids)+") AND purgedAt=''",ids)]
    if len(rows)!=len(ids):raise ValueError('Some selected recordings are no longer available. Refresh and review the selection.')
    if user.get('role')!='super' and any(r['owner']!=user['id'] for r in rows):raise PermissionError('You can manage only recordings you uploaded. No changes were made.')
    return rows

def snapshot(rows):
    return hashlib.sha256(json.dumps(sorted((r['id'],r['sha256'],r['owner'],r['removedAt'],r['purgedAt'],r['title'],r['bytes'],r['tagRevision']) for r in rows),sort_keys=True).encode()).hexdigest()

def album_selection(ident,user,db):
    if not user or user.get('role')!='super':raise PermissionError('Permanent album deletion requires a super user.')
    if not isinstance(ident,str) or not re.fullmatch('[a-f0-9]{32}',ident):raise ValueError('Choose an album from the library.')
    rows=[dict(r) for r in db.execute("SELECT * FROM tracks WHERE purgedAt=''")]
    music.annotate_compilations(rows);music_grouping.annotate(rows,music.inferred_compilation)
    source=next((r for r in rows if r['id']==ident),None)
    if not source:raise LookupError('Album is no longer available.')
    return [r for r in rows if r['groupKey']==source['groupKey']],source

def preview(data,user):
    with connect() as db:
        context='';title=''
        if data.get('albumId'):
            rows,source=album_selection(data['albumId'],user,db);title=source['groupLabel']
            context=json.dumps({'albumId':data['albumId'],'groupKey':source['groupKey'],'title':title})
            rows=selected([r['id'] for r in rows],user,db,True,limit=50000)
        else:rows=selected(data.get('ids'),user,db,True)
        size=0
        for row in rows:
            for folder,extension in (('tracks','.mp3'),('covers','.jpg')):
                path=music.ROOT/folder/(row['id']+extension)
                if not path.parent.resolve().is_relative_to(music.ROOT.resolve()):raise ValueError('Invalid managed file path.')
                if path.exists() or path.is_symlink():size+=path.lstat().st_size
        token=secrets.token_hex(24);db.execute('DELETE FROM music_bulk_previews WHERE expires<?',(time.time(),))
        db.execute('INSERT INTO music_bulk_previews(token,owner,ids,snapshot,expires) VALUES(?,?,?,?,?)',(token,user['id'],json.dumps([r['id'] for r in rows]),snapshot(rows),time.time()+600))
        db.execute('DELETE FROM music_bulk_album_context WHERE token NOT IN (SELECT token FROM music_bulk_previews)')
        if context:db.execute('INSERT INTO music_bulk_album_context VALUES(?,?)',(token,context))
    return {'token':token,'title':title,'count':len(rows),'bytes':size,'phrase':'DELETE '+str(len(rows)),'removedCount':sum(bool(r['removedAt']) for r in rows),'recordings':[{'id':r['id'],'title':r['title'],'artist':r['artist']} for r in rows]}

def execute(data,user):
    action=data.get('action')
    if action=='delete':
        with connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT * FROM music_bulk_previews WHERE token=? AND owner=? AND expires>?',(data.get('token'),user['id'] if user else None,time.time())).fetchone()
            if not row:raise ValueError('Deletion preview expired. Review your selection again.')
            ids=json.loads(row['ids'])
            album_context=db.execute('SELECT context FROM music_bulk_album_context WHERE token=?',(data['token'],)).fetchone()
            rows=selected(ids,user,db,True,limit=50000 if album_context else 1000)
            if album_context:
                context=json.loads(album_context['context']);current,source=album_selection(context['albumId'],user,db)
                if sorted(r['id'] for r in current)!=sorted(ids) or source['groupKey']!=context['groupKey'] or source['groupLabel']!=context['title']:raise ValueError('The album changed. Preview it again before deleting. No files were deleted.')
            if data.get('confirmation')!='DELETE '+str(len(ids)):raise ValueError('Type the confirmation exactly. No files were deleted.')
            if snapshot(rows)!=row['snapshot']:raise ValueError('The selection changed. Preview it again before deleting.')
            # Validate every destination before deleting any files.
            for item in rows:
                for folder in ('tracks','covers'):
                    if not (music.ROOT/folder).resolve().is_relative_to(music.ROOT.resolve()):raise ValueError('Invalid managed storage path.')
            db.execute('DELETE FROM music_bulk_previews WHERE token=?',(data['token'],));db.execute('DELETE FROM music_bulk_album_context WHERE token=?',(data['token'],))
        completed=[];errors=[];freed=0
        for item in rows:
            try:
                result=music.delete_file({'id':item['id'],'confirmTitle':item['title']},user);freed+=result['bytesRemoved'];completed.append(item['id'])
            except Exception as exc:errors.append({'id':item['id'],'title':item['title'],'error':type(exc).__name__})
        return {'completed':completed,'errors':errors,'bytesRemoved':freed}
    if action not in ('tag','untag','remove'):raise ValueError('Choose a bulk action.')
    with music.LOCK,connect() as db:
        rows=selected(data.get('ids'),user,db)
        if action in ('tag','untag'):
            tags=data.get('tags')
            if not isinstance(tags,list) or not 0<len(tags)<=30 or any(not isinstance(t,str) or not t.strip() or len(t.strip())>60 for t in tags):raise ValueError('Enter up to 30 tags, each at most 60 characters.')
            updates=[];remove={t.strip().casefold() for t in tags}
            for row in rows:
                existing=json.loads(row['tags']);merged=[];seen=set()
                for tag in existing+(tags if action=='tag' else []):
                    tag=tag.strip();key=tag.casefold()
                    if key not in seen and not (action=='untag' and key in remove):merged.append(tag);seen.add(key)
                if len(merged)>30:raise ValueError('One selected recording would exceed 30 tags. No changes were made.')
                updates.append((json.dumps(merged),uuid.uuid4().hex,row['id']))
            db.executemany("UPDATE tracks SET tags=?,tagRevision=?,tagState='manual' WHERE id=?",updates)
        else:
            now=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())
            db.executemany("UPDATE tracks SET removedAt=?,tagRevision=?,tagState='manual' WHERE id=?",[(now,uuid.uuid4().hex,r['id']) for r in rows])
    return {'completed':[r['id'] for r in rows],'errors':[]}

def handle(handler):
    if not handler.allowed():return
    user=handler.user()
    if not user:return handler.reply(401,{'error':'Please sign in.'})
    try:
        length=int(handler.headers.get('Content-Length','0'))
        if not 0<length<=128*1024:raise ValueError('Invalid selection size.')
        data=json.loads(handler.rfile.read(length))
        if not isinstance(data,dict):raise ValueError('Invalid bulk request.')
        return handler.reply(200,preview(data,user) if handler.path.endswith('/bulk-preview') else execute(data,user))
    except PermissionError as exc:return handler.reply(403,{'error':str(exc)})
    except LookupError as exc:return handler.reply(404,{'error':str(exc)})
    except ValueError as exc:return handler.reply(422,{'error':str(exc)})
