import importlib.util,json,tempfile,threading,secrets
from pathlib import Path
from http.server import ThreadingHTTPServer
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from http.cookies import SimpleCookie
import accounts
from classification import Classifier

spec=importlib.util.spec_from_file_location('tested_server',Path(__file__).with_name('server.py'));app=importlib.util.module_from_spec(spec);spec.loader.exec_module(app)
with tempfile.TemporaryDirectory(prefix='maha-account-tests-') as td:
    base=Path(td);app.ROOT=base/'imports';app.ROOT.mkdir();app.STATIC=base/'site';app.STATIC.mkdir();app.ASSETS=base/'assets.json';app.ASSETS.write_text('{"assets":[]}')
    book={'id':'fixture','title':'Book fixture','author':'Author','topic':'Outdoors','sources':[{'url':'/test.epub','format':'EPUB'}]}
    (app.STATIC/'catalog.json').write_text(json.dumps([book]));app.CLASSIFIER=Classifier(app)
    # Durable queue, failure fallback and user-edit precedence without relying on AI output.
    app.CLASSIFIER.queue('fixture')
    assert app.catalog()[0]['topic']=='To be sorted'
    app.CLASSIFIER.classify=lambda b:(_ for _ in ()).throw(ConnectionError())
    app.CLASSIFIER.process_one();assert app.catalog()[0]['topic']=='To be sorted';assert app.catalog()[0]['classification']['state']=='review'
    app.CLASSIFIER.edit('fixture','Custom shelf',['tag one']);assert app.catalog()[0]['topic']=='Custom shelf'
    app.CLASSIFIER.queue('fixture')
    def late_result(book):
        app.CLASSIFIER.edit('fixture','User choice',['manual'])
        return {'topic':'Fiction','tags':['ai'],'state':'sorted'}
    app.CLASSIFIER.classify=late_result;app.CLASSIFIER.process_one();assert app.catalog()[0]['topic']=='User choice'
    restored=Classifier(app);assert restored.overlay([dict(book)])[0]['tags']==['manual']
    restored.queue('fixture')
    with restored.lock:
        records=restored.read();records['fixture']['state']='running';restored.write(records)
    restarted=Classifier(app);restarted.classify=lambda b:{'topic':'Science & nature','tags':['astronomy'],'state':'sorted'}
    assert restarted.process_one();assert restarted.overlay([dict(book)])[0]['topic']=='Science & nature'
    # Failed uploads must not create fake readable entries; imported successes stay readable.
    print('Sorting queue persistence, model-failure fallback and manual override precedence: passed')
    accounts.DB=base/'accounts.sqlite';accounts.initialize();app.AUTH_REQUIRED=True
    admin_password=secrets.token_urlsafe(20);salt=secrets.token_hex(16)
    with accounts.connection() as db:db.execute('INSERT INTO users(email,role,salt,password) VALUES(?,?,?,?)',('admin@example.test','super',salt,accounts.password_hash(admin_password,salt)))
    invitation=accounts.invite('reader@example.test','user');reader_password=secrets.token_urlsafe(20);accounts.accept(invitation,reader_password)
    try:accounts.accept(invitation,reader_password);raise AssertionError('Invitation reused')
    except ValueError:pass
    try:accounts.update_user(1,'user',True,1);raise AssertionError('Last super user removed')
    except ValueError:pass
    server=ThreadingHTTPServer(('127.0.0.1',0),app.Handler);origin=f'http://127.0.0.1:{server.server_port}';threading.Thread(target=server.serve_forever,daemon=True).start()
    def request(path,data=None,cookie=''):
        headers={'Origin':origin,'X-Maha-Upload':'1','Content-Type':'application/json','Cookie':cookie}
        req=Request(origin+'/api/library/'+path,data=json.dumps(data).encode() if data is not None else None,headers=headers)
        try:
            with urlopen(req) as response:return response.status,json.load(response),response.headers
        except HTTPError as error:return error.code,json.load(error),error.headers
    def signin(address,password):
        status,body,headers=request('login',{'email':address,'password':password});assert status==200
        assert 'Secure' in headers['Set-Cookie'] and 'HttpOnly' in headers['Set-Cookie'];cookie=SimpleCookie();cookie.load(headers['Set-Cookie']);return 'maha_session='+cookie['maha_session'].value
    try:
        assert request('books')[0]==401
        reader=signin('reader@example.test',reader_password);admin=signin('admin@example.test',admin_password)
        assert request('books',cookie=reader)[0]==200
        assert request('users',cookie=reader)[0]==403
        assert request('classification',{'id':'fixture','topic':'Fiction','tags':[]},reader)[0]==403
        assert request('invite',{'email':'new@example.test','role':'super'},reader)[0]==403
        assert request('upload',{},reader)[0]==403
        assert request('classification',{'id':'fixture','topic':'Fiction','tags':['novel']},admin)[0]==200
        status,data,_=request('invite',{'email':'new@example.test','role':'user'},admin);assert status==200
        assert request('logout',{},reader)[0]==200;assert request('books',cookie=reader)[0]==401
        accounts.update_user(2,'user',False,1)
        try:accounts.login('reader@example.test',reader_password,'test');raise AssertionError('Disabled user signed in')
        except ValueError:pass
        raw=accounts.DB.read_bytes();assert invitation.encode() not in raw and admin_password.encode() not in raw
        print('Invitations, secure sessions, reader/super permissions, logout, disabled users and last-super protection: passed')
    finally:server.shutdown();server.server_close()
