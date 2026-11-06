"""Resumable, preservation-only transfer of the inventoried ZIM collection."""
from pathlib import Path
import csv,json,subprocess,hashlib,time,shlex,traceback,os
root=Path(__file__).resolve().parent.parent
status_path=root/'outputs/kiwix-transfer-status.json';log_path=root/'outputs/kiwix-transfer-log.jsonl';manifest_path=root/'outputs/kiwix-transfer-verified.json'
rows=list(csv.DictReader((root/'outputs/general-knowledge-zim-inventory.csv').open(encoding='utf-8-sig')))
for r in rows:r['bytes']=int(r['bytes'])
preferred={'wikivoyage_en_all_maxi_2021-06.zim':0,'wikibooks_en_all_maxi_2021-03.zim':1,'wikibooks_th_all_maxi_2021-06.zim':2}
rows.sort(key=lambda r:(preferred.get(r['filename'],3),r['bytes']))
verified=json.loads(manifest_path.read_text()) if manifest_path.exists() else []
known={r['remote']:r for r in verified};total=sum(r['bytes'] for r in rows);started=time.time()
def remote(code, timeout=180):
 r=subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=15','-o','ServerAliveInterval=15','-o','ServerAliveCountMax=3','maha','python3 -c '+shlex.quote(code)],text=True,capture_output=True,check=True,timeout=timeout);return r.stdout.strip()
def status(**kw):
 data={'total_files':len(rows),'total_bytes':total,'verified_files':len(verified),'verified_bytes':sum(r['bytes'] for r in verified),'updated_at_unix':time.time(),**kw};tmp=status_path.with_suffix('.tmp');tmp.write_text(json.dumps(data,indent=2));os.replace(tmp,status_path)
def save():
 tmp=manifest_path.with_suffix('.tmp');tmp.write_text(json.dumps(verified,indent=2));os.replace(tmp,manifest_path)
def register():
 code='''from pathlib import Path
import subprocess,json,shutil
base=Path("/mnt/data/kiwix");tool=Path.home()/".local/bin/kiwix-manage";library=base/"library.xml";progress=base/"catalog/registered.json"
if not tool.exists():print("Kiwix tool pending");raise SystemExit(0)
seen=json.loads(progress.read_text()) if progress.exists() else []
for p in sorted((base/"archives").rglob("*.zim")):
 if str(p) in seen:continue
 staging=base/"library.next.xml";shutil.copy2(library,staging)
 r=subprocess.run([str(tool),str(staging),"add",str(p)],capture_output=True,text=True)
 if r.returncode:print("Registration failed: "+p.name+" "+r.stderr[:200]);continue
 staging.replace(library);seen.append(str(p));progress.write_text(json.dumps(seen))
print("Registered "+str(len(seen))+" archive paths")
'''
 return remote(code)
failures=[]
try:
 remote('from pathlib import Path; '+ '; '.join('Path('+repr('/mnt/data/kiwix/archives/'+c)+').mkdir(parents=True,exist_ok=True)' for c in sorted({r['collection'] for r in rows})))
 for index,row in enumerate(rows):
  p=Path(row['path']);dest='/mnt/data/kiwix/archives/'+row['collection']+'/'+row['filename'];part=dest+'.part'
  if dest in known:continue
  try:
   assert p.is_file() and p.stat().st_size==row['bytes'],'Source size changed'
   info=json.loads(remote('import pathlib,json; p=pathlib.Path('+repr(dest)+'); q=pathlib.Path('+repr(part)+');print(json.dumps({"final":p.stat().st_size if p.exists() else None,"partial":q.stat().st_size if q.exists() else 0}))'))
   offset=info['partial'];assert offset<=row['bytes'],'Partial copy larger than source; inspect manually'
   final_exists=info['final'] is not None
   if final_exists:assert info['final']==row['bytes'],'Existing destination differs in size'
   h=hashlib.sha256();sent=offset if not final_exists else row['bytes'];last=0
   status(state='transferring',current_file=row['filename'],current_bytes=sent,current_total=row['bytes'],failures=failures)
   with p.open('rb') as f:
    remaining=sent
    while remaining:
     b=f.read(min(8*1024*1024,remaining));assert b;h.update(b);remaining-=len(b)
    if not final_exists and sent<row['bytes']:
     command='cat >> '+shlex.quote(part)
     proc=subprocess.Popen(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=15','-o','ServerAliveInterval=15','-o','ServerAliveCountMax=3','maha',command],stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
     try:
      while b:=f.read(8*1024*1024):
       proc.stdin.write(b);h.update(b);sent+=len(b)
       if time.time()-last>10:status(state='transferring',current_file=row['filename'],current_bytes=sent,current_total=row['bytes'],failures=failures);last=time.time()
      proc.stdin.close();proc.stdin=None;_,err=proc.communicate()
      if proc.returncode:raise RuntimeError(err.decode(errors='replace')[:500])
     except BaseException:
      proc.kill();proc.wait();raise
   digest=h.hexdigest();checkpath=dest if final_exists else part
   status(state='verifying',current_file=row['filename'],current_bytes=sent,current_total=row['bytes'],failures=failures)
   code='import pathlib,hashlib; p=pathlib.Path('+repr(checkpath)+');h=hashlib.sha256();f=p.open("rb");\nwhile b:=f.read(16777216):h.update(b)\nf.close();assert h.hexdigest()=='+repr(digest)+',"Checksum mismatch";'+('p.rename('+repr(dest)+');' if not final_exists else '')+'print(h.hexdigest())'
   assert remote(code,timeout=7200)==digest
   record={'collection':row['collection'],'filename':row['filename'],'source':str(p),'remote':dest,'bytes':row['bytes'],'sha256':digest,'verified_at_unix':time.time()};verified.append(record);known[dest]=record;save()
   with log_path.open('a') as log:log.write(json.dumps({'state':'verified',**record})+'\n')
   registration=register();status(state='transferring',last_verified=row['filename'],registration=registration,failures=failures)
   print('Verified',len(verified),'/',len(rows),row['filename'],flush=True)
  except Exception as e:
   failures.append({'file':row['filename'],'error':str(e)});status(state='transferring',failures=failures)
   with log_path.open('a') as log:log.write(json.dumps({'state':'failed','file':row['filename'],'error':str(e)})+'\n')
   # Stop on connection failure so a disconnected machine cannot create hundreds of false failures.
   if isinstance(e,(subprocess.CalledProcessError,subprocess.TimeoutExpired,BrokenPipeError,ConnectionError)):raise
 registration=register();status(state='complete' if not failures else 'completed_with_failures',registration=registration,failures=failures)
except BaseException as e:
 status(state='interrupted',error=str(e),failures=failures);raise
