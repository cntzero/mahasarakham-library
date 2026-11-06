"""Read grouping tags into the catalog without changing original MP3 tags."""
import music

with music.connect() as db:
    rows=list(db.execute("SELECT id FROM tracks WHERE albumMetadataVersion=0 AND purgedAt=''"))
completed=0
for offset in range(0,len(rows),100):
    updates=[]
    for row in rows[offset:offset+100]:
        try:
            artist,disc,compilation=music.album_metadata(music.ROOT/'tracks'/(row['id']+'.mp3'))
            updates.append((artist,disc,compilation,row['id']))
        except Exception:
            print('Grouping tags unreadable for recording '+row['id']+'; existing information retained.',flush=True)
    with music.connect() as db:
        db.executemany('UPDATE tracks SET albumArtist=?,disc=?,compilation=?,albumMetadataVersion=1 WHERE id=? AND albumMetadataVersion=0',updates)
    completed+=len(updates)
    print('Album grouping tags read: '+str(completed)+' / '+str(len(rows)),flush=True)
print('Album metadata backfill complete. Original files unchanged.',flush=True)
