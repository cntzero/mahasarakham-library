import subprocess,json,hashlib,time
from pathlib import Path
root=Path(r'E:\Google_Drive_downloads_archive\Manuals  and books\bushcraft_survival_books')
out=Path(__file__).parent/'bushcraft'
(out/'epub').mkdir(parents=True,exist_ok=True)
(out/'logs').mkdir(exist_ok=True)
records=[]
for source in sorted(root.rglob('*.mobi')):
    sha=hashlib.file_digest(source.open('rb'),'sha256').hexdigest()
    target=out/'epub'/(source.stem+'-'+sha[:8]+'.epub')
    log=out/'logs'/(source.stem+'-'+sha[:8]+'.log')
    if target.exists(): status='converted'
    else:
        with log.open('w',encoding='utf-8') as f:
            result=subprocess.run([r'C:\Program Files\Calibre2\ebook-convert.exe',str(source),str(target)],stdout=f,stderr=subprocess.STDOUT,timeout=300)
        status='converted' if result.returncode==0 and target.exists() else 'conversion_failed_review_log'
    records.append({'source':str(source),'sha256':sha,'epub':str(target.resolve()),'status':status})
    (out/'manifest.json').write_text(json.dumps(records,indent=2),encoding='utf-8')
    print(f'{source.name}: {status}',flush=True)
