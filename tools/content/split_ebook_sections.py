"""Build independently attributable search documents; never modify originals."""
from pathlib import Path
import json,re,hashlib,zipfile,csv

root=Path(__file__).resolve().parent.parent
records=json.loads((root/'work/bushcraft/manifest.json').read_text(encoding='utf-8'))
out=root/'outputs/bushcraft-sections-v2'
texts=out/'sections';texts.mkdir(parents=True,exist_ok=True)
rows=[];skipped=[]
for book in records:
    source=Path(book['prepared_text'])
    text=source.read_text(encoding='utf-8')
    starts=list(re.finditer(r'^BOOK: .+\nAUTHOR: .*\nEPUB SECTION: \d+\nSOURCE SECTION: .+\nSOURCE MOBI: .+\nREFERENCE TYPE: .+\n',text,re.M))
    if len(starts)!=book['chapters']:raise ValueError(f'Section count mismatch: {source.name}')
    slug=source.stem[:22]+'-'+book['sha256'][:8]
    included=0
    for i,m in enumerate(starts):
        header=m.group(0)
        body=text[m.end():starts[i+1].start() if i+1<len(starts) else len(text)].strip()
        section=int(re.search(r'EPUB SECTION: (\d+)',header).group(1))
        if not body:
            skipped.append({'book':book['title'],'section':section,'reason':'no extracted body text; image-only sections remain in EPUB'})
            continue
        heading=next((line.strip() for line in body.splitlines() if line.strip()),'Untitled')[:160]
        filename=f'{slug}__section-{section:04d}.txt'
        folder=texts/slug/f'batch-{included//75+1:02d}'
        folder.mkdir(parents=True,exist_ok=True)
        content=header+'SECTION OPENING: '+heading+'\n\n'+body+'\n'
        target=folder/filename;target.write_text(content,encoding='utf-8')
        if len(re.findall(r'^EPUB SECTION: ',content,re.M))!=1:raise ValueError('Ambiguous metadata')
        rows.append({'book':book['title'],'author':book['author'],'epub_section':section,'source_section':re.search(r'^SOURCE SECTION: (.+)',header,re.M).group(1),'file':target.relative_to(out).as_posix(),'bytes':target.stat().st_size,'sha256':hashlib.sha256(target.read_bytes()).hexdigest()})
        included+=1
manifest={'version':2,'documents':rows,'excluded_empty_sections':skipped,'original_books':len(records),'source_sections':sum(b['chapters'] for b in records),'webui_import_status':'pending'}
(out/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
with (out/'manifest.csv').open('w',newline='',encoding='utf-8-sig') as f:
    w=csv.DictWriter(f,fieldnames=rows[0].keys());w.writeheader();w.writerows(rows)
readme=f'''# Bushcraft ebook search library v2

{len(records)} books; {len(rows)} independent text files from {sum(b['chapters'] for b in records)} EPUB spine sections.
{len(skipped)} sections had no extracted text and were excluded; illustrations remain available in the original EPUBs.

Each file contains one EPUB section with its own book/author/source metadata. EPUB section numbers are spine positions, not printed chapters or page numbers. Text files contain no images. Safety-critical statements must be checked against originals and current authoritative references.

Import into a NEW private Open WebUI collection named MAHASARAKHAM - Bushcraft Books v2. Keep embedding concurrency at 2. Import one batch directory (at most 75 files) at a time and wait for completion. Do not use the old whole-book collection in the same test chat. Preserve that old collection until replacement retrieval has passed checks.

The manifest records SHA-256 hashes, source book and EPUB section. Upload/indexing in Open WebUI is pending; staging files on the server is not an import.
'''
(out/'README.md').write_text(readme,encoding='utf-8')
archive=root/'outputs/bushcraft-section-library-v2.zip'
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
    for p in out.rglob('*'):
        if p.is_file():z.write(p,p.relative_to(out).as_posix())
with zipfile.ZipFile(archive) as z:
    if z.testzip():raise ValueError('ZIP failed')
print(json.dumps({'books':len(records),'text_sections':len(rows),'empty_sections_excluded':len(skipped),'batches':len(set(str(Path(r['file']).parent) for r in rows)),'max_file_bytes':max(r['bytes'] for r in rows),'zip_bytes':archive.stat().st_size},indent=2))
