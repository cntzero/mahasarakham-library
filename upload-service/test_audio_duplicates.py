import tempfile,json,shutil,sys
from pathlib import Path
import music
from mutagen.id3 import ID3,TXXX
inventory=json.loads(Path('/mnt/data/projects/maha-library/music-inventory.json').read_text())['files']
sample=Path(min((r for r in inventory if r['status']=='include'),key=lambda r:r['bytes'])['path'])
with tempfile.TemporaryDirectory() as temp:
 temp=Path(temp);variant=temp/'variant.mp3';shutil.copyfile(sample,variant)
 tags=ID3(variant);tags.add(TXXX(encoding=3,desc='MAHA test',text='metadata variant'));tags.save(variant)
 assert music.digest(sample)!=music.digest(variant)
 assert music.audio_digest(sample)==music.audio_digest(variant)
 music.ROOT=temp/'library'
 first=music.add_file(sample,sample.name,1)
 second=music.add_file(variant,sample.name,1)
 assert first['status']=='added' and second['status']=='skipped' and first['id']==second['id']
 assert len(music.catalog({'id':1,'role':'super'}))==1
 assert music.artist_identity('The Beatles')==music.artist_identity('Beatles')
 rows=[{'id':'one','audioSha256':'same','album':'Anthology 2','artist':'Beatles','albumArtist':'The Beatles'}, {'id':'two','audioSha256':'same','album':'Anthology 2','artist':'Beatles','albumArtist':''}]
 assert len(music.collapse_audio_duplicates(rows))==1
 rows[1]['audioSha256']='different'
 assert len(music.collapse_audio_duplicates(rows))==2
 rows[1]['audioSha256']='same';rows[1]['album']='Another release'
 assert len(music.collapse_audio_duplicates(rows))==2
print('Metadata-only duplicate suppression, artist aliases, different audio and separate releases: passed')
