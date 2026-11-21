"""Exile Oracle price forecast (research R8).  Pure Python, standard library only.

Loads forecast-model.json (built by research/forecast/scripts/model.py from GGG's public Currency Exchange history
of six PoE 2 launches) and answers: "it is league day D and this item costs P Divines (and moved X% over the last
7 days) - where will it be in 1, 3, 7 and 14 days?"

    from poe2kit import forecast            # the model is datapack/forecast-model.json
    forecast.forecast('Orb of Annulment', day=9, current_price_div=0.31, recent_change_pct=45)
    -> {'item': ..., 'day': 9, 'horizons': {1: {'median', 'p10', 'p25', 'p75', 'p90'}, 3: ..., 7: ..., 14: ...},
        'confidence': 'medium', 'basis': '...', 'notes': [...]}

The model, in one line per horizon h (all in natural-log price space, x = ln(price in Divines)):
    x_q(D+h) = x(D) + w(h, tier, D) * G(item, D, h) + beta(h, D, sign(e)) * e + s(item, h) * zq(h, phase(D), q)
    tier  the item's liquidity tier (liquid / medium / thin): momentum and quantile tables are fitted per tier
    G   typical drift: median h-day log change at league day D across launches, item value shrunk toward its category
    w   drift weight: how much of the typical path repeated out of sample (fitted; ~0.5-1 early, ~0.1-0.3 late)
    e   excess recent trend = ln(1 + recent_change_pct/100) - G(item, D-7, 7)   (0 when recent change is unknown)
    s   item's robust scale of h-day surprises (shrunk toward its category), times 1.6 if a patch just hit the item
    zq  empirical quantiles (q = 10/25/50/75/90 %) of standardised out-of-sample surprises for that horizon and phase
See forecast-model.md for the method and the honest backtest."""

import bisect
import json
import math
import os

HORIZONS = (1, 3, 7, 14)
QS = ('p10', 'p25', 'median', 'p75', 'p90')
_default = {}


def _here(name):
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), name)


def load(path=None):
    """Read a model file (default: the data pack's forecast-model.json)."""
    from . import config
    path = path or config.data_file('forecast-model.json')
    if not path:
        raise FileNotFoundError('forecast-model.json is missing from the data pack')
    with open(path, encoding='utf-8') as f:
        return json.load(f)


_pts_cache = {}


def _interp(grid, vals, d):
    """Linear interpolation of vals (aligned with grid, may hold None) at day d; clamps outside the grid."""
    key = id(vals)
    hit = _pts_cache.get(key)
    if hit is None or hit[0] is not vals:
        pts = [(g, v) for g, v in zip(grid, vals) if v is not None]
        hit = (vals, [g for g, _ in pts], pts)
        if len(_pts_cache) > 200000:
            _pts_cache.clear()
        _pts_cache[key] = hit
    _, gs, pts = hit
    if not pts:
        return None
    if d <= gs[0]:
        return pts[0][1]
    if d >= gs[-1]:
        return pts[-1][1]
    i = bisect.bisect_right(gs, d)
    (g0, v0), (g1, v1) = pts[i - 1], pts[i]
    return v0 + (v1 - v0) * (d - g0) / (g1 - g0)


def _phase(phases, d):
    for i, (lo, hi) in enumerate(phases):
        if lo <= d <= hi:
            return i
    return len(phases) - 1


class Oracle:
    def __init__(self, model):
        self.m = model
        meth = model['method']
        self.grid = meth['grid']
        self.zphases = meth['z_phases']
        self.mphases = meth['momentum_phases']
        self.max_day = meth['max_day_with_data']
        self.shock_mult = meth.get('patch_shock_scale_multiplier', 1.6)
        self._lower = {k.lower(): k for k in model['items']}

    # ---- pieces of the formula -------------------------------------------------------------------------------
    def _entry(self, item, category):
        name = self._lower.get((item or '').lower())
        it = self.m['items'].get(name) if name else None
        cat = (it or {}).get('category') or category
        ce = self.m['category_paths'].get(cat) if cat else None
        return name, it, cat, ce

    def drift(self, item, day, h, category=None):
        """G(item, day, h): typical h-day log change starting at league day `day`, and where it came from."""
        _, it, cat, ce = self._entry(item, category)
        for src, e in (('item', it), ('category', ce), ('all items', self.m['global'])):
            if e and e.get('drift', {}).get(str(h)):
                v = _interp(self.grid, e['drift'][str(h)], day)
                if v is not None:
                    return v, src
        return 0.0, 'none'

    def scale(self, item, h, category=None):
        _, it, cat, ce = self._entry(item, category)
        for e in (it, ce, self.m['global']):
            if e and e.get('scale', {}).get(str(h)):
                return e['scale'][str(h)]
        return 1.0

    # ---- the forecast ----------------------------------------------------------------------------------------
    def forecast(self, item, day, current_price_div, recent_change_pct=None, category=None, patch_shock=False,
                 liquidity=None):
        """Median and 10/25/75/90 % range of the price (in Divines) 1, 3, 7 and 14 days ahead.
        item: exchange item name (case-insensitive); unknown items fall back to `category` (poe.ninja category
        name, e.g. 'Essences') or to all items.  day: league day (0 = first 24 h; floats allowed).
        recent_change_pct: % change over the last 7 days, as the app's market view shows it (None if unknown).
        patch_shock: True if a patch / hotfix in the last few days touched this item: widens every range.
        liquidity: 'liquid' / 'medium' / 'thin' to override the item's tier (e.g. for items not in the model)."""
        if not current_price_div or current_price_div <= 0:
            raise ValueError('current_price_div must be a positive price in Divine Orbs')
        day = max(0.0, float(day))
        name, it, cat, ce = self._entry(item, category)
        tier = liquidity or (it or {}).get('liquidity') or 'all'
        x0 = math.log(current_price_div)
        notes = []
        e = None
        if recent_change_pct is not None and recent_change_pct > -100 and day >= 7:
            g7, _ = self.drift(item, day - 7, 7, category)
            e = math.log(1 + recent_change_pct / 100.0) - g7
            e = max(-1.5, min(1.5, e))
            if abs(e) > 0.3:
                notes.append(f'last 7 days were {"above" if e > 0 else "below"} the usual move by '
                             f'{(math.exp(abs(e)) - 1) * 100:.0f}%: the model expects part of that to '
                             f'{"continue" if self._beta(1, day, e, tier) > 0 else "reverse"}')
        out = {}
        srcs = set()
        for h in HORIZONS:
            g, src = self.drift(item, day, h, category)
            srcs.add(src)
            w = self._w(h, tier, day)
            mu = w * g + (self._beta(h, day, e, tier) * e if e is not None else 0.0)
            s = self.scale(item, h, category) * (self.shock_mult if patch_shock else 1.0)
            zq = self._zq(h, tier)[_phase(self.zphases, day)]
            out[h] = {q: _round(math.exp(x0 + mu + s * z)) for q, z in zip(QS, zq)}
            out[h]['change_pct'] = round((math.exp(mu + s * zq[2]) - 1) * 100, 1)
        conf = self._confidence(it, day, src_set=srcs, patch_shock=patch_shock)
        basis = []
        if it:
            basis.append(f"{name}: typical path from {it.get('n_leagues', 0)} of {self.m['method']['n_launches']} "
                         f"launches ({it.get('liquidity', '?')} market), drift shrunk toward {cat}")
        elif ce:
            basis.append(f'not in the model: using the {cat} category path')
        else:
            basis.append('not in the model and no category: using the all-items path (very rough)')
        if e is not None:
            basis.append('recent 7-day trend used (momentum / mean-reversion term)')
        elif recent_change_pct is not None and day < 7:
            notes.append('recent trend ignored before day 7 (the model has no week-1 momentum term)')
        if day > self.max_day:
            notes.append(f'day {day:.0f} is past the last launch day with data ({self.max_day}): late-league drift held flat')
        if patch_shock:
            notes.append(f'patch shock: ranges widened x{self.shock_mult}')
        return {'item': name or item, 'category': cat, 'day': round(day, 2), 'current_price_div': current_price_div,
                'horizons': out, 'confidence': conf, 'basis': '; '.join(basis), 'notes': notes}

    def _w(self, h, tier, day):
        t = (self.m.get('drift_weight') or {}).get(str(h))
        if not t:
            return 1.0
        return (t.get(tier) or t['all'])[_phase(self.zphases, day)]

    def _zq(self, h, tier):
        t = self.m['zq'][str(h)]
        return t.get(tier) or t['all']

    def _beta(self, h, day, e, tier='all'):
        if e is None:
            return 0.0
        t = self.m['momentum'][str(h)]
        mom = (t.get(tier) or t['all'])[_phase(self.mphases, day)]
        return mom['beta_up'] if e > 0 else mom['beta_down']

    def _confidence(self, it, day, src_set, patch_shock):
        if 'item' not in src_set or not it:
            return 'low'
        c = it.get('confidence', 'low')
        rank = {'low': 0, 'medium': 1, 'high': 2}[c]
        if day > self.max_day or patch_shock:
            rank -= 1
        if day < 3:
            rank -= 1      # launch days: prices settle by the hour, not the day
        return ['low', 'medium', 'high'][max(0, min(2, rank))]

    def typical_path(self, item, category=None):
        """{day: median price relative to day 1} for an item (or its category)."""
        _, it, cat, ce = self._entry(item, category)
        e = it or ce
        return {int(k): v for k, v in (e or {}).get('typical_path', {}).items()}


def _round(x):
    if x == 0:
        return 0.0
    return round(x, max(0, 3 - int(math.floor(math.log10(abs(x))))))


def _oracle():
    if 'o' not in _default:
        _default['o'] = Oracle(load())
    return _default['o']


def forecast(item, day, current_price_div, recent_change_pct=None, **kw):
    """Module-level shortcut using forecast-model.json next to this file. See Oracle.forecast."""
    return _oracle().forecast(item, day, current_price_div, recent_change_pct, **kw)


if __name__ == '__main__':
    import sys
    a = sys.argv[1:]
    if len(a) < 3:
        print('usage: python forecast.py "<item>" <league day> <price in div> [7-day change %]')
        raise SystemExit(1)
    r = forecast(a[0], float(a[1]), float(a[2]), float(a[3]) if len(a) > 3 else None)
    print(json.dumps(r, indent=1))
