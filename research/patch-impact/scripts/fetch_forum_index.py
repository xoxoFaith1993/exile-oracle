"""Step 1a: list every thread in GGG's official PoE 2 patch-notes forum (forum 2212, public, no login).
Caches each index page under cache/forum/. Polite: 3 s between requests.
Usage: python fetch_forum_index.py"""
import html
import json
import os
import re
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, 'cache', 'forum')
UA = {'User-Agent': 'poe2-personal-toolkit/0.3 (patch research)'}
BASE = 'https://www.pathofexile.com/forum/view-forum/2212'


def get(url, path):
    if os.path.exists(path):
        return open(path, encoding='utf-8').read()
    body = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60).read().decode('utf-8')
    open(path, 'w', encoding='utf-8').write(body)
    time.sleep(3)
    return body


def threads(s):
    out = []
    for m in re.finditer(r'<div class="title">\s*<a href="/forum/view-thread/(\d+)">\s*(.*?)\s*</a>.*?'
                         r'post_by_account" ><a href="/account/view-profile/([^"]+)">.*?<span class="post_date">, ([^<]+)</span>',
                         s, re.S):
        out.append({'thread': int(m.group(1)), 'title': html.unescape(m.group(2)).strip(),
                    'author': m.group(3), 'posted_forum_time': m.group(4).strip()})
    return out


def main():
    os.makedirs(CACHE, exist_ok=True)
    allt, page = [], 1
    while page < 40:
        url = BASE if page == 1 else f'{BASE}/page/{page}'
        s = get(url, os.path.join(CACHE, f'f2212_p{page}.html'))
        t = threads(s)
        if not t:
            break
        new = [x for x in t if x['thread'] not in {y['thread'] for y in allt}]
        if not new:
            break
        allt += new
        print(page, len(t), t[-1]['title'], t[-1]['posted_forum_time'])
        page += 1
    json.dump(allt, open(os.path.join(CACHE, 'forum_threads.json'), 'w', encoding='utf-8'), indent=1)
    print(len(allt), 'threads')


if __name__ == '__main__':
    main()
