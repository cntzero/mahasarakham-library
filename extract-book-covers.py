import json,zipfile,posixpath,xml.etree.ElementTree as ET,io,subprocess,tempfile,os
from pathlib import Path
from urllib.parse import unquote
from PIL import Image,ImageOps
base=Path('/mnt/data/projects/maha-library')
books=json.loads((base/'dist/catalog.json').read_text())
assets={a['url']:a['remote'] for a in json.loads((base/'asset-map.json').read_text())['assets']}
out=base/'cover-update';(out/'covers').mkdir(parents=True,exist_ok=True)
report=[]
for b in books:
 errors=[];image=None;kind=None
 for source in sorted(b['sources'],key=lambda s:s['format']!='EPUB'):
  path=assets.get(source['url'])
  if not path:continue
  try:
   if source['format']=='EPUB':
    with zipfile.ZipFile(path) as z:
     container=ET.fromstring(z.read('META-INF/container.xml'))
     opf=next(e.attrib['full-path'] for e in container.iter() if e.tag.endswith('rootfile'))
     package=ET.fromstring(z.read(opf));items=[e for e in package.iter() if e.tag.endswith('}item')];cover_id=next((e.attrib.get('content') for e in package.iter() if e.tag.endswith('}meta') and e.attrib.get('name')=='cover'),None)
     candidates=[i for i in items if 'cover-image' in i.attrib.get('properties','').split() or i.attrib.get('id')==cover_id]
     candidates += [i for i in items if i.attrib.get('media-type','').startswith('image/') and 'cover' in i.attrib.get('href','').lower() and i not in candidates]
     for item in candidates:
      member=posixpath.normpath(posixpath.join(posixpath.dirname(opf),unquote(item.attrib['href'].split('#')[0])))
      try:image=Image.open(io.BytesIO(z.read(member)));image.load();break
      except Exception:continue
    kind='embedded EPUB cover'
   elif source['format']=='PDF':
    with tempfile.TemporaryDirectory() as td:
     prefix=td+'/cover';subprocess.run(['pdftoppm','-f','1','-singlefile','-scale-to','900','-jpeg',path,prefix],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
     image=Image.open(prefix+'.jpg');image.load()
    kind='PDF first page'
   if image is not None:break
  except Exception as e:errors.append(str(e))
 if image is not None:
  image=ImageOps.exif_transpose(image).convert('RGB');image.thumbnail((640,960));image.save(out/'covers'/f"{b['id']}.jpg",quality=85,optimize=True)
  b['cover']='covers/'+b['id']+'.jpg';b['coverSource']=kind
 report.append({'id':b['id'],'title':b['title'],'cover':b.get('cover'),'source':kind,'errors':errors})
(out/'catalog.json').write_text(json.dumps(books,ensure_ascii=False,indent=2))
(out/'cover-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
print(json.dumps({'total':len(books),'covers':sum(bool(b.get('cover')) for b in books),'missing':[b['title'] for b in books if not b.get('cover')]}))
