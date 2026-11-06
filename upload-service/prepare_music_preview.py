from pathlib import Path
import json,shutil,tarfile
root=Path('/mnt/data/projects/maha-library/music-preview-fixtures');root.mkdir(exist_ok=True)
rows=json.loads(Path('/mnt/data/projects/maha-library/music-inventory.json').read_text())['files']
for i,row in enumerate(sorted((r for r in rows if r['status']=='include'),key=lambda r:r['bytes'])[:3]):shutil.copyfile(row['path'],root/f'fixture-{i}.mp3')
with tarfile.open(root.parent/'music-preview-fixtures.tar','w') as archive:
 for p in root.glob('*.mp3'):archive.add(p,arcname=p.name)
print('Three small fixture songs copied for disposable UI tests.')
