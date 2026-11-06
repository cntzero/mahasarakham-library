import sys,json,os,time
from pathlib import Path
from functools import lru_cache
from concurrent.futures import ProcessPoolExecutor, as_completed
sys.path.insert(0,str(Path(__file__).parent/'pdf-libs'))
os.environ['OMP_THREAD_LIMIT']='1'
import pymupdf
BASE=Path(__file__).parent
@lru_cache(maxsize=3)
def opened(path): return pymupdf.open(path)
def ocr(task):
    path,n=task
    page=opened(path)[n-1]
    tp=page.get_textpage_ocr(language='eng',dpi=220,full=True,tessdata=str(BASE/'tessdata'))
    words=page.get_text('words',textpage=tp)
    # OCR line order can interleave magazine columns. Detect vertical gutters
    # from word geometry, then read each column from top to bottom.
    w,h=page.rect.width,page.rect.height
    body=[v for v in words if h*.08 < (v[1]+v[3])/2 < h*.92]
    def gutter(a,b):
        candidates=[w*(a+(b-a)*i/40) for i in range(41)]
        x=min(candidates,key=lambda x:sum(v[0]<x<v[2] for v in body))
        return x,sum(v[0]<x<v[2] for v in body)
    x1,c1=gutter(.30,.40);x2,c2=gutter(.60,.70)
    xm,cm=gutter(.45,.55)
    threshold=max(10,len(body)*.02)
    cuts=[0,x1,x2,w] if c1<=threshold and c2<=threshold and len(body)>100 else ([0,xm,w] if cm<=threshold and len(body)>100 else [0,w])
    sections=[]
    for left,right in zip(cuts,cuts[1:]):
        selected=sorted([v for v in words if left<=(v[0]+v[2])/2<right],key=lambda v:(v[1],v[0]))
        lines={}
        for v in selected:
            lines.setdefault((v[5],v[6]),[]).append(v)
        ordered=sorted(lines.values(),key=lambda line:(min(v[1] for v in line),min(v[0] for v in line)))
        sections.append('\n'.join(' '.join(v[4] for v in sorted(line,key=lambda v:v[0])) for line in ordered))
    text='\n\n[COLUMN BREAK]\n\n'.join(sections)
    return n,text
def main():
    stage=BASE/'backwoods'
    records=json.loads((stage/'manifest.json').read_text(encoding='utf-8'))
    for record in records:
        if not record['filename'].startswith(('02 -','03 -','04 -')): continue
        cache=stage/'ocr-layout-cache-v2'/Path(record['filename']).stem
        cache.mkdir(parents=True,exist_ok=True)
        tasks=[(record['source'],n) for n in range(1,record['pages']+1) if not (cache/f'{n:04}.txt').exists()]
        with ProcessPoolExecutor(max_workers=12) as pool:
            futures=[pool.submit(ocr,t) for t in tasks]
            for i,f in enumerate(as_completed(futures),1):
                n,text=f.result()
                (cache/f'{n:04}.txt').write_text(text,encoding='utf-8')
                if i%30==0: print(f'{record["filename"]}: {i}/{len(tasks)} pages OCR complete',flush=True)
        out=Path(record['prepared_text'])
        with out.open('w',encoding='utf-8') as stream:
            for n in range(1,record['pages']+1):
                text=(cache/f'{n:04}.txt').read_text(encoding='utf-8')
                stream.write(f'\n\nDOCUMENT: Backwoods Home Magazine | {out.stem}\nPDF PAGE: {n}\nSOURCE FILE: {record["filename"]}\nEXTRACTION: OCR; confirm quantities and wording against the original PDF.\nREFERENCE TYPE: Historical magazine; independently verify safety-critical claims.\n\n{text}\n')
        record['status']='ocr_extracted_pending_review'
        print(f'Completed {record["filename"]}',flush=True)
    current=json.loads((stage/'manifest.json').read_text(encoding='utf-8'))
    updated={r['filename']:r['status'] for r in records if r['filename'].startswith(('02 -','03 -','04 -'))}
    for r in current:
        if r['filename'] in updated: r['status']=updated[r['filename']]
    (stage/'manifest.json').write_text(json.dumps(current,indent=2),encoding='utf-8')
if __name__=='__main__': main()
