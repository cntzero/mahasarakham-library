"""Visibility persists, authorization holds, and originals remain intact."""
import json, secrets, tempfile, threading
from pathlib import Path
from http.server import ThreadingHTTPServer
from urllib.request import Request, urlopen
from urllib.error import HTTPError
import accounts, server as app, collection_controls as controls

with tempfile.TemporaryDirectory() as td:
    root=Path(td);accounts.DB=root/'accounts.sqlite';accounts.initialize()
    with accounts.connection() as db:
        db.execute("INSERT INTO users(email,role,salt,password) VALUES('owner@example.test','super','fixture','fixture')")
        db.execute("INSERT INTO users(email,role,salt,password) VALUES('reader@example.test','user','fixture','fixture')")
        tokens=[secrets.token_urlsafe(24),secrets.token_urlsafe(24)]
        for i,token in enumerate(tokens,1):db.execute('INSERT INTO sessions VALUES(?,?,?)',(accounts.digest(token),i,9999999999))
    app.AUTH_REQUIRED=True;app.STATIC=root/'site';app.STATIC.mkdir();app.ROOT=root/'imports';app.ROOT.mkdir()
    book={'id':'one','title':'Fixture book','topic':'Outdoors','sources':[]}
    (app.STATIC/'catalog.json').write_text(json.dumps([book]));original=root/'fixture.zim';original.write_bytes(b'preserved-original')
    controls.LIBRARY=root/'library.xml';controls.LIBRARY.write_text('<library><book id="zim-one" path="fixture.zim" title="Fixture archive" date="2021-05-01" /></library>')
    service=ThreadingHTTPServer(('127.0.0.1',0),app.Handler);origin=f'http://127.0.0.1:{service.server_port}';threading.Thread(target=service.serve_forever,daemon=True).start()
    def request(path,data=None,token=tokens[0]):
        req=Request(origin+'/api/library/'+path,data=json.dumps(data).encode() if data is not None else None,headers={'Origin':origin,'X-Maha-Upload':'1','Cookie':'maha_session='+token})
        try:
            with urlopen(req) as response:return response.status,json.load(response)
        except HTTPError as error:return error.code,json.load(error)
    try:
        assert request('kiwix',token='')[0]==401
        for kind,ident,visible,removed in [('book','one','books','removed-books'),('kiwix','zim-one','kiwix','hidden-kiwix')]:
            data={'kind':kind,'id':ident,'hidden':True}
            assert request('visibility',data,tokens[1])[0]==403
            assert request(removed,token=tokens[1])[0]==403
            assert len(request(visible)[1])==1
            assert request('visibility',data)[0]==200
            assert request(visible)[1]==[]
            assert len(request(removed)[1])==1
            controls.initialize();assert ident in controls.hidden(kind)
            data['hidden']=False;assert request('visibility',data)[0]==200
            assert len(request(visible)[1])==1
        assert request('visibility',{'kind':'book','id':'missing','hidden':True})[0]==404
        assert request('visibility',{'kind':'book','id':'one','hidden':'yes'})[0]==422
        assert request('metadata',{'id':'one','title':'Updated title','author':'Updated author'},tokens[1])[0]==403
        assert request('metadata',{'id':'one','title':'','author':''})[0]==422
        assert request('metadata',{'id':'one','title':'Updated title','author':'Updated author'})[0]==200
        assert request('books')[1][0]['title']=='Updated title'
        assert json.loads((app.ROOT/'book-metadata.json').read_text())['one']['author']=='Updated author'
        assert app.useful_title('My Document','garage_door_manual.pdf')=='garage door manual'
        assert app.useful_title('A real title','manual.pdf')=='A real title'
        assert original.read_bytes()==b'preserved-original'
        print('Collection controls passed: reader denial, hide/restore, persistence, missing/invalid items, originals preserved.')
    finally:service.shutdown();service.server_close()
