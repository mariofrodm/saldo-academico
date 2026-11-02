import os
import time
import httpx

url=os.environ['APP_URL'].rstrip('/')+'/api/health'
expected=os.environ['EXPECTED_SHA']
for attempt in range(90):
    try:
        result=httpx.get(url,timeout=15,follow_redirects=False)
        if result.status_code==200 and result.json().get('commit')==expected and result.json().get('database')=='ok':
            print('Commit esperado publicado y BD accesible.'); break
    except (httpx.HTTPError,ValueError): pass
    time.sleep(10)
else: raise SystemExit('No se confirmó la publicación del commit esperado antes del límite.')
