"""Isolated import integration checks; never writes to the real library."""
import argparse, importlib.util, io, json, os, shutil, subprocess, tempfile, threading, zipfile
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from http.server import ThreadingHTTPServer
from PIL import Image

parser=argparse.ArgumentParser();parser.add_argument('--require-mobi',action='store_true');args=parser.parse_args()
spec=importlib.util.spec_from_file_location('uploads',Path(__file__).with_name('server.py'));app=importlib.util.module_from_spec(spec);spec.loader.exec_module(app)
def epub(title):
    buf=io.BytesIO();cover=io.BytesIO();Image.new('RGB',(200,300),'green').save(cover,'JPEG')
    with zipfile.ZipFile(buf,'w') as z:
        z.writestr('mimetype','application/epub+zip')
        z.writestr('META-INF/container.xml','<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container"><rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles></container>')
        z.writestr('OEBPS/content.opf',f'''<package xmlns="http://www.idpf.org/2007/opf" version="2.0" unique-identifier="uid"><metadata xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:title>{title}</dc:title><dc:creator>MAHA Test Author</dc:creator><dc:identifier id="uid">urn:test:{title}</dc:identifier><dc:language>en</dc:language><meta name="cover" content="cover"/></metadata><manifest><item id="chapter" href="chapter.xhtml" media-type="application/xhtml+xml"/><item id="cover" href="cover.jpg" media-type="image/jpeg"/><item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/></manifest><spine toc="ncx"><itemref idref="chapter"/></spine></package>''')
        z.writestr('OEBPS/chapter.xhtml',f'<html xmlns="http://www.w3.org/1999/xhtml"><head><title>{title}</title></head><body><h1>{title}</h1><p>This is an isolated book import test.</p></body></html>')
        z.writestr('OEBPS/toc.ncx',f'<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1"><head><meta name="dtb:uid" content="urn:test:{title}"/></head><docTitle><text>{title}</text></docTitle><navMap><navPoint id="c1" playOrder="1"><navLabel><text>Chapter</text></navLabel><content src="chapter.xhtml"/></navPoint></navMap></ncx>')
        z.writestr('OEBPS/cover.jpg',cover.getvalue())
    return buf.getvalue()

with tempfile.TemporaryDirectory(prefix='maha-import-test-') as td:
    base=Path(td);app.ROOT=base/'imports';app.STATIC=base/'site';app.ASSETS=base/'assets.json';app.STATIC.mkdir();(app.STATIC/'catalog.json').write_text('[]');app.ASSETS.write_text('{"assets":[]}')
    for d in ['staging','originals','readable','covers']:(app.ROOT/d).mkdir(parents=True,exist_ok=True)
    server=ThreadingHTTPServer(('127.0.0.1',0),app.Handler);port=server.server_port;origin=f'http://127.0.0.1:{port}'
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    def upload(name,data,origin_header=None):
        from urllib.parse import quote
        req=Request(origin+'/api/library/upload',data=data,headers={'Origin':origin if origin_header is None else origin_header,'X-Maha-Upload':'1','X-File-Name':quote(name),'X-Book-Topic':'General reading','Content-Type':'application/octet-stream'})
        try:
            with urlopen(req,timeout=360) as response:return response.status,json.load(response)
        except HTTPError as e:return e.code,json.load(e)
    try:
        data=epub('Upload Test')
        status,result=upload('test.epub',data);assert status==200 and result['status']=='added',(status,result)
        entry=app.load_imports()[0];assert entry['title']=='Upload Test';assert (app.ROOT/'covers'/(entry['id']+'.jpg')).exists()
        assert upload('renamed.epub',data)[1]['status']=='skipped'
        assert upload('invalid.epub',b'not an ebook')[0]==422
        assert upload('test.exe',b'not a book')[0]==415
        assert upload('other.epub',data,'http://untrusted.example')[0]==403
        assert len(app.load_imports())==1
        old=base/'old.epub';old.write_bytes(epub('Already owned'));app.ASSETS.write_text(json.dumps({'assets':[{'remote':str(old),'url':'/files/test.epub'}]}));(app.STATIC/'catalog.json').write_text(json.dumps([{'id':'owned-fixture','title':'Already owned','sources':[{'url':'/files/test.epub'}]}]))
        assert upload('owned.epub',old.read_bytes())[1]['status']=='skipped'
        saved_queue=app.CLASSIFIER.queue
        app.CLASSIFIER.queue=lambda ident:(_ for _ in ()).throw(ConnectionError('classifier unavailable'))
        try:
            status,result=upload('sorting-offline.epub',epub('Sorting Offline Test'))
            assert status==200 and result['status']=='added'
            assert app.load_imports()[-1]['topic']=='To be sorted'
        finally:app.CLASSIFIER.queue=saved_queue
        # Real PDF fixture is read only. Imports stay in this temporary test root.
        live_assets=Path('/mnt/data/projects/maha-library/asset-map.json')
        pdf=next(Path(a['remote']) for a in json.loads(live_assets.read_text())['assets'] if a['format']=='PDF' and '/who-' in a['remote'])
        status,result=upload('reference.pdf',pdf.read_bytes());assert status==200 and result['status']=='added',(status,result)
        if shutil.which('ebook-convert'):
            mobi_epub=base/'mobi-test.epub';mobi_epub.write_bytes(epub('MOBI Upload Test'));mobi=base/'test.mobi'
            subprocess.run(['ebook-convert',str(mobi_epub),str(mobi)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,timeout=180,env=dict(os.environ,QT_QPA_PLATFORM='offscreen'))
            status,result=upload('converted.mobi',mobi.read_bytes());assert status==200 and result['status']=='added',(status,result)
            entry=app.load_imports()[-1];assert entry['sources'][0]['format']=='EPUB';assert entry['originalUrl'].endswith('.mobi');assert upload('renamed.mobi',mobi.read_bytes())[1]['status']=='skipped'
            print('MOBI original preservation, EPUB conversion and duplicate retry: passed')
        else:
            assert not args.require_mobi,'Install Calibre before running the full checks.'
            print('MOBI conversion check pending Calibre installation.')
        assert app.load_imports()==json.loads((app.ROOT/'catalog.json').read_text())
        with urlopen(origin+'/api/library/books') as response:assert len(json.load(response))==len(app.load_imports())+1
        print('EPUB/PDF import, cover extraction, duplicate detection, invalid-file rejection, origin protection and persisted catalog: passed')
    finally:server.shutdown();server.server_close()
