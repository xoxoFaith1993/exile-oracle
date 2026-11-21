"""Price one item the author copied in game (Ctrl+C), for the overlay.

  1. itemtext.parse() reads the game's item text.
  2. poe.ninja (already in the database) prices currency, gems, fragments, runes and uniques at once.
  3. Rares and uniques whose price depends on rolls get a live trade-site search (trade.py), only when the
     "live trade prices" setting is on. That is one search per copied item; GGG's rate limits are obeyed.
  4. Rares also get our craft-cost floor (crafting.estimate_rare).
Returns one dict the overlay page draws (dashboard/overlay.html)."""

import time

from . import config, cost, itemtext, money, ninja

TRADE_KINDS = ('RARE', 'UNIQUE', 'MAGIC')


def _spark(con, league, item_key, category, days=7):
    rows = con.execute('SELECT ts, value FROM price WHERE league=? AND item_key=? AND category=? AND ts>=? ORDER BY ts',
                       (league, item_key, category, time.time() - days * 86400)).fetchall()
    vals = [r['value'] for r in rows]
    if len(vals) > 40:   # thin to ~40 points
        step = len(vals) / 40
        vals = [vals[int(i * step)] for i in range(40)] + [vals[-1]]
    ch = round((vals[-1] / vals[0] - 1) * 100, 1) if len(vals) > 1 and vals[0] else None
    return vals, ch


def ninja_price(con, league, it):
    """poe.ninja's newest price for this item, or None."""
    idx = cost._latest_index(con, league)
    name = it.get('ninja_name') or it.get('name') or it.get('base')
    cands = idx.get((name or '').lower()) or []
    if it['rarity'] == 'UNIQUE':
        cands = [c for c in cands if c['category'].startswith('Unique')]
        best, _ = cost._pick_unique(cands, it.get('base') or '', it.get('corrupted', False))
    else:
        best = max(cands, key=lambda c: (c.get('volume') or 0, c.get('listings') or 0)) if cands else None
    if not best:
        return None
    vals, ch = _spark(con, league, best['item_key'], best['category'])
    out = {'div': best['value'], 'category': best['category'], 'listings': best.get('listings'),
           'volume': best.get('volume'), 'spark': vals, 'change_pct': ch, 'icon': best.get('icon')}
    if it['rarity'] == 'UNIQUE':
        n = ninja.roll_dependent(con).get(best['name'])
        if n:
            out['roll_dependent'] = n
    return out


def check(con, text, league=None, progress=None, filters=None):
    """filters: the player's edited search rows from the overlay (Search button); forces a trade search."""
    league = league or ninja.current_league(con)
    it = itemtext.parse(text)
    rt = money.rates(con, league)
    res = {'item': itemtext.summary(it), 'league': league, 'ex_per_div': rt.get('ex_per_div'), 'notes': []}
    from . import trade as _t
    try:
        res['icons'] = {'ex': _t.currency_icon('exalted'), 'div': _t.currency_icon('divine')}
    except Exception:
        res['icons'] = {}
    if not it.get('rarity'):
        res['error'] = 'That clipboard text is not an item.'
        return res
    n = ninja_price(con, league, it)
    if n:
        res['ninja'] = n
        res['headline'] = {'div': n['div'], 'qty': it.get('stack') or 1, 'label': 'poe.ninja price'}
    from . import trade
    f = filters or trade.default_filters(it)
    res['filters'] = f
    res['url'] = trade.search_url(league, trade.build_query(it, league, f))
    # every item the trade site can search (rares, uniques, magic, white bases, gems, waystones) is searched as soon
    # as it's copied (the author, 2026-11-20); stackable currency keeps its poe.ninja price
    wants_trade = f is not None
    if it['rarity'] == 'RARE' and it.get('base') and not it.get('unidentified') and not it.get('waystone_tier')             and it.get('cls') not in ('Waystones', 'Tablet', 'Relics', 'Charms', 'Jewels'):
        try:
            from . import crafting
            e = crafting.estimate_rare(con, it['base'], [m['text'] for m in it['explicits']], it.get('ilvl'), league)
            if e and (e.get('est_div') or 0) >= 0.05:   # near-zero means our crafting data didn't really cover it
                res['estimate'] = {'est_div': e['est_div'], 'kind': e.get('kind'), 'note': e.get('note')}
        except Exception as ex:   # bases our crafting data doesn't know
            res['notes'].append(f'No craft estimate: {ex}')
    if wants_trade:
        if not config.settings().get('live_trade', config.is_dev_copy()):
            res['trade'] = {'state': 'off', 'note': 'Live trade prices are off. Switch them on in the dashboard '
                                                    '(Status → Overlay) or use Open on trade.'}
        else:
            res['trade'] = {'state': 'pending'}
            if progress:
                progress(dict(res))
            idx = cost._latest_index(con, league)

            def value_of(name):
                c = [x for x in idx.get(name.lower(), []) if not x['category'].startswith('Unique')]
                return c[0]['value'] if c else None
            res['trade'] = trade.price(it, league, rt, value_of, f)
            t = res['trade']
            if t.get('state') == 'done' and t.get('low_div') is not None and (not res.get('headline') or it['rarity'] == 'GEM'):
                if (t.get('total') or 0) < 20:   # a handful of listings at made-up prices isn't a market
                    res['headline'] = {'div': t['low_div'], 'qty': 1,
                                       'label': f"only {t.get('total')} listed: lowest price (thin market)"}
                    res['notes'].append(f"Only {t.get('total')} listed: these prices are mostly wishful; it probably "
                                        "won't sell for more than the lowest.")
                else:
                    res['headline'] = {'div': t['median_div'] if len(t['prices']) >= 3 else t['low_div'], 'qty': 1,
                                       'label': f"trade site, {'middle of ' + str(len(t['prices'])) + ' cheapest' if len(t['prices']) >= 3 else 'lowest listing'}"}
    t = res.get('trade') or {}
    res['item']['icon'] = (n or {}).get('icon') or t.get('item_icon')
    if not res['item']['icon']:   # nothing from poe.ninja or the trade site: the game's own picture
        try:
            from . import art
            res['item']['art'] = art.for_item(it.get('name'), it.get('base'), it.get('rarity'))
        except Exception:
            pass
    if res.get('estimate') and t.get('state') == 'done' and t.get('prices'):
        # the market answers it; crafting one is usually far dearer than buying, so keep it as a side note
        e = res.pop('estimate')
        mid = t.get('median_div') or t.get('low_div') or 0
        res['notes'].append(f"Crafting one like it: about {e['est_div']:.1f} div (estimate), "
                            + ('cheaper than buying.' if e['est_div'] < mid else 'more than buying one.'))
    if not res.get('headline') and res.get('estimate'):
        res['headline'] = {'div': res['estimate']['est_div'], 'qty': 1, 'label': 'craft cost estimate (no market price)'}
    return res
