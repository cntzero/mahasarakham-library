import importlib.util,json,secrets,sqlite3,tempfile,threading
from pathlib import Path
from http.server import ThreadingHTTPServer
from urllib.request import Request,urlopen
from urllib.error import HTTPError
import accounts,access_workflow as access

spec=importlib.util.spec_from_file_location('access_server',Path(__file__).with_name('server.py'));app=importlib.util.module_from_spec(spec);spec.loader.exec_module(app)
with tempfile.TemporaryDirectory(prefix='maha-access-workflow-test-') as td:
    accounts.DB=Path(td)/'accounts.sqlite'
    # An old account database must migrate without changing passwords or sessions.
    with accounts.connection() as db:
        db.executescript('CREATE TABLE users(id INTEGER PRIMARY KEY,email TEXT UNIQUE NOT NULL,role TEXT NOT NULL,salt TEXT NOT NULL,password TEXT NOT NULL,active INTEGER NOT NULL DEFAULT 1); CREATE TABLE sessions(token TEXT PRIMARY KEY,user_id INTEGER NOT NULL,expires INTEGER NOT NULL); CREATE TABLE invitations(token TEXT PRIMARY KEY,email TEXT NOT NULL,role TEXT NOT NULL,expires INTEGER NOT NULL,used INTEGER NOT NULL DEFAULT 0); CREATE TABLE attempts(key TEXT PRIMARY KEY,count INTEGER NOT NULL,expires INTEGER NOT NULL);')
        owner_password=secrets.token_urlsafe(20);salt=secrets.token_hex(16);hashed=accounts.password_hash(owner_password,salt)
        db.execute('INSERT INTO users(email,role,salt,password) VALUES(?,?,?,?)',('owner@example.test','super',salt,hashed))
    accounts.initialize();accounts.initialize()
    with accounts.connection() as db:assert db.execute('SELECT password FROM users WHERE id=1').fetchone()[0]==hashed
    owner,owner_token=accounts.login('owner@example.test',owner_password,'fixture')
    reader_password=secrets.token_urlsafe(20);accounts.accept(accounts.invite('reader@example.test','user'),reader_password);reader,reader_token=accounts.login('reader@example.test',reader_password,'fixture')
    app.AUTH_REQUIRED=True;app.STATIC=Path(td)/'site';app.STATIC.mkdir();(app.STATIC/'catalog.json').write_text('[]');app.ROOT=Path(td)/'imports';app.ROOT.mkdir()
    server=ThreadingHTTPServer(('127.0.0.1',0),app.Handler);origin=f'http://127.0.0.1:{server.server_port}';threading.Thread(target=server.serve_forever,daemon=True).start()
    def request(path,data=None,token=owner_token):
        req=Request(origin+'/api/library/'+path,data=json.dumps(data).encode() if data is not None else None,headers={'Origin':origin,'X-Maha-Upload':'1','Content-Type':'application/json','Cookie':'maha_session='+token})
        try:
            with urlopen(req) as response:return response.status,json.load(response)
        except HTTPError as error:return error.code,json.load(error)
    try:
        assert request('access',token='')[0]==401
        assert request('access',token=reader_token)[0]==403
        for path in ('access-person','vpn-device','access-disable','invite-revoke'):
            assert request(path,{'email':'other@example.test'},reader_token)[0]==403
        bob={'email':'bob@example.test','mode':'remote','role':'user'}
        assert request('access-person',bob)[0]==200
        assert not any(u['email']==bob['email'] for u in accounts.users())
        status,invite=request('invite',bob);assert status==200
        public=access.overview();assert invite['token'] not in json.dumps(public)
        assert next(p for p in public['people'] if p['email']==bob['email'])['invitation']['status']=='pending'
        assert request('invite-revoke',{'email':bob['email']})[0]==200
        try:accounts.accept(invite['token'],reader_password);raise AssertionError('Canceled invite was accepted')
        except ValueError:pass
        status,invite=request('invite',bob);assert status==200
        profile={'email':bob['email'],'label':'Bob phone','routerProfile':'Bob-Phone','address':'10.5.5.3/32','routerCreated':True,'configShared':True,'certificateInstalled':True,'tested':True,'routerRemoved':False}
        status,created=request('vpn-device',profile);assert status==200,(status,created)
        profile['id']=created['id']
        assert request('vpn-device',dict(profile,address='192.168.1.10'))[0]==422
        assert request('vpn-device',dict(profile,address='10.5.5.1/32'))[0]==422
        assert request('vpn-device',dict(profile,tested=True,configShared=False))[0]==422
        charlie={'email':'charlie@example.test','mode':'remote','role':'user'};assert request('access-person',charlie)[0]==200
        duplicate=dict(profile,email=charlie['email']);duplicate.pop('id')
        assert request('vpn-device',duplicate)[0]==422
        assert request('vpn-device',dict(profile,email=charlie['email']))[0]==422
        accounts.accept(invite['token'],reader_password);bob_user,bob_token=accounts.login(bob['email'],reader_password,'fixture')
        assert request('books',token=bob_token)[0]==200
        assert request('access-disable',{'email':bob['email']})[0]==200
        assert request('books',token=bob_token)[0]==401
        bob_record=next(p for p in access.overview()['people'] if p['email']==bob['email'])
        assert not bob_record['user']['active']
        assert bob_record['devices'][0]['revoke_requested'] and not bob_record['devices'][0]['router_removed']
        assert request('vpn-device',dict(profile,routerRemoved=True))[0]==200
        assert request('vpn-device',duplicate)[0]==200
        assert request('vpn-device',profile)[0]==422 # Removed history cannot be silently reactivated.
        assert request('access-disable',{'email':'owner@example.test'})[0]==422
        assert accounts.session(owner_token)
        # A plan can change from remote to local without falsely claiming router removal.
        assert request('access-person',dict(charlie,mode='local'))[0]==200
        record=next(p for p in access.overview()['people'] if p['email']==charlie['email'])
        assert record['devices'] and not record['devices'][0]['router_removed']
        public=access.overview();serialized=json.dumps(public)
        for secret in (owner_password,reader_password,owner_token,reader_token,bob_token,invite['token']):assert secret not in serialized
        assert any('Library access disabled' in e['event'] for e in public['events'])
        print('Access workflow passed: safe migration, Super-user-only APIs, saved plans/devices, invitation cancellation, address validation/collision handling, immediate session revocation, explicit router-removal tracking, history and last-super protection.')
    finally:server.shutdown();server.server_close()
