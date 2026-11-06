from pathlib import Path
import json,zipfile,hashlib,csv,re
root=Path(__file__).resolve().parent.parent
out=root/'outputs';out.mkdir(exist_ok=True)
summaries=[]
for key in ('backwoods','bushcraft'):
    stage=root/'work'/key
    records=json.loads((stage/'manifest.json').read_text(encoding='utf-8'))
    details=[]
    for r in records:
        p=Path(r['prepared_text']);text=p.read_text(encoding='utf-8')
        # Normalize legacy Windows punctuation from the embedded PDF fonts.
        text=text.translate({0x91:0x2018,0x92:0x2019,0x93:0x201c,0x94:0x201d,0x96:0x2013,0x97:0x2014,0x85:0x2026})
        p.write_text(text,encoding='utf-8')
        count=len(re.findall(r'^PDF PAGE: \d+$',text,re.M)) if key=='backwoods' else len(re.findall(r'^EPUB SECTION: \d+$',text,re.M))
        expected=r['pages'] if key=='backwoods' else r['chapters']
        if count!=expected:raise ValueError(f'{p.name}: {count} labels vs {expected}')
        if len(text)<100:raise ValueError('Empty text: '+str(p))
        details.append({'filename':p.name,'source':r['source'],'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'sections':count,'characters':len(text),'status':r.get('status','')})
    with (out/f'{key}-import-manifest.csv').open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=details[0].keys());w.writeheader();w.writerows(details)
    readme=f'''# {key.title()} prepared reference library

Source files were read without modification. The indexed text is a derived search copy.
Documents: {len(records)}. Page/section labels: {sum(r['sections'] for r in details)}.
Suggested separate private Open WebUI collection: MAHASARAKHAM - {"Backwoods Home Magazine" if key=="backwoods" else "Bushcraft Books"}.
Upload the text files in indexed-text/ to that collection using retrieval mode, not full-document context.
Keep the originals/EPUBs available separately for images, diagrams and source checking.
Server archive: /mnt/data/survival-library/{key}/

Quality limits: page/section labels and non-empty files were checked. This is not a complete editorial or safety review. OCR may misread quantities and column layouts. Historical magazine and ebook advice must be checked against current authoritative guidance for safety-critical tasks. Original PDF page numbers are PDF positions, not necessarily printed page numbers. EPUB section labels are not print pages.

Open WebUI import and retrieval acceptance testing: pending.
Internet-disconnected validation: deferred at the user's request.
'''
    if key=='backwoods':
        readme+='\nKnown source defect: 04 - The Fourth Year.pdf, PDF page 123 reports a truncated image (invalid 2D fax code). Review the original page; OCR cannot restore missing source pixels. Other pages have not received complete visual review.\n'
    with zipfile.ZipFile(out/f'{key}-import-ready.zip','w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        z.writestr('README.md',readme)
        z.write(stage/'manifest.json','catalog/source-manifest.json')
        z.write(out/f'{key}-import-manifest.csv','catalog/import-manifest.csv')
        for p in sorted((stage/'indexed-text').glob('*.txt')):z.write(p,'indexed-text/'+p.name)
    summaries.append({'collection':key,'documents':len(records),'sections':sum(r['sections'] for r in details),'text_bytes':sum(Path(r['prepared_text']).stat().st_size for r in records),'package_bytes':(out/f'{key}-import-ready.zip').stat().st_size})
(out/'library-preparation-summary.json').write_text(json.dumps(summaries,indent=2),encoding='utf-8')
print(json.dumps(summaries,indent=2))
