"""Train, backtest and describe the Exile Oracle price forecast (research R8).

Reads cache/prices.db (build_dataset.py) and writes:
  forecast-model.json        the model forecast.py loads + the research tables (paths, spread, backtest, ...)
  cache/backtest_rows.csv.gz every held-out prediction (for re-checking)
  cache/analysis.json        extra tables used in forecast-model.md
Method (details in forecast-model.md / the JSON 'method' block):
  six softcore launches (EA 0.1 Standard, Dawn of the Hunt, Rise of the Abyssal, Fate of the Vaal, Runes of Aldur,
  Forbidden Rites); league day = floor((hour - launch hour) / 86400); x = ln(price in Divines) at the 21:00 UTC sample.
  Leave-one-launch-out: for each launch L, a model is trained on the other five (with an inner leave-one-out so the
  scale / momentum / quantile tables come from out-of-sample surprises) and scored on L.
Usage: python -I model.py <forecast_dir>"""
import csv, gzip, json, math, os, sqlite3, statistics, sys, time

ROOT = sys.argv[1]
sys.path.insert(0, ROOT)
import forecast as fc  # noqa: E402  (the shipped module: the backtest scores exactly this code)

DB = os.path.join(ROOT, 'cache', 'prices.db')
H = (1, 3, 7, 14)
GRID = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 16, 18, 20, 22, 24, 26, 28, 31, 35, 38, 42, 46, 49, 53, 56,
        63, 70, 77, 84, 91, 98, 105, 112, 119]
PATH_DAYS = [0, 1, 2, 3, 4, 5, 6, 7, 10, 14, 21, 28, 35, 42, 49, 56, 70, 84, 98, 112]
MAXD = 125
ZPH = [[0, 2], [3, 6], [7, 13], [14, 27], [28, 55], [56, 100000]]
MPH = [[0, 20], [21, 48], [49, 100000]]
K_DRIFT = 2.0      # pseudo-launches of category drift mixed into each item's drift
RIDGE = 10.0       # ridge on the momentum fit (sum of e^2 units; ~100 typical cases)
K_SCALE = 15.0     # pseudo-observations of category scale mixed into each item's scale
QLEV = (0.10, 0.25, 0.50, 0.75, 0.90)
LAUNCH_ORDER = ['EA 0.1', 'Dawn of the Hunt', 'Rise of the Abyssal', 'Fate of the Vaal', 'Runes of Aldur',
                'Forbidden Rites']
HC_OF = {'EA 0.1': 'Hardcore', 'Dawn of the Hunt': 'HC Dawn of the Hunt', 'Rise of the Abyssal': 'HC Rise of the Abyssal',
         'Fate of the Vaal': 'HC Fate of the Vaal', 'Runes of Aldur': 'HC Runes of Aldur',
         'Forbidden Rites': 'HC Forbidden Rites'}
SKIP_ITEMS = {'Divine Orb'}


def win(g):
    return 0 if g <= 3 else 1 if g <= 13 else 2 if g <= 27 else 3 if g <= 55 else 4


def med(xs):
    return statistics.median(xs) if xs else None


def quant(xs, q):
    """Linear-interpolated quantile of a sorted list."""
    if not xs:
        return None
    k = (len(xs) - 1) * q
    f = int(k)
    c = min(f + 1, len(xs) - 1)
    return xs[f] + (xs[c] - xs[f]) * (k - f)


def mad_scale(xs):
    if len(xs) < 3:
        return None
    m = statistics.median(xs)
    return 1.4826 * statistics.median(abs(x - m) for x in xs)


# ---------------------------------------------------------------------------------------------------- data
def load():
    db = sqlite3.connect(DB)
    lg = {r[0]: (r[1], r[2]) for r in db.execute('SELECT league, start_hour, kind FROM league')}
    names = {r[0]: (r[1], r[2]) for r in db.execute('SELECT item, name, category FROM item')}
    starts = {k: v[0] for k, v in lg.items()}
    launch_hour = {'EA 0.1': starts['Standard']}
    for n in LAUNCH_ORDER[1:]:
        launch_hour[n] = starts[n]
    order = sorted(launch_hour, key=launch_hour.get)
    succ = {a: launch_hour[b] for a, b in zip(order, order[1:])}
    series = {}   # segment -> name -> {day: (x, units, divvol)}
    cats = {}

    def add(seg, league, dmin, dmax):
        S = series.setdefault(seg, {})
        best = {}
        for day, item, p, u in db.execute('SELECT day, item, price_div, units FROM day WHERE league=? AND day>=? AND day<=?',
                                          (league, dmin, dmax)):
            if not p or p <= 0 or not u or u < 1:
                continue
            nm, c = names.get(item, (item, 'Other'))
            if nm in SKIP_ITEMS:
                continue
            cats.setdefault(nm, c)
            k = (nm, day)
            if k not in best or u > best[k][1]:
                best[k] = (math.log(p), u, u * p)
        for (nm, day), v in best.items():
            S.setdefault(nm, {})[day] = v

    for n in LAUNCH_ORDER:
        lgname = 'Standard' if n == 'EA 0.1' else n
        st = lg[lgname][0]
        last = (succ[n] - st) // 86400 - 1 if n in succ else 10 ** 6
        add(n, lgname, 0, min(last, MAXD + 14))
        hc = HC_OF[n]
        if hc in lg:
            add('HC ' + n if n != 'EA 0.1' else 'Hardcore EA 0.1', hc, 0, min(last, MAXD + 14))
        if n in succ:   # legacy tail: the league after its successor launched
            add('legacy: ' + n, lgname, last + 1, 10 ** 6)
    meta = {'launch_hour': launch_hour, 'successor_hour': succ,
            'segments': {s: {'items': len(v), 'days': len({d for it in v.values() for d in it})} for s, v in series.items()}}
    return series, cats, meta


# ---------------------------------------------------------------------------------------------------- statistics
class Pre:
    """League-specific pieces that do not depend on which leagues are in the training set."""

    def __init__(self, series, cats, leagues, tier):
        self.series, self.cats, self.leagues, self.tier = series, cats, leagues, tier
        self.R = {}      # (L, item, h) -> {d: return}
        self.M = {}      # (L, item, h) -> [window median on GRID or None]
        self.C = {}      # (L, cat, h) -> [...]
        self.A = {}      # (L, h) -> [...]
        for L in leagues:
            for it, xs in series[L].items():
                for h in H:
                    r = {d: xs[d + h][0] - xs[d][0] for d in xs if d + h in xs and d <= MAXD}
                    if not r:
                        continue
                    self.R[(L, it, h)] = r
                    row = []
                    for g in GRID:
                        w = win(g)
                        vals = [r[d] for d in range(g - w, g + w + 1) if d in r]
                        row.append(med(vals))
                    self.M[(L, it, h)] = row
            for h in H:
                bycat, allv = {}, [[] for _ in GRID]
                for (L2, it, h2), row in self.M.items():
                    if L2 != L or h2 != h:
                        continue
                    c = cats.get(it, 'Other')
                    b = bycat.setdefault(c, [[] for _ in GRID])
                    for j, v in enumerate(row):
                        if v is not None:
                            b[j].append(v)
                            allv[j].append(v)
                for c, b in bycat.items():
                    self.C[(L, c, h)] = [med(v) if len(v) >= 3 else None for v in b]
                self.A[(L, h)] = [med(v) for v in allv]
        self.items = sorted({it for L in leagues for it in series[L]})


def drift_tables(pre, S):
    """Shrunk drift on GRID for every item / category / all, trained on leagues S."""
    glob = {}
    for h in H:
        glob[h] = [med([pre.A[(L, h)][j] for L in S if pre.A.get((L, h)) and pre.A[(L, h)][j] is not None])
                   for j in range(len(GRID))]
    catd = {}
    for c in set(pre.cats.values()):
        for h in H:
            row = []
            for j in range(len(GRID)):
                vals = [pre.C[(L, c, h)][j] for L in S if (L, c, h) in pre.C and pre.C[(L, c, h)][j] is not None]
                if vals:
                    n = len(vals)
                    g = glob[h][j] if glob[h][j] is not None else 0.0
                    row.append((n * med(vals) + 1.0 * g) / (n + 1.0))   # category shrunk lightly toward all items
                else:
                    row.append(glob[h][j])
            catd[(c, h)] = row
    itd, nlg = {}, {}
    for it in pre.items:
        c = pre.cats.get(it, 'Other')
        for h in H:
            rows = [pre.M[(L, it, h)] for L in S if (L, it, h) in pre.M]
            if not rows:
                continue
            out = []
            for j in range(len(GRID)):
                vals = [r[j] for r in rows if r[j] is not None]
                base = catd[(c, h)][j]
                if base is None:
                    base = 0.0
                if vals:
                    n = len(vals)
                    out.append((n * med(vals) + K_DRIFT * base) / (n + K_DRIFT))
                else:
                    out.append(base)   # no launch has this item at this day: the category drift (n = 0)
            itd[(it, h)] = out
        nlg[it] = sum(1 for L in S if len(pre.series[L].get(it, {})) >= 10)
    return glob, catd, itd, nlg


def daily_G(tab_row):
    return [fc._interp(GRID, tab_row, d) for d in range(0, MAXD + 1)]


def residuals(pre, L, tabs):
    """Out-of-sample surprises for league L given drift tables trained without L."""
    glob, catd, itd, _ = tabs
    xs_all = pre.series[L]
    out = []
    cacheG = {}

    def G(it, h):
        k = (it, h)
        if k not in cacheG:
            c = pre.cats.get(it, 'Other')
            row = itd.get((it, h))
            gi = daily_G(row) if row and any(v is not None for v in row) else None
            gc = daily_G(catd[(c, h)])
            cacheG[k] = [gi[d] if gi and gi[d] is not None else gc[d] for d in range(MAXD + 1)]
        return cacheG[k]

    for it, xs in xs_all.items():
        for h in H:
            r = pre.R.get((L, it, h))
            if not r:
                continue
            g = G(it, h)
            g7 = G(it, 7)
            for d, rv in r.items():
                if d > MAXD:
                    continue
                e = None
                if d >= 7 and d - 7 in xs:
                    e = (xs[d][0] - xs[d - 7][0]) - g7[d - 7]
                    e = max(-1.5, min(1.5, e))
                out.append((it, d, h, rv - g[d], e, rv))
    return out


def fit_rest(pre, S, tabs_full):
    """Scale, momentum and standardised-quantile tables from inner leave-one-out surprises within S."""
    res = []   # (L, it, d, h, y, e, raw)
    for l in S:
        inner = [x for x in S if x != l]
        tabs = drift_tables(pre, inner)
        for it, d, h, y, e, raw in residuals(pre, l, tabs):
            res.append((l, it, d, h, y, e, raw))
    TIERS = ('liquid', 'medium', 'thin', 'all')
    # drift weight w(h, tier, z-phase): how much of the typical path actually repeated out of sample.
    # Least-absolute-deviation fit of raw = w * G over a grid w in [0, 1.2] (G = raw - y, the inner out-of-sample drift).
    WGRID = [k / 20 for k in range(0, 25)]
    wacc = {}
    for _, it, d, h, y, e, raw in res:
        g = raw - y
        j = fc._phase(ZPH, d)
        for t in (pre.tier.get(it, 'thin'), 'all'):
            wacc.setdefault((h, t, j), []).append((raw, g))
    dw = {}
    for h in H:
        dw[h] = {}
        for t in TIERS:
            dw[h][t] = []
            for j in range(len(ZPH)):
                v = wacc.get((h, t, j)) or []
                if len(v) < 300:
                    v = wacc.get((h, 'all', j)) or []
                if not v:
                    dw[h][t].append(1.0)
                    continue
                if len(v) > 40000:
                    v = v[::len(v) // 40000 + 1]
                best = min(WGRID, key=lambda w: sum(abs(r - w * g) for r, g in v))
                dw[h][t].append(best)

    def wt(h, d, it):
        return dw[h][pre.tier.get(it, 'thin')][fc._phase(ZPH, d)]

    res = [(l, it, d, h, raw - wt(h, d, it) * (raw - y), e, raw) for l, it, d, h, y, e, raw in res]
    # momentum / mean reversion, per horizon, liquidity tier and phase (tier 'all' = pooled, for unknown items)
    acc = {}
    for _, it, d, h, y, e, _ in res:
        if e is None:
            continue
        j = fc._phase(MPH, d)
        yy = max(-1.5, min(1.5, y))
        for t in (pre.tier.get(it, 'thin'), 'all'):
            a_ = acc.setdefault((h, t, j), [0.0, 0.0, 0.0, 0.0])
            if e > 0:
                a_[0] += e * yy; a_[1] += e * e
            else:
                a_[2] += e * yy; a_[3] += e * e
    mom = {}
    for h in H:
        mom[h] = {}
        for t in TIERS:
            mom[h][t] = []
            for j in range(len(MPH)):
                su, nu, sd, nd = acc.get((h, t, j), (0.0, 0.0, 0.0, 0.0))
                bu = max(-0.9, min(0.9, su / (nu + RIDGE)))   # ridge: thin evidence pulls beta toward 0
                bd = max(-0.9, min(0.9, sd / (nd + RIDGE)))
                mom[h][t].append({'beta_up': round(bu, 4), 'beta_down': round(bd, 4)})

    def beta(h, d, e, it):
        if e is None:
            return 0.0
        j = fc._phase(MPH, d)
        m = mom[h][pre.tier.get(it, 'thin')][j]
        return m['beta_up'] if e > 0 else m['beta_down']

    u_by_item, u_by_cat, u_all = {}, {}, {}
    U = []
    for l, it, d, h, y, e, raw in res:
        u = y - beta(h, d, e, it) * e if e is not None else y
        U.append((it, d, h, u, raw))
        u_by_item.setdefault((it, h), []).append(u)
        u_by_cat.setdefault((pre.cats.get(it, 'Other'), h), []).append(u)
        u_all.setdefault(h, []).append(u)
    s_all = {h: mad_scale(u_all[h]) for h in H}
    s_cat = {k: (mad_scale(v) if len(v) >= 30 else None) for k, v in u_by_cat.items()}
    s_item = {}
    for (it, h), v in u_by_item.items():
        sc = s_cat.get((pre.cats.get(it, 'Other'), h)) or s_all[h]
        si = mad_scale(v) if len(v) >= 3 else None
        n = len(v) if si is not None else 0
        s_item[(it, h)] = math.sqrt((n * (si or 0) ** 2 + K_SCALE * sc ** 2) / (n + K_SCALE))
    zs, raw_c = {}, {}
    for it, d, h, u, raw in U:
        sc = s_item.get((it, h)) or s_all[h]
        j = fc._phase(ZPH, d)
        for t in (pre.tier.get(it, 'thin'), 'all'):
            zs.setdefault((h, t, j), []).append(u / sc)
        raw_c.setdefault((h, j), []).append(raw)
    zq, baseq = {}, {}
    for h in H:
        zq[h], baseq[h] = {}, []
        for t in TIERS:
            zall = sorted(z for j in range(len(ZPH)) for z in zs.get((h, t, j), []))
            if len(zall) < 200:
                zall = sorted(z for j in range(len(ZPH)) for z in zs.get((h, 'all', j), []))
            zq[h][t] = []
            for j in range(len(ZPH)):
                z = zs.get((h, t, j), [])
                z = sorted(z) if len(z) >= 200 else zall
                zq[h][t].append([round(quant(z, q), 4) for q in QLEV])
        rall = sorted(r for j in range(len(ZPH)) for r in raw_c.get((h, j), []))
        for j in range(len(ZPH)):
            r = raw_c.get((h, j), [])
            r = sorted(r) if len(r) >= 50 else rall
            m = quant(r, 0.5)
            baseq[h].append([round(quant(r, q) - m, 4) for q in QLEV])
    return {'drift_weight': dw, 'momentum': mom, 's_item': s_item, 's_cat': s_cat, 's_all': s_all, 'zq': zq, 'baseq': baseq,
            'residuals': res}


def build_model(pre, S, with_research=False):
    tabs = drift_tables(pre, S)
    glob, catd, itd, nlg = tabs
    rest = fit_rest(pre, S, tabs)
    items = {}
    for it in pre.items:
        if not any((it, h) in itd for h in H):
            continue
        if nlg.get(it, 0) < 1:
            continue
        e = {'category': pre.cats.get(it, 'Other'), 'n_leagues': nlg[it],
             'drift': {str(h): [None if v is None else round(v, 4) for v in itd[(it, h)]] for h in H if (it, h) in itd},
             'scale': {str(h): round(rest['s_item'].get((it, h)) or rest['s_cat'].get((pre.cats.get(it, 'Other'), h))
                                     or rest['s_all'][h], 4) for h in H}}
        e['liquidity'] = pre.tier.get(it, 'thin')
        n = e['n_leagues']
        e['confidence'] = ('high' if n >= 4 and e['liquidity'] == 'liquid' else
                           'medium' if n >= 3 and e['liquidity'] != 'thin' else 'low')
        items[it] = e
    cats = {}
    for c in sorted(set(pre.cats.values())):
        cats[c] = {'drift': {str(h): [None if v is None else round(v, 4) for v in catd[(c, h)]] for h in H},
                   'scale': {str(h): round(rest['s_cat'].get((c, h)) or rest['s_all'][h], 4) for h in H}}
    model = {'method': {'grid': GRID, 'z_phases': ZPH, 'momentum_phases': MPH, 'max_day_with_data': MAXD,
                        'n_launches': len(S), 'patch_shock_scale_multiplier': 1.6},
             'items': items, 'category_paths': cats,
             'global': {'drift': {str(h): [round(v, 4) if v is not None else None for v in glob[h]] for h in H},
                        'scale': {str(h): round(rest['s_all'][h], 4) for h in H}},
             'drift_weight': {str(h): rest['drift_weight'][h] for h in H},
             'momentum': {str(h): rest['momentum'][h] for h in H},
             'zq': {str(h): rest['zq'][h] for h in H}}
    return model, rest, tabs


# ---------------------------------------------------------------------------------------------------- evaluation
def liquidity_tiers(series, launches):
    vols = {}
    for L in launches:
        for it, xs in series[L].items():
            vols.setdefault(it, []).extend(v[2] for v in xs.values())
    tier = {}
    for it, v in vols.items():
        m = statistics.median(v)
        tier[it] = 'liquid' if m >= 20 else 'medium' if m >= 2 else 'thin'
    return tier


class Row:
    __slots__ = ('set', 'league', 'item', 'cat', 'tier', 'day', 'h', 'actual', 'q', 'trend', 'bq', 'conf')

    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)

    def __getitem__(self, k):
        return getattr(self, k)


def evaluate(series, cats, L, model, baseq, tier, rows, tag, day_override=None, dmin=0, dmax=MAXD):
    """Score the model on segment L. Appends dicts to rows."""
    orc = fc.Oracle(model)
    for it, xs in series.get(L, {}).items():
        for d, (x0, u0, _) in xs.items():
            if not (dmin <= d <= dmax):
                continue
            futs = [h for h in H if d + h in xs]
            if not futs:
                continue
            dd = day_override if day_override is not None else d
            r7 = (math.exp(x0 - xs[d - 7][0]) - 1) * 100 if d - 7 in xs else None
            f = orc.forecast(it, dd, math.exp(x0), r7, category=cats.get(it))
            for h in futs:
                q = f['horizons'][h]
                a = xs[d + h][0] - x0
                pq = [math.log(q[k]) - x0 if q[k] > 0 else -50 for k in fc.QS]
                bq = baseq[h][fc._phase(ZPH, dd)]
                trend = (x0 - xs[d - 7][0]) * h / 7 if d - 7 in xs else None
                rows.append(Row(set=tag, league=L, item=it, cat=cats.get(it, 'Other'), tier=tier.get(it, 'thin'),
                                day=d, h=h, actual=a, q=tuple(pq), trend=trend, bq=bq, conf=f['confidence']))


def pinball(qs, a):
    return sum(max(lv * (a - q), (lv - 1) * (a - q)) for lv, q in zip(QLEV, qs)) / len(QLEV)


def summarize(rows):
    if not rows:
        return None
    n = len(rows)
    below = [sum(1 for r in rows if r['actual'] < r['q'][k]) / n for k in range(5)]
    c50 = sum(1 for r in rows if r['q'][1] <= r['actual'] <= r['q'][3]) / n
    c80 = sum(1 for r in rows if r['q'][0] <= r['actual'] <= r['q'][4]) / n
    ae = sorted(abs(r['actual'] - r['q'][2]) for r in rows)
    ae0 = sorted(abs(r['actual']) for r in rows)
    tr = [r for r in rows if r['trend'] is not None]
    aet = sorted(abs(r['actual'] - r['trend']) for r in tr)
    aem_tr = sorted(abs(r['actual'] - r['q'][2]) for r in tr)
    big = [r for r in rows if abs(r['q'][2]) >= math.log(1.10)]
    dir_hit = (sum(1 for r in big if r['actual'] * r['q'][2] > 0) / len(big)) if big else None
    mv = [r for r in rows if abs(r['actual']) >= math.log(1.05)]
    dir_all = (sum(1 for r in mv if r['actual'] * r['q'][2] > 0) / len(mv)) if mv else None
    pl = sum(pinball(r['q'], r['actual']) for r in rows) / n
    plb = sum(pinball(r['bq'], r['actual']) for r in rows) / n
    pct = lambda x: round((math.exp(x) - 1) * 100, 1)
    return {'n': n,
            'coverage_50': round(c50, 3), 'coverage_80': round(c80, 3),
            'calibration_below': {f'p{int(q * 100)}': round(b, 3) for q, b in zip(QLEV, below)},
            'median_abs_error_pct': {'model': pct(quant(ae, .5)), 'no_change': pct(quant(ae0, .5)),
                                     'model_on_trend_subset': pct(quant(aem_tr, .5)) if aem_tr else None,
                                     'last_week_trend': pct(quant(aet, .5)) if aet else None},
            'direction_hit_rate_when_model_calls_10pct_move': round(dir_hit, 3) if dir_hit is not None else None,
            'share_of_cases_model_calls_10pct_move': round(len(big) / n, 3),
            'direction_hit_rate_on_real_5pct_moves': round(dir_all, 3) if dir_all is not None else None,
            'pinball_loss': round(pl, 4), 'pinball_loss_no_change_with_empirical_bands': round(plb, 4),
            'pinball_skill_vs_no_change': round(1 - pl / plb, 3) if plb else None}


def group(rows, key):
    out = {}
    for r in rows:
        out.setdefault(key(r), []).append(r)
    return {k: summarize(v) for k, v in sorted(out.items(), key=lambda kv: str(kv[0]))}


# ---------------------------------------------------------------------------------------------------- research tables
def typical_paths(series, launches, cats, items):
    out, catacc = {}, {}
    for it in items:
        per = {}
        for L in launches:
            xs = series[L].get(it)
            if not xs or 1 not in xs:
                continue
            a = xs[1][0]
            for d in PATH_DAYS:
                w = win(d)
                vals = [xs[k][0] for k in range(d - w, d + w + 1) if k in xs]
                if vals:
                    per.setdefault(d, []).append(med(vals) - a)
                    catacc.setdefault((cats.get(it, 'Other'), L, d), []).append(med(vals) - a)
        if not per:
            continue
        tp, sp = {}, {}
        for d, v in sorted(per.items()):
            v = sorted(v)
            tp[str(d)] = _r(math.exp(med(v)))
            sp[str(d)] = [_r(math.exp(quant(v, q))) for q in (.1, .25, .75, .9)] if len(v) >= 3 else None
        out[it] = (tp, sp, {d: len(v) for d, v in per.items()})
    catp = {}
    for (c, L, d), v in catacc.items():
        catp.setdefault(c, {}).setdefault(d, []).append(med(v))
    cat_out = {}
    for c, dd in catp.items():
        tp, sp = {}, {}
        for d, v in sorted(dd.items()):
            v = sorted(v)
            tp[str(d)] = _r(math.exp(med(v)))
            sp[str(d)] = [_r(math.exp(quant(v, q))) for q in (.1, .25, .75, .9)] if len(v) >= 3 else None
        cat_out[c] = (tp, sp)
    return out, cat_out


def _r(x):
    return fc._round(x)


def research_stats(pre, rest, model, launches, cats, tier):
    """Volatility, autocorrelation, trend continuation, spike reversion, shocks: all from the final model's inner
    leave-one-out surprises (each league scored by drift trained on the other five)."""
    res = rest['residuals']
    s_item = rest['s_item']
    u = {}   # (L, it, h) -> {d: y}
    for l, it, d, h, y, e, raw in res:
        u.setdefault((l, it, h), {})[d] = y
    # autocorrelation of 1-day surprises (lag 1) and of 7-day surprises (lag 7, non-overlapping)
    def corr(pairs):
        if len(pairs) < 30:
            return None
        a = [max(-1.5, min(1.5, p[0])) for p in pairs]; b = [max(-1.5, min(1.5, p[1])) for p in pairs]
        ma, mb = sum(a) / len(a), sum(b) / len(b)
        va = sum((x - ma) ** 2 for x in a); vb = sum((x - mb) ** 2 for x in b)
        return round(sum((x - ma) * (y - mb) for x, y in zip(a, b)) / math.sqrt(va * vb), 3) if va and vb else None
    ac = {}
    for (l, it, h), ys in u.items():
        if h not in (1, 7):
            continue
        c = cats.get(it, 'Other')
        lag = 1 if h == 1 else 7
        for d, y in ys.items():
            if d + lag in ys:
                ph = 'days 0-13' if d < 14 else 'days 14-55' if d < 56 else 'day 56+'
                for k in (('all', ph), (c, 'all'), ('all', 'all')):
                    ac.setdefault((h, k), []).append((y, ys[d + lag]))
    autocorr = {f'{"daily_lag1" if h == 1 else "weekly_lag1"}|{k[0]}|{k[1]}': corr(v) for (h, k), v in ac.items()}
    # trend continuation: does the sign of the last 7 days repeat over the next 7?
    cont = {}
    for L in launches:
        for it, xs in pre.series[L].items():
            c = cats.get(it, 'Other')
            y7 = u.get((L, it, 7), {})
            for d in xs:
                if d < 7 or d - 7 not in xs or d + 7 not in xs or d > MAXD:
                    continue
                past, fut = xs[d][0] - xs[d - 7][0], xs[d + 7][0] - xs[d][0]
                if abs(past) < math.log(1.05) or abs(fut) < 1e-9:
                    continue
                ph = 'days 7-20' if d <= 20 else 'days 21-48' if d <= 48 else 'day 49+'
                same = past * fut > 0
                ex = None
                if d - 7 in y7 and d in y7 and abs(y7[d - 7]) >= math.log(1.05):
                    ex = y7[d - 7] * y7[d] > 0
                for k in (('all', ph), (c, 'all'), ('all', 'all'), (tier.get(it, 'thin'), 'all')):
                    cc = cont.setdefault(k, [0, 0, 0, 0])
                    cc[0] += same; cc[1] += 1
                    if ex is not None:
                        cc[2] += ex; cc[3] += 1
    continuation = {f'{k[0]}|{k[1]}': {'raw_same_sign_rate': round(v[0] / v[1], 3) if v[1] else None, 'n': v[1],
                                       'vs_typical_same_sign_rate': round(v[2] / v[3], 3) if v[3] else None, 'n_vs_typical': v[3]}
                    for k, v in cont.items()}
    # spikes: 1-day surprise beyond +-2.5 scale; what happens over the following 7 days (vs typical drift)
    spikes = {}
    events = []
    for (l, it, h), ys in u.items():
        if h != 1:
            continue
        s1 = s_item.get((it, 1))
        y7 = u.get((l, it, 7), {})
        xs = pre.series[l][it]
        for d, y in ys.items():
            if not s1 or abs(y) < 2.5 * s1 or abs(y) < math.log(1.3):
                continue
            if d + 1 not in y7:
                continue
            give = -y7[d + 1] / y
            kind = 'spike up' if y > 0 else 'crash down'
            for k in ((kind, 'all'), (kind, cats.get(it, 'Other')), (kind, tier.get(it, 'thin'))):
                spikes.setdefault(k, []).append(give)
            # level shift test for regime detection: 7 days after vs 7 days before
            before = [xs[k][0] for k in range(d - 6, d + 1) if k in xs]
            after = [xs[k][0] for k in range(d + 1, d + 8) if k in xs]
            if len(before) >= 3 and len(after) >= 3:
                shift = med(after) - med(before)
                persistent = shift * y > 0 and abs(shift) >= 0.5 * abs(y)
                events.append((l, d + 1, it, y, persistent, give))
    reversion = {}
    for k, v in spikes.items():
        v = sorted(v)
        reversion[f'{k[0]}|{k[1]}'] = {'n': len(v), 'median_share_given_back_in_7d': round(quant(v, .5), 3),
                                       'share_of_events_half_reversed': round(sum(1 for x in v if x >= .5) / len(v), 3),
                                       'share_of_events_extended': round(sum(1 for x in v if x < 0) / len(v), 3)}
    # regime / patch-shock days: many persistent level shifts on the same league day
    per_day = {}
    for l, d, it, y, pers, give in events:
        if pers:
            per_day.setdefault((l, d), []).append((abs(y), it, y))
    shocks = []
    for L in launches:
        counts = [len(per_day.get((L, d), [])) for d in range(1, MAXD + 1)]
        base = statistics.median(counts) if counts else 0
        nitems = len(pre.series[L])
        for d in range(1, MAXD + 1):
            n = len(per_day.get((L, d), []))
            if n >= max(8, 3 * base + 3, 0.02 * nitems):
                top = sorted(per_day[(L, d)], reverse=True)[:6]
                ups = sum(1 for _, _, y in per_day[(L, d)] if y > 0)
                shocks.append({'league': L, 'day': d, 'items_with_lasting_jump': n, 'baseline_per_day': base,
                               'share_up': round(ups / n, 2),
                               'top': [f'{it} {"+" if y > 0 else ""}{(math.exp(y) - 1) * 100:.0f}%' for _, it, y in top]})
    # post-shock widening: 7-day surprise scale after an item's own lasting jump vs all origins
    post, norm = [], []
    ev_keys = {(l, it, d) for l, d, it, y, pers, g in events if pers}
    for (l, it, h), ys in u.items():
        if h != 7:
            continue
        s7 = s_item.get((it, 7))
        if not s7:
            continue
        for d, y in ys.items():
            (post if (l, it, d) in ev_keys or (l, it, d - 1) in ev_keys else norm).append(y / s7)
    shock_mult = None
    if len(post) >= 30:
        shock_mult = round(mad_scale(post) / mad_scale(norm), 2)
    # dispersion between launches: spread of the 7-day drift across leagues (per grid day, median over items)
    disp = {}
    for j, g in enumerate(GRID):
        sds = []
        for it in pre.items:
            vals = [pre.M[(L, it, 7)][j] for L in launches if (L, it, 7) in pre.M and pre.M[(L, it, 7)][j] is not None]
            if len(vals) >= 3:
                sds.append(mad_scale(vals) or statistics.pstdev(vals))
        if sds:
            disp[g] = round(statistics.median(sds), 3)
    return {'autocorr': autocorr, 'trend_continuation': continuation, 'spike_reversion': reversion,
            'shock_days': shocks, 'post_shock_scale_ratio': shock_mult, 'n_post_shock_obs': len(post),
            'cross_launch_sd_of_7d_drift_by_day': disp}


# ---------------------------------------------------------------------------------------------------- main
def main():
    t0 = time.time()
    series, cats, meta = load()
    launches = [L for L in LAUNCH_ORDER if series.get(L)]
    print('segments', json.dumps(meta['segments']), flush=True)
    tier = liquidity_tiers(series, launches)
    pre = Pre(series, cats, launches, tier)
    print('pre done', round(time.time() - t0), 's', flush=True)
    rows = []
    for L in launches:
        S = [x for x in launches if x != L]
        model, rest, _ = build_model(pre, S)
        evaluate(series, cats, L, model, rest['baseq'], tier, rows, 'loo')
        # ablations: category paths only (no item knowledge), and no momentum term
        evaluate(series, cats, L, dict(model, items={}), rest['baseq'], tier, rows, 'loo-category-only')
        nomom = {h: {t: [{'beta_up': 0.0, 'beta_down': 0.0} for _ in MPH] for t in v} for h, v in model['momentum'].items()}
        evaluate(series, cats, L, dict(model, momentum=nomom), rest['baseq'], tier, rows, 'loo-no-momentum')
        del rest
        print('fold', L, len(rows), round(time.time() - t0), 's', flush=True)
    final, rest, tabs = build_model(pre, launches)
    # transfer tests with the final model (never trained on these segments)
    for L in launches:
        hc = 'Hardcore EA 0.1' if L == 'EA 0.1' else 'HC ' + L
        if hc in series:
            evaluate(series, cats, hc, final, rest['baseq'], tier, rows, 'hardcore')
        lg = 'legacy: ' + L
        if lg in series:
            evaluate(series, cats, lg, final, rest['baseq'], tier, rows, 'legacy', day_override=MAXD, dmin=0, dmax=10 ** 6)
    print('eval done', len(rows), round(time.time() - t0), 's', flush=True)
    loo = [r for r in rows if r['set'] == 'loo']
    bt = {'per_horizon': {}, 'by_phase': {}, 'by_category': {}, 'by_liquidity': {}, 'by_league': {},
          'by_confidence': {}, 'hardcore_transfer': {}, 'legacy_leagues': {}}
    for h in H:
        rh = [r for r in loo if r['h'] == h]
        s = summarize(rh)
        bt['per_horizon'][str(h)] = dict(s, hit_rate={'inside_25_75': s['coverage_50'], 'inside_10_90': s['coverage_80'],
                                                      'direction_when_calling_10pct': s['direction_hit_rate_when_model_calls_10pct_move']},
                                         calibration=s['calibration_below'])
        bt.setdefault('per_horizon_liquid_or_medium', {})[str(h)] = summarize([r for r in rh if r['tier'] != 'thin'])
        bt['by_phase'][str(h)] = group(rh, lambda r: f'{ZPH[fc._phase(ZPH, r["day"])][0]}-{ZPH[fc._phase(ZPH, r["day"])][1]}')
        bt['by_category'][str(h)] = group(rh, lambda r: r['cat'])
        bt['by_liquidity'][str(h)] = group(rh, lambda r: r['tier'])
        bt['by_league'][str(h)] = group(rh, lambda r: r['league'])
        bt['by_confidence'][str(h)] = group(rh, lambda r: r['conf'])
        bt['hardcore_transfer'][str(h)] = summarize([r for r in rows if r['set'] == 'hardcore' and r['h'] == h])
        bt['legacy_leagues'][str(h)] = summarize([r for r in rows if r['set'] == 'legacy' and r['h'] == h])
        for v in ('loo-category-only', 'loo-no-momentum'):
            vr = [r for r in rows if r['set'] == v and r['h'] == h]
            bt.setdefault('ablations', {}).setdefault(v, {})[str(h)] = {
                'all': summarize(vr), 'by_liquidity': group(vr, lambda r: r['tier'])}
    # research tables + item entries
    paths, cpaths = typical_paths(series, launches, cats, list(final['items']))
    stats = research_stats(pre, rest, final, launches, cats, tier)
    if stats['post_shock_scale_ratio']:
        final['method']['patch_shock_scale_multiplier'] = max(1.0, min(3.0, stats['post_shock_scale_ratio']))
    cat_cov = {c: v['coverage_80'] for c, v in bt['by_category']['7'].items() if v}
    rev_cat = {k.split('|')[1]: v for k, v in stats['spike_reversion'].items()}
    for it, e in final['items'].items():
        tp, sp, nd = paths.get(it, ({}, {}, {}))
        e['typical_path'] = tp
        e['spread'] = sp
        s1, s7 = e['scale']['1'], e['scale']['7']
        e['volatility'] = {'daily_surprise_pct': round((math.exp(s1) - 1) * 100, 1),
                           'weekly_surprise_pct': round((math.exp(s7) - 1) * 100, 1)}
        cr = rev_cat.get(e['category'])
        e['reversion'] = {'category_spike_giveback_7d': cr['median_share_given_back_in_7d'] if cr else None,
                          'momentum_beta_7d': final['momentum']['7']}
        e['reversion'].pop('momentum_beta_7d')
    for c, e in final['category_paths'].items():
        tp, sp = cpaths.get(c, ({}, {}))
        e['typical_path'] = tp
        e['spread'] = sp
        e['n_items'] = sum(1 for v in final['items'].values() if v['category'] == c)
    final['backtest'] = bt
    final['research'] = {k: stats[k] for k in ('autocorr', 'trend_continuation', 'spike_reversion', 'shock_days',
                                                'post_shock_scale_ratio', 'cross_launch_sd_of_7d_drift_by_day')}
    final['launches'] = {L: {'launch_hour_utc': meta['launch_hour'][L], 'successor_hour_utc': meta['successor_hour'].get(L),
                             'items': meta['segments'][L]['items'], 'days': meta['segments'][L]['days']} for L in launches}
    final['segments'] = meta['segments']
    m = final['method']
    m.update({
        'made': '2026-11-21',
        'units': 'prices in Divine Orbs; x = ln(price); league day = floor((hour - launch hour)/86400); one price per day = the 21:00 UTC hourly sample (volume-weighted pair ratio, the app\'s prices_from_page)',
        'data': 'GGG public Currency Exchange history (https://web.poecdn.com/api/currency-exchange/poe2/<hour>), daily 21:00 UTC samples Dec 2024 - Nov 2026 (+09:00 on launch days 0-21) + the app DB ls_price (hours 0-167 of FotV/RoA/FR) and ex_price (hourly since 2026-11-06). Only hours where the item actually traded (units >= 1).',
        'launches_used': launches,
        'horizons': list(H),
        'formula': {
            'forecast': 'x_q(D+h) = x(D) + w(h,liquidity,phase_z(D)) * G(item,D,h) + beta(h,liquidity,phase_m(D),sign e) * e + s(item,h) * m_shock * zq(h,liquidity,phase_z(D),q)',
            'window_median': 'M_L(i,g,h) = median{ x_L(d+h) - x_L(d) : |d - g| <= w(g) }, w(g) = 0 (g<=3), 1 (<=13), 2 (<=27), 3 (<=55), 4',
            'item_drift': f'G(i,g,h) = (n * median_L M_L(i,g,h) + K * Gc(c,g,h)) / (n + K), K = {K_DRIFT}, n = launches with data at g',
            'category_drift': 'Gc(c,g,h) = (n * median_L median_{i in c} M_L(i,g,h) + 1 * Gall(g,h)) / (n + 1)',
            'interpolation': 'G at non-grid days: linear between grid days; before/after the grid: clamped',
            'drift_weight': 'w = argmin_w sum|raw - w * G| over w in {0, 0.05, ..., 1.2}, raw = actual h-day ln change, G = drift trained without that launch (inner leave-one-out); per horizon, liquidity tier and z-phase',
            'excess_trend': 'e = clip(ln(1 + recent_change_pct/100) - G(i, D-7, 7), -1.5, 1.5); only for D >= 7',
            'momentum_fit': 'beta_up = sum(e+ * y)/sum(e+^2), beta_down = sum(e- * y)/sum(e-^2), y = clip(x(D+h)-x(D)-w*G, +-1.5), out-of-sample y and e (inner leave-one-launch-out); ridge: + 10 in each denominator; clamped to [-0.9, 0.9]',
            'scale': f's(i,h) = sqrt((n * MAD_i^2 + {K_SCALE} * MAD_c^2) / (n + {K_SCALE})), MAD = 1.4826 * median|u - median u| of out-of-sample surprises u = y - beta*e',
            'quantiles': 'zq = empirical 10/25/50/75/90 % quantiles of u / s(i,h), pooled over items of the same liquidity tier, per horizon and z-phase (tier all = pooled, used for items not in the model)',
            'patch_shock': 'm_shock = post-jump / normal robust scale of 7-day surprises (1 when no patch)',
            'confidence': "item: high = >=4 launches and liquid (median traded value >= 20 div per hourly sample); medium = >=3 launches and not thin (>= 2 div per hourly sample); low otherwise; forecast() lowers it one step before day 3, past the last data day, or with patch_shock",
        },
        'liquidity_tiers': 'liquid: median traded value >= 20 div per hourly sample; medium >= 2; thin below (thin hourly prices jump 50-200% between days on noise alone)',
        'hyperparameters_fixed_in_advance': {'K_drift': K_DRIFT, 'K_scale': K_SCALE, 'grid': 'see grid'},
    })
    json.dump(final, open(os.path.join(ROOT, 'forecast-model.json'), 'w', encoding='utf-8'), ensure_ascii=False,
              separators=(',', ':'))
    with gzip.open(os.path.join(ROOT, 'cache', 'backtest_rows.csv.gz'), 'wt', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['set', 'league', 'item', 'cat', 'tier', 'day', 'h', 'actual_logchg', 'q10', 'q25', 'q50', 'q75',
                    'q90', 'trend', 'conf'])
        for r in rows:
            if r['set'] not in ('loo', 'hardcore', 'legacy'):
                continue
            w.writerow([r['set'], r['league'], r['item'], r['cat'], r['tier'], r['day'], r['h'], round(r['actual'], 4)]
                       + [round(x, 4) for x in r['q']] + [None if r['trend'] is None else round(r['trend'], 4), r['conf']])
    json.dump({'backtest': bt, 'research': final['research'], 'segments': meta['segments'],
               'momentum': final['momentum'], 'zq': final['zq'], 'global_scale': final['global']['scale']},
              open(os.path.join(ROOT, 'cache', 'analysis.json'), 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
    print('done', round(time.time() - t0), 's; items', len(final['items']))


if __name__ == '__main__':
    main()
