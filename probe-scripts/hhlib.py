import json, time, urllib.request, urllib.parse, urllib.error

UA = "salary-radar/0.1 (midat.faizov@gmail.com)"
BASE = "https://api.hh.ru"
PAUSE = 1.2

def get(path, params=None, timeout=30, base=BASE, pause=True):
    url = base + path
    if params:
        url += "?" + urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            status, headers, body = r.status, dict(r.headers), r.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        status, headers, body = e.code, dict(e.headers), e.read().decode("utf-8", "replace")
    if pause:
        time.sleep(PAUSE)
    return status, headers, body, url

def jload(body):
    try:
        return json.loads(body)
    except Exception:
        return None
