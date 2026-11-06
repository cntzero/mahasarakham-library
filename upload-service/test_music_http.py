"""Disposable HTTP checks against the real API and authentication handler."""
import json, tempfile, threading, secrets
from pathlib import Path
from http.server import ThreadingHTTPServer
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from http.cookies import SimpleCookie
import server as app, accounts, music

inventory=json.loads(Path('/mnt/data/projects/maha-library/music-inventory.json').read_text())['files']
sample=Path(min((r for r in inventory if r['status']=='include'),key=lambda r:r['bytes'])['path']).read_bytes()
with tempfile.TemporaryDirectory(prefix='maha-music-http-') as td:
    base=Path(td); music.ROOT=base/'music'; accounts.DB=base/'accounts.sqlite'; accounts.initialize(); app.AUTH_REQUIRED=True
    passwords={}
    for email,role in [('owner@example.test','user'),('other@example.test','user'),('admin@example.test','super')]:
        password=secrets.token_urlsafe(22);salt=secrets.token_hex(16);passwords[email]=password
        with accounts.connection() as db: db.execute('INSERT INTO users(email,role,salt,password) VALUES(?,?,?,?)',(email,role,salt,accounts.password_hash(password,salt)))
    httpd=ThreadingHTTPServer(('127.0.0.1',0),app.Handler); origin=f'http://127.0.0.1:{httpd.server_port}'
    threading.Thread(target=httpd.serve_forever,daemon=True).start()
    def request(path,data=None,cookie='',foreign=False,raw=False):
        headers={'Origin':'https://foreign.example' if foreign else origin,'X-Maha-Upload':'1','Cookie':cookie,'Content-Type':'audio/mpeg' if raw else 'application/json','X-File-Name':'fixture.mp3'}
        body=data if raw else json.dumps(data).encode() if data is not None else None
        try:
            with urlopen(Request(origin+'/api/library/'+path,data=body,headers=headers)) as response:return response.status,json.load(response),response.headers
        except HTTPError as error:return error.code,json.load(error),error.headers
    def login(email):
        status,_,headers=request('login',{'email':email,'password':passwords[email]});assert status==200
        cookie=SimpleCookie();cookie.load(headers['Set-Cookie']);return 'maha_session='+cookie['maha_session'].value
    try:
        assert request('music')[0]==401
        owner=login('owner@example.test');other=login('other@example.test');admin=login('admin@example.test')
        assert request('music/upload',sample,owner,foreign=True,raw=True)[0]==403
        status,result,_=request('music/upload',sample,owner,raw=True);assert status==200,(status,result)
        ident=result['id']
        assert request('music/metadata',{'id':ident,'title':'Denied'},other)[0]==403
        assert request('music/classify',{'id':ident},other)[0]==403
        assert request('music/metadata',{'id':ident,'title':'Owner edit','tags':['favorite']},owner)[0]==200
        assert request('music/metadata',{'id':ident,'title':'Admin edit'},admin)[0]==200
        assert request('music/upload',sample,other,raw=True)[0]==200
        status,rows,_=request('music',cookie=other);assert status==200 and len(rows)==1 and not rows[0]['canEdit']
        assert rows[0]['bytes']==len(sample)
        assert request('music/upload',b'not an mp3',owner,raw=True)[0]==422
        assert request('music/remove',{'id':ident},other)[0]==403
        assert request('music/remove',{'id':ident},owner)[0]==200
        assert request('music',cookie=other)[1]==[]
        assert (music.ROOT/'tracks'/(ident+'.mp3')).is_file()
        assert request('music/upload',sample,other,raw=True)[0]==200
        assert request('music',cookie=other)[1]==[]
        assert request('music/remove',{'id':ident},admin)[0]==200
        assert request('music',cookie=admin)[1][0]['removedAt']
        assert request('music/delete',{'id':ident,'confirmTitle':'Admin edit'},owner)[0]==403
        assert request('music/delete',{'id':ident,'confirmTitle':'wrong'},admin)[0]==422
        assert (music.ROOT/'tracks'/(ident+'.mp3')).is_file()
        status,result,_=request('music/delete',{'id':ident,'confirmTitle':'Admin edit'},admin)
        assert status==200 and result['bytesRemoved']>=len(sample)
        assert not (music.ROOT/'tracks'/(ident+'.mp3')).exists()
        assert request('music',cookie=admin)[1]==[]
        assert request('music/upload',sample,owner,raw=True)[0]==200
        assert request('music',cookie=admin)[1]==[]
        assert not (music.ROOT/'tracks'/(ident+'.mp3')).exists()
        print('Permanent deletion: super-only, exact-title confirmation, managed file removed and reimport suppressed: passed')
        print('Music removal ownership, preserved files and duplicate-import suppression: passed')
        print('Music HTTP authentication, uploads, duplicate ownership, owner/super editing and origin protection: passed')
    finally:httpd.shutdown();httpd.server_close()

