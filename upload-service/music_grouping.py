"""Shared display grouping for catalog, discoveries and browser actions; never edits tags."""
import re,json,unicodedata,datetime

def date(year,month,day):
 try:return datetime.date(int(year),int(month),int(day)).isoformat()
 except ValueError:return ''

def episode_date(row):
 if not row.get('artist') or row['artist']=='Unknown artist':return ''
 album=(row.get('album') or '').strip();match=re.match(r'^(\d{4})',row.get('year') or '');year=int(match[1]) if match else 0
 match=re.fullmatch(r'(\d{4})[./-](\d{2})[./-](\d{2})',album)
 if match:return date(*match.groups())
 months=['january','february','march','april','may','june','july','august','september','october','november','december']
 match=re.fullmatch(r'([a-z]+)\s+(\d{1,2})(?:st|nd|rd|th)?[,]?\s+(\d{4})',album,re.I)
 if match and match[1].lower() in months:return date(match[3],months.index(match[1].lower())+1,match[2])
 match=re.fullmatch(r'(\d{1,2})(?:st|nd|rd|th)?\s+([a-z]+)[,]?\s+(\d{4})',album,re.I)
 if match and match[2].lower() in months:return date(match[3],months.index(match[2].lower())+1,match[1])
 match=re.fullmatch(r'(\d{2})(\d{2})(\d{2})',album)
 if match and year and year%100==int(match[3]):return date(year,match[2],match[1])
 match=re.fullmatch(r'(\d{2}|\d{4})[./-](\d{2})[./-](\d{2})\s+s\d+e\d+',album,re.I)
 if match:
  value=int(match[1])
  if len(match[1])==2:
   if not year or year%100!=value:return ''
   value=year
  return date(value,match[2],match[3])
 return ''

def series(row):
 artist=(row.get('artist') or '').strip()
 if re.fullmatch(r'round the horne(?:\s*-\s*bbc)?',artist,re.I) or (artist.lower()=='kenneth horne' and (re.match(r'round the horne\s+vol',row.get('title') or '',re.I) or re.match(r'rhrn\s',row.get('originalName') or '',re.I))):return 'Round the Horne'
 return artist if episode_date(row) else ''

def title(row):
 value=(row.get('album') or 'Unknown album').strip()
 return re.sub(r'\s*(?:\(\s*(?:disc|disk|cd)\s*\d+(?:\s*(?:of|/)\s*\d+)?\s*\)|\[\s*(?:disc|disk|cd)\s*\d+\s*\]|[-–:]\s*(?:disc|disk|cd)\s*\d+)\s*$','',value,flags=re.I).strip() or value

def artist(row,is_compilation):
 value=row.get('resolvedAlbumArtist') or ('Various Artists' if row.get('inferredCompilation') else (row.get('albumArtist') or '').strip()) or ('Various Artists' if is_compilation(row) else row.get('artist') or 'Unknown artist')
 return re.sub(r'\s+(?:featuring|feat\.?|ft\.?)\s+.+$','',value,flags=re.I).strip()

def annotate(rows,is_compilation):
 covers={r['id']:r for r in rows if 'id' in r}
 for row in rows:
  row.pop('unknownSingles',None)
  programme=series(row);album=title(row);display_artist=artist(row,is_compilation)
  identity=unicodedata.normalize('NFKC',programme or display_artist).lower()
  identity=re.sub(r'^the\s+','',re.sub(r'\s+',' ',re.sub(r'\.(?=\s|$)','',identity)).strip())
  row['groupKey']=json.dumps([identity,'dated-episodes' if programme else 'album','' if programme else unicodedata.normalize('NFKC',album).lower()],ensure_ascii=False,separators=(',',':'))
  row['groupLabel']=programme or album;row['displayAlbumArtist']=display_artist;row['normalizedAlbumTitle']=album
  match=re.match(r'^\s*(\d+)',str(row.get('disc') or ''));disc=int(match[1]) if match else 0
  if disc<=0:
   match=re.search(r'(?:disc|disk|cd)\s*(\d+)',row.get('album') or '',re.I);disc=int(match[1]) if match else 1
  row['sortDisc']=disc
  sort_date=episode_date(row)
  if not sort_date and programme:
   match=re.search(r'(?:^|\s)(\d{2}|\d{4})[./-](\d{2})[./-](\d{2})\s+s\d+e\d+',row.get('originalName') or '',re.I)
   if match:
    year=int(match[1]);year=year+(1900 if year>=30 else 2000) if len(match[1])==2 else year
    sort_date=date(year,match[2],match[3])
  row['sortEpisodeDate']=sort_date
  if row.get('manualAlbumGroup'):
   row['groupKey']='manual:'+row['manualAlbumGroup'];row['groupLabel']=row['manualAlbumTitle'];row['normalizedAlbumTitle']=row['manualAlbumTitle'];row['displayAlbumArtist']=row['manualAlbumArtist']
   cover=covers.get(row.get('manualAlbumCoverId'),{})
   row['groupCover']=cover.get('cover') or row.get('cover','')
 # Collect only natural one-recording unknown-album groups. Manual merges and
 # multi-recording groups keep their identity; hidden duplicate copies count once.
 unknown={}
 for row in rows:
  if row.get('manualAlbumGroup') or (row.get('album') or '').strip().casefold() not in ('','unknown album','album unknown'):continue
  if row.get('purgedAt'):continue
  unknown.setdefault((row['groupKey'],bool(row.get('removedAt'))),[]).append(row)
 for (_,removed),group in unknown.items():
  identities={(r.get('audioSha256') or r.get('id') or id(r),(r.get('title') or '').casefold(),r.get('track') or '',r.get('disc') or '') for r in group}
  if len(identities)==1:
   for row in group:
    row['groupKey']='collection:unknown-album-singles'+(':removed' if removed else '')
    row['groupLabel']='Unknown album';row['normalizedAlbumTitle']='Unknown album';row['displayAlbumArtist']='Various Artists';row['unknownSingles']=True
 return rows
