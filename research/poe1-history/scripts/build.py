"""Turn cache/metrics.json + cache/poe2_checks.json into ../poe1-history.json (laws with counts, curves, sources).

Every count below is computed here from the data, with the threshold written next to it.
PoE 1 is used as ANALOGY for PoE 2 (different currencies, trade system and data type); see caveats.
Usage: python -I build.py
"""
import csv
import datetime as dt
import json
import math
import os
import statistics as st
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from analyse import spearman  # noqa: E402
from fetch import LEAGUES  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
M = json.load(open(os.path.join(ROOT, "cache", "metrics.json"), encoding="utf-8"))
P2 = json.load(open(os.path.join(ROOT, "cache", "poe2_checks.json"), encoding="utf-8"))
ITEM_LEAGUES = [lg for lg in LEAGUES if lg != "Essence"]


def g(lg, *path):
    x = M[lg]
    for p in path:
        if x is None:
            return None
        x = x.get(str(p)) if isinstance(x, dict) else None
    return x


def count(leagues, test):
    ok, bad, n = [], [], 0
    for lg in leagues:
        r = test(lg)
        if r is None:
            continue
        n += 1
        (ok if r else bad).append(lg)
    return len(ok), n, bad


def pct(v):
    return f"{(v - 1) * 100:+.0f}%"


def med(vals):
    vals = [v for v in vals if v is not None]
    return st.median(vals) if vals else None


def q(vals, p):
    vals = sorted(v for v in vals if v is not None)
    k = (len(vals) - 1) * p
    lo, hi = math.floor(k), math.ceil(k)
    return vals[lo] + (vals[hi] - vals[lo]) * (k - lo)


laws = []


def law(text, leagues, test, poe2_mapping, poe2_check, poe2_evidence, extra=None):
    ok, n, bad = count(leagues, test)
    share = ok / n if n else 0
    status = "law (80%+)" if share >= 0.8 else ("tendency (60-79%)" if share >= 0.6 else "not a law (<60%)")
    entry = {"law": text, "holds_in": ok, "out_of": n, "share": round(share, 2), "status": status,
             "exceptions": bad, "poe2_mapping": poe2_mapping, "poe2_check": poe2_check,
             "poe2_evidence": poe2_evidence, "label": "PoE 1 history (analogy for PoE 2, not PoE 2 fact)"}
    if extra:
        entry.update(extra)
    laws.append(entry)
    return entry


r2 = P2["ratio_summary"]
c2 = P2["curves"]


def p2(item, key="d1_d42"):
    return c2.get(item, {}).get(key, {})


# ---------- Currency ratio ----------
ratio_rel = {lg: {d: v / M[lg]["ratio_d1"] for d, v in M[lg]["ratio_abs"].items()} for lg in LEAGUES}
peak_days = [M[lg]["ratio_peak_day"] for lg in LEAGUES]
peak_x = [M[lg]["ratio_peak"] / M[lg]["ratio_d1"] for lg in LEAGUES]
law("Chaos per top orb (Exalted before 3.19, Divine after) rises at least 1.2x from day 1 to day 14.",
    LEAGUES, lambda lg: ratio_rel[lg].get("14", 0) >= 1.2,
    "PoE 1 Chaos:top-orb <-> PoE 2 Ex:Div (everyday currency vs the store of value).", "confirmed",
    "PoE 2 Ex per Div d1->d14: " + ", ".join(f"{k} {P2['ratios'][k]['1']['ex_per_div']}->{P2['ratios'][k]['14']['ex_per_div']}" for k in r2),
    {"median_d14_multiple": round(med([ratio_rel[lg].get("14") for lg in LEAGUES]), 2)})
law("The ratio's biggest single jump is week 1: day 7 is at least 1.4x day 1.",
    LEAGUES, lambda lg: ratio_rel[lg].get("7", 0) >= 1.4,
    "Same pair as above.", "confirmed",
    "PoE 2 Ex per Div d1->d6: FotV 92->146 (1.6x), RoA 51.5->87 (1.7x), FR 84->262 (3.1x).",
    {"median_d7_multiple": round(med([ratio_rel[lg].get("7") for lg in LEAGUES]), 2)})
law("The ratio does NOT peak in week 1: its (3-day smoothed) high over days 1-70 comes on day 10 or later.",
    LEAGUES, lambda lg: M[lg]["ratio_peak_day"] >= 10,
    "Same pair.", "confirmed",
    "PoE 2 Ex per Div peaked on d14 (FotV), d42 (RoA), d42 (FR).",
    {"peak_day_median": med(peak_days), "peak_day_p10_p90": [round(q(peak_days, .1)), round(q(peak_days, .9))]})
law("The ratio's peak is 1.8x-4x its day-1 value (a 2-3x rise is typical).",
    LEAGUES, lambda lg: 1.8 <= M[lg]["ratio_peak"] / M[lg]["ratio_d1"] <= 4.0,
    "Same pair; the SIZE is where the analogy breaks.", "contradicted",
    "PoE 2 Ex per Div rose 4.4x / 10.7x / 8.4x from d1 to peak: Exalted Orbs deflate far harder than PoE 1 Chaos.",
    {"median_multiple": round(med(peak_x), 2)})
law("Late slide: the last 7 days of the league trade at least 10% below the day 1-70 ratio peak.",
    LEAGUES, lambda lg: M[lg]["ratio_end"] <= 0.9 * M[lg]["ratio_peak"],
    "Same pair.", "partly",
    "PoE 2 Ex per Div fell 25-34% from peak by week 10-11 in all three (FR 709->468 by d77; RoA 553->375 at d70, "
    "but back to 506-544 at d108-119).")
law("The everyday currency loses at least 40% against the top orb by day 14 (Chaos Orb priced in Ex/Div).",
    LEAGUES, lambda lg: (g(lg, "curves", "chaos_orb", 14) or 9) <= 0.6,
    "PoE 1 Chaos <-> PoE 2 Exalted Orb.", "confirmed",
    "PoE 2 Exalted lost 53-79% of its Div value by d6 and 83-92% by d28 (stronger than PoE 1).",
    {"median_chaos_in_top_d14": med([g(lg, "curves", "chaos_orb", 14) for lg in LEAGUES]),
     "median_chaos_in_top_d42": med([g(lg, "curves", "chaos_orb", 42) for lg in LEAGUES])})

# ---------- Mirror ----------
mir = [lg for lg in LEAGUES if g(lg, "mirror_top_rel", 42)]
law("Mirror of Kalandra keeps rising in top-orb terms: day 42 is at least 1.5x day 7.",
    mir, lambda lg: g(lg, "mirror_top_rel", 42) >= 1.5,
    "PoE 1 Mirror <-> PoE 2 Mirror (and the other pure sinks: Hinekora's Lock).", "confirmed",
    "PoE 2 Mirror in Div d6->d42: " + ", ".join(f"{k} {v}x" for k, v in p2("Mirror of Kalandra", "d7_d42").items())
    + "; Hinekora's Lock d1->d42 " + ", ".join(f"{k} {v}x" for k, v in p2("Hinekora's Lock").items()),
    {"median_d7_d42_top": round(med([g(lg, "mirror_top_rel", 42) for lg in mir]), 2),
     "median_d7_d42_chaos": round(med([g(lg, "mirror_chaos_rel", 42) for lg in mir]), 2),
     "median_d7_d70_top": round(med([g(lg, "mirror_top_rel", 70) for lg in mir]), 2),
     "note": "Mirror quotes before day 7 are troll listings; Kalandra dropped (bad quotes). "
             "PoE 2 Mirror d6->d42 is similar in the 0.5 leagues (2.4-3.6x) and 23x in 0.4 (Divine-rich temple farming)."})

# ---------- Common currency / groups ----------
law("Common currency (Alchemy, Fusing, Chromatic, Alteration, Jeweller's, Regal, Chance, Scouring, Vaal...) "
    "is worth at most 60% of its day-1 top-orb value by day 42.",
    LEAGUES, lambda lg: g(lg, "curves", "common_currency", 42) is not None and g(lg, "curves", "common_currency", 42) <= 0.6,
    "PoE 1 basic orbs <-> PoE 2 Transmute/Aug/Regal/Alch lines and Greater/Lesser orbs.", "confirmed",
    "PoE 2 Greater Exalted -93/-93/-96% by d21; Transmute/Aug/Regal/Alch lines -82 to -99% by d42.",
    {"median_d14": med([g(lg, "curves", "common_currency", 14) for lg in LEAGUES]),
     "median_d42": med([g(lg, "curves", "common_currency", 42) for lg in LEAGUES])})
law("Common currency just tracks the Chaos Orb: its top-orb curve at day 42 is within 35% of the Chaos Orb's own.",
    LEAGUES, lambda lg: abs(g(lg, "curves", "common_currency", 42) / g(lg, "curves", "chaos_orb", 42) - 1) <= 0.35
    if g(lg, "curves", "common_currency", 42) and g(lg, "curves", "chaos_orb", 42) else None,
    "PoE 1 basic orbs vs Chaos <-> PoE 2 basic orbs vs Exalted.", "partly",
    "In PoE 2 the basic orbs crash 80-99% in Div while Ex loses 83-92%: similar by d28-42 but basic orbs fall FASTER "
    "in week 1 (Greater Jeweller's -96 to -99% by d14). PoE 1 basic orbs barely move in Chaos.")
law("Breach/Timeless/Simulacrum SPLINTERS crash: at most 30% of their day-1 top-orb value by day 42.",
    LEAGUES, lambda lg: g(lg, "curves", "splinters", 42) <= 0.3 if g(lg, "curves", "splinters", 42) else None,
    "PoE 1 splinters <-> PoE 2 Breach Splinter / Simulacrum Splinter.", "contradicted",
    "PoE 2 Breach Splinter d1->d42: " + json.dumps(p2("Breach Splinter")) + "; Simulacrum Splinter: "
    + json.dumps(p2("Simulacrum Splinter")) + " (flat to up, not a crash).",
    {"median_d42": med([g(lg, "curves", "splinters", 42) for lg in LEAGUES])})
law("Pinnacle keys/fragments (Sacrifice/Mortal sets, Shaper/Elder fragments, Breachstones, Emblems, Writs) fall "
    "with the Chaos Orb: at most 60% of their day-1 top-orb value by day 42.",
    LEAGUES, lambda lg: g(lg, "curves", "pinnacle_keys", 42) <= 0.6 if g(lg, "curves", "pinnacle_keys", 42) else None,
    "PoE 1 boss keys <-> PoE 2 pinnacle keys (Trialmaster Fates, Breachstone, Simulacrum).", "contradicted",
    "PoE 2 Victorious Fate d1->d42: " + json.dumps(p2("Victorious Fate")) + "; Breachstone: " + json.dumps(p2("Breachstone"))
    + ". PoE 2 keys mostly RISE in Div; PoE 1 keys are farmed in bulk and fall.",
    {"median_d42": med([g(lg, "curves", "pinnacle_keys", 42) for lg in LEAGUES])})
law("Scarabs (worth 5c+ on day 1) lose at least 30% of their top-orb value by day 42.",
    LEAGUES, lambda lg: g(lg, "curves", "scarab", 42) <= 0.7 if g(lg, "curves", "scarab", 42) else None,
    "PoE 1 scarabs <-> PoE 2 Precursor Tablets (map-juicing consumables).", "unknown",
    "Tablets don't trade on the PoE 2 Currency Exchange, so research/market has no tablet curve.",
    {"median_d42": med([g(lg, "curves", "scarab", 42) for lg in LEAGUES])})
law("Common essences (5c+ on day 1) lose at least 40% of their top-orb value by day 42.",
    ITEM_LEAGUES, lambda lg: g(lg, "curves", "essences_common", 42) <= 0.6 if g(lg, "curves", "essences_common", 42) else None,
    "PoE 1 common essences <-> PoE 2 common/Greater essences.", "confirmed",
    "PoE 2 essence category -90% (RoA) / -89% (FR) by d42; FotV +38% (outlier).",
    {"median_d42": med([g(lg, "curves", "essences_common", 42) for lg in ITEM_LEAGUES])})
law("Special essences (Hysteria, Insanity, Horror, Delirium) beat common essences by day 70 (higher top-orb ratio).",
    ITEM_LEAGUES, lambda lg: (g(lg, "curves", "essences_special", 70) or 0) > (g(lg, "curves", "essences_common", 70) or 9)
    if g(lg, "curves", "essences_special", 70) and g(lg, "curves", "essences_common", 70) else None,
    "PoE 1 corrupted essences <-> PoE 2 Essence of Delirium / Perfect Essence of the Infinite.", "partly",
    "PoE 2 Essence of Delirium rose 12x / 8x / 24x d1->d42; PoE 1 special essences only recover towards their day-1 level.",
    {"median_special_d70": med([g(lg, "curves", "essences_special", 70) for lg in ITEM_LEAGUES])})
law("Blight oils (5c+ on day 1) lose at least 50% of their top-orb value by day 42.",
    ITEM_LEAGUES, lambda lg: g(lg, "curves", "oil", 42) <= 0.5 if g(lg, "curves", "oil", 42) else None,
    "PoE 1 oils <-> PoE 2 liquid emotions (both: anoint/instil drops).", "partly",
    "PoE 2 Diluted and low-tier liquid emotions -96 to -99% by d14; category -98% (RoA), -95% (FR), -27% (FotV). "
    "PoE 1 oils crashed in 3.8-3.18 but have held since 3.19 (exceptions list), so PoE 2 looks like early-era PoE 1.",
    {"median_d42": med([g(lg, "curves", "oil", 42) for lg in ITEM_LEAGUES])})
law("Fossils (5c+ on day 1) lose at least 30% of their top-orb value by day 42.",
    ITEM_LEAGUES, lambda lg: g(lg, "curves", "fossil", 42) <= 0.7 if g(lg, "curves", "fossil", 42) else None,
    "PoE 1 fossils <-> PoE 2 crafting omens.", "partly",
    "PoE 2 weak omens -98 to -99% by d42 (fits), but top omens rose 3-91x (Whittling, Light, Annulment): PoE 2 "
    "crafting consumables split harder into winners and losers.",
    {"median_d42": med([g(lg, "curves", "fossil", 42) for lg in ITEM_LEAGUES])})
law("PoE 1 omens (3.24+) end week 6 at or above their day-1 top-orb value.",
    ITEM_LEAGUES, lambda lg: g(lg, "curves", "omen", 42) >= 1.0 if g(lg, "curves", "omen", 42) else None,
    "PoE 1 omens <-> PoE 2 top crafting omens.", "partly",
    "PoE 2 Omen of Light 91x / 4.6x / 5.5x, Whittling 49x / 3x / 15x d1->d42; weak omens -98%. PoE 1 omens peak late "
    "(median day 53) and are back near day-1 value by day 70, but dip in between.",
    {"median_d42": med([g(lg, "curves", "omen", 42) for lg in ITEM_LEAGUES])})
law("Delirium orbs (5c+ on day 1) are worth more in top-orb terms on day 42 than on day 1.",
    ITEM_LEAGUES, lambda lg: g(lg, "curves", "deliriumorb", 42) > 1.0 if g(lg, "curves", "deliriumorb", 42) else None,
    "PoE 1 Delirium orbs (map juicing) <-> PoE 2 has no direct item; nearest are Simulacrum / Delirium splinters.", "partly",
    "PoE 2 Simulacrum d1->d42: " + json.dumps(p2("Simulacrum")) + " (mixed).",
    {"median_d42": med([g(lg, "curves", "deliriumorb", 42) for lg in ITEM_LEAGUES])})
law("Catalysts lose at least 40% of their top-orb value by day 42.",
    LEAGUES, lambda lg: g(lg, "curves", "catalysts", 42) <= 0.6 if g(lg, "curves", "catalysts", 42) else None,
    "PoE 1 catalysts <-> PoE 2 Refined catalysts.", "contradicted",
    "PoE 2 Refined Sibilant Catalyst: " + json.dumps(p2("Refined Sibilant Catalyst")) + " (40x+ risers).",
    {"median_d42": med([g(lg, "curves", "catalysts", 42) for lg in LEAGUES])})

# ---------- Uniques ----------
def chase_vs_basket(lg):
    c, u = g(lg, "chase_rel_d3", 42), g(lg, "curves", "all_uniques", 42)
    u3 = g(lg, "curves", "all_uniques", 3)
    return (c / (u / u3)) if c and u and u3 else None


law("Chase uniques (the 8 dearest on day 3) beat the median unique (5c+) by at least 2x from day 3 to day 42 "
    "(top-orb terms): they hold value while ordinary uniques melt.",
    ITEM_LEAGUES, lambda lg: chase_vs_basket(lg) >= 2 if chase_vs_basket(lg) else None,
    "PoE 1 Headhunter/Mageblood tier <-> PoE 2 chase uniques (and chase lineage gems).", "unknown",
    "No PoE 2 unique curves exist (uniques are not on the exchange). Nearest PoE 2 analogue, chase lineage gems "
    "(Uhtred's Exodus 1.1->59 / 7->335 / 14->280 Div), rises far more, and scarce exchange sinks rise 5-90x.",
    {"median_chase_d3_d42_top": med([g(lg, "chase_rel_d3", 42) for lg in ITEM_LEAGUES]),
     "median_chase_d3_d42_chaos": med([g(lg, "chase_rel_d3_chaos", 42) for lg in ITEM_LEAGUES]),
     "median_outperformance_x": round(med([chase_vs_basket(lg) for lg in ITEM_LEAGUES]), 2)})
law("Chase uniques stay within 0.5x-2x of their day-3 top-orb price at day 42 (no crash, no moon).",
    ITEM_LEAGUES, lambda lg: 0.5 <= g(lg, "chase_rel_d3", 42) <= 2 if g(lg, "chase_rel_d3", 42) else None,
    "Same.", "unknown", "No PoE 2 unique curves.")
law("Uniques (10c+) fall more in week 1 than in any later week (Chaos terms).",
    ITEM_LEAGUES, lambda lg: min(M[lg]["weekly_uniques_chaos"], key=lambda w: M[lg]["weekly_uniques_chaos"][w]) == "1"
    if M[lg].get("weekly_uniques_chaos") else None,
    "PoE 1 uniques <-> PoE 2 uniques; tested on PoE 2 exchange items instead.", "partly",
    "PoE 2 median exchange item d1->d6 in Div: " + json.dumps(P2["median_item_d1_d6"])
    + "; common drops halve within ~3 days. No PoE 2 unique data.",
    {"median_week1_pct": med([M[lg]["weekly_uniques_chaos"].get("1") for lg in ITEM_LEAGUES]),
     "median_week2_pct": med([M[lg]["weekly_uniques_chaos"].get("2") for lg in ITEM_LEAGUES])})
law("'Week 2 crash' (folk claim): week 2 is the worst week for uniques (Chaos terms).",
    ITEM_LEAGUES, lambda lg: min(M[lg]["weekly_uniques_chaos"], key=lambda w: M[lg]["weekly_uniques_chaos"][w]) == "2"
    if M[lg].get("weekly_uniques_chaos") else None,
    "Folk claim, tested.", "contradicted",
    "PoE 2 exchange: the drop is front-loaded (days 0-3), not week 2. The real week-2 effect is a SMALLER second leg.")
law("Week 2 is still a down week for uniques (Chaos terms, median change < 0).",
    ITEM_LEAGUES, lambda lg: M[lg]["weekly_uniques_chaos"].get("2", 0) < 0 if M[lg].get("weekly_uniques_chaos") else None,
    "PoE 1 uniques <-> PoE 2 common exchange drops.", "partly",
    "PoE 2 common drops keep falling to their floor by ~d14 (3/3); PoE 2 uniques not measured.")
law("Early-spike uniques (biggest day-1 -> week-1 risers, a proxy for build enablers once the meta forms) "
    "are at least 20% below their peak (Chaos) by day 28.",
    ITEM_LEAGUES, lambda lg: M[lg]["spiker_d28_vs_peak_chaos"] <= 0.8 if M[lg].get("spiker_d28_vs_peak_chaos") else None,
    "PoE 1 build-enabler uniques <-> PoE 2 meta items that spike in week 1 (Uncut Skill Gem L20, common soul cores).",
    "partly",
    "PoE 2: Soul Core of Tacati peaks ~d10 then -58 to -83% by d42; Uncut Skill Gem (L20) peaks d6-14, FotV -77% "
    "after. Same shape, different item class; no PoE 2 unique data.",
    {"median_d28_vs_peak_chaos": round(med([M[lg].get("spiker_d28_vs_peak_chaos") for lg in ITEM_LEAGUES]), 2),
     "median_d42_vs_peak_top": round(med([M[lg].get("spiker_d42_vs_peak_top") for lg in ITEM_LEAGUES]), 2)})
sp_days = [d for lg in ITEM_LEAGUES for d in M[lg].get("spiker_peak_days", [])]
law("Early-spike uniques peak by day 7 (true peak, searched over days 2-28) for most of them (> 50%).",
    ITEM_LEAGUES, lambda lg: sum(1 for d in M[lg]["spiker_peak_days"] if d <= 7) / len(M[lg]["spiker_peak_days"]) > 0.5
    if M[lg].get("spiker_peak_days") else None,
    "Same.", "partly", "PoE 2 week-1 spikers peak d6-14 (Uncut Skill Gem L20, Tacati ~d10): a little later.",
    {"share_peak_by_d3": round(sum(1 for d in sp_days if d <= 3) / len(sp_days), 2),
     "share_peak_by_d7": round(sum(1 for d in sp_days if d <= 7) / len(sp_days), 2),
     "share_peak_d8_28": round(sum(1 for d in sp_days if d > 7) / len(sp_days), 2)})

# ---------- League mechanic loot ----------
nl = [lg for lg in ITEM_LEAGUES if M[lg].get("new_first_week") and M[lg].get("old_same_week")]
law("New league-mechanic loot does NOT fall harder in its first week than older items over the same days "
    "(top-orb terms). The folk law 'mechanic loot crashes hardest in week 1' fails.",
    nl, lambda lg: M[lg]["new_first_week"] >= M[lg]["old_same_week"],
    "PoE 1 new-mechanic items <-> PoE 2 items new in a launch.", "confirmed",
    "Consistent: it FAILS in PoE 2 too. Items new to the exchange d1->d6 in Div: RoA "
    f"{P2['new_vs_old_items']['Runes of Aldur']['new_d1_d6']} vs old {P2['new_vs_old_items']['Runes of Aldur']['old_d1_d6']}, FR "
    f"{P2['new_vs_old_items']['Forbidden Rites']['new_d1_d6']} vs {P2['new_vs_old_items']['Forbidden Rites']['old_d1_d6']}.",
    {"note": "'New' = item name never priced in an earlier league, first priced on days 1-7. The folk version "
             "(new loot falls harder) held in only the exception leagues.", "median_new": med([M[lg]["new_first_week"] for lg in nl]),
     "median_old": med([M[lg]["old_same_week"] for lg in nl])})


# ---------- Weekends ----------
def we(w):
    if not w:
        return None
    return st.mean([w.get("Sat", 0), w.get("Sun", 0)]) - st.mean([w.get(k, 0) for k in ("Tue", "Wed", "Thu")])


law("Weekend dip: item prices (10c+, Chaos) sit lower on Sat/Sun than Tue-Thu (days 8-63, detrended).",
    ITEM_LEAGUES, lambda lg: we(M[lg].get("weekday_resid_items_chaos")) < 0 if M[lg].get("weekday_resid_items_chaos") else None,
    "PoE 1 weekend demand/supply <-> PoE 2 weekends.", "unknown",
    "PoE 2 Forbidden Rites days 63-77 (two weekends only), residual % by weekday: "
    + json.dumps(P2["fr_late_weekday_resid_pct"]) + " - too short to call.",
    {"median_effect_pct": round(med([we(M[lg].get("weekday_resid_items_chaos")) for lg in ITEM_LEAGUES]), 2),
     "early_leagues_effect": "negative in most leagues up to Kalandra, positive from Ancestor on"})
law("Weekend dip in the ratio: Chaos per top orb is lower on Sat/Sun than Tue-Thu (days 8-63, detrended).",
    LEAGUES, lambda lg: we(M[lg]["weekday_resid_ratio"]) < 0,
    "Same pair as the ratio laws.", "unknown", "Not tested in PoE 2 (needs daily ratios beyond week 1).",
    {"median_effect_pct": round(med([we(M[lg]["weekday_resid_ratio"]) for lg in LEAGUES]), 2)})

# ---------- End of league ----------
law("End of league: uniques (10c+) are dearer in Chaos in the last 14 days than in the 14 before.",
    ITEM_LEAGUES, lambda lg: M[lg]["end_uniques_chaos_chg"] > 0 if M[lg].get("end_uniques_chaos_chg") is not None else None,
    "PoE 1 thin end-of-league markets <-> PoE 2 late league (volume down 65-98% by week 6-10).", "unknown",
    "PoE 2 late-league unique prices not measured; exchange risers plateau or dip after ~d56 (e.g. Omen of Light).",
    {"median_pct": med([M[lg].get("end_uniques_chaos_chg") for lg in ITEM_LEAGUES]),
     "ratio_last14_vs_prev14_median_pct": med([M[lg].get("end_ratio_chg") for lg in LEAGUES])})

# ---------- Cheap vs dear ----------
law("'Rich get richer': items dearer on day 1 gain more (or lose less) by day 42 (Spearman rho > 0).",
    LEAGUES, lambda lg: M[lg]["rich_richer_rho"] > 0 if M[lg].get("rich_richer_rho") is not None else None,
    "PoE 1 item/currency cross-section <-> PoE 2 exchange cross-section.", "partly",
    "Same sign but much stronger in PoE 2: rho d1->d6 = " + ", ".join(f"{k} {v['rho_d1_d6']}" for k, v in P2["rich_richer"].items()
                                                         if "rho_d1_d6" in v)
    + f"; curve items d1->d42 pooled rho {P2['rich_richer']['curve_items_d1_d42_pooled']['rho']}.",
    {"median_rho": round(med([M[lg]["rich_richer_rho"] for lg in LEAGUES]), 3),
     "note": "PoE 1 day-1 prices are poe.ninja LISTING prices and over-shoot (day-1 asks revert); PoE 2 data are executed exchange trades."})

# ---------- Hype ----------
steam = {}
with open(os.path.join(ROOT, "cache", "steamcharts_238960.csv"), encoding="utf-8") as f:
    for row in csv.DictReader(f, delimiter=";"):
        steam[row["Month"]] = float(row["Peak"])
hype = {}
prev = []
for lg in LEAGUES:
    d = dt.date.fromisoformat(M[lg]["start"])
    pk = steam.get(d.strftime("%B %Y"))
    if pk and prev:
        hype[lg] = {"steam_launch_month_peak": pk, "vs_prev3_median": round(pk / st.median(prev[-3:]), 2)}
    elif pk:
        hype[lg] = {"steam_launch_month_peak": pk, "vs_prev3_median": None}
    if pk:
        prev.append(pk)
hl = [lg for lg in ITEM_LEAGUES if hype.get(lg, {}).get("vs_prev3_median")]
metrics = {
    "ratio_d1_to_d14": lambda lg: ratio_rel[lg].get("14"),
    "ratio_d1_to_peak": lambda lg: M[lg]["ratio_peak"] / M[lg]["ratio_d1"],
    "mirror_top_d7_to_d42": lambda lg: g(lg, "mirror_top_rel", 42),
    "uniques_week1_pct": lambda lg: M[lg]["weekly_uniques_chaos"].get("1"),
    "chase_top_d3_to_d42": lambda lg: g(lg, "chase_rel_d3", 42),
    "spikers_d28_vs_peak": lambda lg: M[lg].get("spiker_d28_vs_peak_chaos"),
}
hype_res = {"index": "Steam peak players in the launch month / median of the previous 3 launches (SteamCharts; "
                     "Steam is only part of PoE's players, the standalone client is not counted).",
            "leagues": hype, "spearman_vs_index": {}, "hyped_vs_quiet_median": {}}
ranked = sorted(hl, key=lambda lg: hype[lg]["vs_prev3_median"])
third = len(ranked) // 3
quiet, hyped = ranked[:third], ranked[-third:]
hype_res["quiet"], hype_res["hyped"] = quiet, hyped
for name, fn in metrics.items():
    pairs = [(hype[lg]["vs_prev3_median"], fn(lg)) for lg in hl if fn(lg) is not None]
    hype_res["spearman_vs_index"][name] = {"rho": round(spearman([a for a, _ in pairs], [b for _, b in pairs]), 2),
                                           "n": len(pairs)}
    hype_res["hyped_vs_quiet_median"][name] = {"hyped": round(med([fn(lg) for lg in hyped]), 2),
                                               "quiet": round(med([fn(lg) for lg in quiet]), 2)}

# ---------- Curves ----------
league_curves = {"chaos_per_top_orb": {lg: {d: round(v, 3) for d, v in ratio_rel[lg].items()} for lg in LEAGUES},
                 "mirror_top_orb_base_d7": {lg: M[lg]["mirror_top_rel"] for lg in mir}}
for lg in LEAGUES:
    for grp, cv in M[lg]["curves"].items():
        if lg == "Essence" and grp not in ("common_currency", "chaos_orb", "splinters", "pinnacle_keys", "catalysts"):
            continue
        league_curves.setdefault(grp, {})[lg] = cv
league_curves["chase_uniques_base_d3"] = {lg: M[lg]["chase_rel_d3"] for lg in ITEM_LEAGUES if M[lg].get("chase_rel_d3")}
timing = {}
for grp in sorted({k for lg in LEAGUES for k in M[lg].get("group_peak_trough", {})}):
    pts = [M[lg]["group_peak_trough"][grp] for lg in ITEM_LEAGUES if grp in M[lg].get("group_peak_trough", {})]
    timing[grp] = {"leagues": len(pts), "median_peak_day": med([p["peak_day"] for p in pts]),
                   "median_trough_day": med([p["trough_day"] for p in pts]),
                   "median_trough_rel": round(med([p["trough"] for p in pts]), 3)}
summary = {}
for grp, per in league_curves.items():
    summary[grp] = {}
    for d in ("1", "3", "7", "14", "28", "42", "70"):
        v = [c.get(d) for c in per.values() if c.get(d) is not None]
        if v:
            summary[grp][d] = round(st.median(v), 3)

ratios_abs = {lg: {"top_orb": M[lg]["top_orb"], "start": M[lg]["start"], "chaos_per_top": M[lg]["ratio_abs"],
                   "peak_day": M[lg]["ratio_peak_day"], "peak": M[lg]["ratio_peak"], "last7_median": M[lg]["ratio_end"],
                   "mirror_chaos": M[lg]["mirror_chaos"]} for lg in LEAGUES}
examples = {lg: {"chase_uniques": M[lg].get("chase_names"), "early_spikers": M[lg].get("spiker_names", [])[:8]}
            for lg in ITEM_LEAGUES}

out = {
    "made": "2026-11-21",
    "about": "PoE 1 league-economy history (33 challenge leagues, Essence 2016 -> Allflame 2026) from poe.ninja's public "
             "economy dumps, used as ANALOGY for Path of Exile 2. Nothing here is PoE 2 fact; each law carries a "
             "poe2_check against research/market (PoE 2 exchange data, 3 launches). Prices: poe.ninja daily values in "
             "Chaos; curves in top-orb terms (Exalted before 3.19 Kalandra, Divine from Kalandra on), relative to "
             "league day 1 unless the group name says otherwise. Day 0 = launch Friday (partial). Item groups only "
             "use items worth 5c+ on day 1 (below that, listings sit on a ~1c floor).",
    "leagues": LEAGUES,
    "laws": laws,
    "league_curves": league_curves,
    "league_curves_median": summary,
    "group_timing": timing,
    "ratios": ratios_abs,
    "hype": hype_res,
    "examples": examples,
    "sources": [
        {"title": "poe.ninja PoE 1 economy data dumps (CC-BY-SA), one zip per league", "url": "https://poe.ninja/poe1/data",
         "api": "https://poe.ninja/poe1/api/data/dumps and /dump?name=<League>", "accessed": "2026-11-21",
         "note": "33 zips, 1.1 GB, cached raw on F:\\Research-cache\\poe1\\zips; slimmed copies in cache/slim."},
        {"title": "SteamCharts: Path of Exile (app 238960) monthly peak players", "url": "https://steamcharts.com/app/238960",
         "accessed": "2026-11-21", "note": "Steam players only."},
        {"title": "Exile Oracle PoE 2 market study (research/market/market-trends.json, sources.md)",
         "url": "research/market/market-trends.json", "accessed": "2026-11-21"},
        {"title": "Exile Oracle app DB (read-only): ls_price days 0-6 of 3 launches, ex_price FR days 63-77",
         "url": "<data folder>\\data\\poe2kit.db", "accessed": "2026-11-21"},
        {"title": "Checked, not used (derived from the same poe.ninja dumps or not a dataset): Kaggle 'Path of Exile "
                  "currency economy', github produdez/poe-economy, poeledger", "url": "https://github.com/produdez/poe-economy",
         "accessed": "2026-11-21"},
    ],
    "caveats": [
        "ANALOGY ONLY: PoE 1 uses player-to-player trade with listing prices; PoE 2 has a Currency Exchange with executed trades.",
        "poe.ninja dump values are daily LISTING-based estimates, not trades, and have no volume; thin items (Mirror, "
        "day 0-2 uniques) are noisy. Mirror quotes before day 7 are ignored; Kalandra's Mirror quotes were unusable.",
        "Top orb switch at 3.19 Kalandra (Exalted -> Divine): ratio laws compare different orbs before and after.",
        "Essence (2016) has item data only from day 48: excluded from item laws.",
        "Group membership is by name/type rules in analyse.py; 'new league-mechanic loot' = names never priced before.",
        "Settlers ran ~10 months (until 3.26); end-of-league measures use each league's real last day in the dump.",
        "Steam player counts miss the standalone client; the hype index is relative only.",
        "Liquidity could not be measured: the dumps have no volume or listing counts.",
    ],
}
with open(os.path.join(ROOT, "poe1-history.json"), "w", encoding="utf-8") as f:
    json.dump(out, f, indent=1, ensure_ascii=False)
for x in laws:
    extra = {k: v for k, v in x.items() if k not in ("law", "holds_in", "out_of", "share", "exceptions", "poe2_mapping",
                                                     "poe2_check", "poe2_evidence", "label")}
    print(f"{x['holds_in']}/{x['out_of']} [{x['poe2_check']}] {x['law']}\n    exc {x['exceptions']} {extra}")
print(json.dumps(hype_res["spearman_vs_index"]), json.dumps(hype_res["hyped_vs_quiet_median"]))
print("hyped", hyped, "quiet", quiet)
print(json.dumps(timing))
print(json.dumps(summary))
