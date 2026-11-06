"""Real MP3 parsing/copy fixtures plus ownership, duplicates and AI race checks."""
import tempfile,json,hashlib,io,sys
from pathlib import Path
import music,music_tag_worker as worker
inventory=json.loads(Path('/mnt/data/projects/maha-library/music-inventory.json').read_text())['files']
sample=Path(min((row for row in inventory if row['status']=='include'),key=lambda row:row['bytes'])['path'])
original_sha=music.digest(sample)
class Response:
 def __enter__(self):return self
 def __exit__(self,*args):pass
 def read(self):return json.dumps({'message':{'content':json.dumps({'tags':['rock'],'confidence':.95})}}).encode()
with tempfile.TemporaryDirectory(prefix='maha-music-test-') as temporary:
 music.ROOT=Path(temporary)/'library';user={'id':10,'role':'user'};other={'id':11,'role':'user'};superuser={'id':1,'role':'super'}
 added=music.add_file(sample,sample.name,10,source_path=sample);assert added['status']=='added';ident=added['id']
 assert music.digest(music.ROOT/'tracks'/(ident+'.mp3'))==original_sha
 assert music.add_file(sample,'same.mp3',11)['status']=='skipped'
 assert len(music.catalog(user))==1 and music.catalog(user)[0]['canEdit']
 assert not music.catalog(other)[0]['canEdit'] and music.catalog(superuser)[0]['canEdit']
 try:music.edit({'id':ident,'title':'Unauthorized change'},other);raise AssertionError('Ownership bypass')
 except PermissionError:pass
 try:music.queue_tags(ident,other);raise AssertionError('AI ownership bypass')
 except PermissionError:pass
 music.edit({'id':ident,'title':'Fixture title','tags':['favorite']},user)
 assert music.catalog(user)[0]['title']=='Fixture title' and music.catalog(user)[0]['tags']==['favorite']
 music.queue_tags(ident,user)
 def racing_edit(*args,**kwargs):
  music.edit({'id':ident,'tags':['manual wins']},user);return Response()
 worker.urlopen=racing_edit;assert worker.process_one()
 assert music.catalog(user)[0]['tags']==['manual wins'] and music.catalog(user)[0]['tagState']=='manual'
 music.queue_tags(ident,superuser);worker.urlopen=lambda *a,**k:Response();assert worker.process_one()
 assert music.catalog(user)[0]['tagState']=='sorted' and 'rock' in music.catalog(user)[0]['tags']
 invalid=Path(temporary)/'bad.mp3';invalid.write_bytes(b'not MP3 audio')
 try:music.add_file(invalid,'bad.mp3',10);raise AssertionError('Invalid audio accepted')
 except ValueError:pass
 assert len(music.catalog(user))==1
assert music.digest(sample)==original_sha,'Original source must never change'
print('Music MP3 validation, verified copies, duplicate detection, owner/super permissions, manual tags, AI backfill and manual-edit race: passed')
