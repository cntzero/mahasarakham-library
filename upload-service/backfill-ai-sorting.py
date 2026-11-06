"""Owner-authorized one-time AI backfill through the running library API."""
import json, secrets, sys, time
from pathlib import Path
from urllib.request import Request,urlopen
import accounts

origin='http://127.0.0.1:8123'
state_path=Path(sys.argv[1])
state_path.parent.mkdir(parents=True,exist_ok=True)
token=secrets.token_urlsafe(32)
with accounts.connection() as db:
    user=db.execute("SELECT id FROM users WHERE active=1 AND role='super' ORDER BY id LIMIT 1").fetchone()
    if not user:raise SystemExit('No active Super user is available.')
    db.execute('INSERT INTO sessions VALUES(?,?,?)',(accounts.digest(token),user['id'],int(time.time())+86400))

def request(path,data=None):
    req=Request(origin+'/api/library/'+path,data=json.dumps(data).encode() if data is not None else None,headers={'Origin':origin,'X-Maha-Upload':'1','Content-Type':'application/json','Cookie':'maha_session='+token})
    with urlopen(req,timeout=30) as response:return json.load(response)

def save():
    state['updatedAt']=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())
    temp=state_path.with_suffix('.tmp');temp.write_text(json.dumps(state,indent=2));temp.replace(state_path)

try:
    if state_path.exists():state=json.loads(state_path.read_text())
    else:
        books=request('books');backup=state_path.parent/'before-classification.json'
        source=Path('/mnt/data/survival-library/imported-books/classification.json')
        backup.write_bytes(source.read_bytes() if source.exists() else b'{}')
        (state_path.parent/'before-catalog.json').write_text(json.dumps(books,indent=2))
        state={'status':'running','total':len(books),'books':[{'id':b['id'],'title':b['title'],'status':'not-queued'} for b in books]};save()
    for book in state['books']:
        if book['status']=='not-queued':
            result=request('classify',{'id':book['id']});book.update(status='queued',revision=result['revision']);save()
    deadline=time.monotonic()+23*3600
    while time.monotonic()<deadline:
        current={b['id']:b for b in request('books')}
        for book in state['books']:
            if book['status'] not in ('queued','running'):continue
            latest=current.get(book['id']);record=latest.get('classification',{}) if latest else {}
            if not latest:book['status']='removed-during-backfill'
            elif record.get('revision')!=book['revision']:book['status']='changed-during-backfill'
            elif record.get('state') in ('queued','running'):book['status']=record['state']
            elif record.get('state')=='sorted':book.update(status='sorted',category=latest['topic'],tags=latest.get('tags',[]))
            elif record.get('suggestedTopic'):
                # Accept the model's lower-confidence suggestion as requested.
                result=request('classification',{'id':book['id'],'topic':record['suggestedTopic'],'tags':latest.get('tags',[])})
                book.update(status='accepted-suggestion',category=result['topic'],tags=result['tags'],aiRecord=record)
            else:book.update(status='needs-review',note=record.get('note','AI sorting did not produce a category.'))
        remaining=sum(b['status'] in ('queued','running','not-queued') for b in state['books'])
        state['remaining']=remaining
        state['counts']={s:sum(b['status']==s for b in state['books']) for s in sorted({b['status'] for b in state['books']})}
        if not remaining:state['status']='complete'
        save()
        if not remaining:print(json.dumps({'status':state['status'],'counts':state['counts']}),flush=True);break
        time.sleep(3)
    else:state['status']='timed-out';save()
except Exception as error:
    if 'state' in globals():state['status']='interrupted';state['error']=type(error).__name__;save()
    raise
finally:
    accounts.logout(token)
