"""Step 2: Internet Archive. List (CDX) every archived copy of poe.ninja's PoE 2 unique-item economy JSON
(stash item overview + item history) and download the raw captures (id_ form). Economy endpoints only.
4 s between requests to archive.org; everything cached in ../cache."""
import json, os
import fetchlib as f

OUT = os.path.join(f.CACHE, 'wayback')
os.makedirs(OUT, exist_ok=True)
CDX = ('https://web.archive.org/cdx/search/cdx?url=poe.ninja/poe2/api/economy/stash/&matchType=prefix'
       '&output=json&fl=timestamp,original,statuscode,length&limit=5000')

if __name__ == '__main__':
    s, rows = f.get_json(CDX, spacing=5, timeout=240)
    caps = [dict(zip(rows[0], r)) for r in rows[1:] if r[2] == '200']
    got = []
    for c in caps:
        if '/builds/' in c['original'] or 'character' in c['original']:
            continue
        url = f"https://web.archive.org/web/{c['timestamp']}id_/{c['original']}"
        st, d = f.get_json(url, spacing=4, timeout=120)
        print(c['timestamp'], c['original'].split('economy/')[1][:90], st, 'ok' if d is not None else 'NOJSON')
        if d is not None:
            got.append({'timestamp': c['timestamp'], 'url': c['original'], 'wayback': url, 'data': d})
    json.dump(got, open(os.path.join(OUT, 'captures.json'), 'w'))
    print(len(got), 'captures saved')
