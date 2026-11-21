"""Launch-day data sweep: read the installed PoE 2 game files (read-only, game closed) into JSON tables.

    python launch_sweep.py            # extract + convert, folder named after the Steam build id
    python launch_sweep.py --check    # just report what's installed and which tables the schema can read

Steps:
  1. find the install (Steam, F:) and its build id;
  2. poe2x extracts data/balance (the .datc64 tables) to F:\\PoE2Toolkit\\gamefiles\\<build>\\raw;
  3. datc64.py converts every table the schema matches to JSON in ...\\<build>\\tables;
  4. a report lists tables read, tables whose schema is out of date (expect some right after a patch,
     until the community schema catches up), and errors.
Nothing is ever written to the game folder."""

import json
import os
import re
import shutil
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from poe2kit import datc64  # noqa: E402

from poe2kit import config  # noqa: E402

GAME = config.poe2_dir() or ''
INDEX = os.path.join(GAME, 'Bundles2', '_.index.bin')
POE2X = config.poe2x()
OUT_ROOT = config.GAMEFILES_DIR
# The tables the toolkit uses first; everything else is converted too when it matches the schema.
KEY_TABLES = ['BaseItemTypes', 'Mods', 'Stats', 'Tags', 'ItemClasses', 'SkillGems', 'GemEffects',
              'GrantedEffects', 'ActiveSkills', 'UniqueStashLayout', 'Words', 'PassiveSkills',
              'Ascendancy', 'Characters', 'CurrencyItems', 'ModType']


def build_id():
    try:
        with open(config.steam_manifest() or '', encoding='utf-8') as f:
            s = f.read()
        bid = re.search(r'"buildid"\s+"(\d+)"', s)
        state = re.search(r'"StateFlags"\s+"(\d+)"', s)
        done = re.search(r'"BytesDownloaded"\s+"(\d+)"', s), re.search(r'"BytesToDownload"\s+"(\d+)"', s)
        return (bid.group(1) if bid else 'unknown', int(state.group(1)) if state else None,
                tuple(int(m.group(1)) if m else 0 for m in done))
    except OSError:
        return 'not-installed', None, (0, 0)


def main(argv):
    bid, state, (got, total) = build_id()
    ready = os.path.exists(INDEX) and state == 4  # 4 = fully installed
    print(f'build {bid}, Steam state {state}, downloaded {got / 1e9:.1f}/{total / 1e9:.1f} GB, index found: '
          f'{os.path.exists(INDEX)}')
    if '--check' in argv or not ready:
        if not ready:
            print('Not ready: wait until Steam says the install is complete, and close the game before sweeping.')
        return 0 if '--check' in argv else 1
    out = os.path.join(OUT_ROOT, bid)
    raw, tables = os.path.join(out, 'raw'), os.path.join(out, 'tables')
    t0 = time.time()
    if '--convert-only' in argv and os.path.isdir(raw):
        print('using already-extracted files in', raw)
    else:
        print('extracting data tables with poe2x ...')
        # the tables, plus the atlas layout and stat texts the Atlas page reads (poe2kit/atlas.py, statdesc.py)
        p = subprocess.run([POE2X, 'extract', INDEX, raw, 'data/balance', 'metadata/atlasskillgraphs',
                            'data/statdescriptions'], capture_output=True, text=True)
        print(p.stdout[-2000:], p.stderr[-2000:])
        if p.returncode != 0:
            return 2
    if os.path.isdir(tables):
        shutil.rmtree(tables)  # our own converted output only (never the game folder)
    print('converting tables ...')
    rep = datc64.dump_folder(os.path.join(raw, 'data', 'balance'), tables)
    rep['build'] = bid
    rep['seconds'] = round(time.time() - t0)
    rep['key_tables_missing'] = [k for k in KEY_TABLES if not any(o.lower().startswith(k.lower() + ' (') for o in rep['ok'])]
    with open(os.path.join(out, 'sweep-report.json'), 'w', encoding='utf-8') as f:
        json.dump(rep, f, indent=1)
    print(f"read {len(rep['ok'])} English tables, {len(rep['empty'])} empty, {len(rep['schema_mismatch'])} schema mismatches, "
          f"{len(rep['errors'])} errors in {rep['seconds']} s")
    print('key tables not read:', rep['key_tables_missing'] or 'none')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
