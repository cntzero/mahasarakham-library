"""Copy selected inventory MP3s, hash verify and de-duplicate. Keep all sources."""
import json,time
from pathlib import Path
import music
plan=Path('/mnt/data/projects/maha-library/music-inventory.json')
rows=json.loads(plan.read_text())['files'];results=[]
report=Path('/mnt/data/projects/maha-library/music-import-results.json')
selected=[r for r in rows if r['status']=='include']
for i,row in enumerate(selected,1):
 try:result=music.add_file(row['path'],Path(row['path']).name,source_path=row['path'])
 except Exception as exc:result={'status':'error','message':str(exc)}
 results.append({'source':row['path'],**result})
 if i%50==0 or i==len(selected):
  temp=report.with_suffix('.tmp');temp.write_text(json.dumps(results,indent=2,ensure_ascii=False));temp.replace(report)
  print('Imported',i,'/',len(selected),'added',sum(r['status']=='added' for r in results),'duplicates',sum(r['status']=='skipped' for r in results),'errors',sum(r['status']=='error' for r in results),flush=True)
