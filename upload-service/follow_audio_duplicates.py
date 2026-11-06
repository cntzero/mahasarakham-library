import subprocess,time,sys
from pathlib import Path
script=Path(__file__).with_name('index_audio_duplicates.py')
while True:
 subprocess.run([sys.executable,str(script)],check=True)
 active=subprocess.run(['pgrep','-f','^python3 /mnt/data/projects/maha-library/upload-service/receive_windows_music.py'],capture_output=True).returncode==0
 if not active:break
 print('Import still active; checking new files again in 60 seconds.',flush=True)
 time.sleep(60)
print('Final duplicate pass complete.',flush=True)
