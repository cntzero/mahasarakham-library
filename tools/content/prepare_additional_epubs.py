from pathlib import Path
import json,zipfile,xml.etree.ElementTree as ET,posixpath,re,hashlib,sys
from urllib.parse import unquote
sys.path.insert(0,str(Path('work/html-libs').resolve()))
from bs4 import BeautifulSoup
root=Path.cwd();audit=json.loads((root/'outputs/humble-epub-audit.json').read_text());out=root/'outputs/humble-additional-books';upload=out/'upload';upload.mkdir(parents=True,exist_ok=True)
records=[];empty=[];books=[]
for b in audit['epubs']:
 if b['group'] not in ('additional_pdf_title','additional_other_title'):continue
 source=Path(b['path']);slug=re.sub('[^a-z0-9]+','-',b['title'].lower()).strip('-')[:65]+'-'+b['sha256'][:8];folder=upload/slug;folder.mkdir(exist_ok=True);book_rows=[]
 with zipfile.ZipFile(source) as z:
  c=ET.fromstring(z.read('META-INF/container.xml'));opf=c.find('.//{*}rootfile').attrib['full-path'];doc=ET.fromstring(z.read(opf));items={x.attrib['id']:x.attrib for x in doc.findall('.//{*}manifest/{*}item')}
  for n,ref in enumerate(doc.findall('.//{*}spine/{*}itemref'),1):
   item=items[ref.attrib['idref']];path=posixpath.normpath(posixpath.join(posixpath.dirname(opf),unquote(item['href'].split('#')[0])))
   raw=z.read(path);s=BeautifulSoup(raw,'html.parser');body=s.body or s
   for x in body.select('script,style,noscript'):x.decompose()
   heading=next((x.get_text(' ',strip=True) for x in body.select('h1,h2,h3') if x.get_text(strip=True)),None)
   text=body.get_text('\n',strip=True);text=re.sub(r'[ \t]+',' ',text);text=re.sub(r'\n{3,}','\n\n',text).strip()
   if not text:
    empty.append({'book':b['title'],'section':n,'source_section':path,'reason':'no text; illustrations retained in original EPUB'});continue
   heading=heading or text.splitlines()[0][:160]
   content=f"BOOK: {b['title']}\nAUTHOR: {b.get('author') or 'Not stated'}\nEPUB SECTION: {n}\nSECTION HEADING: {heading}\nSOURCE SECTION: {path}\nSOURCE EPUB: {source}\nREFERENCE TYPE: Commercial ebook; claims not independently verified. EPUB section is a spine position, not a printed page number.\n\n{text}\n"
   target=folder/f'{slug}__section-{n:04d}.txt';target.write_text(content,encoding='utf-8');r={'book':b['title'],'section':n,'source_section':path,'file':str(target.relative_to(out)),'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'characters':len(text),'replacement_characters':text.count('\ufffd')};records.append(r);book_rows.append(r)
 books.append({'title':b['title'],'source':str(source),'source_sha256':b['sha256'],'spine_sections':b['spine_sections'],'prepared_sections':len(book_rows),'folder':str(folder.relative_to(out))})
 print('Prepared',len(books),b['filename'],len(book_rows),flush=True)
manifest={'books':books,'documents':records,'empty_sections':empty,'webui_import_status':'not imported'};(out/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
for r in records:assert hashlib.sha256((out/r['file']).read_bytes()).hexdigest()==r['sha256']
assert len(books)==44
assert len(list(upload.rglob('*.txt')))==len(records)
(out/'README.md').write_text(f'''# Additional Humble Bundle books\n\n44 EPUB titles; {len(records)} independently labelled section text files. {len(empty)} spine entries had no extractable text; their illustrations remain in the original EPUBs. All prepared-file hashes checked.\n\nCreate a new private collection: MAHASARAKHAM — Additional Practical Books. Upload the upload directory once. Do not upload this parent directory with manifest/README.\n\nOriginal EPUBs and PDFs remain unchanged on E:. Keep them for images, tables, and layout. Text extraction and matching were checked structurally, not fully edited page by page. EPUB section numbers are spine positions, not printed pages. These files have NOT been imported. Existing titles were excluded by the title/filename audit; editions have not been fully compared.\n''',encoding='utf-8')
print(json.dumps({'books':len(books),'documents':len(records),'empty_sections':len(empty),'replacement_characters':sum(r['replacement_characters'] for r in records),'max_section_characters':max(r['characters'] for r in records)}))
