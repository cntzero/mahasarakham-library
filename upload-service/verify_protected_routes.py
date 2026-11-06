import json,ssl
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.error import HTTPError

context=ssl.create_default_context(cafile='/etc/maha-library/pki/ca.crt')
base='https://192.168.1.64'
try:
    urlopen(base+'/api/library/books',context=context,timeout=10)
    raise AssertionError('Unauthenticated API request was accepted.')
except HTTPError as error:
    assert error.code==401,error.code
source=json.loads(Path('/mnt/data/projects/maha-library/asset-map.json').read_text())['assets'][0]['url']
for path in ('/catalog.json',source):
    with urlopen(Request(base+path,method='HEAD'),context=context,timeout=10) as response:
        assert response.headers.get_content_type()=='text/html','A book/catalog file was accessible before sign-in.'
with urlopen(base+'/login.html',context=context,timeout=10) as response:
    assert b'Sign in' in response.read()
print('TLS verification and unauthenticated API/catalog/original-book protection: passed')
