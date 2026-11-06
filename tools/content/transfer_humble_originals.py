from pathlib import Path
import json,subprocess,hashlib,time
root=Path.cwd();dest='/mnt/data/survival-library/humble-books/originals';catalog='/mnt/data/survival-library/humble-books/catalog'
files=sorted(x for x in Path(r'E:\Books').iterdir() if x.is_file() and x.suffix.lower() in ['.pdf','.epub'])
subprocess.run(['ssh','-o','BatchMode=yes','maha',f'mkdir -p {dest} {catalog}'],check=True)
# Original files have been hashed in earlier audits. Recheck before transfer and record actual current content.
rows=[]
for p in files:
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(4194304),b''):h.update(b)
 rows.append({'filename':p.name,'source':str(p),'bytes':p.stat().st_size,'sha256':h.hexdigest()})
manifest=root/'outputs/humble-originals-transfer-manifest.json';manifest.write_text(json.dumps({'destination':dest,'files':rows},indent=2))
print(f'Transferring {len(files)} original PDFs and EPUBs (6.14 GiB)',flush=True)
for start in range(0,len(files),10):
 batch=files[start:start+10]
 subprocess.run(['scp','-q',*[str(p) for p in batch],f'maha:{dest}/'],check=True)
 print(f'Transferred {min(start+10,len(files))}/{len(files)}',flush=True)
subprocess.run(['scp','-q',str(manifest),f'maha:{catalog}/transfer-manifest.json'],check=True)
code='''import json,hashlib,pathlib
m=json.loads(pathlib.Path("/mnt/data/survival-library/humble-books/catalog/transfer-manifest.json").read_text());bad=[]
for r in m["files"]:
 p=pathlib.Path(m["destination"])/r["filename"];h=hashlib.sha256()
 with p.open("rb") as f:
  for b in iter(lambda:f.read(4194304),b""):h.update(b)
 if h.hexdigest()!=r["sha256"]:bad.append(r["filename"])
result={"verified_files":len(m["files"]),"failures":bad,"destination":m["destination"]};pathlib.Path("/mnt/data/survival-library/humble-books/catalog/verification.json").write_text(json.dumps(result,indent=2));print(json.dumps(result));assert not bad
'''
r=subprocess.run(['ssh','-o','BatchMode=yes','maha','python3 -'],input=code,text=True,capture_output=True,check=True)
print(r.stdout,flush=True);(root/'outputs/humble-originals-server-verification.json').write_text(r.stdout)
