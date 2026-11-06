import tempfile,json,io,time,os
from pathlib import Path
from PIL import Image
import music,music_art as art,music_identify as identify,music_identify_worker as worker
admin={'id':1,'role':'super'};owner={'id':2,'role':'user'};other={'id':3,'role':'user'}
def fails(fn,kind):
 try:fn()
 except kind:return
 raise AssertionError('Expected '+kind.__name__)
with tempfile.TemporaryDirectory() as directory:
 music.ROOT=Path(directory);ids=['a'*32,'b'*32]
 with music.connect() as db:
  for i,ident in enumerate(ids):
   db.execute("INSERT INTO tracks(id,sha256,title,artist,album,albumArtist,owner,tags,bytes,genre,year,track,disc,albumMetadataVersion) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(ident,ident,'Old '+str(i),'Artist','Old Album','Artist',2,'[]',4,'Rock','2000',str(i+1),'1',1))
   (music.ROOT/'tracks'/(ident+'.mp3')).write_bytes(b'MP3!')
 original_which=identify.shutil.which;identify.shutil.which=lambda name:'/usr/bin/fpcalc'
 identify.settings_path().write_text(json.dumps({'client':'fixture-client'}))
 worker.set_health(False,'Offline')
 fails(lambda:identify.start({'id':ids[0]},owner),ValueError)
 worker.set_health(True,'Reachable')
 fails(lambda:identify.start({'id':ids[0]},other),PermissionError)
 image=Image.new('RGB',(60,60),'blue');buffer=io.BytesIO();image.save(buffer,'PNG');cover=art.cache_image(buffer.getvalue())
 detail={'albumFields':{'album':'Correct Album','albumArtist':'Various Artists','year':'2001','compilation':True},'matches':[{'title':'Correct Song','artist':'Correct Artist','track':'7','disc':'1','genre':'Pop'}],'suggestedTags':['pop'],'cover':cover,'source':'https://musicbrainz.org/release/fixture'}
 worker.recognize=lambda job:[{'recording':'recording','release':'release','title':'Correct Song','artist':'Correct Artist','album':'Correct Album','date':'2001','genres':['pop']}]
 worker.release_details=lambda candidate:detail
 job=identify.start({'id':ids[0]},owner)['id'];assert worker.process_one()
 assert identify.status(other)['jobs']==[]
 fails(lambda:identify.choose({'id':job,'candidate':0},other),ValueError)
 identify.choose({'id':job,'candidate':0},owner);assert worker.process_one()
 with music.connect() as db:assert db.execute('SELECT title FROM tracks WHERE id=?',(ids[0],)).fetchone()[0]=='Old 0','Recognition must not auto-apply'
 fails(lambda:identify.apply({'id':job,'fields':[],'artwork':False,'scope':'track','artScope':'track'},owner),ValueError)
 result=identify.apply({'id':job,'fields':['title','album','tags'],'artwork':True,'scope':'album','artScope':'album','match':0},owner)
 assert result['count']==2
 with music.connect() as db:
  rows={r['id']:dict(r) for r in db.execute('SELECT * FROM tracks')}
 assert rows[ids[0]]['title']=='Correct Song' and rows[ids[1]]['title']=='Old 1'
 assert all(r['album']=='Correct Album' for r in rows.values())
 assert all(r['artist']=='Artist' for r in rows.values()),'Unchecked artist must remain unchanged'
 assert json.loads(rows[ids[0]]['tags'])==['pop'] and json.loads(rows[ids[1]]['tags'])==[]
 assert all((music.ROOT/'tracks'/(ident+'.mp3')).read_bytes()==b'MP3!' for ident in ids)
 assert all((music.ROOT/'covers'/(ident+'.jpg')).exists() for ident in ids)
 fails(lambda:identify.apply({'id':job,'fields':['title'],'scope':'track','artScope':'track'},owner),ValueError)
 # Edits after recognition invalidate the apply preview.
 job=identify.start({'id':ids[0]},owner)['id'];worker.process_one();identify.choose({'id':job,'candidate':0},owner);worker.process_one()
 with music.connect() as db:db.execute("UPDATE tracks SET title='Manual edit' WHERE id=?",(ids[0],))
 fails(lambda:identify.apply({'id':job,'fields':['title'],'scope':'track','artScope':'track'},owner),ValueError)
 # Album-wide application cannot cross ownership boundaries.
 with music.connect() as db:db.execute('UPDATE tracks SET owner=3 WHERE id=?',(ids[1],))
 job=identify.start({'id':ids[0]},owner)['id'];worker.process_one();identify.choose({'id':job,'candidate':0},owner);worker.process_one()
 fails(lambda:identify.apply({'id':job,'fields':['album'],'scope':'album','artScope':'track'},owner),PermissionError)
 assert 'fixture-client' not in json.dumps(identify.status(owner)), 'Saved application key must never be returned'
 identify.shutil.which=original_which
print('Identification: offline gating, owner privacy, explicit choices, selected-field/album scopes, original audio preservation, artwork, replay and stale-edit protection: passed')
