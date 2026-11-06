"""MAHA LAN book imports. Originals are immutable; catalog commits are atomic."""
import hashlib, io, json, os, posixpath, re, shutil, subprocess, tempfile, threading, time, zipfile
from pathlib import Path
from urllib.parse import unquote, urlsplit
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import xml.etree.ElementTree as ET
from PIL import Image, ImageOps
from classification import Classifier, CATEGORIES
import accounts
import access_workflow
import collection_controls
import music
import music_tag_worker
import music_art
import music_bulk
import music_identify
import music_merges
import personal_library
import music_downloads
from http.cookies import SimpleCookie

ROOT=Path(os.environ.get('MAHA_IMPORT_ROOT','/mnt/data/survival-library/imported-books'))
STATIC=Path(os.environ.get('MAHA_STATIC_ROOT','/srv/www/maha-library/current/dist'))
ASSETS=Path(os.environ.get('MAHA_ASSET_MAP','/mnt/data/projects/maha-library/asset-map.json'))
MAX_BYTES=1024**3
AUTH_REQUIRED=os.environ.get('MAHA_REQUIRE_AUTH')=='1'
LOCK=threading.Lock()
class _State:
    def __getattr__(self,name):return globals()[name]
CLASSIFIER=Classifier(_State())

def load_imports():
    p=ROOT/'catalog.json'
    return json.loads(p.read_text()) if p.exists() else []

def useful_title(title,name):
    clean=(title or '').strip()
    if clean.casefold() in {'','my document','document','untitled','untitled document','microsoft word'}:
        return re.sub(r'[_\s]+',' ',Path(name).stem).strip() or 'Untitled book'
    return clean

def catalog():
    books=json.loads((STATIC/'catalog.json').read_text())+load_imports()
    path=ROOT/'book-metadata.json';metadata=json.loads(path.read_text()) if path.exists() else {}
    for book in books:
        if book.get('originalName'):book['title']=useful_title(book.get('title'),book['originalName'])
        book.update(metadata.get(book['id'],{}))
    return CLASSIFIER.overlay(books)

def edit_metadata(ident,title,author):
    if not isinstance(title,str) or not title.strip() or len(title)>500:raise ValueError('Enter a title of 1–500 characters.')
    if not isinstance(author,str) or len(author)>500:raise ValueError('Use an author of up to 500 characters.')
    with LOCK:
        path=ROOT/'book-metadata.json';data=json.loads(path.read_text()) if path.exists() else {}
        data[ident]={'title':title.strip(),'author':author.strip() or 'Author not listed'}
        pending=path.with_suffix('.tmp');pending.write_text(json.dumps(data,ensure_ascii=False,indent=2));os.replace(pending,path)
    return data[ident]

def epub_metadata(path):
    with zipfile.ZipFile(path) as z:
        if len(z.infolist())>30000 or sum(i.file_size for i in z.infolist())>2*1024**3:
            raise ValueError('This ebook is too large to process safely.')
        def read(member,limit=24*1024**2):
            info=z.getinfo(member)
            if info.file_size>limit:raise ValueError('An ebook metadata or cover file is too large.')
            return z.read(member)
        container=ET.fromstring(read('META-INF/container.xml'))
        opf=next(e.attrib['full-path'] for e in container.iter() if e.tag.endswith('rootfile'))
        package=ET.fromstring(read(opf));items=[e for e in package.iter() if e.tag.endswith('}item')]
        if not any(e.tag.endswith('}spine') for e in package.iter()):raise ValueError('EPUB has no reading order.')
        title=next((e.text for e in package.iter() if e.tag.endswith('}title') and e.text),'')
        author='; '.join(e.text for e in package.iter() if e.tag.endswith('}creator') and e.text)
        cover_id=next((e.attrib.get('content') for e in package.iter() if e.tag.endswith('}meta') and e.attrib.get('name')=='cover'),None)
        candidates=[i for i in items if 'cover-image' in i.attrib.get('properties','').split() or i.attrib.get('id')==cover_id]
        candidates += [i for i in items if i.attrib.get('media-type','').startswith('image/') and 'cover' in i.attrib.get('href','').lower() and i not in candidates]
        cover=None
        for item in candidates:
            try:
                member=posixpath.normpath(posixpath.join(posixpath.dirname(opf),unquote(item.attrib['href'].split('#')[0])))
                cover=Image.open(io.BytesIO(read(member)));cover.load();break
            except Exception:cover=None
        return title,author,cover

def run(args,timeout=90,env=None):
    return subprocess.run(args,check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=timeout,env=env)

def existing_duplicate(path,digest):
    size=path.stat().st_size
    books=catalog()
    for b in books:
        if b.get('sha256')==digest:return b
    if ASSETS.exists():
        for a in json.loads(ASSETS.read_text()).get('assets',[]):
            p=Path(a['remote'])
            try:
                if p.stat().st_size!=size:continue
                with p.open('rb') as f:other=hashlib.file_digest(f,'sha256').hexdigest()
                if other==digest:
                    return next((b for b in books if any(s['url']==a['url'] for s in b.get('sources',[]))),{'title':p.stem})
            except OSError:continue
    return None

def import_book(path,name,topic,digest):
    duplicate=existing_duplicate(path,digest)
    if duplicate:return {'status':'skipped','message':'Already in the library','title':duplicate['title'],'id':duplicate.get('id')}
    ext=Path(name).suffix.lower();ident='import-'+digest[:24]
    with tempfile.TemporaryDirectory(dir=ROOT/'staging') as td:
        work=Path(td);reading=path;cover=None;title='';author=''
        if ext=='.mobi':
            reading=work/'converted.epub';env=dict(os.environ,QT_QPA_PLATFORM='offscreen',CALIBRE_CONFIG_DIRECTORY=str(work/'calibre-config'),HOME=str(work))
            run(['ebook-convert',str(path),str(reading)],timeout=300,env=env)
        if ext in {'.epub','.mobi'}:
            title,author,cover=epub_metadata(reading);fmt='EPUB'
        else:
            if path.open('rb').read(5)!=b'%PDF-':raise ValueError('This file is not a valid PDF.')
            info=run(['pdfinfo',str(path)]).stdout.decode('utf-8','replace')
            fields={line.split(':',1)[0]:line.split(':',1)[1].strip() for line in info.splitlines() if ':' in line}
            title=fields.get('Title','');author=fields.get('Author','');fmt='PDF'
            if fields.get('Encrypted','').startswith('yes'):raise ValueError('Password-protected PDFs cannot be imported.')
            try:
                run(['pdftoppm','-f','1','-singlefile','-scale-to','900','-jpeg',str(path),str(work/'cover')])
                cover=Image.open(work/'cover.jpg');cover.load()
            except Exception:cover=None
        original=ROOT/'originals'/(ident+ext);shutil.copyfile(path,original)
        source=original
        if ext=='.mobi':
            source=ROOT/'readable'/(ident+'.epub');shutil.copyfile(reading,source)
        entry={'id':ident,'title':useful_title(title,name)[:500],'author':author.strip()[:500] or 'Author not listed','topic':topic,'format':fmt,'sources':[{'format':fmt,'url':'/uploads/'+str(source.relative_to(ROOT))}],'sha256':digest,'originalName':name,'originalUrl':'/uploads/'+str(original.relative_to(ROOT)),'importedAt':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())}
        if cover is not None:
            try:
                cover=ImageOps.exif_transpose(cover).convert('RGB');cover.thumbnail((640,960))
                cover.save(ROOT/'covers'/(ident+'.jpg'),quality=85,optimize=True)
                entry['cover']='/uploads/covers/'+ident+'.jpg'
            except Exception:pass
        entry['topic']='To be sorted';entry['tags']=[]
        entries=load_imports();entries.append(entry)
        pending=ROOT/'catalog.json.tmp';pending.write_text(json.dumps(entries,ensure_ascii=False,indent=2));os.replace(pending,ROOT/'catalog.json')
        try:CLASSIFIER.queue(ident)
        except Exception:pass  # A sorting failure must never fail a completed import.
        return {'status':'added','title':entry['title'],'id':ident,'message':'Added to library; sorting in background'}

class Handler(BaseHTTPRequestHandler):
    def user(self):
        cookie=SimpleCookie()
        try:cookie.load(self.headers.get('Cookie',''))
        except Exception:return None
        return accounts.session(cookie['maha_session'].value) if 'maha_session' in cookie else None
    def token(self):
        cookie=SimpleCookie();cookie.load(self.headers.get('Cookie',''))
        return cookie['maha_session'].value if 'maha_session' in cookie else ''
    def allowed(self,superuser=False):
        if not AUTH_REQUIRED:return True
        user=self.user()
        if not user:self.reply(401,{'error':'Please sign in.'});return False
        if superuser and user['role']!='super':self.reply(403,{'error':'Super user access is required.'});return False
        return True
    def reply(self,status,data):
        raw=json.dumps(data,ensure_ascii=False).encode();self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(raw)));self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff')
        if getattr(self,'catalog_etag',None):self.send_header('ETag',self.catalog_etag);self.catalog_etag=None
        if getattr(self,'set_cookie',None):self.send_header('Set-Cookie',self.set_cookie)
        self.end_headers();self.wfile.write(raw)
    def do_GET(self):
        if self.path=='/api/library/health':return self.reply(200,{'ready':True,'mobi':bool(shutil.which('ebook-convert')),'accessWorkflow':True,'collectionControls':True,'bookMetadata':True,'music':True,'musicDownloads':True,'musicDiscoveries':True,'personalLibrary':True,'albumMerges':True,'musicIdentification':True})
        if self.path=='/api/library/session':return self.reply(200,{'enabled':AUTH_REQUIRED,'user':self.user() if AUTH_REQUIRED else None,'secureUrl':os.environ.get('MAHA_PUBLIC_URL','')})
        if self.path=='/api/library/auth-check':return self.reply(200 if not AUTH_REQUIRED or self.user() else 401,{})
        if not self.allowed():return
        if self.path=='/api/library/access':
            if not AUTH_REQUIRED:return self.reply(409,{'error':'Enable library accounts first.'})
            if self.allowed(True):return self.reply(200,access_workflow.overview())
            return
        if self.path=='/api/library/trust-certificate':
            path=Path('/mnt/data/projects/maha-library/maha-local-root-ca.crt')
            if not path.is_file():return self.reply(404,{'error':'The public trust certificate is not available.'})
            raw=path.read_bytes();self.send_response(200);self.send_header('Content-Type','application/x-x509-ca-cert');self.send_header('Content-Disposition','attachment; filename="MAHA-Local-Root-CA.crt"');self.send_header('Content-Length',str(len(raw)));self.send_header('X-Content-Type-Options','nosniff');self.end_headers();self.wfile.write(raw);return
        if self.path=='/api/library/users':
            if self.allowed(True):return self.reply(200,accounts.users())
            return
        if self.path in ('/api/library/books','/api/library/kiwix','/api/library/removed-books','/api/library/hidden-kiwix'):
            kind='kiwix' if 'kiwix' in self.path else 'book'
            removed=self.path in ('/api/library/removed-books','/api/library/hidden-kiwix')
            if removed and not self.allowed(True):return
            rows=collection_controls.archives() if kind=='kiwix' else catalog()
            hidden=collection_controls.hidden(kind) if AUTH_REQUIRED else set()
            return self.reply(200,[b for b in rows if (b['id'] in hidden)==removed])
        if self.path=='/api/library/music/discoveries':return self.reply(200,music.discovery_candidates())
        if self.path.startswith('/api/library/music/download/'):return music_downloads.stream(self)
        if self.path=='/api/library/music':
            user=self.user();etag=music.catalog_etag(user)
            if self.headers.get('If-None-Match')==etag:
                self.send_response(304);self.send_header('ETag',etag);self.send_header('Cache-Control','private, no-cache');self.end_headers();return
            self.catalog_etag=etag
            return self.reply(200,music.catalog(user))
        if self.path=='/api/library/music/identify':return music_identify.handle(self)
        if self.path=='/api/library/music/merges':return music_merges.handle(self)
        if self.path=='/api/library/personal':return personal_library.handle(self)
        if self.path=='/api/library/categories':return self.reply(200,{'categories':CATEGORIES})
        self.reply(404,{'error':'Not found'})
    def do_POST(self):
        origin=urlsplit(self.headers.get('Origin',''))
        if origin.scheme not in {'http','https'} or origin.netloc!=self.headers.get('Host') or self.headers.get('X-Maha-Upload')!='1':
            return self.reply(403,{'error':'Open Add books from your MAHA library website.'})
        try:
            if self.path in ('/api/library/login','/api/library/accept-invite','/api/library/logout','/api/library/invite','/api/library/user','/api/library/access-person','/api/library/vpn-device','/api/library/access-disable','/api/library/invite-revoke'):
                if not AUTH_REQUIRED:return self.reply(409,{'error':'Accounts are not enabled yet.'})
                size=int(self.headers.get('Content-Length','0'))
                if not 0<size<=16384:return self.reply(400,{'error':'Invalid request'})
                data=json.loads(self.rfile.read(size))
                if self.path.endswith('/login'):
                    user,token=accounts.login(data.get('email'),data.get('password'),self.headers.get('X-Real-IP',self.client_address[0]))
                    self.set_cookie='maha_session='+token+'; Path=/; HttpOnly; SameSite=Strict; Secure; Max-Age=604800'
                    return self.reply(200,user)
                if self.path.endswith('/accept-invite'):
                    accounts.accept(data.get('token',''),data.get('password'));return self.reply(200,{'accepted':True})
                if self.path.endswith('/logout'):
                    accounts.logout(self.token());self.set_cookie='maha_session=; Path=/; HttpOnly; SameSite=Strict; Secure; Max-Age=0';return self.reply(200,{})
                if not self.allowed(True):return
                actor=self.user()['id']
                if self.path.endswith('/access-person'):return self.reply(200,access_workflow.save_person(data,actor))
                if self.path.endswith('/vpn-device'):return self.reply(200,access_workflow.save_device(data,actor))
                if self.path.endswith('/access-disable'):return self.reply(200,access_workflow.disable_access(data.get('email'),actor))
                if self.path.endswith('/invite-revoke'):return self.reply(200,access_workflow.revoke_invite(data.get('email'),actor))
                if self.path.endswith('/invite'):
                    access_workflow.save_person({'email':data.get('email'),'role':data.get('role'),'mode':data.get('mode','local')},actor)
                    token=accounts.invite(data.get('email'),data.get('role'))
                    access_workflow.record_event(actor,data.get('email'),'Library invitation created: '+data.get('role'))
                    return self.reply(200,{'token':token,'expiresInDays':7})
                target=next((u for u in accounts.users() if u['id']==data.get('id')),None)
                accounts.update_user(data.get('id'),data.get('role'),data.get('active'),actor)
                if target and not data.get('active'):access_workflow.disable_access(target['email'],actor)
                if target:access_workflow.record_event(actor,target['email'],'Account settings updated: '+data.get('role')+(' enabled' if data.get('active') else ' disabled'))
                return self.reply(200,{})
            if self.path=='/api/library/music/identify':return music_identify.handle(self)
            if self.path=='/api/library/music/merges':return music_merges.handle(self)
            if self.path=='/api/library/personal':return personal_library.handle(self)
            if self.path=='/api/library/music/download':
                if not self.allowed():return
                user=self.user()
                if not user:return self.reply(401,{'error':'Please sign in.'})
                size=int(self.headers.get('Content-Length','0'))
                if not 0<size<=65536:raise ValueError('Invalid download request.')
                data=json.loads(self.rfile.read(size))
                if not isinstance(data,dict):raise ValueError('Invalid download request.')
                return self.reply(200,music_downloads.create(data,user))
            if self.path in ('/api/library/music/bulk','/api/library/music/bulk-preview'):return music_bulk.handle(self)
            if self.path in ('/api/library/music/art/lookup','/api/library/music/art/status','/api/library/music/art/apply','/api/library/music/art/upload'):return music_art.handle(self)
            if self.path in ('/api/library/music/upload','/api/library/music/metadata','/api/library/music/classify','/api/library/music/remove','/api/library/music/delete'):return music.post(self)
            if not self.allowed(True):return
            if self.path=='/api/library/visibility':
                if not AUTH_REQUIRED:return self.reply(409,{'error':'Enable library accounts before managing visibility.'})
                size=int(self.headers.get('Content-Length','0'))
                if not 0<size<=16384:return self.reply(400,{'error':'Invalid request size'})
                data=json.loads(self.rfile.read(size));kind=data.get('kind');ident=data.get('id')
                rows=collection_controls.archives() if kind=='kiwix' else catalog()
                if not any(b['id']==ident for b in rows):return self.reply(404,{'error':'Item not found'})
                actor=self.user()['id'] if AUTH_REQUIRED else None
                return self.reply(200,collection_controls.set_hidden(kind,ident,data.get('hidden'),actor))
            if self.path not in ('/api/library/upload','/api/library/classification','/api/library/classify','/api/library/metadata'):return self.reply(404,{'error':'Not found'})
            if self.path in ('/api/library/classification','/api/library/classify','/api/library/metadata'):
                size=int(self.headers.get('Content-Length','0'))
                if not 0<size<=16384:return self.reply(400,{'error':'Invalid request size'})
                data=json.loads(self.rfile.read(size));ident=data.get('id')
                if not any(b['id']==ident for b in catalog()):return self.reply(404,{'error':'Book not found'})
                if self.path.endswith('/metadata'):return self.reply(200,edit_metadata(ident,data.get('title'),data.get('author','')))
                if self.path.endswith('/classify'):record=CLASSIFIER.queue(ident)
                else:record=CLASSIFIER.edit(ident,data.get('topic'),data.get('tags',[]))
                return self.reply(200,record)
            length=int(self.headers.get('Content-Length','0'))
            if length<=0 or length>MAX_BYTES:return self.reply(413,{'error':'Each book must be between 1 byte and 1 GB.'})
            name=unquote(self.headers.get('X-File-Name','')).replace('\\','/').rsplit('/',1)[-1][:240]
            if Path(name).suffix.lower() not in {'.epub','.pdf','.mobi'}:return self.reply(415,{'error':'Choose EPUB, PDF, or MOBI books.'})
            if Path(name).suffix.lower()=='.mobi' and not shutil.which('ebook-convert'):return self.reply(503,{'error':'MOBI conversion is not installed yet.'})
            topic='To be sorted'
            if not LOCK.acquire(blocking=False):return self.reply(409,{'error':'Another import is running. Try this file again shortly.'})
            try:
                if shutil.disk_usage(ROOT).free<length*3+2*1024**3:return self.reply(507,{'error':'Not enough free storage for this book.'})
                self.connection.settimeout(180)
                with tempfile.NamedTemporaryFile(dir=ROOT/'staging',suffix=Path(name).suffix) as f:
                    left=length;digest=hashlib.sha256()
                    while left:
                        chunk=self.rfile.read(min(left,1024**2))
                        if not chunk:raise ValueError('Upload was interrupted. Please retry this file.')
                        f.write(chunk);digest.update(chunk);left-=len(chunk)
                    f.flush();result=import_book(Path(f.name),name,topic,digest.hexdigest())
                self.reply(200,result)
            finally:LOCK.release()
        except subprocess.TimeoutExpired:self.reply(422,{'error':'Book processing timed out. Other files can continue.'})
        except ValueError as e:
            self.reply(422,{'error':str(e) if self.path!='/api/library/upload' else 'Could not read this book. It may be damaged, protected, or an unsupported edition.'})
        except (zipfile.BadZipFile,ET.ParseError,KeyError,StopIteration):self.reply(422,{'error':'Could not read this book. It may be damaged, protected, or an unsupported edition.'})
        except subprocess.CalledProcessError:self.reply(422,{'error':'Could not convert or read this book. Check for DRM, password protection, or damage.'})
        except (BrokenPipeError,ConnectionResetError):pass
        except Exception:
            import traceback;traceback.print_exc();self.reply(500,{'error':'Import failed. The remaining files can continue; retry this file afterward.'})

if __name__=='__main__':
    for d in ['staging','originals','readable','covers']:(ROOT/d).mkdir(parents=True,exist_ok=True)
    if AUTH_REQUIRED:accounts.initialize()
    CLASSIFIER.start()
    music_tag_worker.start()
    ThreadingHTTPServer(('127.0.0.1',int(os.environ.get('MAHA_API_PORT','8123'))),Handler).serve_forever()
