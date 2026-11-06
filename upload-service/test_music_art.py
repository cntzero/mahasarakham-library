"""Disposable artwork fixtures: no production library writes or network calls."""
import tempfile,json,io,threading,secrets,base64
from pathlib import Path
from http.server import ThreadingHTTPServer
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from http.cookies import SimpleCookie
from PIL import Image
import music,music_art as art,music_art_worker as worker,accounts,server as app

with tempfile.TemporaryDirectory(prefix='maha-art-test-') as temp:
    music.ROOT=Path(temp)/'music';accounts.DB=Path(temp)/'accounts.sqlite';accounts.initialize();app.AUTH_REQUIRED=True
    inventory=json.loads(Path('/mnt/data/projects/maha-library/music-inventory.json').read_text())['files']
    sample=Path(min((r for r in inventory if r['status']=='include'),key=lambda r:r['bytes'])['path'])
    result=music.add_file(sample,sample.name,1);ident=result['id'];original=music.digest(sample)
    with art.connect() as db:db.execute("UPDATE tracks SET cover='' WHERE id=?",(ident,))
    image=Image.new('RGB',(64,64),'red');buf=io.BytesIO();image.save(buf,'PNG');raw=buf.getvalue();cached=art.cache_image(raw)
    assert cached.startswith('/music-media/covers/art-')
    for bad in ['http://archive.org/x','https://127.0.0.1/x','https://archive.org.evil.example/x','https://user:pass@archive.org/x','https://archive.org:8123/x']:
        try:worker.allowed_url(bad);raise AssertionError('Unsafe URL accepted')
        except ValueError:pass
    try:art.normalized_jpeg(b'not an image');raise AssertionError('Invalid image accepted')
    except ValueError:pass
    real_fetch=worker.fetch
    def fixture_fetch(url,limit=0):
        if 'musicbrainz.org/ws/2/' in url:
            return json.dumps({'release-groups':[{'id':'12345678-1234-1234-1234-123456789abc','title':'Fixture Album','first-release-date':'2000','artist-credit':[{'name':'Fixture Artist'}]}]}).encode()
        assert url=='https://coverartarchive.org/release-group/12345678-1234-1234-1234-123456789abc/front-500'
        return raw
    worker.fetch=fixture_fetch
    matched=worker.search({'id':'fixture-search','album':'Fixture Album','artist':'Fixture Artist'})
    assert len(matched)==1 and matched[0]['exact'] and matched[0]['year']=='2000'
    worker.fetch=real_fetch
    job=art.enqueue({'ids':[ident],'album':'Fixture Album','artist':'Fixture Artist'})
    assert art.enqueue({'ids':[ident],'album':'Fixture Album','artist':'Fixture Artist'})['id']==job['id']
    candidate={'title':'Fixture Album','artist':'Fixture Artist','year':'2000','url':cached,'source':'https://musicbrainz.org/release-group/fixture','exact':True}
    worker.search=lambda job:[candidate]
    assert worker.process_one()
    assert art.status()['jobs'][0]['state']=='applied'
    with art.connect() as db:row=dict(db.execute('SELECT * FROM tracks WHERE id=?',(ident,)).fetchone())
    assert row['artKind']=='archive' and (music.ROOT/'covers'/(ident+'.jpg')).is_file()
    job=art.enqueue({'ids':[ident],'album':'Fixture Album','artist':'Fixture Artist','replaceExisting':True})
    replacement=Image.new('RGB',(70,70),'blue');buf=io.BytesIO();replacement.save(buf,'PNG');manual=art.cache_image(buf.getvalue())
    art.apply_image([ident],manual,'uploaded','Manual',True)
    manual_sha=music.digest(music.ROOT/'covers'/(ident+'.jpg'))
    worker.process_one();assert music.digest(music.ROOT/'covers'/(ident+'.jpg'))==manual_sha
    job=art.enqueue({'ids':[ident],'album':'Ambiguous','artist':'Artist','replaceExisting':True});worker.search=lambda job:[{**candidate,'exact':False}]
    worker.process_one();assert art.status()['jobs'][0]['state']=='review'
    worker.urlopen=lambda *a,**k:(_ for _ in ()).throw(ConnectionError())
    fallback,ai=worker.fallback({'album':'Offline test','artist':'Local Artist'})
    assert not ai and (music.ROOT/'covers'/fallback.rsplit('/',1)[-1]).is_file()
    job=art.enqueue({'ids':[ident],'album':'Offline','artist':'Local Artist','replaceExisting':True});worker.search=lambda job:(_ for _ in ()).throw(ConnectionError())
    worker.process_one();assert art.status()['jobs'][0]['state']=='waiting'
    assert art.status()['jobs'][0]['nextAttempt']>0 and art.status()['jobs'][0]['lastError']
    assert music.digest(music.ROOT/'covers'/(ident+'.jpg'))==manual_sha
    # A generated fallback must not prevent a successful scheduled online retry.
    with art.connect() as db:db.execute("UPDATE tracks SET cover='',artKind='' WHERE id=?",(ident,))
    retry_job=art.enqueue({'ids':[ident],'album':'Retry Fixture','artist':'Artist'})
    worker.process_one()
    assert art.status()['jobs'][0]['state']=='waiting'
    with art.connect() as db:
        assert db.execute('SELECT cover FROM tracks WHERE id=?',(ident,)).fetchone()['cover']
        db.execute('UPDATE artwork_jobs SET nextAttempt=0 WHERE id=?',(retry_job['id'],))
    worker.search=lambda job:[candidate]
    worker.process_one()
    with art.connect() as db:
        assert db.execute('SELECT state FROM artwork_jobs WHERE id=?',(retry_job['id'],)).fetchone()['state']=='applied'
        assert db.execute('SELECT artKind FROM tracks WHERE id=?',(ident,)).fetchone()['artKind']=='archive'
    passwords={}
    for email,role in [('admin@example.test','super'),('reader@example.test','user')]:
        salt=secrets.token_hex(16);passwords[email]=secrets.token_urlsafe(22)
        with accounts.connection() as db:db.execute('INSERT INTO users(email,role,salt,password) VALUES(?,?,?,?)',(email,role,salt,accounts.password_hash(passwords[email],salt)))
    httpd=ThreadingHTTPServer(('127.0.0.1',0),app.Handler);origin=f'http://127.0.0.1:{httpd.server_port}';threading.Thread(target=httpd.serve_forever,daemon=True).start()
    def request(path,data,cookie='',foreign=False):
        headers={'Origin':'https://foreign.example' if foreign else origin,'X-Maha-Upload':'1','Content-Type':'application/json','Cookie':cookie}
        try:
            with urlopen(Request(origin+'/api/library/'+path,data=json.dumps(data).encode(),headers=headers)) as response:return response.status,json.load(response),response.headers
        except HTTPError as error:return error.code,json.load(error),error.headers
    def login(email):
        status,_,headers=request('login',{'email':email,'password':passwords[email]});assert status==200
        cookie=SimpleCookie();cookie.load(headers['Set-Cookie']);return 'maha_session='+cookie['maha_session'].value
    try:
        admin=login('admin@example.test');reader=login('reader@example.test')
        assert request('music/art/status',{},reader)[0]==403
        assert request('music/art/status',{},admin,True)[0]==403
        assert request('music/art/status',{},admin)[0]==200
        assert request('music/art/upload',{'ids':[ident],'image':base64.b64encode(raw).decode()},reader)[0]==403
        assert request('music/art/upload',{'ids':[ident],'image':base64.b64encode(raw).decode()},admin)[0]==200
        assert request('music/art/lookup',{'ids':['../bad'],'album':'Bad','artist':'Bad'},admin)[0]==422
        assert request('music/art/apply',{'job':job['id'],'candidate':-1},admin)[0]==422
    finally:httpd.shutdown();httpd.server_close()
    assert music.digest(sample)==original
print('Artwork queue, caching, exact/ambiguous matching, offline fallback, manual override race, image/URL validation, super-user authorization and original preservation: passed')
