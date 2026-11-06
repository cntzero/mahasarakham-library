import sys, json, hashlib, subprocess, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / 'pdf-libs'))
import pymupdf

source = Path(r'D:\Books\Backwoods Home Magazine')
stage = Path(__file__).parent / 'backwoods'
textdir = stage / 'indexed-text'
textdir.mkdir(parents=True, exist_ok=True)
records = []
for path in sorted(source.rglob('*.pdf')):
    doc = pymupdf.open(path)
    record = {'source':str(path), 'filename':path.name, 'pages':len(doc),
              'sha256':hashlib.file_digest(path.open('rb'),'sha256').hexdigest(),
              'low_text_pages':[], 'text_characters':0}
    out = textdir / (path.stem + '.txt')
    with out.open('w',encoding='utf-8') as stream:
        for n,page in enumerate(doc,1):
            text=page.get_text(sort=True).strip()
            if len(text)<80: record['low_text_pages'].append(n)
            record['text_characters'] += len(text)
            stream.write(f'\n\nDOCUMENT: Backwoods Home Magazine | {path.stem}\nPDF PAGE: {n}\nSOURCE FILE: {path.name}\nREFERENCE TYPE: Historical magazine; independently verify safety-critical claims.\n\n{text}\n')
    record['prepared_text']=str(out.resolve())
    record['status']='needs_ocr' if record['text_characters']<len(doc)*100 else 'text_extracted_pending_review'
    records.append(record)
    print(f'{path.name}: {len(doc)} pages, {record["text_characters"]} chars, {record["status"]}',flush=True)
    (stage/'manifest.json').write_text(json.dumps(records,indent=2),encoding='utf-8')
print('Preparation complete',flush=True)
