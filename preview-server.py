"""Read-only preview. Only explicitly mapped original files can be served."""
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlsplit, unquote
import argparse,json

parser=argparse.ArgumentParser()
parser.add_argument('--port',type=int,default=8766)
parser.add_argument('--server-paths',action='store_true')
args=parser.parse_args()
root=Path(__file__).resolve().parent
assets=json.loads((root/'asset-map.json').read_text())['assets']
paths={unquote(a['url']):Path(a['remote'] if args.server_paths else a['local']) for a in assets}
class Handler(SimpleHTTPRequestHandler):
    def __init__(self,*a,**kw):super().__init__(*a,directory=str(root/'dist'),**kw)
    def translate_path(self,path):
        key=unquote(urlsplit(path).path)
        if key.startswith('/files/'):
            return str(paths.get(key,root/'missing-file'))
        return super().translate_path(path)
    def list_directory(self,path):
        self.send_error(403,'Directory listing disabled')
        return None
    def end_headers(self):
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Referrer-Policy','no-referrer')
        super().end_headers()
print(f'Local preview on http://127.0.0.1:{args.port}',flush=True)
ThreadingHTTPServer(('127.0.0.1',args.port),Handler).serve_forever()
