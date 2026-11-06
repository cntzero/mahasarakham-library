"""Reversible catalog visibility. Original books and ZIM files are never deleted."""
import os, time
from pathlib import Path
from urllib.parse import quote
import xml.etree.ElementTree as ET
import accounts

LIBRARY=Path(os.environ.get('MAHA_KIWIX_LIBRARY','/mnt/data/kiwix/library.xml'))

def initialize():
    with accounts.connection() as db:
        db.execute('CREATE TABLE IF NOT EXISTS collection_visibility(kind TEXT NOT NULL, item_id TEXT NOT NULL, hidden INTEGER NOT NULL, actor INTEGER, updated INTEGER NOT NULL, PRIMARY KEY(kind,item_id))')

def hidden(kind):
    initialize()
    with accounts.connection() as db:
        return {r['item_id'] for r in db.execute('SELECT item_id FROM collection_visibility WHERE kind=? AND hidden=1',(kind,))}

def set_hidden(kind,ident,value,actor):
    if kind not in ('book','kiwix') or not isinstance(ident,str) or not ident or len(ident)>200 or type(value) is not bool:
        raise ValueError('Choose an item and whether to hide it.')
    initialize()
    with accounts.connection() as db:
        db.execute('INSERT INTO collection_visibility VALUES(?,?,?,?,?) ON CONFLICT(kind,item_id) DO UPDATE SET hidden=excluded.hidden,actor=excluded.actor,updated=excluded.updated',(kind,ident,int(value),actor,int(time.time())))
    return {'id':ident,'hidden':value}

def archives():
    if not LIBRARY.is_file():return []
    rows=[]
    for b in ET.parse(LIBRARY).getroot().findall('book'):
        p=Path(b.get('path',''))
        if not p.is_absolute():p=LIBRARY.parent/p
        if not p.is_file():continue
        rows.append({'id':b.get('id'),'title':b.get('title') or p.stem,'description':b.get('description',''),'language':b.get('language',''),'date':b.get('date',''),'collection':b.get('creator',''),'edition':p.stem,'size':p.stat().st_size,'url':'/kiwix/content/'+quote(p.stem,safe=''),'cover':'/kiwix/catalog/v2/illustration/'+quote(b.get('id',''),safe='')+'/?size=48'})
    return rows
