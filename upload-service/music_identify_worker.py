"""Separate online worker: fingerprints, recognition and release artwork; never auto-applies."""
import json,time,subprocess,shutil,re,hashlib
from urllib.request import Request,build_opener,HTTPRedirectHandler
from urllib.parse import urlencode,quote
from urllib.error import HTTPError,URLError
import music_identify as identify,music_art as art,music_art_worker as archive
class NoRedirect(HTTPRedirectHandler):
 def redirect_request(self,*args,**kwargs):raise ValueError('Recognition provider redirected unexpectedly.')
OPENER=build_opener(NoRedirect())
def set_health(online,message):
 with identify.connect() as db:db.execute('INSERT OR REPLACE INTO identification_status VALUES(1,?,?,?)',(int(online),time.time(),message))
def probe():
 try:
  for host in ('https://api.acoustid.org/robots.txt','https://musicbrainz.org/robots.txt'):
   try:
    with OPENER.open(Request(host,headers={'User-Agent':'MAHA-LocalLibrary/1.0 (https://discerntechnologies.com)'}),timeout=6) as response:response.read(1024)
   except HTTPError as e:
    if e.code not in (400,401,404,405):raise
  set_health(True,'Online recognition services are reachable.');return True
 except Exception:set_health(False,'Internet connection required — MAHA cannot reach the recognition services.');return False
def credits(value):return ''.join(c.get('name',c.get('artist',{}).get('name',''))+c.get('joinphrase','') for c in value if isinstance(c,dict))[:500]
class RecognitionNetworkError(ConnectionError):pass
def mb(url):
 # Metadata GETs are safe to retry; keep provider pacing and URL validation.
 archive.allowed_url(url)
 for attempt in range(3):
  time.sleep(max(0,1.1-(time.monotonic()-archive.LAST_MB)));archive.LAST_MB=time.monotonic()
  try:
   request=Request(url,headers={'User-Agent':'MAHA-LocalLibrary/1.0 (https://discerntechnologies.com)','Accept':'application/json'})
   with archive.OPENER.open(request,timeout=15) as response:
    raw=response.read(2*1024**2+1)
    if len(raw)>2*1024**2:raise ValueError('MusicBrainz response was too large.')
    return json.loads(raw)
  except (URLError,TimeoutError,ConnectionError) as error:
   if isinstance(error,HTTPError) and error.code not in (408,429,500,502,503,504):raise
   print('MusicBrainz connection:',type(error).__name__,getattr(error,'code','network'),'attempt',attempt+1,flush=True)
   if attempt==2:raise RecognitionNetworkError('MusicBrainz metadata is temporarily unavailable. Retry identification in a minute; no changes were applied.') from error
   retry=error.headers.get('Retry-After','') if isinstance(error,HTTPError) and error.headers else ''
   if retry.isdigit() and int(retry)>60:raise RecognitionNetworkError('MusicBrainz is rate limiting requests. Wait a few minutes before retrying; no changes were applied.') from error
   time.sleep(max(2*(attempt+1),int(retry) if retry.isdigit() else 0))
def recognize(job):
 path=art.music.ROOT/'tracks'/(job['source']+'.mp3')
 if not shutil.which('fpcalc'):raise ValueError('Fingerprinting tool missing. Run the identification installer.')
 result=subprocess.run(['fpcalc','-json','-length','120',str(path)],capture_output=True,text=True,timeout=90)
 try:fingerprint=json.loads(result.stdout)
 except ValueError:raise ValueError('This MP3 could not be fingerprinted. Try another track.')
 if not fingerprint.get('fingerprint') or not fingerprint.get('duration'):raise ValueError('No usable audio fingerprint was produced.')
 payload=urlencode({'client':identify.settings().get('client',''),'duration':round(fingerprint['duration']),'fingerprint':fingerprint['fingerprint'],'meta':'recordings','format':'json'}).encode()
 with OPENER.open(Request('https://api.acoustid.org/v2/lookup',data=payload,headers={'Content-Type':'application/x-www-form-urlencoded','User-Agent':'MAHA-LocalLibrary/1.0'}),timeout=25) as response:
  raw=response.read(2*1024**2+1)
  if len(raw)>2*1024**2:raise ValueError('Recognition response was too large.')
  data=json.loads(raw)
 if data.get('status')!='ok':raise ValueError('AcoustID rejected this lookup. Check the application API key and try again.')
 candidates=[];seen=set()
 for result in sorted(data.get('results',[]),key=lambda r:r.get('score',0),reverse=True)[:3]:
  for recording in result.get('recordings',[])[:2]:
   ident=recording.get('id','')
   if not re.fullmatch('[a-f0-9-]{36}',ident):continue
   recording_data=mb('https://musicbrainz.org/ws/2/recording/'+ident+'?inc=artist-credits+releases+genres&fmt=json')
   genres=[g.get('name','') for g in sorted(recording_data.get('genres',[]),key=lambda g:g.get('count',0),reverse=True)[:6] if g.get('name')]
   for release in recording_data.get('releases',[])[:6]:
    rid=release.get('id','')
    if not re.fullmatch('[a-f0-9-]{36}',rid) or (ident,rid) in seen:continue
    seen.add((ident,rid));candidates.append({'recording':ident,'release':rid,'title':recording_data.get('title','')[:500],'artist':credits(recording_data.get('artist-credit',[])),'album':release.get('title','')[:500],'date':release.get('date',''),'country':release.get('country',''),'score':result.get('score',0),'genres':genres})
    if len(candidates)>=12:return candidates
 return candidates
def release_details(candidate):
 ident=candidate['release'];release=mb('https://musicbrainz.org/ws/2/release/'+ident+'?inc=recordings+artist-credits+release-groups&fmt=json');matches=[]
 for medium in release.get('media',[]):
  for track in medium.get('tracks',[]):
   recording=track.get('recording',{})
   if recording.get('id')!=candidate['recording']:continue
   matches.append({'title':str(track.get('title') or recording.get('title') or candidate['title'])[:500],'artist':credits(track.get('artist-credit') or recording.get('artist-credit') or []) or candidate['artist'],'track':str(track.get('number') or track.get('position') or ''),'disc':str(medium.get('position') or 1),'genre':', '.join(candidate.get('genres',[])[:2])[:500]})
 if not matches:raise ValueError('This release no longer contains the matched recording. Choose another release.')
 artwork='';art_message='No cover art is available for this release.'
 try:artwork=art.cache_image(archive.fetch('https://coverartarchive.org/release/'+ident+'/front-500'));art_message='Artwork loaded for your review.'
 except HTTPError as e:art_message='No cover art is available for this release.' if e.code==404 else 'Artwork service unavailable; metadata can still be reviewed.'
 except Exception:art_message='Artwork could not be retrieved; metadata can still be reviewed.'
 artist=credits(release.get('artist-credit',[]));groups=release.get('release-group',{});types=groups.get('secondary-types',[])
 return {'albumFields':{'album':str(release.get('title') or candidate['album'])[:500],'albumArtist':artist or candidate['artist'],'year':str(release.get('date') or candidate['date'])[:4],'compilation':'Compilation' in types or artist.casefold()=='various artists'},'matches':matches,'suggestedTags':candidate.get('genres',[]),'cover':artwork,'artMessage':art_message,'source':'https://musicbrainz.org/release/'+ident}
def process_one():
 with identify.connect() as db:
  db.execute('BEGIN IMMEDIATE');row=db.execute("SELECT * FROM identification_jobs WHERE state IN ('queued','details_queued') OR (state IN ('running','loading_details') AND updated<?) ORDER BY created LIMIT 1",(time.time()-240,)).fetchone()
  if not row:return False
  job=dict(row);details=job['state'] in ('details_queued','loading_details');db.execute('UPDATE identification_jobs SET state=?,updated=? WHERE id=?',('loading_details' if details else 'running',time.time(),job['id']))
 try:
  if details:
   detail=release_details(json.loads(job['candidates'])[job['chosen']]);values={'state':'ready','details':json.dumps(detail),'message':'Review the proposed fields and artwork. Nothing has been applied.'}
  else:
   candidates=recognize(job);values={'state':'review' if candidates else 'no_match','candidates':json.dumps(candidates),'message':'Choose a recording/release match. A song may appear on several different albums.' if candidates else 'No audio match found. Try another track from this album.'}
 except Exception as e:
  network=(isinstance(e,(URLError,TimeoutError,ConnectionError)) and not isinstance(e,HTTPError)) or (isinstance(e,HTTPError) and e.code in (429,500,502,503,504));message=str(e) if isinstance(e,RecognitionNetworkError) else 'AcoustID recognition is temporarily unavailable. Retry in a minute; no changes were applied.' if network else str(e)[:300] if isinstance(e,ValueError) else 'Identification failed ('+type(e).__name__+'). Try another track.'
  values={'state':'error','message':message}
  if network:set_health(False,'Internet connection required — recognition services are unavailable.')
 with identify.connect() as db:db.execute('UPDATE identification_jobs SET '+','.join(k+'=?' for k in values)+',updated=? WHERE id=?',(*values.values(),time.time(),job['id']))
 return True
if __name__=='__main__':
 last_probe=0
 while True:
  try:
   if time.monotonic()-last_probe>=60:probe();last_probe=time.monotonic()
   if not process_one():time.sleep(3)
  except Exception as e:print('Identification worker:',type(e).__name__,flush=True);time.sleep(5)
