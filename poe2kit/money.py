"""How prices are shown: 1 div or more stays in divines; under 1 div it's shown in exalts (with chaos).
Rates are live from poe.ninja (stored at every snapshot), so this follows the league's own ratio."""

import json

from . import db


def rates(con, league):
    r = json.loads(db.kv_get(con, f'rates:{league}', '{}') or '{}')
    return {'ex_per_div': r.get('exalted'), 'chaos_per_div': r.get('chaos')}


def _num(x):
    if x >= 100:
        return f'{x:,.0f}'
    if x >= 10:
        return f'{x:.0f}'
    return f'{x:.1f}'.rstrip('0').rstrip('.')


def fmt(div, rt):
    """div value -> short text, e.g. '2.5 div', '333 ex (≈ 7.2 chaos)', '<1 ex'."""
    if div is None:
        return None
    ex, ch = rt.get('ex_per_div'), rt.get('chaos_per_div')
    if div >= 1 or not ex:
        return f'{_num(div)} div'
    e = div * ex
    text = '<1 ex' if e < 1 else f'{_num(e)} ex'
    if ch:
        c = div * ch
        text += f' (≈ {_num(c)} chaos)' if c >= 0.1 else ''
    return text


def annotate(rows, rt, key='value_div', out='price'):
    """Add a display price to each dict in rows (in place) and return rows."""
    for r in rows:
        if isinstance(r, dict) and r.get(key) is not None:
            r[out] = fmt(r[key], rt)
    return rows
