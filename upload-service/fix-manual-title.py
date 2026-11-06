import json, shutil
from pathlib import Path
root=Path('/mnt/data/survival-library/imported-books');path=root/'book-metadata.json';data=json.loads(path.read_text()) if path.exists() else {}
ident='import-0e2d97476fc588e9eba31f0c'
if ident not in data:
    backup=Path('/mnt/data/backups/manual-title-20261104');backup.mkdir(exist_ok=True)
    if path.exists():shutil.copy2(path,backup/'before-book-metadata.json')
    else:(backup/'before-book-metadata.json').write_text('{}')
    data[ident]={'title':'Garage door opener manual','author':'dlybarger'}
    temp=path.with_suffix('.tmp');temp.write_text(json.dumps(data,indent=2));temp.replace(path)
    print('Manual display title corrected; original PDF unchanged.')
else:print('Existing user-edited title retained.')
