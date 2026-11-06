"""Update exactly one existing GoDaddy A record, using a private PAT credential."""
import argparse,datetime,ipaddress,json,os,re,sys
from pathlib import Path
from urllib.request import Request,build_opener,HTTPRedirectHandler
from urllib.error import HTTPError,URLError
from urllib.parse import quote,urlencode

DOMAIN='discerntechnologies.com';NAME='vpn'
BASE='https://api.godaddy.com/v3/domains/zones/'+DOMAIN+'/dns-records'
PROVIDERS=('https://api4.ipify.org','https://checkip.amazonaws.com')
class SafeError(Exception):pass
class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):raise SafeError('Unexpected HTTP redirect; no update made.')
OPENER=build_opener(NoRedirect())

def public_ipv4(value):
    try:address=ipaddress.IPv4Address(value.strip())
    except Exception:raise SafeError('IP lookup did not return an IPv4 address.')
    if not address.is_global:raise SafeError('IP lookup returned a non-public address; no update made.')
    return str(address)

def discover_ip():
    values=[]
    for url in PROVIDERS:
        try:
            with OPENER.open(Request(url,headers={'User-Agent':'MAHA-VPN-DDNS/1'}),timeout=12) as response:
                values.append(public_ipv4(response.read(128).decode('ascii')))
        except SafeError:raise
        except Exception:raise SafeError('Public IP lookup failed; retaining the existing DNS record.')
    if len(set(values))!=1:raise SafeError('Public IP sources disagree; retaining the existing DNS record.')
    return values[0]

def api(method,url,token,data=None):
    if not (url==BASE or url.startswith(BASE+'?') or url.startswith(BASE+'/')):raise SafeError('Request outside the permitted VPN-record API path.')
    body=json.dumps(data).encode() if data is not None else None
    request=Request(url,data=body,method=method,headers={'Authorization':'Bearer '+token,'Content-Type':'application/json','Accept':'application/json','User-Agent':'MAHA-VPN-DDNS/1'})
    try:
        with OPENER.open(request,timeout=20) as response:
            raw=response.read(1024**2)
            return json.loads(raw) if raw else None
    except HTTPError as error:
        # Never print response bodies or authentication headers.
        raise SafeError(f'GoDaddy API returned HTTP {error.code}. Check token validity, DNS permissions, and account eligibility.')
    except (URLError,TimeoutError):raise SafeError('GoDaddy API could not be reached; DNS update was not confirmed.')

def find_record(token):
    response=api('GET',BASE+'?'+urlencode({'type':'A','name':NAME,'page':1,'pageSize':100}),token)
    if not isinstance(response,dict) or not isinstance(response.get('items'),list):raise SafeError('Unexpected GoDaddy record-list response; no update made.')
    if len(response['items'])>=100:raise SafeError('Ambiguous record-list pagination; no update made.')
    records=[r for r in response['items'] if r.get('type')=='A' and r.get('name')==NAME]
    if len(records)!=1:raise SafeError('Expected exactly one existing vpn A record; no records created or removed.')
    record=records[0]
    if not isinstance(record.get('recordId'),str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}',record['recordId']):raise SafeError('Record identifier missing or unexpected; no update made.')
    public_ipv4(record.get('data',''))
    if not isinstance(record.get('ttl'),int) or not 600<=record['ttl']<=86400:raise SafeError('Unexpected record TTL; no update made.')
    return record

def synchronize(token,address,check=False,state=None):
    address=public_ipv4(address);record=find_record(token)
    if record['data']==address:return {'status':'current','address':address,'message':'VPN DNS already matches the current public IP.'}
    if check:return {'status':'would-update','address':address,'oldAddress':record['data'],'message':'Credentials verified; the VPN record needs an IP update.'}
    if state:
        state.mkdir(parents=True,exist_ok=True);(state/'record-before-update.json').write_text(json.dumps(record,indent=2))
    payload={'name':NAME,'type':'A','data':address,'ttl':record['ttl']}
    api('PUT',BASE+'/'+quote(record['recordId'],safe=''),token,payload)
    confirmed=find_record(token)
    if confirmed['data']!=address:raise SafeError('GoDaddy did not confirm the expected VPN IP. No further records were changed.')
    return {'status':'updated','address':address,'oldAddress':record['data'],'message':'VPN A record updated and verified.'}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true');args=parser.parse_args()
    credential_dir=os.environ.get('CREDENTIALS_DIRECTORY')
    token_path=Path(credential_dir)/'godaddy-pat' if credential_dir else Path('/etc/maha-vpn-ddns/token')
    state=Path(os.environ.get('STATE_DIRECTORY','/var/lib/maha-vpn-ddns'))
    try:
        token=token_path.read_text().strip()
        if not token or any(c.isspace() for c in token):raise SafeError('The saved token is empty or contains whitespace.')
        result=synchronize(token,discover_ip(),args.check,state if not args.check else None)
        result['checkedAt']=datetime.datetime.now(datetime.timezone.utc).isoformat()
        if not args.check:
            state.mkdir(parents=True,exist_ok=True);pending=state/'status.tmp';pending.write_text(json.dumps(result,indent=2));os.replace(pending,state/'status.json')
        print(json.dumps(result))
    except SafeError as error:print(str(error),file=sys.stderr);return 1
    except Exception:print('DNS check failed unexpectedly. Credentials were not displayed; existing DNS was retained unless an update was already submitted.',file=sys.stderr);return 1
    return 0

if __name__=='__main__':sys.exit(main())
