"""poe2 MCP server: Claude's window into the PoE 2 toolkit (prices, exchange history, Build Vault).

Speaks MCP (JSON-RPC 2.0, one JSON object per line) over stdin/stdout. Standard library only.
Read-only and documented sources only: poe.ninja economy API, GGG's public Currency Exchange API.
"""

import datetime
import json
import os
import sys
import time
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from poe2kit import config, cost, db, gamedata, ggg_exchange, net, ninja, pob, vault  # noqa: E402

PROTOCOL_VERSION = '2025-06-18'


def _age(ts):
    if not ts:
        return 'never'
    mins = (db.now() - float(ts)) / 60
    return f'{mins:.0f} min ago' if mins < 120 else f'{mins / 60:.1f} h ago'


def _active(con):
    try:
        from poe2kit import chars
        c = chars.characters(con)
        return next(({k: x[k] for k in ('id', 'label', 'ascendancy', 'level', 'skill')}
                     for x in c['characters'] if x['active']), None)
    except Exception:
        return None


def t_status(a):
    con = db.connect()
    try:
        n_price = con.execute('SELECT COUNT(*) FROM price').fetchone()[0]
        n_items = con.execute('SELECT COUNT(DISTINCT item_key) FROM price').fetchone()[0]
        n_ex = con.execute('SELECT COUNT(*) FROM exchange_hour').fetchone()[0]
        cur = db.kv_get(con, 'ggg_exchange_cursor')
        return {
            'league': ninja.current_league(con),
            'leagues': [l['id'] for l in ninja.leagues(con)],
            'price_rows': n_price, 'items_tracked': n_items,
            'last_price_snapshot': _age(db.kv_get(con, 'last_snapshot')),
            'exchange_hours_rows': n_ex,
            'exchange_synced_to': datetime.datetime.fromtimestamp(int(cur)).isoformat() if cur else None,
            'builds_in_vault': con.execute('SELECT COUNT(*) FROM build').fetchone()[0],
            'active_character': _active(con),   # R17: the character every page follows (vault build id)
            'profile': {k: config.profile().get(k) for k in ('class', 'ascendancy', 'path', 'configured')},
            'experience': config.experience(),   # how much to explain (the player picks it in Settings)
            'db': config.DB_PATH,
        }
    finally:
        con.close()


def t_refresh(a):
    con = db.connect()
    try:
        out = {'prices': ninja.snapshot(con, a.get('league'))}
        if a.get('exchange', True):
            pages, stored, live = ggg_exchange.sync(con, max_pages=int(a.get('max_hours', 24)))
            out['ggg_exchange'] = {'hours_fetched': pages, 'markets_stored': stored, 'at_live_edge': live}
        return out
    finally:
        con.close()


def t_price(a):
    con = db.connect()
    try:
        rows = ninja.latest(con, a['query'], a.get('league'), int(a.get('limit', 15)))
        if not rows:
            return {'note': 'No match in stored prices. Run poe2_refresh first, or try a shorter name.'}
        from poe2kit import money
        rt = money.rates(con, a.get('league') or ninja.current_league(con))
        return [{'name': r['name'], 'base': r['base'], 'icon': r['icon'], 'category': r['category'], 'price': money.fmt(r['value'], rt),
                 'value_div': r['value'], 'volume': r['volume'], 'listings': r['listings'], 'as_of': _age(r['ts'])}
                for r in rows]
    finally:
        con.close()


def t_history(a):
    con = db.connect()
    try:
        league = a.get('league') or ninja.current_league(con)
        rows = con.execute('SELECT ts, name, value, unit, volume FROM price WHERE league=? AND name LIKE ? '
                           'ORDER BY ts', (league, f'%{a["query"]}%')).fetchall()
        series = {}
        for r in rows:
            series.setdefault(r['name'], []).append(
                [datetime.datetime.fromtimestamp(r['ts']).strftime('%m-%d %H:%M'), r['value']])
        return {'league': league, 'unit': rows[0]['unit'] if rows else None, 'series': series}
    finally:
        con.close()


def t_movers(a):
    """Biggest % changes between the latest snapshot and the one ~N hours before."""
    con = db.connect()
    try:
        league = a.get('league') or ninja.current_league(con)
        hours = float(a.get('hours', 24))
        latest_ts = con.execute('SELECT MAX(ts) FROM price WHERE league=?', (league,)).fetchone()[0]
        if not latest_ts:
            return {'note': 'No price history yet.'}
        old_ts = con.execute('SELECT MAX(ts) FROM price WHERE league=? AND ts<=?',
                             (league, latest_ts - hours * 3600)).fetchone()[0]
        if not old_ts:
            first = con.execute('SELECT MIN(ts) FROM price WHERE league=?', (league,)).fetchone()[0]
            return {'note': f'History only goes back {_age(first)}; need {hours:.0f} h. The monitor fills this in.'}
        q = ('SELECT n.name, n.category, n.value nv, o.value ov, n.unit FROM '
             '(SELECT item_key, name, category, value, unit FROM price WHERE league=? AND ts=?) n JOIN '
             '(SELECT item_key, value FROM price WHERE league=? AND ts=?) o USING(item_key) '
             'WHERE o.value > ? AND n.value > 0')
        rows = con.execute(q, (league, latest_ts, league, old_ts, float(a.get('min_value', 0.0001)))).fetchall()
        ch = sorted(({'name': r['name'], 'category': r['category'], 'now': r['nv'], 'before': r['ov'],
                      'change_pct': round((r['nv'] / r['ov'] - 1) * 100, 1), 'unit': r['unit']} for r in rows),
                    key=lambda x: x['change_pct'])
        n = int(a.get('limit', 10))
        return {'league': league, 'window_hours': hours, 'risers': ch[::-1][:n], 'fallers': ch[:n]}
    finally:
        con.close()


def t_vault_add(a):
    con = db.connect()
    try:
        bid, s = vault.add(con, a['pob_code'], a.get('label') or None, a.get('owner', 'me'), a.get('league'),
                           a.get('source_url'), a.get('notes'))
        return {'id': bid, 'class': s['class'], 'ascendancy': s['ascendancy'], 'level': s['level'],
                'main_skill': s['main_skill']}
    finally:
        con.close()


def t_vault_list(a):
    con = db.connect()
    try:
        vault.import_folder(con)
        return [dict(r) | {'added': datetime.datetime.fromtimestamp(r['added']).strftime('%Y-%m-%d')}
                for r in vault.listing(con, a.get('owner'), a.get('ascendancy'))]
    finally:
        con.close()


def t_vault_show(a):
    con = db.connect()
    try:
        b = vault.get(con, int(a['id']))
        if not b:
            return {'error': 'no such build'}
        if not a.get('include_code'):
            b.pop('pob_code', None)
        b.pop('stats_json', None)
        return b
    finally:
        con.close()


def t_build_planner(a):
    """Export a build to the game's own Build Planner (.build file the game reads and watches).
    With build_id the build keeps a saved plan (notes, edits, followed character) that every rewrite uses."""
    from poe2kit import buildplanner as bp, buildplan
    if a.get('list'):
        return {'folder': bp.folder(), 'files': bp.files()}
    if a.get('remove'):
        return bp.remove(a['remove'])
    con = db.connect()
    try:
        bid = a.get('build_id')
        if bid is None:   # a pasted PoB code: one-off export, nothing saved
            doc, rep = bp.make(con, None, a.get('pob_code'), a.get('notes'), a.get('name'),
                               a.get('include_gear', True) is not False)
            out = {'report': rep, 'folder': bp.folder()}
            if a.get('write'):
                out['write'] = bp.write(doc, bool(a.get('confirm')))
            else:
                out['preview'] = doc
        else:
            if a.get('check'):   # Path of Building before/after for the given edits; nothing saved
                return buildplan.check(con, bid, a.get('edits') or {})
            if a.get('forget'):
                db.kv_set(con, buildplan.KEY + str(int(bid)), '{}')
            follow = a.get('follow')
            buildplan.save(con, bid, notes=a.get('notes'), edits=a.get('edits'), name=a.get('name'),
                           follow=(follow or None) if follow != '' else '',
                           levelling_route=a.get('levelling_route') if 'levelling_route' in a else None)
            res = buildplan.export(con, bid, write=bool(a.get('write')), confirm=bool(a.get('confirm')))
            out = {'report': res['report'], 'plan': buildplan.get(con, bid), 'folder': bp.folder()}
            if a.get('write'):
                out['write'] = res['write']
            else:
                out['preview'] = res['doc']
        if (out.get('write') or {}).get('needs_ok'):
            out['ask_player'] = ("Ask the player first: this puts a file in their game's BuildPlanner folder. "
                                 'Then call again with write=true, confirm=true.')
        return out
    finally:
        con.close()


def t_levelling(a):
    """Review a levelling route with Path of Building before switching it on for the in-game plan."""
    from poe2kit import buildplan, route, stagecheck, vault
    import xml.etree.ElementTree as ET
    con = db.connect()
    try:
        bid = a.get('build_id')
        r = con.execute('SELECT label, pob_code FROM build WHERE id=?', (int(bid),)).fetchone() if bid is not None else None
        if not r:
            return {'error': 'give build_id (poe2_vault_list)'}
        xml, _ = buildplan.apply_edits(vault.decode(r['pob_code']), buildplan.get(con, bid).get('edits'))
    finally:
        con.close()
    mode = a.get('mode') or 'route'
    if mode == 'route':
        root = ET.fromstring(xml)
        tree = root.find('Tree')
        spec = tree.findall('Spec')[max(0, int(tree.get('activeSpec') or 1) - 1)]
        ver = spec.get('treeVersion') or '0_5'
        have = [int(x) for x in (spec.get('nodes') or '').split(',') if x]
        main, asc, _s = route.order(have, ver, root.find('Build').get('className'))
        nodes, _, _ = route._tree(ver)
        lv = route.levels(len(main))
        ws = route.weapon_set_nodes(main, lv, ver)
        upto = int(a.get('up_to_level') or 100)
        rows = [{'level': l, 'node': nodes.get(n, {}).get('n'), 'kind': nodes.get(n, {}).get('k'),
                 'stats': '; '.join(nodes.get(n, {}).get('s') or [])[:90], 'weapon_set': bool(n in ws)}
                for n, l in zip(main, lv) if l <= upto]
        return {'build': r['label'], 'passives': rows,
                'ascendancy': [{'level': l, 'node': nodes.get(n, {}).get('n')} for n, l in
                               zip(asc, route.asc_levels(len(asc)))],
                'how': 'Order = best value per point from the class start (a rule of thumb: check that life and '
                       'resistances come early enough). Levels = 1 point per level + 2 per point quest. If it looks '
                       'right (or after fixing it with poe2_build_planner edits), switch it on with '
                       'poe2_build_planner levelling_route=true.'}
    lvl = int(a.get('level') or 14)
    if mode == 'test':
        cat = stagecheck.catalogue()
        g = cat.get(str(a.get('skill', '')).lower())
        if not g:
            return {'error': f"unknown skill {a.get('skill')}"}
        sups = tuple(cat[x.lower()]['id'] for x in a.get('supports') or [] if x.lower() in cat)
        return stagecheck.check(xml, lvl, g['id'], sups)
    if mode == 'rank_supports':
        return stagecheck.rank(xml, lvl, a.get('skill'), a.get('supports') or [], kind='supports',
                               limit=int(a.get('limit') or 30))
    if mode == 'rank_skills':
        return {'level': lvl, 'ranked': stagecheck.rank(xml, lvl, None, a.get('supports') or [],
                                                        candidates=a.get('skills') or [], kind='skills')}
    if mode == 'gems':   # what can be cut by this level, with tags, to pick candidates from
        cat = stagecheck.catalogue()
        return {'level': lvl, 'skills': [{'name': g['name'], 'from': g['level'], 'tags': g['tags']} for g in cat.values()
                                         if not g['support'] and g['level'] and g['level'] <= lvl]}
    return {'error': 'mode: route | gems | test | rank_supports | rank_skills'}


def t_lab(a):
    """Build Lab (dashboard): roadmap, power curves and what-if cards the player sees while you explain in chat."""
    from poe2kit import buildplan, lab
    con = db.connect()
    from poe2kit import mapmods
    bid = a.get('build_id') or mapmods.active_build(con)   # R17: the active character unless told otherwise
    act = a.get('action') or 'cards'
    if act == 'roadmap':
        r = lab.roadmap(con, bid)
        return dict(r, route=f"{len(r['route'])} passives (first: {r['route'][:3]})", note='Drawn on the Build Lab tab.')
    if act == 'curves':
        if a.get('start'):
            lab.start_curves(bid)
        return lab.curves_state(con, bid)
    if act == 'suggest':
        if not a.get('title') or not a.get('change'):
            raise ValueError('suggest needs title and change ({"item": {"slot", "item_text"}} and/or {"edits": {...}})')
        c = lab.suggest(con, bid, a['title'], a['change'], a.get('why') or '', a.get('cost_div'))
        return {'card': c, 'note': 'Shown on the Build Lab tab with its before/after numbers.'}
    if act == 'retest':
        return lab.retest(con, bid, a['card_id'])
    if act == 'remove':
        return lab.remove_card(con, bid, a['card_id'])
    return {'build_id': bid, 'cards': lab.cards(con, bid)}


def t_campaign(a):
    """R16: the campaign rush guide, the rewards checklist and where the player is now (from the game log)."""
    from poe2kit import campaign
    con = db.connect()
    g = campaign.guide(con)
    part = (a.get('part') or 'summary').lower()
    if a.get('tick'):
        campaign.set_done(con, str(a['tick']), bool(a.get('on', True)))
        g = campaign.guide(con)
    if part == 'summary':
        return {'progress': g['progress'], 'zone': g['zone'], 'missing': [r for r in g['rewards'] if not r['done']],
                'trials': g['trials'], 'breakpoints': g['breakpoints'], 'version': g['meta']}
    return {k: g[k] for k in ('acts', 'rewards', 'progress', 'zone', 'trials', 'tips', 'mistakes', 'times', 'watch',
                              'breakpoints', 'rush_vs_full', 'meta') if k in g}


def t_atlas(a):
    """R15: atlas strategies, a strategy's setup (drawn on the Atlas page), rolling costs, tablets, earnings per hour."""
    from poe2kit import atlasplan
    con = db.connect()
    act = (a.get('action') or 'strategies').lower()
    if act == 'setup':
        r = atlasplan.setup(a.get('strategy') or '')
        r.pop('allocated', None)
        return r
    if act == 'rolling':
        return atlasplan.rolling(con)
    if act == 'tablets':
        return atlasplan.tablets()
    if act == 'roi':
        return atlasplan.roi(con, a.get('strategy'), maps_per_hour=a.get('maps_per_hour'),
                             extra_div=a.get('extra_div') or 0)
    r = atlasplan.strategies(con)
    for s in r['strategies']:
        s.pop('key_nodes', None)
    return r


def t_oracle(a):
    """The Oracle's market advice from three league launches: phase, what to do now, item outlook."""
    from poe2kit import oracle, prophecy, mapmods
    con = db.connect()
    mode = (a.get('mode') or 'advice').lower()
    if mode == 'omen':
        return {'omen': prophecy.omen(con), 'countdowns': prophecy.countdowns(con)}
    if mode == 'timeline':
        return {'timeline': prophecy.timeline(con), 'countdowns': prophecy.countdowns(con)}
    if mode == 'forecast':
        if not a.get('item'):
            return {'error': 'item is needed for a forecast'}
        r = prophecy.forecast_item(con, a['item'], day=a.get('day'))
        r.pop('past', None)
        return r
    if mode == 'patch':
        return prophecy.patch_prophecy(a['text'], con) if a.get('text') else (prophecy.latest_patch_prophecy(con) or {'error': 'no patch notes stored'})
    if mode == 'farm':
        return prophecy.farm_oracle(con, a.get('build_id') or mapmods.active_build(con), a.get('day'))
    if mode == 'uniques':
        return prophecy.unique_history(a.get('item'))
    if mode == 'spreads':
        from poe2kit import spreads
        return spreads.find(con)
    r = oracle.advice(con, day=a.get('day'))
    if a.get('item'):
        want = a['item'].lower()
        r['items'] = [x for x in r.get('items') or [] if want in x['item'].lower()]
        r['hold_note'] = {x['item']: oracle.hold_note(x['item']) for x in r['items']}
    else:
        r['items'] = (r.get('items') or [])[:int(a.get('top') or 15)]
    r.pop('about', None)
    return r


def t_doctor(a):
    """Check every part of the toolkit; returns findings + the troubleshooting guide written for Claude."""
    from poe2kit import doctor
    out = doctor.run()
    if not a.get('with_guide', True):
        out.pop('guide', None)
    return out


def t_from_overlay(a):
    """Items the player sent from the price-check overlay with its Ask the Oracle button (newest first)."""
    from poe2kit import overlaysrv
    items = overlaysrv.inbox(a.get('limit') or 3, bool(a.get('clear')))
    return {'items': items,
            'how_to_help': 'Each entry has the exact in-game item text (item_text), the poe.ninja price, the cheapest '
                           'trade listings and what was searched. For "is it an upgrade?" use poe2_whatif with '
                           'item_text and the slot; for rares, poe2_craft_* tools can tell what it would cost to make; '
                           'prices are in divines (ex_per_div converts).' if items else
                           'Nothing sent yet: in game, price check an item and press Ask the Oracle in the popup.'}


def t_trade_link(a):
    """Build an official trade-site search URL for the user to open (no trade API calls are made)."""
    league = a.get('league') or ninja.current_league()
    q = {'query': {'status': {'option': 'online'}}, 'sort': {'price': 'asc'}}
    if a.get('name'):
        q['query']['name'] = a['name']
    if a.get('type'):
        q['query']['type'] = a['type']
    url = (f'https://www.pathofexile.com/trade2/search/poe2/{urllib.parse.quote(league)}?q='
           + urllib.parse.quote(json.dumps(q, separators=(',', ':'))))
    return {'url': url, 'note': 'Open this in your browser; the toolkit itself never queries the trade site.'}


def t_build_cost(a):
    con = db.connect()
    try:
        if not a.get('pob_code') and a.get('build_id') is None:
            return {'error': 'give pob_code (a Path of Building code) or build_id (from poe2_vault_list)'}
        r = cost.build_cost(con, a.get('pob_code'), a.get('build_id'), a.get('league'), bool(a.get('include_swap')))
        if not a.get('full'):
            r.pop('all_priced', None)
        return r
    finally:
        con.close()


def _ref(a, prefix=''):
    if a.get(prefix + 'pob_code'):
        return {'pob_code': a[prefix + 'pob_code']}
    if a.get(prefix + 'build_id') is not None:
        return {'build_id': int(a[prefix + 'build_id'])}
    raise ValueError(f'give {prefix}build_id or {prefix}pob_code')


def t_pob_stats(a):
    con = db.connect()
    try:
        mg = a.get('main_group')
        return pob.stats_for(con, **_ref(a), main_group=int(mg) if mg is not None else None)
    finally:
        con.close()


def t_show(a):
    """Put a view on the dashboard (http://127.0.0.1:47830). The server computes it, so chat stays short."""
    import time as _t
    view = a.get('view')
    builders = {'build_cost': t_build_cost, 'upgrades': t_upgrades, 'stats': t_pob_stats, 'compare': t_compare,
                'whatif': t_whatif, 'craft': t_craft}
    if view in builders:
        data = builders[view](dict(a, full=True))
        if isinstance(data, dict) and data.get('error'):
            return data
    elif view == 'character':
        from poe2kit import character
        con = db.connect()
        try:
            data = character.character(con, int(a['build_id']))
        finally:
            con.close()
    elif view == 'price_history':
        h = t_history({'query': a['query']})
        series = h.get('series', {})
        name = next((n for n in series if n.lower() == a['query'].lower()), next(iter(series), None))
        if not name:
            return {'error': f"no stored history for {a['query']!r}"}
        view, data = 'chart', {'title': f'{name}: price history', 'subtitle': h.get('league'), 'name': name,
                               'unit': h.get('unit') or 'div', 'points': series[name]}
    elif view == 'craftlab':
        # load a crafting setup into the Craft tab: base, ilvl, targets [{fid,max_tier}|{text,side}], optional state
        from poe2kit import craftsim
        data = a.get('data') or {}
        if isinstance(data, str):
            data = json.loads(data)
        if a.get('build_id') is not None and a.get('slot'):
            from poe2kit import character
            con = db.connect()
            try:
                c = character.character(con, int(a['build_id']))
            finally:
                con.close()
            it = next((g for g in c['gear'] + c['jewels'] if g['slot'].lower() == a['slot'].lower()), None)
            if not it:
                return {'error': 'no item in that slot'}
            ilvl = int(''.join(ch for ch in (it.get('item_level') or '') if ch.isdigit()) or 82)
            mods = craftsim.import_item(it['base'], ilvl, [m['t'] for m in it['explicits']])
            data = {'base': it['base'], 'ilvl': ilvl,
                    'targets': [{'fid': m['fid'], 'max_tier': m['tier']} if m['fid'] is not None else
                                {'text': m['text'], 'side': m['side']} for m in mods]}
    elif view in ('chart', 'table', 'note'):
        data = a.get('data') or {}
        if isinstance(data, str):
            data = json.loads(data)
    else:
        return {'error': 'view must be character, craft, craftlab, build_cost, upgrades, stats, compare, whatif, price_history, chart, table or note'}
    con = db.connect()
    try:
        db.kv_set(con, 'show', json.dumps({'ts': _t.time(), 'type': view, 'caption': a.get('caption', ''), 'data': data},
                                          default=str))
    finally:
        con.close()
    return {'shown': view, 'dashboard': 'http://127.0.0.1:47830', 'note': 'The dashboard switches to it within 3 s.'}


def t_craft(a):
    from poe2kit import crafting
    con = db.connect()
    try:
        if a.get('item_text'):
            return crafting.from_item_text(con, a['item_text'], a.get('league'))
        if a.get('build_id') is not None and a.get('slot'):
            return crafting.from_build(con, int(a['build_id']), a['slot'], a.get('league'))
        if a.get('base') and a.get('mods'):
            mods = [m for m in a['mods'].splitlines() if m.strip()] if isinstance(a['mods'], str) else a['mods']
            return crafting.analyze(con, a['base'], mods, a.get('item_level'), a.get('league'))
        return {'error': 'give item_text (Ctrl+C / PoB text), or build_id + slot, or base + mods'}
    finally:
        con.close()


def t_patch_notes(a):
    from poe2kit import patchnotes
    con = db.connect()
    try:
        if a.get('text'):
            r = patchnotes.analyze(con, a['text'], a.get('title') or 'pasted notes')
        else:
            patchnotes.sync(con, 30)
            lst = patchnotes.listing(con)
            if not lst:
                return {'error': 'no patch notes found'}
            gid = a.get('gid') or lst[0]['gid']
            r = patchnotes.get(con, gid)
            r['others'] = lst[:10]
        r.pop('all', None)
        return r
    finally:
        con.close()


def t_league_plan(a):
    from poe2kit import leagueplan
    con = db.connect()
    try:
        if a.get('list_classes'):
            return leagueplan.classes()
        prof = config.profile()
        asc = [x.strip() for x in (a.get('ascendancies') or ','.join(prof.get('path') or [prof.get('ascendancy') or ''])).split(',') if x.strip()]
        return leagueplan.plan(con, a.get('class_name') or prof.get('class') or 'Witch', asc, a.get('target_build'),
                               float(a.get('budget_div') or 0.05))
    finally:
        con.close()


def t_farm(a):
    from poe2kit import farm
    con = db.connect()
    try:
        r = farm.board(con, a.get('league'))
        if not a.get('full'):
            for m in r['mechanics']:
                m['top_items'] = m['top_items'][:3]
        return r
    finally:
        con.close()


def t_top1(a):
    from poe2kit import topcheck
    con = db.connect()
    try:
        act = a.get('action') or 'check'
        if act == 'status':
            return topcheck.status(con)
        if act == 'js':
            return {'list_js': topcheck.LIST_JS, 'char_js': topcheck.CHAR_JS,
                    'how': 'On request only. In the browser pane open poe.ninja/poe2/builds/<league>?class=<Ascendancy>'
                           '&sort=level|dps|ehp, run list_js, pass its output as data with action=save_list (3 sorts). '
                           'For wealth open ~10 of the top-1% paths from the level list (poe.ninja.../character/<path>), '
                           'run char_js, save each with action=save_char. One page at a time.'}
        if act == 'save_list':
            return topcheck.save_list(con, a['data'])
        if act == 'save_char':
            return topcheck.save_char(con, a['data'], a.get('scope'))
        bid = a.get('build_id')
        if not bid:
            r = con.execute("SELECT id FROM build WHERE owner='me' ORDER BY id DESC LIMIT 1").fetchone()
            bid = r['id']
        return topcheck.check(con, int(bid), a.get('league'), a.get('scope'))
    finally:
        con.close()


def t_league_start(a):
    from poe2kit import leaguestart
    con = db.connect()
    try:
        r = leaguestart.playbook(con)
        items = r.pop('items')
        if a.get('item'):
            q = a['item'].lower()
            r['item_history'] = {n: v for n, v in items.items() if q in n.lower()}
        return r
    finally:
        con.close()


def t_sessions(a):
    from poe2kit import clientlog
    con = db.connect()
    try:
        clientlog.sync(con)
        r = clientlog.sessions(con, limit=int(a.get('limit') or 5))
        if not a.get('full'):
            for x in r['sessions']:
                x['maps'] = x['maps'][-15:]
        return r
    finally:
        con.close()


def t_my_characters(a):
    from poe2kit import charimport
    con = db.connect()
    try:
        r = charimport.list_characters(con, fresh=bool(a.get('fresh')))
        from poe2kit import chars
        if isinstance(r, dict):   # R17: the vault characters and which one the dashboard is following
            r['vault_characters'] = chars.characters(con)
        return r
    finally:
        con.close()


def t_import_character(a):
    from poe2kit import charimport
    con = db.connect()
    try:
        return charimport.import_character(con, a['name'], fresh=bool(a.get('fresh')))
    finally:
        con.close()


def t_upgrades(a):
    from poe2kit import upgrades
    con = db.connect()
    try:
        mg = a.get('main_group')
        slots = [x.strip() for x in a['slots'].split(',')] if isinstance(a.get('slots'), str) else a.get('slots')
        return upgrades.find(con, **_ref(a), budget_div=a.get('budget_div'), slots=slots,
                             main_group=int(mg) if mg is not None else None, league=a.get('league'),
                             top=int(a.get('top', 5)))
    finally:
        con.close()


def t_whatif(a):
    con = db.connect()
    try:
        mg = a.get('main_group')
        return pob.whatif(con, **_ref(a), slot=a['slot'], item_text=a['item_text'],
                          main_group=int(mg) if mg is not None else None)
    finally:
        con.close()


def t_compare(a):
    con = db.connect()
    try:
        r = pob.compare(con, _ref(a, 'a_'), _ref(a, 'b_'))
        if a.get('show') and a.get('a_build_id') and a.get('b_build_id'):   # put it on the Compare page
            from poe2kit import compare
            compare.push(con, a['a_build_id'], a['b_build_id'], a.get('note'))
            r['shown'] = 'On the Compare page (radar, stat bars, max hits, the two trees overlaid, gear, skills).'
        return r
    finally:
        con.close()


def t_wishlist(a):
    from poe2kit import wishlist
    con = db.connect()
    try:
        act = a.get('action') or 'list'
        if act == 'add':
            r = wishlist.add(con, a.get('item'), a.get('target'), a.get('unit') or 'div', a.get('side') or 'buy',
                             a.get('note') or '')
            if not r.get('ok'):
                return r
        elif act == 'remove':
            r = wishlist.remove(con, a.get('item'))
        elif act.startswith('wanted'):
            from poe2kit import tradewatch
            if act == 'wanted_add':
                r = tradewatch.add(con, a.get('text'), a.get('name'), a.get('target'), a.get('unit') or 'div')
            elif act == 'wanted_check':
                return tradewatch.check(con, a.get('id'))
            elif act == 'wanted_remove':
                r = tradewatch.remove(con, a.get('id'))
            if act != 'wanted' and not r.get('ok'):
                return r
            return tradewatch.status(con)
        return wishlist.status(con)
    finally:
        con.close()


def t_read_rare(a):
    return gamedata.read_item(a['base'], [m for m in a['mods'].splitlines() if m.strip()] if isinstance(a['mods'], str)
                              else a['mods'])


S = lambda **p: {'type': 'object', 'properties': p}  # noqa: E731
STR, NUM, BOOL = {'type': 'string'}, {'type': 'number'}, {'type': 'boolean'}

TOOLS = [
    ('poe2_status', 'Toolkit status: current league, how much price/exchange history is stored, builds in vault, and the '
     'active character (the one the player picked in the top bar: answer for it unless they name another).',
     S(), t_status),
    ('poe2_refresh', 'Pull fresh prices from poe.ninja (cached, polite) and sync GGG hourly Currency Exchange history.',
     S(league=STR, exchange=BOOL, max_hours=NUM), t_refresh),
    ('poe2_price', 'Latest stored price for items/currency whose name contains query (poe.ninja data).',
     S(query=STR, league=STR, limit=NUM) | {'required': ['query']}, t_price),
    ('poe2_history', 'Stored price history for items matching query, for trend questions.',
     S(query=STR, league=STR) | {'required': ['query']}, t_history),
    ('poe2_movers', 'Biggest price risers and fallers over the last N hours (default 24) from stored history.',
     S(hours=NUM, league=STR, limit=NUM, min_value=NUM), t_movers),
    ('poe2_vault_add', 'Save a Path of Building (PoE 2) code to the Build Vault forever. owner="me" or the source.',
     S(pob_code=STR, label=STR, owner=STR, league=STR, source_url=STR, notes=STR) | {'required': ['pob_code', 'label']},
     t_vault_add),
    ('poe2_vault_list', 'List builds in the vault (also imports new vault/<league>/*.pob.txt files).',
     S(owner=STR, ascendancy=STR), t_vault_list),
    ('poe2_vault_show', 'Show one vault build: class, ascendancy, main skill, PoB stats, gear list.',
     S(id=NUM, include_code=BOOL) | {'required': ['id']}, t_vault_show),
    ('poe2_build_cost', 'Price a whole build: every unique (name + base), socketed rune/soul core, lineage support and '
     'skill gem from live poe.ninja prices; total, most expensive pieces, a cheap-to-endgame buy order. Rares come '
     'back with mods + trade links to check. Use for "how do I get this build / what does it cost".',
     S(pob_code=STR, build_id=NUM, league=STR, include_swap=BOOL, full=BOOL), t_build_cost),
    ('poe2_pob_stats', 'Run a build through headless Path of Building: real DPS, life/ES/mana/spirit, EHP, max hits, '
     'resistances, and DPS for every skill in the build. build_id from the vault or a pob_code; main_group picks '
     'which skill group counts as main (from the skills list).', S(build_id=NUM, pob_code=STR, main_group=NUM),
     t_pob_stats),
    ('poe2_show', 'Show a view on the toolkit dashboard (http://127.0.0.1:47830) while answering in chat. view = '
     'character (build_id: poe.ninja-style page: gear grid, tooltips, skills, stats, passive tree) | craft (same args as poe2_craft) | craftlab (build_id + slot, or data {base, ilvl, targets:[{fid,max_tier}|{text,side}], state}: loads the interactive Craft tab) | build_cost | upgrades | stats | whatif (build_id/pob_code + the same args as those tools) | compare '
     '(a_/b_ args) | price_history (query) | chart (data: {title, points: [[label, value]], unit}) | table '
     '(data: {title, columns, rows}) | note (data: {title, text}). caption = one line saying what it is.',
     S(view=STR, caption=STR, build_id=NUM, pob_code=STR, a_build_id=NUM, a_pob_code=STR, b_build_id=NUM,
       b_pob_code=STR, budget_div=NUM, slots=STR, slot=STR, item_text=STR, main_group=NUM, query=STR,
       data={'type': 'object'}) | {'required': ['view']}, t_show),
    ('poe2_patch_notes', "Patch notes vs the player's builds: every line that touches their gems, uniques, keystones, ascendancy "
     'with buff/nerf guesses, plus lines on their watch list (profile). Latest official post by default (Steam), '
     'a gid from the list, or pasted text (for forum-only notes).', S(gid=STR, text=STR, title=STR), t_patch_notes),
    ('poe2_league_plan', 'League start planner for any class and any chain of ascendancies (they can be changed any '
     'time, e.g. "Lich,Blood Mage"): campaign quest rewards per act, skill gems for the class ranked by unlock tier and '
     'match to target_build (a vault id), ascendancy nodes ranked by what your past builds took, and cheap leveling '
     'uniques from live prices. list_classes=true lists classes + ascendancies.',
     S(class_name=STR, ascendancies=STR, target_build=NUM, budget_div=NUM, list_classes=BOOL), t_league_plan),
    ('poe2_farm', 'Farm advisor: ranks league mechanics (breach, delirium, ritual, expedition, abyss, essences, soul '
     'cores, runes, idols, boss fragments...) by what their loot is worth and how much of it trades per day on '
     'poe.ninja, with 24 h / 7 d trends once history exists and the prices of matching tablets. A market view, not '
     'drops per hour.', S(league=STR, full=BOOL), t_farm),
    ('poe2_top1', "Top 1% check (goal: reach and keep the top 1%): the player's character vs the top 1% of their "
     'ascendancy on poe.ninja on level, DPS, effective HP and gear value, with the gap on each and what closes it. '
     'build_id = vault id (default: their newest). action: check (default) | status (how old the benchmarks are) | js '
     '(page scripts + how to refresh benchmarks, on request only) | save_list / save_char (data = script output).',
     S(build_id=NUM, league=STR, scope=STR, action=STR, data=STR), t_top1),
    ('poe2_league_start', 'League start playbook from the last PoE 2 launches (GGG Currency Exchange history, hour by '
     'hour, first 7 days): per mechanic the average realistic drop value on day 1..7 of each league, the items '
     'that crashed hardest by day 7 (sell on day 1) and the ones that held or rose (keep). item = a name to get its '
     'day-by-day prices per league. Exchange items only (no uniques).', S(item=STR), t_league_start),
    ('poe2_sessions', "The player's play sessions from the game's own log (Client.txt): time in maps / hideout / town / "
     'campaign / trials, maps run, average map time, maps per hour, deaths, level-ups, campaign time per act, and every '
     'map run (portals back in = same run). Local file only, no GGG API.', S(limit=NUM, full=BOOL), t_sessions),
    ('poe2_craft', 'Crafting Lab: how to make a rare item. Reads every mod (tier, prefix/suffix, normal / essence-only / '
     'desecrated), the base + item level needed, rough odds per Exalt tier with side omens, and a step-by-step route '
     'with live currency costs. Input: item_text (Ctrl+C or PoB text), or build_id + slot (e.g. a top build saved in '
     'the vault), or base + mods. Odds assume equal weights (real weights are not in the game files): treat as a floor.',
     S(item_text=STR, build_id=NUM, slot=STR, base=STR, mods=STR, item_level=NUM, league=STR), t_craft),
    ('poe2_my_characters', "List the player's PoE 2 characters (all leagues incl. Standard) through Path of Building's own "
     'GGG login, in the background. Cached 15 min; only call when needed.', S(fresh=BOOL), t_my_characters),
    ('poe2_import_character', "Import one of the player's characters live (gear, tree, jewels, skills) through headless Path "
     'of Building and save it to the vault; returns build_id for poe2_show/character, cost, upgrades. Reuses an import '
     'from the last 15 min unless fresh=true. On request only, never in loops.',
     S(name=STR, fresh=BOOL) | {'required': ['name']}, t_import_character),
    ('poe2_upgrades','Upgrade finder: tries every affordable unique (live poe.ninja prices, optional budget_div) in '
     'each gear slot through Path of Building, ranks by DPS and defence gained (and per divine), and leaves out '
     "items you can't equip or that break spirit reservations, saying why. slots = comma list to limit it.",
     S(build_id=NUM, pob_code=STR, budget_div=NUM, slots=STR, main_group=NUM, league=STR, top=NUM), t_upgrades),
    ('poe2_whatif','What if I swap this item? Puts item_text (in-game Ctrl+C text) into slot (Helmet, Body Armour, '
     'Gloves, Boots, Amulet, Ring 1, Ring 2, Belt, Weapon 1, Weapon 2) and shows every stat that changes.',
     S(build_id=NUM, pob_code=STR, slot=STR, item_text=STR, main_group=NUM) | {'required': ['slot', 'item_text']},
     t_whatif),
    ('poe2_compare', 'Compare two builds in Path of Building side by side (b vs a, % differences). Use a_build_id / '
     'a_pob_code and b_build_id / b_pob_code (a = the player). show=true (vault ids only) puts it on the '
     'Compare page of the dashboard: a radar, stat bars, biggest hit per damage type, the two passive trees overlaid, gear slot by slot '
     'and skills; note = your short verdict shown on top. Use show=true whenever the player asks to compare builds.',
     S(a_build_id=NUM, a_pob_code=STR, b_build_id=NUM, b_pob_code=STR, show=BOOL, note=STR), t_compare),
    ('poe2_read_rare', 'Read a rare item: tier (T1 = best) and roll % of each mod, plus a quality summary. '
     'base = base type (e.g. "Vile Robe"), mods = one mod per line.', S(base=STR, mods=STR) | {'required': ['base', 'mods']},
     t_read_rare),
    ('poe2_build_planner',
     "Put a build into Path of Exile 2's in-game Build Planner (GGG's documented .build file; the game shows the "
     'passive path, skills + supports to cut and gear-slot hints, and reloads the file by itself when it changes). '
     'Give build_id (vault) or pob_code. With build_id the build keeps a SAVED PLAN that every rewrite uses: '
     'notes {"description": str, "passives": {node name: text}, "skills": {gem name: text}, "slots": {"Helmet"|'
     '"Ring 1"|...: text}} (text may use game markup like "<green>{take before maps}"); edits {"add_passives": '
     '[node names or game ids], "remove_passives": [...], "swap_gems": {"old gem": "new gem"}}; follow = the '
     "character name whose level-ups (from the game log) rewrite the file with 'next' notes ('' stops following). "
     'Before saving edits, call with check=true + edits: Path of Building shows DPS/life/res before vs after and warns '
     "about unconnected nodes; tell the player, then save. write=true saves 'Exile Oracle - <name>.build' (the "
     'first write ever needs confirm=true after asking the player); without write you get a preview. forget=true '
     "clears the saved plan. list=true shows the folder; remove=<file> deletes one of the toolkit's own files. "
     'Several PoB trees titled "Level 30", "Level 60", "Endgame" become a levelling route. levelling_route=true '
     'switches on the automatic passive order (levels, weapon-set notes) ONLY after you reviewed it with '
     'poe2_levelling; without it the plan shows the full endgame path.',
     S(build_id=NUM, pob_code=STR, name=STR, notes={'type': 'object'}, edits={'type': 'object'}, follow=STR,
       levelling_route=BOOL,
       check=BOOL, forget=BOOL, include_gear=BOOL, write=BOOL, confirm=BOOL, list=BOOL, remove=STR), t_build_planner),
    ('poe2_levelling',
     'Review a levelling route for a vault build BEFORE it goes into the in-game Build Planner (the automatic order '
     'is a rule of thumb; plans stay a plain endgame path until you switch the route on). mode="route": the passive '
     'order with the level each comes at (check life/res come early enough); mode="gems": skills cuttable by '
     '`level`; mode="test": one skill + supports at `level` in Path of Building (DPS, life, mana; no gear); '
     'mode="rank_supports": every cuttable support for `skill` ranked by DPS gain (slow: ~2 min); '
     'mode="rank_skills": compare `skills` at `level`. Then save levelling skills with poe2_build_planner edits '
     '{"levelling_skills": [...]} and switch the route on with levelling_route=true.',
     S(build_id=NUM, mode=STR, level=NUM, up_to_level=NUM, skill=STR, supports={'type': 'array'},
       skills={'type': 'array'}, limit=NUM), t_levelling),
    ('poe2_lab',
     'The Build Lab tab on the dashboard: the player watches it while you work in chat. action="suggest" puts a '
     'what-if card on it, measured by Path of Building right away: title, why, cost_div (optional) and change = '
     '{"item": {"slot": "Amulet", "item_text": "<in-game Ctrl+C or PoB item text>"}} and/or {"edits": '
     '{"add_passives": [...], "remove_passives": [...], "swap_gems": {"old": "new"}}}. The card shows DPS, EHP, life, '
     'ES, max hits and res before/after. action="cards" lists them, "retest"/"remove" take card_id. '
     'action="roadmap" = the levelling route the Lab draws; action="curves" (start=true runs ~1 min in the background) '
     '= DPS/EHP by level. Use it whenever you compare options: the player sees the numbers, not just your words.',
     S(build_id=NUM, action=STR, title=STR, why=STR, cost_div=NUM, change={'type': 'object'}, card_id=NUM, start=BOOL),
     t_lab),
    ('poe2_campaign',
     'Campaign rush: the researched fastest route act by act, every permanent reward (passive points, spirit, '
     'resistances, life) with a checklist the player ticks, the ascendancy trials, flask / boots / life breakpoints, '
     'common mistakes, and the zone the player is in now (from the game log). part="summary" (default: progress, '
     'missing rewards, current zone) or "full". tick=<reward key> (on=false to untick) only when the player says '
     'they took it. Researched for 0.5: Acts 5-6 arrive in 1.0; say so.',
     S(part=STR, tick=STR, on=BOOL), t_campaign),
    ('poe2_atlas',
     'Endgame (the Atlas, Maps and Tablets pages): action="strategies" (default): 11 farming strategies with div/hour now and next league phase '
     '(our farming research at live prices), atlas points each setup takes, tablets and waystone setup, plus when to '
     'switch. action="setup" + strategy: its key atlas nodes and the connecting path (the player can draw it with '
     'Show on tree on the Atlas page). action="rolling": what each waystone rolling method costs today. '
     'action="tablets": tablet types, their mods, pairing. action="roi" + strategy (+ maps_per_hour, extra_div; '
     'defaults: the own pace of the player from the game log, no extra cost): div/hour low / mid / high, already net of the '
     'usual inputs. It is a rough guide from one recorded session per strategy: give the range and say so. For map mod '
     'danger use the Maps page or the overlay (Ctrl+D on a waystone).',
     S(action=STR, strategy=STR, extra_div=NUM, maps_per_hour=NUM), t_atlas),
    ('poe2_oracle',
     'The Oracle: market timing from the last three league launches (GGG exchange history, prices in Divines). '
     'mode="advice" (default): league day and phase, what to do now and next, and for 42 key items where they usually '
     'go in the next 7 days (sell now / hold / steady) next to the live price. mode="omen": the strongest call today + '
     'countdowns (1.0 launch, plan windows). mode="timeline": what usually happens when, day 0 to 70+. '
     'mode="forecast" + item: median and 10-90% range at +1/+3/+7/+14 days from a model tested on six launches (its '
     'range held 79% of the time; direction calls right ~60%). mode="patch" (+ text = pasted notes, else the newest '
     'stored notes): which items a patch should move and how much, from 276 measured patches. mode="farm" '
     '(+ build_id): div/hour per strategy now and next phase, checked against the PoB damage and EHP of the build. '
     'mode="spreads": Currency Exchange gaps (the same item cheaper vs one of Ex / Div / Chaos than vs another, held '
     '3+ hours with real volume; past trades, check the live exchange, gold fee not counted). '
     'mode="uniques" (+ item): chase unique prices by league day in past leagues. item = one item; day = pretend '
     'another league day (e.g. plan day 0 of 1.0). Say it is history, not a promise, and that patches move prices.',
     S(mode=STR, day=NUM, item=STR, top=NUM, text=STR, build_id=NUM), t_oracle),
    ('poe2_doctor',
     'Something in the toolkit is broken or acting odd (overlay, prices, dashboard, Build Planner, Path of Building, '
     "Claude connection)? Call this FIRST: it checks every part (read-only) and returns what's wrong, which sections "
     'of the troubleshooting guide apply, and the guide itself (written for you: checks, safe restarts, fixes, '
     'rules). Then fix it with the player step by step.',
     S(with_guide=BOOL), t_doctor),
    ('poe2_from_overlay',
     "Items the player sent from the in-game price-check overlay (its Ask the Oracle button, called Ask Claude before 0.4.0), newest first: the exact "
     'item text, poe.ninja price, cheapest trade listings, what was searched, craft estimate. Call this when the '
     'player says they sent / just checked an item. limit (default 3), clear=true empties the list.',
     S(limit=NUM, clear=BOOL), t_from_overlay),
    ('poe2_wishlist',
     "The player's chase-item wishlist (its own Wishlist page under Market): items they want to buy (side=buy: tell me when it drops to the "
     'target) or sell (side=sell: when it rises to it) at a target price. action=list (default) shows each wish with '
     'its live price, the last 7 days, how far from the target, next week\'s likely range from the price forecast (heading = likely / '
     'maybe) and calls from the newest patch notes. action=add needs item (the poe.ninja name); target + unit '
     '(div, ex or chaos) are optional: without a target the item is just tracked (no target alerts). action=remove needs item. '
     'Wanted items (saved trade-site searches, e.g. a staff with specific stats): action=wanted lists them with the '
     'last check; wanted_add needs text (a trade-site link or the in-game item text), optional name / target / unit; '
     'wanted_check (id) runs ONE trade search now, only when the player asks (cheapest listings, new ones, re-priced, '
     'gone = sold or taken down, the pinned listing); wanted_remove (id). Never check in a loop. The dashboard alerts on a hit, a forecast heading there, or a patch call, '
     'and a hit becomes the Home omen. Add only what the player asked for.',
     S(action={'type': 'string', 'enum': ['list', 'add', 'remove', 'wanted', 'wanted_add', 'wanted_check', 'wanted_remove']},
       item=STR, target=NUM, text=STR, name=STR, id=STR,
       unit={'type': 'string', 'enum': ['div', 'ex', 'chaos']}, side={'type': 'string', 'enum': ['buy', 'sell']}, note=STR),
     t_wishlist),
    ('poe2_trade_link', 'Make an official trade-site search link (by unique name and/or base type) to open in a browser.',
     S(name=STR, type=STR, league=STR), t_trade_link),
]
TOOL_MAP = {t[0]: t for t in TOOLS}


def send(obj):
    sys.stdout.buffer.write((json.dumps(obj, ensure_ascii=False) + '\n').encode('utf-8'))
    sys.stdout.buffer.flush()


# ---------------- the Oracle feed (Build Lab): each tool call, in words, for the dashboard ----------------

# Sent to every AI app that connects (Claude, ChatGPT / Codex, Gemini CLI, ...): how to use Exile Oracle well.
INSTRUCTIONS = (
    "Exile Oracle: the player's own Path of Exile 2 companion, used through you (any MCP app). In the app you are "
    '"the Oracle". Start with poe2_status: league, data freshness, profile (class / ascendancy), the ACTIVE character '
    '(answer for it unless they name another) and experience (how much to explain).\n'
    'How to work:\n'
    '- Real numbers from the tools, explained plainly at the depth poe2_status.experience asks for (new players: terms '
    'explained, one clear pick; veterans: brief and numeric). You help, they decide: offer next steps, never present '
    'a plan as the only way to play.\n'
    '- Say where each number comes from and how sure it is. Label theory as theory: levelling routes are a rule of '
    'thumb until reviewed; the campaign route was researched for 0.5; forecasts are ranges from past launches, not '
    'promises; brand-new items have no history. Never invent a number a tool did not give.\n'
    '- If a tool fails, tell the player in one plain line and work around it (saved data, another tool, or ask them). '
    'Never stop at an error. If problems repeat, call poe2_doctor and follow its guide.\n'
    '- Show your work: poe2_show puts views on the dashboard; every build option you compare goes on the Build Lab '
    'as a what-if card (poe2_lab, measured by Path of Building). The player watches while you talk.\n'
    'How the tools fit together (pick what the question needs; this is a map, not a script):\n'
    '- A build: poe2_vault_list / poe2_vault_show -> poe2_pob_stats (real DPS / EHP / max hits) -> poe2_lab cards for '
    'options -> poe2_upgrades (DPS per divine) -> poe2_top1 (gap to the top 1%) -> poe2_compare. Their characters: '
    'poe2_my_characters / poe2_import_character, only when asked.\n'
    '- A league start or a fresh start: poe2_league_plan (class + ascendancy chain: rewards, gems, ascendancy nodes, '
    'cheap levelling uniques) -> poe2_levelling (review the route) -> poe2_build_planner (into the game\'s planner) '
    '-> poe2_campaign (rush route, rewards checklist) -> poe2_league_start (sell / hold in days 1-7) -> poe2_farm and '
    'poe2_atlas (first maps: strategy, setup, earnings per hour as a range).\n'
    '- The market: poe2_oracle (omen, timeline, forecast, patch, farm, uniques, spreads), poe2_price / poe2_history / '
    'poe2_movers, poe2_wishlist (chase items; wanted items = saved trade searches, checked only when the player '
    'asks). Crafting: poe2_read_rare -> poe2_craft. Patch notes vs their builds: poe2_patch_notes.\n'
    'Rules: read-only toward the game. Data: the poe.ninja economy API, GGG public Currency Exchange history, the '
    "player's Build Vault and game log. Never call poe.ninja builds / profile APIs. GGG's trade site only when the "
    'player presses something (the overlay, or a wanted-item check they ask for, one search at a time); otherwise '
    'give a poe2_trade_link. Never send a report or suggestion yourself. Roll-dependent uniques are priced at the '
    'cheapest roll and rares at an estimated craft cost: say so.\n'
)

FEED_WORDS = {
    'poe2_price': 'looked up prices', 'poe2_history': 'read price history', 'poe2_movers': 'checked the market movers',
    'poe2_vault_add': 'saved a build to the vault', 'poe2_vault_list': 'listed your builds',
    'poe2_vault_show': 'opened a build', 'poe2_build_cost': 'priced a build',
    'poe2_pob_stats': 'ran Path of Building', 'poe2_show': 'put a view on your dashboard',
    'poe2_patch_notes': 'read the patch notes', 'poe2_league_plan': 'planned a league start',
    'poe2_farm': 'ranked what to farm', 'poe2_league_start': 'read the league-start playbook',
    'poe2_sessions': 'read your play sessions', 'poe2_craft': 'worked on a craft',
    'poe2_my_characters': 'listed your characters', 'poe2_import_character': 'imported a character',
    'poe2_upgrades': 'tried every unique in every slot', 'poe2_whatif': 'tested an item swap',
    'poe2_compare': 'compared two builds (Compare page)', 'poe2_read_rare': 'read a rare item',
    'poe2_build_planner': 'worked on the in-game Build Planner', 'poe2_levelling': 'checked the levelling route',
    'poe2_lab': 'used the Build Lab', 'poe2_oracle': 'read the market history (the Oracle)', 'poe2_campaign': 'read the campaign guide', 'poe2_atlas': 'planned the atlas', 'poe2_doctor': 'checked the app for problems',
    'poe2_wishlist': 'checked your wishlist', 'poe2_from_overlay': 'read the items you sent', 'poe2_trade_link': 'made a trade-site link',
    'poe2_status': 'checked the app status', 'poe2_refresh': 'refreshed prices', 'poe2_top1': 'ran the Top 1% check',
}
CLIENT = {'name': None}


def _feed(tool, args, ok, ms, err=None):
    """Remember the call for the Build Lab's Oracle feed (last 60, local only; no item text)."""
    try:
        bits = []
        for k in ('action', 'mode', 'build_id', 'query', 'item', 'name', 'slot', 'level', 'skill', 'title', 'budget_div'):
            v = args.get(k)
            if v not in (None, ''):
                v = str(v)[:60]
                bits.append({'build_id': f'build #{v}', 'budget_div': f'budget {v} div', 'level': f'level {v}',
                             'slot': f'slot {v}', 'skill': v, 'action': v, 'mode': v}.get(k, v))
        con = db.connect()
        try:
            feed = json.loads(db.kv_get(con, 'oracle:feed') or '[]')
            feed.append({'ts': time.time(), 'tool': tool, 'what': FEED_WORDS.get(tool, tool), 'detail': ' · '.join(bits),
                         'ok': ok, 'ms': ms, 'error': (err or '')[:160] or None, 'client': CLIENT['name']})
            db.kv_set(con, 'oracle:feed', json.dumps(feed[-60:]))
        finally:
            con.close()
    except Exception:
        pass


REQUIRED = {   # inputs a tool can't work without (also sent to the AI app in each tool's schema)
    'poe2_price': ['query'], 'poe2_history': ['query'], 'poe2_vault_add': ['pob_code'], 'poe2_vault_show': ['id'],
    'poe2_import_character': ['name'], 'poe2_read_rare': ['base', 'mods'],
}
for _t in TOOLS:   # the required inputs go into each schema, so the AI app knows them up front
    if REQUIRED.get(_t[0]):
        _t[2]['required'] = REQUIRED[_t[0]]


def _check_args(name, args, schema):
    """Wrong or missing inputs -> one plain message for the AI app (and the cleaned arguments)."""
    props = (schema or {}).get('properties') or {}
    out, problems = {}, []
    for k, v in args.items():
        t = (props.get(k) or {}).get('type')
        if v is None or t is None:
            out[k] = v
            continue
        if t == 'string' and not isinstance(v, str):
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                v = str(v)
            else:
                problems.append(f'{k} should be text')
                continue
        elif t in ('number', 'integer'):
            try:
                v = float(v) if t == 'number' else int(float(v))
            except (TypeError, ValueError):
                problems.append(f'{k} should be a number')
                continue
        elif t == 'boolean' and not isinstance(v, bool):
            if str(v).lower() in ('true', '1', 'yes'):
                v = True
            elif str(v).lower() in ('false', '0', 'no'):
                v = False
            else:
                problems.append(f'{k} should be true or false')
                continue
        elif t == 'object' and not isinstance(v, dict):
            try:
                v = json.loads(v) if isinstance(v, str) else None
            except ValueError:
                v = None
            if not isinstance(v, dict):
                problems.append(f'{k} should be an object ({{...}})')
                continue
        out[k] = v
    missing = [k for k in REQUIRED.get(name, []) if out.get(k) in (None, '')]
    if missing:
        problems.append('missing ' + ', '.join(missing))
    return out, problems


def _dispatch(name, args):
    """Run one tool. Returns (text for the AI app, is_error)."""
    tool = TOOL_MAP[name]
    args, problems = _check_args(name, args if isinstance(args, dict) else {}, tool[2])
    if problems:
        return (f"{name} needs different input: {'; '.join(problems)}. See the tool's description for what each "
                'input means, then call it again.'), True
    try:
        return json.dumps(tool[3](args), indent=1, ensure_ascii=False, default=str), False
    except Exception as e:   # plain words + a hint for the assistant, never a bare Python error (poe2kit/safety.py)
        from poe2kit import safety
        return safety.for_ai(e), True


def handle(msg):
    method, mid = msg.get('method'), msg.get('id')
    if mid is None:
        return
    if method == 'initialize':
        CLIENT['name'] = (((msg.get('params') or {}).get('clientInfo') or {}).get('name')) or None   # Claude, Codex, Gemini...
        send({'jsonrpc': '2.0', 'id': mid, 'result': {
            'protocolVersion': (msg.get('params') or {}).get('protocolVersion') or PROTOCOL_VERSION,
            'capabilities': {'tools': {}},
            'serverInfo': {'name': 'poe2', 'version': config.VERSION},
            'instructions': INSTRUCTIONS}})
    elif method == 'tools/list':
        send({'jsonrpc': '2.0', 'id': mid, 'result': {'tools': [
            {'name': n, 'description': d, 'inputSchema': s} for n, d, s, _ in TOOLS]}})
    elif method == 'tools/call':
        p = msg.get('params') or {}
        tool = TOOL_MAP.get(p.get('name'))
        if not tool:
            send({'jsonrpc': '2.0', 'id': mid, 'error': {'code': -32602, 'message': 'Unknown tool'}})
            return
        t0 = time.time()
        text, err = _dispatch(p.get('name'), p.get('arguments') or {})
        _feed(p.get('name'), p.get('arguments') or {}, not err, int((time.time() - t0) * 1000), text if err else None)
        send({'jsonrpc': '2.0', 'id': mid, 'result': {'content': [{'type': 'text', 'text': text}], 'isError': err}})
    elif method == 'ping':
        send({'jsonrpc': '2.0', 'id': mid, 'result': {}})
    else:
        send({'jsonrpc': '2.0', 'id': mid, 'error': {'code': -32601, 'message': f'Method not found: {method}'}})


def main():
    for line in sys.stdin.buffer:
        line = line.strip()
        if line:
            try:
                handle(json.loads(line))
            except ValueError:
                pass


if __name__ == '__main__':
    main()
