"""PoE 2 side of the check: numbers each PoE 1 law is compared against.

Reads (read-only): research/market/market-trends.json (the existing PoE 2 study) and, for a few group-wide
tests that study did not run, the app DB <data folder>\\data\\poe2kit.db (ls_price = GGG exchange days 0-6 of
three launches; ex_price = Forbidden Rites days 63-77). Writes cache/poe2_checks.json.
Usage: python -I poe2_check.py
"""
import datetime as dt
import json
import math
import os
import sqlite3
import statistics as st
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from analyse import spearman  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
MARKET = os.path.join(HERE, "..", "..", "market", "market-trends.json")
DB = r"<data folder>\data\poe2kit.db"
OUT = os.path.join(HERE, "..", "cache", "poe2_checks.json")
ORDER = ["Fate of the Vaal", "Runes of Aldur", "Forbidden Rites"]


def main():
    mk = json.load(open(MARKET, encoding="utf-8"))
    res = {"ratios": mk["ratios"], "curves": {}}
    cv = mk["curves_div"]

    def rel(item, a, b):
        out = {}
        for lg, s in cv.get(item, {}).items():
            if str(a) in s and str(b) in s and s[str(a)]:
                out[lg] = round(s[str(b)] / s[str(a)], 3)
        return out
    for item in cv:
        res["curves"][item] = {"d1_d6": rel(item, 1, 6), "d1_d14": rel(item, 1, 14), "d1_d42": rel(item, 1, 42),
                               "d7_d42": rel(item, 6, 42), "d14_d42": rel(item, 14, 42)}
    # Ratio peak day and late slide.
    rp = {}
    for lg, s in mk["ratios"].items():
        days = {int(d): v["ex_per_div"] for d, v in s.items() if v.get("ex_per_div")}
        pk = max(days, key=days.get)
        last = max(days)
        rp[lg] = {"peak_day": pk, "peak": days[pk], "d0": days.get(0), "d1": days.get(1),
                  "last_day": last, "last": days[last], "d1_to_peak_x": round(days[pk] / days[1], 1)}
    res["ratio_summary"] = rp

    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    daily = defaultdict(lambda: defaultdict(dict))  # league -> item -> day -> median div
    rows = defaultdict(list)
    for lg, h, item, pdv in con.execute("select league, offset_h, item, price_div from ls_price where price_div > 0"):
        rows[(lg, item, h // 24)].append(pdv)
    for (lg, item, d), v in rows.items():
        daily[lg][item][d] = st.median(v)
    # (a) items new in a launch (absent from the earlier launches' exchange) vs older items, d1 -> d6 in Div.
    seen = set()
    newold = {}
    for lg in ORDER:
        items = daily[lg]
        if seen:
            new = [s[6] / s[1] for it, s in items.items() if it not in seen and 1 in s and 6 in s]
            old = [s[6] / s[1] for it, s in items.items() if it in seen and 1 in s and 6 in s]
            newold[lg] = {"new_n": len(new), "new_d1_d6": round(st.median(new), 3) if new else None,
                          "old_n": len(old), "old_d1_d6": round(st.median(old), 3) if old else None}
        seen |= set(items)
    res["new_vs_old_items"] = newold
    # (b) rich get richer: log price d1 vs log change d1 -> d6 (all exchange items).
    rr = {}
    for lg in ORDER:
        xs, ys = [], []
        for s in daily[lg].values():
            if 1 in s and 6 in s:
                xs.append(math.log(s[1]))
                ys.append(math.log(s[6] / s[1]))
        rr[lg] = {"rho_d1_d6": round(spearman(xs, ys), 3), "n": len(xs)}
    xs, ys = [], []
    for item, s in cv.items():
        for lg, c in s.items():
            if "1" in c and "42" in c and c["1"] > 0:
                xs.append(math.log(c["1"]))
                ys.append(math.log(c["42"] / c["1"]))
    rr["curve_items_d1_d42_pooled"] = {"rho": round(spearman(xs, ys), 3), "n": len(xs)}
    res["rich_richer"] = rr
    # (c) median exchange item, d1 -> d6 in Div (week-1 deflation of everything vs the Divine).
    res["median_item_d1_d6"] = {lg: round(st.median([s[6] / s[1] for s in daily[lg].values() if 1 in s and 6 in s]), 3)
                                for lg in ORDER}
    # (d) weekend effect, Forbidden Rites days 63-77 (two weekends only): daily median Div price, residual vs
    #     centred 7-day mean, by weekday.
    byday = defaultdict(lambda: defaultdict(list))
    for hour, item, pdv in con.execute(
            "select hour, item, price_div from ex_price where league='Forbidden Rites' and price_div > 0"):
        byday[item][dt.datetime.fromtimestamp(hour, dt.UTC).date()].append(pdv)
    resid = defaultdict(list)
    for item, dd in byday.items():
        s = {d: st.median(v) for d, v in dd.items() if len(v) >= 12}
        for d in s:
            win = [s.get(d + dt.timedelta(days=k)) for k in range(-3, 4)]
            if all(win):
                lw = [math.log(x) for x in win]
                resid[d].append(max(-0.3, min(0.3, lw[3] - st.mean(lw))))
    wd = defaultdict(list)
    for d, v in resid.items():
        if len(v) >= 20:
            wd[d.strftime("%a")].append(st.mean(v))
    res["fr_late_weekday_resid_pct"] = {k: round(st.mean(v) * 100, 3) for k, v in wd.items()}
    con.close()
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(res, f, indent=1)
    print(json.dumps({k: res[k] for k in ("ratio_summary", "new_vs_old_items", "rich_richer", "median_item_d1_d6",
                                          "fr_late_weekday_resid_pct")}, indent=1))


if __name__ == "__main__":
    main()
