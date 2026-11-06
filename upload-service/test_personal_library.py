import tempfile,json,threading
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from http.server import ThreadingHTTPServer
import personal_library as personal,accounts,music,server
u={'id':1,'role':'user'};v={'id':2,'role':'user'}
def fails(fn,kind):
 try:fn()
 except kind:return
 raise AssertionError('Expected '+kind.__name__)
with tempfile.TemporaryDirectory() as directory:
 root=Path(directory);accounts.DB=root/'accounts.sqlite';music.ROOT=root/'music';ids=['a'*32,'b'*32,'c'*32]
 with music.connect() as db:
  for i,ident in enumerate(ids):db.execute("INSERT INTO tracks(id,sha256,title,artist,owner,tags) VALUES(?,?,?,?,?,?)",(ident,ident,'Track '+str(i),'Artist',1,'[]'))
 fails(lambda:personal.read(None),PermissionError)
 for kind in personal.KINDS:
  ident=ids[0] if kind=='song' else kind+'-reference'
  item={'kind':kind,'id':ident,'title':'Title','url':'music.html?track='+ids[0] if kind=='song' else '/index.html'}
  personal.save({'action':'favorite','item':item,'saved':True},u);personal.save({'action':'favorite','item':item,'saved':True},u)
 assert len(personal.read(u)['favorites'])==6 and not personal.read(v)['favorites']
 with music.connect() as db:db.execute('UPDATE tracks SET cover=? WHERE id=?',('/music-media/covers/'+ids[0]+'.jpg',ids[0]))
 assert next(i for i in personal.read(u)['favorites'] if i['kind']=='song')['cover'].endswith(ids[0]+'.jpg')
 personal.save({'action':'favorite','item':{'kind':'book','id':'book-reference'},'saved':False},v)
 assert len(personal.read(u)['favorites'])==6
 for url in ['javascript:alert(1)','//evil.example/a','https://evil.example/','/\\evil.example/','/bad\npath']:
  fails(lambda:personal.save({'action':'favorite','saved':True,'item':{'kind':'book','id':'bad','title':'Bad','url':url}},u),ValueError)
 state=personal.save({'action':'create','name':'Road trip','ids':ids[:2]+ids[:1]},u);playlist=state['playlists'][0]
 assert [t['id'] for t in playlist['tracks']]==ids[:2]
 assert not personal.read(v)['playlists']
 fails(lambda:personal.save({'action':'delete','id':playlist['id'],'revision':playlist['revision']},v),LookupError)
 personal.save({'action':'append','id':playlist['id'],'revision':playlist['revision'],'ids':ids[1:]},u)
 fails(lambda:personal.save({'action':'rename','id':playlist['id'],'revision':playlist['revision'],'name':'Stale overwrite'},u),ValueError)
 playlist=personal.read(u)['playlists'][0]
 state=personal.save({'action':'reorder','id':playlist['id'],'revision':playlist['revision'],'ids':list(reversed(ids))},u);playlist=state['playlists'][0]
 assert [t['id'] for t in playlist['tracks']]==list(reversed(ids))
 with music.connect() as db:db.execute("UPDATE tracks SET removedAt='removed' WHERE id=?",(ids[0],))
 assert not personal.read(u)['playlists'][0]['tracks'][-1]['available']
 fails(lambda:personal.save({'action':'append','id':playlist['id'],'revision':playlist['revision'],'ids':[ids[0]]},u),ValueError)
 personal.save({'action':'delete','id':playlist['id'],'revision':playlist['revision']},u)
 assert not personal.read(u)['playlists']
 with music.connect() as db:assert db.execute('SELECT count(*) FROM tracks').fetchone()[0]==3
 class Handler(server.Handler):
  def user(self):return u if self.headers.get('Cookie')=='test=one' else v if self.headers.get('Cookie')=='test=two' else None
  def log_message(self,*args):pass
 server.AUTH_REQUIRED=True;http=ThreadingHTTPServer(('127.0.0.1',0),Handler);threading.Thread(target=http.serve_forever,daemon=True).start();base='http://127.0.0.1:'+str(http.server_port)
 def request(cookie=None,data=None,foreign=False):
  headers={'Origin':'https://evil.example' if foreign else base,'X-Maha-Upload':'1','Content-Type':'application/json'}
  if cookie:headers['Cookie']=cookie
  req=Request(base+'/api/library/personal',data=json.dumps(data).encode() if data else None,headers=headers)
  try:
   with urlopen(req) as response:return response.status,json.load(response)
  except HTTPError as e:return e.code,json.load(e)
 assert request()[0]==401
 assert len(request('test=one')[1]['favorites'])==6 and not request('test=two')[1]['favorites']
 assert request('test=one',{'action':'create','name':'HTTP playlist'},True)[0]==403
 assert request('test=two',{'action':'create','name':'HTTP playlist'})[0]==200
 assert not request('test=one')[1]['playlists']
 http.shutdown();http.server_close()
print('Personal favorites and playlists: user isolation, idempotence, safe URLs, order, duplicate prevention, stale revisions, unavailable tracks, media preservation, authentication and origin enforcement: passed')
