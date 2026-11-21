"""Patch notes: fetch GGG's posts (Steam News API, public), parse them into lines, and flag every line that
touches the author's builds (gems, uniques, keystones, ascendancy, Witch / Blood Mage) with a rough buff/nerf tag.
Also works on pasted text (for notes that are only on the forum)."""

import json
import re
import time
import urllib.request

from . import config, db, gamedata, vault

STEAM = 'https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/?appid=2694490&count={n}&maxlength=0&feeds=steam_community_announcements&format=json'
BUFF = re.compile(r'\b(increased|more|now (?:also )?(?:grants|gains|deals|has)|higher|faster|added|no longer (?:has|requires|costs|consumes)|buff|improved|reduced (?:cost|cooldown|mana cost|reservation|spirit))', re.I)
NERF = re.compile(r'\b(reduced|less|lower|slower|removed|no longer|now requires|nerf|decreased|can no longer)', re.I)


_PREV = re.compile(r'(\d+(?:\.\d+)?)(?:\s*-\s*(\d+(?:\.\d+)?))?\s*%?[^()]{0,80}?\(previously\s*\+?(\d+(?:\.\d+)?)(?:\s*-\s*(\d+(?:\.\d+)?))?', re.I)
_WORSE_WHEN_UP = re.compile(r'cost|cooldown|reservation|requirement|duration of .*debuff|damage taken|delay', re.I)


def _numeric_direction(text):
    """'X (previously Y)': compare the numbers. Higher is better unless it's a cost/cooldown/requirement."""
    m = _PREV.search(text)
    if not m:
        return None
    a1, a2, b1, b2 = m.groups()
    new = (float(a1) + float(a2 or a1)) / 2
    old = (float(b1) + float(b2 or b1)) / 2
    if new == old:
        return 'change'
    up = new > old
    if _WORSE_WHEN_UP.search(text[:m.end()]) and not re.search(r'efficiency|recovery', text[:m.end()], re.I):
        up = not up
    return 'buff' if up else 'nerf'


def fetch_posts(n=30):
    req = urllib.request.Request(STEAM.format(n=n), headers={'User-Agent': config.user_agent()})
    with urllib.request.urlopen(req, timeout=30) as r:
        items = json.loads(r.read())['appnews']['newsitems']
    return [{'gid': it['gid'], 'title': it['title'], 'date': it['date'], 'url': it.get('url'), 'contents': it['contents']}
            for it in items]


def _clean(t):
    return re.sub(r'\s+', ' ', re.sub(r'\[[^\]]*\]', '', t or '')).strip()


def parse(contents):
    """GGG's BBCode (both layouts: [p]/[b] sections or [h3] headings) or pasted text -> lines."""
    out, section = [], 'General'
    if '[' not in contents:  # pasted plain text
        for raw in contents.splitlines():
            l = raw.strip(' 	-•*')
            if not l:
                continue
            if len(l) < 70 and not l.endswith('.') and raw.strip() == l:
                section = l
                continue
            out.append({'section': section, 'text': l, 'parent': None})
        return out
    tokens = re.split(r'(\[/?[a-z0-9*]+(?:=[^\]]*)?\])', contents, flags=re.I)
    depth, cur, heading, hbuf, loose, bold_only = 0, None, False, '', '', True
    last = {}

    def flush():
        nonlocal cur
        if cur is not None:
            text = _clean(cur['text'])
            if text:
                parent = last.get(cur['depth'] - 1) if cur['depth'] > 1 else None
                out.append({'section': section, 'text': text, 'parent': parent})
                last[cur['depth']] = text[:200]
        cur = None

    for tk in tokens:
        low = tk.lower()
        if re.fullmatch(r'\[h\d\]', low):
            flush(); heading, hbuf = True, ''
        elif re.fullmatch(r'\[/h\d\]', low):
            heading = False
            if _clean(hbuf):
                section = _clean(hbuf)[:120]
        elif low == '[list]':
            flush(); depth += 1
        elif low == '[/list]':
            flush(); depth = max(0, depth - 1)
        elif low == '[*]':
            flush(); cur = {'text': '', 'depth': max(depth, 1)}
        elif low == '[/*]':
            flush()
        elif low == '[p]':
            if depth == 0 and cur is None:
                loose, bold_only = '', True
        elif low == '[/p]':
            if depth == 0 and cur is None:
                t = _clean(loose)
                if t and len(t) < 120 and bold_only:
                    section = t
                loose = ''
        elif low in ('[b]', '[/b]', '[i]', '[/i]', '[u]', '[/u]') or low.startswith('[url') or low.startswith('[/url')                 or low.startswith('[img'):
            pass
        elif tk.startswith('[') and tk.endswith(']'):
            pass
        else:
            if heading:
                hbuf += tk
            elif cur is not None:
                cur['text'] += tk
            elif depth == 0:
                if tk.strip():
                    loose += tk
                    # text outside [b] means it's a paragraph, not a section title
                    bold_only = bold_only and False if not re.search(r'\[b\]\s*$', '') else bold_only
    flush()
    return out


def _vocab(con):
    """Names in the author's own builds (owner 'me'), most specific first."""
    from . import character
    mine = {}
    for r in con.execute("SELECT id, label FROM build WHERE owner='me' ORDER BY id DESC").fetchall():
        try:
            c = character.character(con, r['id'])
        except Exception:
            continue
        for g in c['skills']:
            for gem in g['gems']:
                mine.setdefault(gem['name'], ('gem', r['label']))
        for it in c['gear'] + c['jewels']:
            if it['rarity'] == 'UNIQUE':
                mine.setdefault(it['name'], ('unique', r['label']))
            for rn in it.get('runes') or []:
                mine.setdefault(rn, ('rune', r['label']))
        for k in c['keystones']:
            mine.setdefault(k['name'], ('keystone', r['label']))
        for a in c['ascendancy_nodes']:
            if len(a['name']) > 5 and a['name'] not in ('Life', 'Life Leech'):
                mine.setdefault(a['name'], ('ascendancy node', r['label']))
        if c.get('ascendancy'):
            mine.setdefault(c['ascendancy'], ('ascendancy', r['label']))
    return mine


def analyze(con, contents, title='pasted notes'):
    lines = parse(contents)
    watch_words = config.watch_words()
    mine = _vocab(con)
    names = sorted(mine, key=len, reverse=True)
    pats = [(n, re.compile(r'(?<![\w])' + re.escape(n) + r'(?![\w])', re.I)) for n in names if len(n) >= 4]
    for_you, watch = [], []
    for ln in lines:
        text = ln['text']
        ctx = (ln.get('parent') or '') + ' ' + text
        hits = [n for n, p in pats if p.search(ctx)]
        direction = _numeric_direction(text)
        if not direction:
            b, nf = len(BUFF.findall(text)), len(NERF.findall(text))
            direction = 'buff?' if b > nf else 'nerf?' if nf > b else 'change'
        row = dict(ln, direction=direction)
        if hits:
            row['hits'] = [{'name': h, 'kind': mine[h][0], 'build': mine[h][1]} for h in hits[:6]]
            for_you.append(row)
        elif any(w in ctx.lower() for w in watch_words):
            row['watch'] = [w for w in watch_words if w in ctx.lower()][:4]
            watch.append(row)
    sections = {}
    for ln in lines:
        sections[ln['section']] = sections.get(ln['section'], 0) + 1
    return {'title': title, 'lines': len(lines), 'sections': sections, 'for_your_builds': for_you,
            'witch_blood_mage_watch': watch, 'all': lines,
            'note': 'buff?/nerf? are word-based guesses: read the line. Hits come from the builds you own in the vault.'}


def store(con, gid, title, date, result):
    con.execute('CREATE TABLE IF NOT EXISTS patch_notes (gid TEXT PRIMARY KEY, title TEXT, date REAL, result TEXT)')
    con.execute('INSERT OR REPLACE INTO patch_notes VALUES(?,?,?,?)', (gid, title, date, json.dumps(result)))
    con.commit()


def listing(con):
    con.execute('CREATE TABLE IF NOT EXISTS patch_notes (gid TEXT PRIMARY KEY, title TEXT, date REAL, result TEXT)')
    rows = con.execute('SELECT gid, title, date, result FROM patch_notes ORDER BY date DESC').fetchall()
    out = []
    for r in rows:
        res = json.loads(r['result'])
        out.append({'gid': r['gid'], 'title': r['title'], 'date': r['date'], 'lines': res['lines'],
                    'for_you': len(res['for_your_builds']), 'watch': len(res['witch_blood_mage_watch'])})
    return out


def get(con, gid):
    r = con.execute('SELECT * FROM patch_notes WHERE gid=?', (gid,)).fetchone()
    return dict(json.loads(r['result']), gid=r['gid'], date=r['date']) if r else None


def is_patch_post(title):
    t = title.lower()
    return 'patch notes' in t or 'hotfix' in t or re.search(r'\b\d+\.\d+\.\d+[a-z]?\b', t) is not None


def sync(con, n=30):
    """Analyze official patch-note posts not seen yet. Returns the new results."""
    new = []
    con.execute('CREATE TABLE IF NOT EXISTS patch_notes (gid TEXT PRIMARY KEY, title TEXT, date REAL, result TEXT)')
    for p in fetch_posts(n):
        if not is_patch_post(p['title']) or len(p['contents']) < 1500:
            continue
        if con.execute('SELECT 1 FROM patch_notes WHERE gid=?', (p['gid'],)).fetchone():
            continue
        res = analyze(con, p['contents'], p['title'])
        res['url'] = p['url']
        store(con, p['gid'], p['title'], p['date'], res)
        new.append({'gid': p['gid'], 'title': p['title'], 'for_you': len(res['for_your_builds']),
                    'watch': len(res['witch_blood_mage_watch'])})
    return new
