import sys,json,hashlib,tempfile,os,sqlite3,time
from pathlib import Path
sys.path.insert(0,'/opt/maha-library-api')
import music
base=Path('/mnt/data/projects/maha-library/windows-music-import');base.mkdir(exist_ok=True)
state=sqlite3.connect(base/'progress.sqlite');state.execute('CREATE TABLE IF NOT EXISTS files(source TEXT PRIMARY KEY,size INTEGER,mtime INTEGER,status TEXT,result TEXT)')
r=sys.stdin.buffer
def reply(value):print(json.dumps(value),flush=True)
while True:
 line=r.readline()
 if not line:break
 header=json.loads(line);source=header['source'];size=header['size'];mtime=header['mtime']
 previous=state.execute('SELECT status,result FROM files WHERE source=? AND size=? AND mtime=?',(source,size,mtime)).fetchone()
 if previous and previous[0] in ('added','skipped'):
  reply({'ready':False,'resume':True,'result':json.loads(previous[1])});continue
 reply({'ready':True})
 path=None
 try:
  with tempfile.NamedTemporaryFile(dir=base,suffix='.mp3',delete=False) as f:
   path=Path(f.name);remaining=size;digest=hashlib.sha256()
   while remaining:
    chunk=r.read(min(1024*1024,remaining))
    if not chunk:raise EOFError('Transfer interrupted')
    f.write(chunk);digest.update(chunk);remaining-=len(chunk)
  expected=json.loads(r.readline())['sha256']
  if digest.hexdigest()!=expected:raise ValueError('Transfer hash mismatch')
  result=music.add_file(path,header['name'],owner=1,source_path=source)
  result['sha256']=expected
 except EOFError:raise
 except Exception as e:result={'status':'error','message':str(e)}
 finally:
  if path is not None:path.unlink(missing_ok=True)
 state.execute('INSERT OR REPLACE INTO files VALUES(?,?,?,?,?)',(source,size,mtime,result['status'],json.dumps(result)));state.commit();reply({'result':result})

