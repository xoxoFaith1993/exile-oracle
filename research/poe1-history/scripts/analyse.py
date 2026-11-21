"""PoE 1 league-economy history from poe.ninja dumps (cache/slim).  ANALOGY material for PoE 2, not PoE 2 fact.

Writes cache/metrics.json: per-league ratio paths, group curves, and every number the laws in build.py count.
Prices: poe.ninja daily values in Chaos. "Top orb" = Exalted Orb before Kalandra (3.19), Divine Orb from
Kalandra on (the 3.19 swap made Divine the top currency). Group curves are in TOP-ORB terms (the PoE 2 research
prices in Divines), relative to league day 1 (day 0 is the partial launch Friday).
Usage: python -I analyse.py
"""
import csv
import datetime as dt
import gzip
import json
import math
import os
import statistics as st
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fetch import LEAGUES  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
SLIM = os.path.join(HERE, "..", "cache", "slim")
OUT = os.path.join(HERE, "..", "cache", "metrics.json")
DIVINE_FROM = LEAGUES.index("Kalandra")
CURVE_DAYS = [0, 1, 2, 3, 4, 5, 6, 7, 10, 14, 21, 28, 35, 42, 56, 70, 84]
BASE = 1
MIN_ITEM_BASE = 5  # chaos; see the listing-floor note in group curves

COMMON_CURRENCY = ["Orb of Alchemy", "Orb of Fusing", "Chromatic Orb", "Orb of Alteration", "Jeweller's Orb",
                   "Regal Orb", "Orb of Chance", "Orb of Scouring", "Vaal Orb", "Orb of Regret",
                   "Cartographer's Chisel", "Blessed Orb", "Gemcutter's Prism", "Glassblower's Bauble",
                   "Orb of Augmentation", "Orb of Transmutation"]
SPECIAL_ESSENCES = {"Essence of Hysteria", "Essence of Insanity", "Essence of Horror", "Essence of Delirium"}


def is_splinter(n):
    return (n.startswith("Splinter of ") or n in ("Simulacrum Splinter", "Crescent Splinter", "Ritual Splinter")
            or (n.startswith("Timeless") and n.endswith("Splinter")))


def is_pinnacle_key(n):
    return (n.startswith("Sacrifice at ") or n.startswith("Mortal ") or n.startswith("Fragment of ")
            or "Breachstone" in n or n in ("Simulacrum", "Divine Vessel", "Offering to the Goddess",
                                            "The Maven's Writ", "Maven's Writ", "Reality Fragment")
            or n.endswith("Emblem") or n.endswith("'s Key") or "Crest" in n or n.startswith("Uber ")
            or n.startswith("Blessing of "))


def is_unique(t):
    return t.startswith("Unique") and t not in ("UniqueRelic",)


def dayof(start, d):
    return (dt.date.fromisoformat(d) - start).days


def load(league):
    cur_pay, cur_get = defaultdict(dict), defaultdict(dict)
    with gzip.open(os.path.join(SLIM, f"{league}.currency.csv.gz"), "rt", encoding="utf-8") as f:
        rows = list(csv.DictReader(f, delimiter=";"))
    start = min(dt.date.fromisoformat(r["Date"]) for r in rows)
    for r in rows:
        v = float(r["Value"] or 0)
        if v <= 0:
            continue
        d = dayof(start, r["Date"])
        if r["Pay"] == "Chaos Orb":
            cur_pay[r["Get"]][d] = v
        elif r["Get"] == "Chaos Orb":
            cur_get[r["Pay"]][d] = 1 / v
    cur = {}
    for n in set(cur_pay) | set(cur_get):
        s = dict(cur_get.get(n, {}))
        s.update(cur_pay.get(n, {}))
        cur[n] = s
    items, conf_high = defaultdict(dict), defaultdict(int)
    with gzip.open(os.path.join(SLIM, f"{league}.items.csv.gz"), "rt", encoding="utf-8") as f:
        for r in csv.DictReader(f, delimiter=";"):
            if r["Links"] in ("5 links", "6 links"):
                continue
            v = float(r["Value"] or 0)
            if v <= 0:
                continue
            d = dayof(start, r["Date"])
            items[(r["Type"], r["Name"], r["Variant"], r["Links"])][d] = v
            if r["Confidence"] == "High":
                conf_high[d] += 1
    return start, cur, items, conf_high


def at(s, d):
    """Robust value of a daily series at day d: exact for d<=3, +-1 day median to d14, +-2 after."""
    w = 0 if d <= 3 else (1 if d <= 14 else 2)
    vals = [s[x] for x in range(d - w, d + w + 1) if x in s]
    if not vals and d <= 3:
        vals = [s[x] for x in (d - 1, d + 1) if x in s]
    return st.median(vals) if vals else None


def smooth(s, lo, hi):
    out = {}
    for d in range(lo, hi + 1):
        vals = [s[x] for x in (d - 1, d, d + 1) if x in s]
        if len(vals) >= 2:
            out[d] = st.median(vals)
    return out


def rel_curve(series_list, days=CURVE_DAYS, base=BASE):
    """Median over items of price(d)/price(base)."""
    out = {}
    for d in days:
        rs = []
        for s in series_list:
            b, v = at(s, base), at(s, d)
            if b and v:
                rs.append(v / b)
        if len(rs) >= max(1, min(3, len(series_list))):
            out[d] = round(st.median(rs), 4)
    return out


def spearman(xs, ys):
    def ranks(a):
        o = sorted(range(len(a)), key=lambda i: a[i])
        r = [0] * len(a)
        for k, i in enumerate(o):
            r[i] = k
        return r
    if len(xs) < 5:
        return None
    rx, ry = ranks(xs), ranks(ys)
    mx, my = st.mean(rx), st.mean(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = math.sqrt(sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry))
    return num / den if den else None


def main():
    seen_names = set()
    res = {}
    for li, league in enumerate(LEAGUES):
        start, cur, items, conf_high = load(league)
        topname = "Divine Orb" if li >= DIVINE_FROM else "Exalted Orb"
        top = cur[topname]
        end = max(top)
        m = {"start": start.isoformat(), "weekday0": start.strftime("%a"), "top_orb": topname, "last_day": end}

        def in_top(s):
            return {d: v / at(top, d) for d, v in s.items() if at(top, d)}

        # 1. Ratio path (chaos per top orb), absolute and relative.
        m["ratio_abs"] = {d: round(at(top, d), 2) for d in CURVE_DAYS if at(top, d)}
        sm = smooth(top, 1, min(end, 120))
        sm70 = {d: v for d, v in sm.items() if d <= 70}
        pk = max(sm70, key=sm70.get)
        m["ratio_peak_day"], m["ratio_peak"] = pk, round(sm70[pk], 2)
        m["ratio_peak_day_full"] = max(sm, key=sm.get)
        last7 = [top[d] for d in range(end - 6, end + 1) if d in top]
        m["ratio_end"] = round(st.median(last7), 2)
        m["ratio_d1"] = at(top, 1)
        # Divine:Chaos for every league too (Divine was a mid-tier orb before 3.19).
        m["divine_abs"] = {d: round(at(cur["Divine Orb"], d), 2) for d in CURVE_DAYS if at(cur["Divine Orb"], d)}

        # 2. Mirror.
        # Drop absurd Mirror quotes (< 20 top orbs: troll or mislabelled listings, e.g. Kalandra day 1-7).
        mir = {d: v for d, v in cur.get("Mirror of Kalandra", {}).items() if at(top, d) and v >= 20 * at(top, d)}
        m["mirror_chaos"] = {d: round(at(mir, d), 1) for d in CURVE_DAYS if at(mir, d)}
        mir_top = in_top(mir)
        m["mirror_top_rel"] = rel_curve([mir_top], base=7) if mir_top else {}  # day 1-3 Mirror listings are trolls
        m["mirror_chaos_rel"] = rel_curve([mir], base=7) if mir else {}
        msm = smooth(mir_top, 1, min(end, 120))
        if msm:
            m["mirror_top_peak_day"] = max(msm, key=msm.get)

        # 3. Groups (top-orb terms).
        groups = defaultdict(list)
        for n, s in cur.items():
            if n in ("Chaos Orb", topname):
                continue
            ts = in_top(s)
            if n in COMMON_CURRENCY:
                groups["common_currency"].append(ts)
            if is_splinter(n):
                groups["splinters"].append(ts)
            elif is_pinnacle_key(n):
                groups["pinnacle_keys"].append(ts)
            if n.endswith(" Catalyst"):
                groups["catalysts"].append(ts)
        groups["chaos_orb"] = [{d: 1 / at(top, d) for d in top if at(top, d)}]
        uniq_pool = {}
        for k, s in items.items():
            t, n, var, lk = k
            if is_unique(t):
                uniq_pool[k] = s
            if (at(s, BASE) or 0) < MIN_ITEM_BASE:
                continue  # trade items sit on a ~1c listing floor; cheaper ones only track the Chaos Orb
            ts = in_top(s)
            if is_unique(t):
                groups["all_uniques"].append(ts)
            elif t == "Essence":
                groups["essences_special" if n in SPECIAL_ESSENCES else "essences_common"].append(ts)
            elif t in ("Scarab", "Fossil", "Resonator", "Oil", "DeliriumOrb", "Incubator", "Omen", "Tattoo",
                       "DivinationCard", "Invitation", "Vial", "Artifact"):
                groups[t.lower()].append(ts)
            if not is_unique(t):
                groups["all_non_unique_items"].append(ts)

        items_ok = league != "Essence"  # Essence item data only starts on day 48
        # chase uniques: 8 dearest uniques on day 3 (chaos) with data on >= 25 of days 3-42.
        def cover(s, a, b):
            return sum(1 for d in range(a, b + 1) if d in s)
        if items_ok:
            pool = [(k, s) for k, s in uniq_pool.items() if cover(s, 3, 42) >= 25 and at(s, 3)]
            chase, cn = [], set()
            for k, s in sorted(pool, key=lambda ks: -at(ks[1], 3)):
                if k[1] not in cn and len(chase) < 8:
                    chase.append((k, s))
                    cn.add(k[1])
            groups["chase_uniques"] = [in_top(s) for _, s in chase]
            m["chase_names"] = [k[1] for k, _ in chase]
            m["chase_rel_d3"] = {d: v for d, v in rel_curve([in_top(s) for _, s in chase], base=3).items()}
            m["chase_rel_d3_chaos"] = rel_curve([s for _, s in chase], base=3)
            # early spikers ("build enablers once the meta forms"): selected ONLY on the day1 -> max(days 2-7)
            # rise; the outcome (true peak day within 2-28, value at d28/d42) is measured afterwards.
            sp = []
            for k, s in uniq_pool.items():
                p1 = at(s, 1)
                wk = {d: s[d] for d in range(2, 8) if d in s}
                if not p1 or p1 < 2 or len(wk) < 4 or cover(s, 7, 42) < 20:
                    continue
                if max(wk.values()) < 10:
                    continue
                sp.append((max(wk.values()) / p1, k, s))
            sp.sort(key=lambda x: -x[0])
            spn, sp2 = set(), []
            for x in sp:
                if x[1][1] not in spn:
                    sp2.append(x)
                    spn.add(x[1][1])
            sp = sp2[:15]
            out = []
            for r, k, s in sp:
                sm2 = smooth(s, 2, 28)
                pd = max(sm2, key=sm2.get)
                out.append((k[1], round(r, 1), pd, sm2[pd], s))
            m["spiker_names"] = [(n, r, pd) for n, r, pd, _, _ in out]
            m["spiker_peak_days"] = [pd for _, _, pd, _, _ in out]
            def ratio_to_peak(d, top_terms):
                v = []
                for _, _, pd, pv, s in out:
                    x = at(s, d)
                    if not x:
                        continue
                    v.append((x / at(top, d)) / (pv / at(top, pd)) if top_terms else x / pv)
                return st.median(v) if v else None
            m["spiker_d28_vs_peak_chaos"] = ratio_to_peak(28, False)
            m["spiker_d42_vs_peak_chaos"] = ratio_to_peak(42, False)
            m["spiker_d28_vs_peak_top"] = ratio_to_peak(28, True)
            m["spiker_d42_vs_peak_top"] = ratio_to_peak(42, True)
            groups["early_spike_uniques"] = [in_top(s) for *_, s in out]

        # 4. League-mechanic loot: names (any type) never seen in an earlier league, first priced in days 0-7
        #    (non-unique, non-divination-card). Their first 7 days of trading vs older items over the same days.
        new, old, firsts = [], [], []
        names_now = set()
        for n, s in list(cur.items()) + [(k[1], s) for k, s in items.items()
                                         if not is_unique(k[0]) and k[0] not in ("DivinationCard", "UniqueRelic")]:
            names_now.add(n)
            if n in ("Chaos Orb", topname):
                continue
            f = min(d for d in s if d >= 1) if any(d >= 1 for d in s) else None
            if f is None:
                continue
            if n not in seen_names and f <= 7:
                new.append(in_top(s))
                firsts.append(f)
            elif n in seen_names:
                old.append(in_top(s))
        for k in items:
            names_now.add(k[1])
        if li > 0 and items_ok and len(new) >= 3:
            f0 = int(st.median(firsts))
            def wk_change(lst, a):
                v = [at(s, a + 7) / at(s, a) for s in lst if at(s, a) and at(s, a + 7)]
                return (round(st.median(v), 4), len(v)) if v else (None, 0)
            m["new_item_count"] = len(new)
            m["new_first_day"] = f0
            m["new_first_week"], m["new_n"] = wk_change(new, f0)
            m["old_same_week"], m["old_n"] = wk_change(old, f0)
            groups["league_mechanic_new_items"] = new
        seen_names |= names_now

        # 5. Curves for every group.
        m["curves"] = {g: rel_curve(v) for g, v in groups.items() if v}
        m["group_sizes"] = {g: len(v) for g, v in groups.items()}
        m["group_peak_trough"] = {}
        for g, v in groups.items():
            dense = rel_curve(v, days=list(range(1, 71)))
            if len(dense) > 30:
                m["group_peak_trough"][g] = {"peak_day": max(dense, key=dense.get), "peak": dense[max(dense, key=dense.get)],
                                             "trough_day": min(dense, key=dense.get), "trough": dense[min(dense, key=dense.get)]}

        # 6. Weekly change of the all-unique basket and the non-unique basket (median log change per week).
        def weekly(series_list, weeks=8, floor=0):
            out = {}
            for w in range(1, weeks + 1):
                a, b = (1, 7) if w == 1 else (7 * (w - 1), 7 * w)
                ch = []
                for s in series_list:
                    va, vb = at(s, a), at(s, b)
                    if va and vb and va >= floor:
                        ch.append(math.log(vb / va))
                if len(ch) >= 5:
                    out[w] = round(math.expm1(st.median(ch)) * 100, 1)
            return out
        if items_ok:
            m["weekly_uniques_top"] = weekly(groups["all_uniques"])
            m["weekly_uniques_chaos"] = weekly(list(uniq_pool.values()), floor=10)
            m["weekly_nonunique_chaos"] = weekly([s for k, s in items.items() if not is_unique(k[0])], floor=10)
            m["weekly_nonunique_top"] = weekly(groups["all_non_unique_items"])
        m["weekly_ratio"] = weekly([top])

        # 7. Weekend effect: residual of log price vs its centred 7-day mean, days 8-63, by weekday.
        def weekday_resid(series_list):
            by = defaultdict(list)
            for d in range(8, 64):
                rs = []
                for s in series_list:
                    win = [s.get(x) for x in range(d - 3, d + 4)]
                    if all(win):
                        lw = [math.log(x) for x in win]
                        rs.append(max(-0.3, min(0.3, lw[3] - st.mean(lw))))
                if len(rs) >= 3 or (len(series_list) == 1 and rs):
                    by[(start + dt.timedelta(days=d)).strftime("%a")].append(st.mean(rs))
            return {k: round(st.mean(v) * 100, 3) for k, v in by.items()}
        if items_ok:
            big = [s for s in items.values() if cover(s, 8, 63) >= 50
                   and st.median([s[d] for d in range(8, 64) if d in s]) >= 10]
            m["weekday_resid_items_chaos"] = weekday_resid(big)
            m["weekday_items_n"] = len(big)
        m["weekday_resid_currency_chaos"] = weekday_resid(
            [s for n, s in cur.items() if n != "Chaos Orb" and cover(s, 8, 63) >= 50])
        m["weekday_resid_ratio"] = weekday_resid([top])

        # 8. Liquidity proxy: item rows with High confidence per day.
        if items_ok:
            lq = smooth({d: float(v) for d, v in conf_high.items()}, 0, end)
            lpk = max((d for d in lq if d <= 70), key=lq.get)
            m["liquidity_peak_day"] = lpk
            m["liquidity_rel"] = {d: round(lq[d] / lq[lpk], 3) for d in (1, 7, 14, 28, 42, 56, 70) if d in lq}

        # 9. End of league: last 14 days vs the 14 before (ratio, Mirror in top orb, unique basket in chaos).
        def endchg(s):
            a = [s[d] for d in range(end - 27, end - 13) if d in s]
            b = [s[d] for d in range(end - 13, end + 1) if d in s]
            return round((st.median(b) / st.median(a) - 1) * 100, 1) if a and b else None
        m["end_ratio_chg"] = endchg(top)
        if items_ok:
            m["end_uniques_top_chg"] = st.median([c for c in (endchg(in_top(s)) for s in uniq_pool.values()
                                                  if cover(s, end - 27, end) >= 20
                                                  and st.median([s[d] for d in range(end - 27, end + 1) if d in s]) >= 10)
                                                  if c is not None] or [0])
        m["end_mirror_top_chg"] = endchg(mir_top) if mir_top else None
        if items_ok:
            def worth(s):
                return st.median([s[d] for d in range(end - 27, end + 1) if d in s]) >= 10
            ch = [endchg(s) for s in uniq_pool.values() if cover(s, end - 27, end) >= 20 and worth(s)]
            ch = [c for c in ch if c is not None]
            m["end_uniques_chaos_chg"] = st.median(ch) if ch else None
            chn = [endchg(s) for k, s in items.items()
                   if not is_unique(k[0]) and cover(s, end - 27, end) >= 20 and worth(s)]
            chn = [c for c in chn if c is not None]
            m["end_nonunique_chaos_chg"] = st.median(chn) if chn else None

        # 10. Rich get richer: day-1 price vs d1->d42 change (top-orb terms), non-unique items + currency.
        xs, ys = [], []
        for s in groups["all_non_unique_items"] + [in_top(s) for n, s in cur.items() if n not in ("Chaos Orb", topname)]:
            b, v = at(s, 1), at(s, 42)
            if b and v:
                xs.append(math.log(b))
                ys.append(math.log(v / b))
        m["rich_richer_rho"] = spearman(xs, ys)
        m["rich_richer_n"] = len(xs)
        res[league] = m
        print(f"{league}: ratio peak d{pk}, mirror d42 {m['mirror_top_rel'].get(42)}, rho {m['rich_richer_rho']}",
              flush=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(res, f, indent=1, default=str)


if __name__ == "__main__":
    main()
