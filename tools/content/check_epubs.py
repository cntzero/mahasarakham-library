import json,zipfile,xml.etree.ElementTree as ET,csv
from pathlib import Path
from html.parser import HTMLParser
class Text(HTMLParser):
    def __init__(self): super().__init__();self.parts=[];self.skip=0
    def handle_starttag(self,tag,attrs):
        if tag in ('script','style'): self.skip+=1
        if tag in ('p','br','div','h1','h2','h3','li'): self.parts.append('\n')
    def handle_endtag(self,tag):
        if tag in ('script','style'): self.skip=max(0,self.skip-1)
    def handle_data(self,data):
        if not self.skip:self.parts.append(data)
base=Path(__file__).parent/'bushcraft'
records=json.loads((base/'manifest.json').read_text())
(base/'indexed-text').mkdir(exist_ok=True)
for record in records:
    if record['status']!='converted':continue
    with zipfile.ZipFile(record['epub']) as z:
        if z.testzip(): raise ValueError('Corrupt EPUB')
        container=ET.fromstring(z.read('META-INF/container.xml'))
        opf=next(e.attrib['full-path'] for e in container.iter() if e.tag.endswith('rootfile'))
        root=ET.fromstring(z.read(opf));parent=Path(opf).parent
        record['title']=next((e.text for e in root.iter() if e.tag.endswith('}title')),Path(record['source']).stem)
        record['author']='; '.join(e.text or '' for e in root.iter() if e.tag.endswith('}creator'))
        items={e.attrib['id']:e.attrib['href'] for e in root.iter() if e.tag.endswith('}item')}
        chapters=[items[e.attrib['idref']] for e in root.iter() if e.tag.endswith('}itemref')]
        target=base/'indexed-text'/(Path(record['epub']).stem+'.txt')
        chars=0
        with target.open('w',encoding='utf-8') as f:
            for n,href in enumerate(chapters,1):
                path=(parent/href.split('#')[0]).as_posix()
                from urllib.parse import unquote
                parser=Text();parser.feed(z.read(unquote(path)).decode('utf-8',errors='replace'))
                text=''.join(parser.parts);chars+=len(text)
                f.write(f'\n\nBOOK: {record["title"]}\nAUTHOR: {record["author"]}\nEPUB SECTION: {n}\nSOURCE SECTION: {path}\nSOURCE MOBI: {Path(record["source"]).name}\nREFERENCE TYPE: Commercial ebook; independently verify safety-critical claims.\n\n{text}\n')
        record.update(chapters=len(chapters),text_characters=chars,validation='zip_and_spine_checked',prepared_text=str(target.resolve()))
(base/'manifest.json').write_text(json.dumps(records,indent=2),encoding='utf-8')
print(json.dumps({'books':len(records),'validated':sum(r.get('validation')=='zip_and_spine_checked' for r in records),'total_text_characters':sum(r.get('text_characters',0) for r in records)},indent=2))
