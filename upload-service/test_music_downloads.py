"""Real HTTP ZIP streaming and access checks using disposable MP3 copies."""
import tempfile,json,secrets,threading,io,zipfile,shutil,hashlib
from pathlib import Path
from http.server import ThreadingHTTPServer
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from http.cookies import SimpleCookie
from mutagen.mp3 import MP3
from mutagen.id3 import TIT2
import music,accounts,server as app

with tempfile.TemporaryDirectory(prefix='maha-download-tests-') as temp:
    base=Path(temp);music.ROOT=base/'music';accounts.DB=base/'accounts.sqlite';accounts.initialize();app.AUTH_REQUIRED=True
    inventory=json.loads(Path('/mnt/data/projects/maha-library/music-inventory.json').read_text())['files']
    sample=Path(min((r for r in inventory if r['status']=='include'),key=lambda r:r['bytes'])['path']);original=music.digest(sample)
    first=music.add_file(sample,sample.name,1)['id'];copy=base/'copy.mp3';shutil.copyfile(sample,copy);audio=MP3(copy)
    if audio.tags is None:audio.add_tags()
    audio.tags.add(TIT2(encoding=3,text='Second fixture'));audio.save();second=music.add_file(copy,'second.mp3',1)['id']
    with music.connect() as db:
        db.execute("UPDATE tracks SET title='../unsafe/title' WHERE id=?",(first,))
    passwords={}
    for email in ('one@example.test','two@example.test'):
        salt=secrets.token_hex(16);passwords[email]=secrets.token_urlsafe(20)
        with accounts.connection() as db:db.execute('INSERT INTO users(email,role,salt,password) VALUES(?,?,?,?)',(email,'user',salt,accounts.password_hash(passwords[email],salt)))
    httpd=ThreadingHTTPServer(('127.0.0.1',0),app.Handler);origin=f'http://127.0.0.1:{httpd.server_port}';threading.Thread(target=httpd.serve_forever,daemon=True).start()
    def request(path,data=None,cookie='',foreign=False):
        headers={'Origin':'https://foreign.example' if foreign else origin,'X-Maha-Upload':'1','Content-Type':'application/json','Cookie':cookie}
        try:
            with urlopen(Request(origin+path,data=json.dumps(data).encode() if data is not None else None,headers=headers)) as response:return response.status,response.read(),response.headers
        except HTTPError as error:return error.code,error.read(),error.headers
    def login(email):
        status,_,headers=request('/api/library/login',{'email':email,'password':passwords[email]});assert status==200
        cookie=SimpleCookie();cookie.load(headers['Set-Cookie']);return 'maha_session='+cookie['maha_session'].value
    try:
        one=login('one@example.test');two=login('two@example.test');status,raw,_=request('/api/library/music/discoveries',cookie=one);assert status==200 and len(json.loads(raw))==1
        data={'ids':[second,first],'title':'Fixture Album'}
        assert request('/api/library/music/download',data)[0]==401
        assert request('/api/library/music/download',data,one,True)[0]==403
        status,raw,_=request('/api/library/music/download',data,one);assert status==200;url=json.loads(raw)['url']
        assert request(url,cookie=two)[0]==404
        assert request(url)[0]==401
        status,raw,headers=request(url,cookie=one);assert status==200 and headers['Content-Type']=='application/zip'
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            assert len(archive.namelist())==2 and archive.testzip() is None
            assert archive.namelist()[0].startswith('001') and archive.namelist()[1].startswith('002')
            assert all('/' not in name and '\\' not in name for name in archive.namelist())
            assert hashlib.sha256(archive.read(archive.namelist()[0])).hexdigest()==music.digest(copy)
            assert hashlib.sha256(archive.read(archive.namelist()[1])).hexdigest()==original
        with music.connect() as db:db.execute('UPDATE music_downloads SET expires=0')
        assert request(url,cookie=one)[0]==404
        assert request('/api/library/music/download',{'ids':['../bad'],'title':'Bad'},one)[0]==422
        music.remove(first,{'id':1,'role':'user'})
        assert request('/api/library/music/download',data,one)[0]==422
    finally:httpd.shutdown();httpd.server_close()
    assert music.digest(sample)==original
print('Album ZIP streaming, original bytes, entry order, safe filenames, authenticated reader access, user-bound expiry, removal and origin protection: passed')
