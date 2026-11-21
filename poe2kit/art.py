"""Game-file art lookups: base items, uniques, skills and passives -> PNG.
Uses the newest game build with an art-index.json: this PC's own extraction (art_sweep.py) if there is one, else the
art bundled with an installed copy (toolkit\\gameart\\<build>)."""

import glob
import json
import os

from . import config

ROOT = config.GAMEFILES_DIR
_cache = {'mtime': None, 'idx': None, 'dir': None}


def _index():
    files = glob.glob(os.path.join(ROOT, '*', 'art-index.json')) or \
        glob.glob(os.path.join(config.ROOT, 'gameart', '*', 'art-index.json'))
    if not files:
        return None, None
    newest = max(files, key=os.path.getmtime)
    m = os.path.getmtime(newest)
    if _cache['mtime'] != m:
        with open(newest, encoding='utf-8') as f:
            idx = json.load(f)
        idx_l = {k: {n.lower(): v for n, v in d.items()} for k, d in idx.items() if isinstance(d, dict)}
        _cache.update(mtime=m, idx=idx_l, dir=os.path.join(os.path.dirname(newest), 'art'))
    return _cache['idx'], _cache['dir']


def find(kind, name):
    """kind: base | unique | skill | passive. Returns a relative art path (for /art/<path>) or None."""
    idx, _ = _index()
    if not idx or not name:
        return None
    return idx.get(kind, {}).get(name.lower())


def file_for(rel):
    """Absolute PNG path for a relative art path, refusing anything outside the art folder."""
    _, d = _index()
    if not d:
        return None
    p = os.path.normpath(os.path.join(d, rel))
    return p if p.startswith(os.path.normpath(d) + os.sep) and os.path.exists(p) else None
