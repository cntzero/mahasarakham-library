import time
import music_art_worker as worker
original=worker.art.connect
worker.ONLINE_AFTER=time.monotonic()+60
worker.art.connect=lambda:(_ for _ in ()).throw(AssertionError('Cooldown must not claim an album'))
assert worker.process_one() is False
worker.art.connect=original
worker.ONLINE_AFTER=0
print('Provider cooldown leaves queued albums and retry counts untouched: passed')
