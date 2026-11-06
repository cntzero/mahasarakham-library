import copy,io,json,tempfile
from pathlib import Path
from urllib.error import HTTPError
import update

record={'recordId':'vpn-record-id','name':'vpn','type':'A','data':'68.234.171.235','ttl':600}
calls=[];records=[copy.deepcopy(record)]
def fake_api(method,url,token,data=None):
    calls.append((method,url,data))
    if method=='GET':return {'items':copy.deepcopy(records)}
    assert method=='PUT' and url==update.BASE+'/vpn-record-id'
    assert data['name']=='vpn' and data['type']=='A'
    assert set(data)=={'name','type','data','ttl'}
    records[0].update(data);return copy.deepcopy(records[0])
real_api=update.api;update.api=fake_api
assert update.synchronize('fixture','68.234.171.235')['status']=='current'
assert not any(c[0]=='PUT' for c in calls)
assert update.synchronize('fixture','8.8.8.8',check=True)['status']=='would-update'
assert not any(c[0]=='PUT' for c in calls)
with tempfile.TemporaryDirectory() as td:
    result=update.synchronize('fixture','8.8.8.8',state=Path(td))
    assert result['status']=='updated'
    assert json.loads((Path(td)/'record-before-update.json').read_text())['data']=='68.234.171.235'
    assert len([c for c in calls if c[0]=='PUT'])==1
for bad in ('192.168.1.64','127.0.0.1','100.64.0.1','not an IP','::1'):
    try:update.synchronize('fixture',bad);raise AssertionError('Invalid public address accepted')
    except update.SafeError:pass
for invalid in ([],[copy.deepcopy(record),copy.deepcopy(record)],[dict(record,name='@')],[dict(record,type='CNAME')]):
    records[:]=invalid;before=len([c for c in calls if c[0]=='PUT'])
    try:update.synchronize('fixture','8.8.4.4');raise AssertionError('Ambiguous/wrong record accepted')
    except update.SafeError:pass
    assert len([c for c in calls if c[0]=='PUT'])==before
records[:]=[copy.deepcopy(record)];records[0]['ttl']=3600
update.synchronize('fixture','8.8.4.4');assert records[0]['ttl']==3600
update.api=real_api
class Reply:
    def __init__(self,value):self.value=value
    def __enter__(self):return self
    def __exit__(self,*args):pass
    def read(self,*args):return self.value.encode()
class Lookup:
    def __init__(self,values):self.values=iter(values)
    def open(self,*args,**kwargs):return Reply(next(self.values))
opener=update.OPENER;update.OPENER=Lookup(['68.234.171.235','68.234.171.235']);assert update.discover_ip()=='68.234.171.235'
update.OPENER=Lookup(['68.234.171.235','8.8.8.8'])
try:update.discover_ip();raise AssertionError('Disagreeing IPs accepted')
except update.SafeError:pass
class Denied:
    def open(self,*args,**kwargs):raise HTTPError(update.BASE,401,'Unauthorized',{},io.BytesIO(b'private-fixture-token'))
update.OPENER=Denied()
try:update.api('GET',update.BASE,'private-fixture-token');raise AssertionError('Authentication error ignored')
except update.SafeError as error:assert 'private-fixture-token' not in str(error)
update.OPENER=opener
try:update.api('PUT','https://example.test/unrelated','fixture',{});raise AssertionError('Foreign API path accepted')
except update.SafeError:pass
print('DDNS tests passed: exact-record updates, no-op/check mode, backups, invalid/ambiguous records, public-IP agreement, preserved TTL, and secret-safe errors.')
