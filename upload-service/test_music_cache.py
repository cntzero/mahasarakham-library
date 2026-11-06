import tempfile,threading,json
from pathlib import Path
from http.server import ThreadingHTTPServer
from urllib.request import Request,urlopen
from urllib.error import HTTPError
import music,server
with tempfile.TemporaryDirectory() as directory:
 music.ROOT=Path(directory)
 with music.connect() as db:db.execute("INSERT INTO tracks(id,sha256,title,artist,album,owner,tags,duration,bytes,albumMetadataVersion,tagState) VALUES(?,?,?,?,?,?,?,?,?,?,?)",('a'*32,'a'*64,'Track','Artist','Album',1,'[]',180,100,1,'manual'))
 class Handler(server.Handler):
  def user(self):return {'id':2 if self.headers.get('Cookie')=='other' else 1,'role':'user'}
  def log_message(self,*args):pass
 server.AUTH_REQUIRED=True;http=ThreadingHTTPServer(('127.0.0.1',0),Handler);threading.Thread(target=http.serve_forever,daemon=True).start();url='http://127.0.0.1:'+str(http.server_port)+'/api/library/music'
 with urlopen(url) as response:etag=response.headers['ETag'];assert len(json.load(response))==1
 try:urlopen(Request(url,headers={'If-None-Match':etag}))
 except HTTPError as e:assert e.code==304 and e.read()==b''
 else:raise AssertionError('Unchanged catalog downloaded again')
 with urlopen(Request(url,headers={'If-None-Match':etag,'Cookie':'other'})) as response:assert response.status==200 and response.headers['ETag']!=etag
 with music.connect() as db:db.execute("UPDATE tracks SET title='New title'")
 with urlopen(Request(url,headers={'If-None-Match':etag})) as response:assert response.status==200 and json.load(response)[0]['title']=='New title'
 # Background artwork grouping can change the representation without a DB write.
 old=music.catalog_etag({'id':1,'role':'user'});music._COVER_REVISION+=1
 assert music.catalog_etag({'id':1,'role':'user'})!=old
 http.shutdown();http.server_close()
print('Catalog caching: unchanged data returns 304; account, metadata and background-grouping changes invalidate the cache: passed')
