"""Public player counts: SteamCharts monthly table for Path of Exile (Steam app 238960).

Steam is only part of PoE's player base (many use the standalone client), so this is a relative hype index only.
Writes cache/steamcharts_238960.csv (Month;Avg;Peak).  Usage: python -I players.py
"""
import csv
import html
import os
import re
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "cache", "steamcharts_238960.csv")
URL = "https://steamcharts.com/app/238960"

req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0 (economy-research script)"})
text = urllib.request.urlopen(req, timeout=60).read().decode("utf-8", "replace")
rows = []
for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", text, re.S):
    cells = [html.unescape(re.sub("<[^>]+>", "", c)).strip() for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S)]
    if len(cells) == 5 and cells[0] != "Month":
        rows.append((cells[0], cells[1], cells[4]))
with open(OUT, "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f, delimiter=";")
    w.writerow(["Month", "Avg", "Peak"])
    w.writerows(rows)
print(f"{len(rows)} months -> {OUT}")
