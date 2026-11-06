from pathlib import Path
import json,subprocess,shlex,hashlib,tarfile,os,time
root=Path(__file__).resolve().parent.parent;inventory=json.loads((root/'outputs/full-web-mirror-inventory.json').read_text());assert not inventory['errors']
source=Path('\\\\?\\'+inventory['source_root']);dest='/mnt/data/survival-library/web-articles';archive=dest+'/preservation/askaprepper-mirror-2021.tar.gz';statuspath=root/'outputs/web-mirror-transfer-status.json';records=[];last=0
ssh=['ssh','-o','BatchMode=yes','-o','ConnectTimeout=15','-o','ServerAliveInterval=15','-o','ServerAliveCountMax=3','maha']
def remote(code,timeout=300):return subprocess.run(ssh+['python3 -c '+shlex.quote(code)],text=True,capture_output=True,timeout=timeout,check=True).stdout
remote('from pathlib import Path; Path('+repr(dest+'/preservation')+').mkdir(parents=True,exist_ok=True); Path('+repr(dest+'/originals')+').mkdir(exist_ok=True)')
proc=subprocess.Popen(ssh+['cat > '+shlex.quote(archive+'.part')],stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
archivehash=hashlib.sha256()
class Stream:
 def write(self,b):archivehash.update(b);return proc.stdin.write(b)
 def flush(self):return proc.stdin.flush()
class ReadHash:
 def __init__(self,f):self.f=f;self.h=hashlib.sha256()
 def read(self,n=-1):b=self.f.read(n);self.h.update(b);return b
try:
 with tarfile.open(fileobj=Stream(),mode='w|gz',compresslevel=1) as tar:
  for i,r in enumerate(inventory['files'],1):
   p=source/Path(r['relative_path']);st=p.stat();assert st.st_size==r['bytes'] and st.st_mtime_ns==r['mtime_ns'],'Source changed: '+str(p)
   info=tarfile.TarInfo('askaprepper/'+r['relative_path']);info.size=st.st_size;info.mtime=st.st_mtime;info.mode=0o644
   with p.open('rb') as f:
    reader=ReadHash(f);tar.addfile(info,reader);records.append({**r,'sha256':reader.h.hexdigest()})
   if time.time()-last>10:
    statuspath.write_text(json.dumps({'state':'copying_preservation_archive','files_packed':i,'total_files':len(inventory['files']),'bytes_packed':sum(x['bytes'] for x in records)},indent=2));print('Packed',i,'/',len(inventory['files']),flush=True);last=time.time()
 proc.stdin.close();proc.stdin=None;_,err=proc.communicate();assert proc.returncode==0,err.decode(errors='replace')
 manifest=root/'outputs/web-mirror-preservation-manifest.json';manifest.write_text(json.dumps({'source_root':inventory['source_root'],'remote_originals':dest+'/originals/askaprepper','archive':archive,'archive_sha256':archivehash.hexdigest(),'files':records},indent=2),encoding='utf-8')
 subprocess.run(['scp','-q',str(manifest),'maha:'+dest+'/preservation/manifest.json'],check=True)
 statuspath.write_text(json.dumps({'state':'verifying_and_extracting','files_packed':len(records),'total_files':len(records)}))
 code='''from pathlib import Path
import hashlib,tarfile,json
base=Path("/mnt/data/survival-library/web-articles");m=json.loads((base/"preservation/manifest.json").read_text());p=Path(m["archive"]+".part");h=hashlib.sha256()
with p.open("rb") as f:
 while b:=f.read(16777216):h.update(b)
assert h.hexdigest()==m["archive_sha256"],"Archive checksum mismatch"
p.rename(m["archive"])
with tarfile.open(m["archive"]) as t:t.extractall(base/"originals",filter="data")
fail=[]
for r in m["files"]:
 p=base/"originals/askaprepper"/r["relative_path"]
 if hashlib.sha256(p.read_bytes()).hexdigest()!=r["sha256"]:fail.append(r["relative_path"])
result={"state":"complete" if not fail else "verification_failed","verified_files":len(m["files"]),"failures":fail,"originals":str(base/"originals/askaprepper"),"archive_sha256":m["archive_sha256"]};(base/"preservation/verification.json").write_text(json.dumps(result,indent=2));print(json.dumps(result));assert not fail
'''
 result=remote(code,timeout=3600);statuspath.write_text(result,encoding='utf-8');print(result,flush=True)
except BaseException as e:
 if proc.poll() is None:proc.kill();proc.wait()
 statuspath.write_text(json.dumps({'state':'interrupted','error':str(e),'files_packed':len(records),'total_files':len(inventory['files'])},indent=2));raise
