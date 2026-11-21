"""Cut each raw poe.ninja dump down to what the analysis needs.

Keeps only the softcore CHALLENGE league (not Hardcore, not Standard) and drops the huge item types we do not
use (base types, skill gems, enchants, cluster jewels, normal maps, beasts...). Output, small enough for the repo:
  cache/slim/<League>.currency.csv.gz   Date;Get;Pay;Value;Confidence  (all pairs)
  cache/slim/<League>.items.csv.gz      Date;Type;Name;Variant;Links;Value;Confidence  (Value is in Chaos)
Usage:  python -I slim.py   (reads F:\\Research-cache\\poe1\\zips, resumable)
"""
import csv
import gzip
import io
import os
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fetch import LEAGUES, ZIPS  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "cache", "slim")
DROP_TYPES = {
    "BaseType", "SkillGem", "HelmetEnchant", "ClusterJewel", "Map", "ScourgedMap", "BlightedMap",
    "BlightRavagedMap", "Beast", "Watchstone", "Prophecy", "UniqueMap", "Memory", "Wombgift",
}


def member(z, league, kind):
    want = f"{league}.{kind}.csv"
    for n in z.namelist():
        if os.path.basename(n) == want:
            return n
    return None


def slim(league):
    zp = os.path.join(ZIPS, f"{league}.zip")
    if not os.path.exists(zp):
        print(f"{league}: no zip")
        return
    os.makedirs(OUT, exist_ok=True)
    with zipfile.ZipFile(zp) as z:
        for kind, cols in (("currency", ["Date", "Get", "Pay", "Value", "Confidence"]),
                           ("items", ["Date", "Type", "Name", "Variant", "Links", "Value", "Confidence"])):
            out = os.path.join(OUT, f"{league}.{kind}.csv.gz")
            if os.path.exists(out):
                continue
            n = member(z, league, kind)
            if not n:
                print(f"{league}: no {kind} csv in zip")
                continue
            tmp = out + ".part"
            kept = 0
            try:
                with z.open(n) as raw, gzip.open(tmp, "wt", encoding="utf-8", newline="") as g:
                    r = csv.DictReader(io.TextIOWrapper(raw, "utf-8-sig"), delimiter=";")
                    w = csv.writer(g, delimiter=";")
                    w.writerow(cols)
                    for row in r:
                        if row.get("League") != league:
                            continue
                        if kind == "items" and row["Type"] in DROP_TYPES:
                            continue
                        w.writerow([row.get(c, "") for c in cols])
                        kept += 1
                os.replace(tmp, out)
            finally:
                if os.path.exists(tmp):
                    os.remove(tmp)
            print(f"{league} {kind}: {kept} rows, {os.path.getsize(out)/1e6:.1f} MB", flush=True)


if __name__ == "__main__":
    for lg in sys.argv[1:] or LEAGUES:
        slim(lg)
