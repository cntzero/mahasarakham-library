from pathlib import Path
import urllib.request,re,html,json,hashlib,sys,concurrent.futures
sys.path.insert(0,str(Path('work/pdf-libs').resolve()))
import fitz
url='https://www.who.int/teams/environment-climate-change-and-health/water-sanitation-and-health/environmental-health-in-emergencies/technical-notes-on-wash-in-emergencies'
links={int(re.search(r'who-tn-(\d+)',u)[1]):u for u in json.loads(Path('work/who-download-urls.json').read_text())}
assert len(links)==15,links
out=Path('outputs/who-wash-reference-set');out.mkdir(exist_ok=True)
upload=Path('outputs/who-wash-remaining-14-upload');upload.mkdir(exist_ok=True)
def get(item):
 n,u=item;name=u.split('/')[-1].split('?')[0];data=urllib.request.urlopen(urllib.request.Request(u,headers={"User-Agent":"Mozilla/5.0"}),timeout=90).read();assert data.startswith(b'%PDF')
 p=out/name;p.write_bytes(data)
 with fitz.open(p) as d:
  text='\n'.join(page.get_text() for page in d);pages=len(d)
 assert pages>=4 and len(text)>2000,(n,pages,len(text))
 if n!=5:(upload/name).write_bytes(data)
 return {'note':n,'filename':name,'url':u,'pages':pages,'sha256':hashlib.sha256(data).hexdigest(),'extracted_characters':len(text),'document_date':'Updated July 2013' if '2013' in text else 'check document','import_status':'previously uploaded' if n==5 else 'pending'}
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:rows=sorted(pool.map(get,links.items()),key=lambda r:r['note'])
(out/'manifest.json').write_text(json.dumps({'official_index':url,'documents':rows},indent=2))
print(json.dumps({'downloaded':len(rows),'upload_files':len(list(upload.glob('*.pdf'))),'pages':sum(r['pages'] for r in rows),'folder':str(upload.resolve())}))
