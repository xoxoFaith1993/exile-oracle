"""Build datapack\\ : small files a fresh install uses instead of extracted game files and Claude-made research.
Run before each release (python make_datapack.py). Nothing personal goes in: no builds, characters or settings.

  worldareas.json       zone id -> name / act / town / level        (Sessions tab, from the game's WorldAreas table)
  essence_map.json      mod id -> essences that guarantee it        (Craft lab, from EssenceMods / Essences / Mods)
  currency_effects.json crafting currency + omen descriptions        (Craft lab)
  quest_rewards.json    campaign rewards per act                     (League start planner, from Path of Building)
  benchmarks.json       latest Top 1% cutoffs + top-1% gear samples (Top 1% tab; refreshed by the author with Claude)
  playbook.json         league start playbook (days 1-7 of past launches)   (Farming tab)
Drop-rate research ships as research\\drop-rates.json (already in the app folder)."""

import json
import os
import shutil
import time

from poe2kit import clientlog, config, crafting, db, leaguestart

OUT = os.path.join(config.ROOT, 'datapack')


def main():
    os.makedirs(OUT, exist_ok=True)
    con = db.connect()
    json.dump(crafting.essence_map(), open(os.path.join(OUT, 'essence_map.json'), 'w', encoding='utf-8'))
    areas = {k: {f: v.get(f) for f in ('Id', 'Name', 'Act', 'IsTown', 'AreaLevel', 'IsMapArea')}
             for k, v in clientlog.areas().items()}
    json.dump(areas, open(os.path.join(OUT, 'worldareas.json'), 'w', encoding='utf-8'))
    for name in ('currency_effects.json', 'quest_rewards.json'):
        p = os.path.join(config.DATA_DIR, name)
        if os.path.exists(p):
            shutil.copy2(p, OUT)
    bench = {'made': time.time(),
             'lists': [dict(r) for r in con.execute('SELECT * FROM bench')],
             'chars': [dict(r) for r in con.execute('SELECT * FROM bench_char')]}
    json.dump(bench, open(os.path.join(OUT, 'benchmarks.json'), 'w', encoding='utf-8'))
    pb = leaguestart.playbook(con)
    pb.pop('items', None)
    pb['made'] = time.time()
    json.dump(pb, open(os.path.join(OUT, 'playbook.json'), 'w', encoding='utf-8'))
    for f in sorted(os.listdir(OUT)):
        print(f'{f:<24} {os.path.getsize(os.path.join(OUT, f)) / 1024:8.1f} KB')


if __name__ == '__main__':
    main()
