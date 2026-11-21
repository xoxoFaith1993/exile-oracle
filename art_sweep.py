"""Art sweep: pull item / gem / skill / passive art out of the installed PoE 2 (read-only) and make PNGs.

    python art_sweep.py              extract + convert + build the name -> picture index
    python art_sweep.py --index-only rebuild just the index (after a table re-convert)

Output (per game build): F:\\PoE2Toolkit\\gamefiles\\<build>\\art\\... (PNG, same folder layout as the game,
lower-case) and art-index.json mapping base items, uniques, gems, skills and passives to their PNG.
Personal use only: GGG's art stays on this PC."""

import concurrent.futures
import json
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import launch_sweep as ls  # noqa: E402  (install paths, build id)
from poe2kit import datc64  # noqa: E402

FOLDERS = ['art/2ditems/' + f for f in ('armours', 'weapons', 'gems', 'currency', 'offhand', 'flasks', 'maps',
                                         'quivers', 'belts', 'rings', 'amulets', 'jewels', 'crafting', 'relics',
                                         'charms', 'divination')] + ['art/2dart/skillicons']


def convert_one(src, dst):
    from PIL import Image
    if os.path.exists(dst):
        return 'skip'
    try:
        with Image.open(src) as im:
            im.load()
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            im.save(dst + '.part.png')
        os.replace(dst + '.part.png', dst)
        return 'ok'
    except Exception as e:
        return f'error: {type(e).__name__}: {e}'


def tables_dir(build):
    return os.path.join(ls.OUT_ROOT, build, 'tables')


def load(build, name, lenient=False):
    """Read a converted table; if the schema is a bit out of date, read the raw file leniently (leading columns)."""
    p = os.path.join(tables_dir(build), name + '.json')
    if os.path.exists(p):
        with open(p, encoding='utf-8') as f:
            return json.load(f)
    raw = os.path.join(ls.OUT_ROOT, build, 'raw', 'data', 'balance', name.lower() + '.datc64')
    t = datc64.Table(raw, name)
    if not t.exact and lenient and t.width > t.schema_width:
        t.exact = True  # columns added at the end of the row: the schema's columns still line up at the start
    return t.to_list()


def art_png(dds_path):
    if not dds_path:
        return None
    rel = dds_path.replace('\\', '/').lower()
    if rel.endswith('.dds'):
        rel = rel[:-4] + '.png'
    return rel


def build_index(build, art_root):
    bit = load(build, 'BaseItemTypes')
    ivi = load(build, 'ItemVisualIdentity', lenient=True)
    words = load(build, 'Words')
    usl = load(build, 'UniqueStashLayout')
    passives = load(build, 'PassiveSkills')
    active = load(build, 'ActiveSkills')

    def vis(i):
        if i is None or i >= len(ivi):
            return None
        rel = art_png(ivi[i].get('DDSFile'))
        return rel if rel and os.path.exists(os.path.join(art_root, rel)) else None

    idx = {'base': {}, 'unique': {}, 'passive': {}, 'skill': {}, 'build': build}
    for b in bit:
        name = b.get('Name')
        rel = vis(b.get('ItemVisualIdentity'))
        if name and rel and name not in idx['base']:
            idx['base'][name] = rel
    for u in usl:
        w = u.get('WordsKey')
        name = words[w].get('Text') if w is not None and w < len(words) else None
        rel = vis(u.get('ItemVisualIdentityKey'))
        if name and rel:
            idx['unique'].setdefault(name, rel)
    for p in passives:
        rel = art_png(p.get('Icon_DDSFile'))
        if p.get('Name') and rel and os.path.exists(os.path.join(art_root, rel)):
            idx['passive'].setdefault(p['Name'], rel)
    for a in active:
        rel = art_png(a.get('Icon_DDSFile'))
        if a.get('DisplayedName') and rel and os.path.exists(os.path.join(art_root, rel)):
            idx['skill'].setdefault(a['DisplayedName'], rel)
    return idx


def main(argv):
    bid, state, _ = ls.build_id()
    if state != 4:
        print('PoE 2 install not complete')
        return 1
    out = os.path.join(ls.OUT_ROOT, bid)
    raw, art = os.path.join(out, 'raw'), os.path.join(out, 'art')
    t0 = time.time()
    if '--index-only' not in argv:
        print('extracting art with poe2x ...')
        p = subprocess.run([ls.POE2X, 'extract', ls.INDEX, raw] + FOLDERS, capture_output=True, text=True)
        print(p.stdout[-1500:], p.stderr[-800:])
        if p.returncode != 0:
            return 2
        jobs = []
        for f in FOLDERS:
            base = os.path.join(raw, *f.split('/'))
            for root, _, files in os.walk(base):
                for fn in files:
                    if fn.lower().endswith('.dds'):
                        src = os.path.join(root, fn)
                        rel = os.path.relpath(src, raw).replace(os.sep, '/').lower()[:-4] + '.png'
                        jobs.append((src, os.path.join(art, *rel.split('/'))))
        print(f'converting {len(jobs)} textures ...')
        counts, errors = {}, []
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
            for i, r in enumerate(ex.map(lambda j: convert_one(*j), jobs)):
                k = 'error' if r.startswith('error') else r
                counts[k] = counts.get(k, 0) + 1
                if k == 'error' and len(errors) < 20:
                    errors.append(f'{jobs[i][0]}: {r}')
                if i and i % 2000 == 0:
                    print(f'  {i}/{len(jobs)} ({round(time.time() - t0)} s)')
        print('converted:', counts, ('first errors: ' + ' | '.join(errors[:5])) if errors else '')
    idx = build_index(bid, art)
    with open(os.path.join(out, 'art-index.json'), 'w', encoding='utf-8') as f:
        json.dump(idx, f)
    print(f"index: {len(idx['base'])} bases, {len(idx['unique'])} uniques, {len(idx['skill'])} skills, "
          f"{len(idx['passive'])} passives ({round(time.time() - t0)} s total)")
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
