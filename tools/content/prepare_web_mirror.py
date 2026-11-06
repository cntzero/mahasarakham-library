from pathlib import Path
import os,sys,re,json,hashlib,csv,concurrent.futures,html
sys.path.insert(0,str(Path('work/html-libs').resolve()))
from bs4 import BeautifulSoup
base=Path(r'D:\Backup of WD elements ext drive\Off_line_internet\Websites\www_askaprepper_com\www.askaprepper.com')
out=Path('outputs/offline-web-articles-v2');upload=out/'upload';upload.mkdir(parents=True,exist_ok=True)
jobs=[]
for domain,sub in [('askaprepper','www.askaprepper.com'),('wikipedia-en','en.wikipedia.org/wiki')]:
 for e in os.scandir(base/sub):
  if e.is_file() and e.name.lower().endswith(('.html','.htm')):jobs.append((domain,Path(e.path)))
  elif e.is_dir():
   p=Path(e.path)/'index.html'
   if p.is_file():jobs.append((domain,p))
print('Candidates:',len(jobs),flush=True)
def extract(job):
 domain,p=job
 try:
  raw=p.read_bytes()
  try: decoded=raw.decode('utf-8')
  except UnicodeDecodeError: decoded=raw.decode('cp1252',errors='replace')
  s=BeautifulSoup(decoded,'html.parser');meta=s.find('meta',property='og:type')
  if domain=='askaprepper':
   body=s.select_one('.entry-content');heading=s.select_one('h1.jeg_post_title')
   if not body or not heading:return {'status':'excluded','path':str(p),'reason':'no article title/body'}
  else:
   body=s.select_one('#mw-content-text .mw-parser-output') or s.select_one('#mw-content-text');heading=s.select_one('#firstHeading')
   if not body or not heading:return {'status':'excluded','path':str(p),'reason':'no encyclopedia article body'}
   if ':' in heading.get_text():return {'status':'excluded','path':str(p),'reason':'Wikipedia special namespace'}
  title=heading.get_text(' ',strip=True)
  for x in body.select('script,style,noscript,form,nav,aside,.sharedaddy,.jnews_inline_related_post,.jeg_ad,.adsbygoogle,.mw-editsection,.navbox,.vertical-navbox,.toc,.reflist') :x.decompose()
  text=body.get_text('\n',strip=True);text=re.sub(r'\n{3,}','\n\n',text)
  if domain=='askaprepper':text=re.split(r'\nYou may also like:\s*\n',text,maxsplit=1)[0].rstrip()
  if len(text)<500:return {'status':'excluded','path':str(p),'reason':'short/empty body'}
  mir=re.search(r'Mirrored from (\S+) by HTTrack',decoded)
  if mir:
   u=html.unescape(mir[1]);u=u if u.startswith('http') else 'https://'+u
  else:
   from urllib.parse import urljoin
   link=s.find('link',rel='canonical');u=urljoin('https://www.askaprepper.com/' if domain=='askaprepper' else 'https://en.wikipedia.org/wiki/',link.get('href','')) if link else 'Original URL not determined'
  date=s.find('meta',property='article:published_time');published=date.get('content','not stated') if date else 'not stated'
  sha=hashlib.sha256(text.encode()).hexdigest()
  return {'status':'ready','domain':domain,'title':title,'source_url':u,'publication_date':published,'source_path':str(p),'body_sha256':sha,'body':text,'characters':len(text)}
 except Exception as e:return {'status':'error','path':str(p),'reason':str(e)}
rows=[];seen=set()
with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
 for i,r in enumerate(pool.map(extract,jobs)):
  if r['status']=='ready':
   if r['body_sha256'] in seen:r.pop('body');r['status']='duplicate'
   else:
    seen.add(r['body_sha256']);slug=re.sub(r'[^a-z0-9]+','-',r['title'].lower()).strip('-')[:95];name=f"{slug}-{r['body_sha256'][:10]}.txt"
    folder=upload/r['domain'];folder.mkdir(exist_ok=True);dest=folder/name
    content=f"TITLE: {r['title']}\nSOURCE URL: {r['source_url']}\nPUBLICATION DATE: {r['publication_date']}\nMIRROR STARTED: 2021-06-10; individual page capture date not verified\nSOURCE TYPE: {'Commercial preparedness website; claims not independently verified' if r['domain']=='askaprepper' else 'Wikipedia historical snapshot; verify claims against cited sources'}\nLOCAL ORIGINAL: {r['source_path']}\n\n"+r.pop('body')+'\n'
    dest.write_text(content,encoding='utf-8');r['prepared_file']=str(dest.resolve());r['prepared_sha256']=hashlib.sha256(dest.read_bytes()).hexdigest()
  rows.append(r)
  if (i+1)%250==0:print('Processed',i+1,flush=True)
counts={k:sum(r['status']==k for r in rows) for k in ['ready','duplicate','excluded','error']}
(out/'manifest.json').write_text(json.dumps({'scope':'Immediate HTML files and index.html in immediate subdirectories of main Ask a Prepper and English Wikipedia wiki folders; other domains and deeper variants not exhaustively scanned','counts':counts,'documents':rows},indent=2),encoding='utf-8')
print(json.dumps(counts),flush=True)
