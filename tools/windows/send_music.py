import os,sys,json,subprocess,hashlib,time,collections
from pathlib import Path
import argparse
parser=argparse.ArgumentParser(description='Resume verified MP3 transfers to MAHA over SSH.')
parser.add_argument('--root',required=True,help='Windows music folder')
parser.add_argument('--ssh',default='maha',help='SSH host alias')
parser.add_argument('--output',default=str(Path(__file__).resolve().parent))
args=parser.parse_args()
root=str(Path(args.root).resolve())
prefix=chr(92)*2+'?'+chr(92)
if os.name=='nt' and not root.startswith(prefix):root=prefix+root
work=Path(args.output);work.mkdir(parents=True,exist_ok=True)
rows=[];errors=[]
for base,dirs,names in os.walk(root,onerror=lambda e:errors.append(str(e))):
 for name in names:
  if not name.lower().endswith('.mp3'):continue
  p=os.path.join(base,name)
  try:
   st=os.stat(p);rows.append({'path':p,'source':p[4:] if p.startswith(prefix) else p,'size':st.st_size,'mtime':st.st_mtime_ns,'name':name})
  except OSError as e:errors.append(str(e))
(work/'music-manifest.json').write_text(json.dumps({'files':rows,'errors':errors},ensure_ascii=False),encoding='utf-8')
print(json.dumps({'total':len(rows),'bytes':sum(r['size'] for r in rows),'scanErrors':errors}),flush=True)
counts=collections.Counter();sent=0;start=time.time()
p=subprocess.Popen(['ssh','-o','BatchMode=yes','-o','ServerAliveInterval=20','-o','ServerAliveCountMax=6',args.ssh,'PYTHONPATH=/opt/maha-library-api/music-vendor python3 /mnt/data/projects/maha-library/upload-service/receive_windows_music.py'],stdin=subprocess.PIPE,stdout=subprocess.PIPE)
with (work/'music-transfer-results.jsonl').open('a',encoding='utf-8') as report:
 for i,row in enumerate(rows,1):
  p.stdin.write((json.dumps({k:v for k,v in row.items() if k!='path'})+'\n').encode());p.stdin.flush()
  ack=json.loads(p.stdout.readline())
  if ack['ready']:
   digest=hashlib.sha256()
   with open(row['path'],'rb') as f:
    while chunk:=f.read(1024*1024):p.stdin.write(chunk);digest.update(chunk);sent+=len(chunk)
   p.stdin.write((json.dumps({'sha256':digest.hexdigest()})+'\n').encode());p.stdin.flush();ack=json.loads(p.stdout.readline())
  result=ack['result'];counts['resumed' if ack.get('resume') else result['status']]+=1
  report.write(json.dumps({'source':row['source'],**result},ensure_ascii=False)+'\n');report.flush()
  if i%20==0 or i==len(rows):
   progress={'done':i,'total':len(rows),'counts':dict(counts),'sentGB':round(sent/1e9,2),'elapsedSeconds':round(time.time()-start)}
   (work/'music-transfer-progress.json').write_text(json.dumps(progress),encoding='utf-8');print(json.dumps(progress),flush=True)
p.stdin.close();code=p.wait();print('Transfer finished, SSH status',code,flush=True)
if code:sys.exit(code)
