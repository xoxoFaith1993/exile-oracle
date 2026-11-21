"""Download poe.ninja's public PoE 1 economy data dumps (CC-BY-SA), politely.

Source: https://poe.ninja/poe1/data  (list: /poe1/api/data/dumps, file: /poe1/api/data/dumps/dump?name=<league>)
Economy dumps only. Never touches poe.ninja builds/character APIs.

Raw zips go to F:\\Research-cache\\poe1\\zips (total > 500 MB, so off D:), one at a time, 3 s apart,
resumable (a file with the right size is skipped). Usage:  python -I fetch.py [League ...]
"""
import json
import os
import sys
import time
import urllib.parse
import urllib.request

ZIPS = r"F:\Research-cache\poe1\zips"
BASE = "https://poe.ninja/poe1/api/data/dumps"
UA = "Mozilla/5.0 (economy-research script; one request at a time)"

# Main challenge leagues only (no Ruthless, no short event leagues).
LEAGUES = [
    "Essence", "Breach", "Legacy", "Harbinger", "Abyss", "Bestiary", "Incursion", "Delve", "Betrayal",
    "Synthesis", "Legion", "Blight", "Metamorph", "Delirium", "Harvest", "Heist", "Ritual", "Ultimatum",
    "Expedition", "Scourge", "Archnemesis", "Sentinel", "Kalandra", "Sanctum", "Crucible", "Ancestor",
    "Affliction", "Necropolis", "Settlers", "Mercenaries", "Keepers", "Mirage", "Allflame",
]


def get(url, method="GET"):
    req = urllib.request.Request(url, method=method, headers={"User-Agent": UA})
    return urllib.request.urlopen(req, timeout=120)


def main(names):
    os.makedirs(ZIPS, exist_ok=True)
    with get(BASE) as r:
        listing = json.load(r)
    with open(os.path.join(ZIPS, "_listing.json"), "w", encoding="utf-8") as f:
        json.dump(listing, f, indent=1)
    for name in names:
        url = f"{BASE}/dump?name={urllib.parse.quote(name)}"
        out = os.path.join(ZIPS, f"{name}.zip")
        with get(url, "HEAD") as r:
            size = int(r.headers.get("Content-Length") or 0)
        if os.path.exists(out) and os.path.getsize(out) == size:
            print(f"{name}: cached ({size/1e6:.1f} MB)", flush=True)
            continue
        part = out + ".part"
        try:
            with get(url) as r, open(part, "wb") as f:
                while chunk := r.read(1 << 20):
                    f.write(chunk)
            os.replace(part, out)
            print(f"{name}: {os.path.getsize(out)/1e6:.1f} MB", flush=True)
        finally:
            if os.path.exists(part):
                os.remove(part)
        time.sleep(3)


if __name__ == "__main__":
    main(sys.argv[1:] or LEAGUES)
