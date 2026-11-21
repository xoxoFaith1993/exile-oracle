"""poe2 MCP server: Claude's window into the PoE 2 toolkit (prices, exchange history, Build Vault).

Speaks MCP (JSON-RPC 2.0, one JSON object per line) over stdin/stdout. Standard library only.
Read-only and documented sources only: poe.ninja economy API, GGG's public Currency Exchange API.
"""

import datetime
import json
import os
import sys
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from poe2kit import config, cost, db, gamedata, ggg_exchange, net, ninja, pob, vault  # noqa: E402

PROTOCOL_VERSION = '2025-06-18'


def _age(ts):
    if not ts:
        return 'never'
    mins = (db.now() - float(ts)) / 60
    return f'{mins:.0f} min ago' if mins < 120 else f'{mins / 60:.1f} h ago'


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
        bid, s = vault.add(con, a['pob_code'], a['label'], a.get('owner', 'me'), a.get('league'),
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
    """Export a build to the game's own Build Planner (.build file the game reads and watches)."""
    from poe2kit import buildplanner as bp
    if a.get('list'):
        return {'folder': bp.folder(), 'files': bp.files()}
    if a.get('remove'):
        return bp.remove(a['remove'])
    con = db.connect()
    try:
        doc, rep = bp.make(con, a.get('build_id'), a.get('pob_code'), a.get('notes'), a.get('name'),
                           a.get('include_gear', True) is not False)
    finally:
        con.close()
    out = {'report': rep, 'folder': bp.folder()}
    if a.get('write'):
        out['write'] = bp.write(doc, bool(a.get('confirm')))
        if out['write'].get('needs_ok'):
            out['ask_player'] = ("Ask the player first: this puts a file in their game's BuildPlanner folder. "
                                 'Then call again with write=true, confirm=true.')
    else:
        out['preview'] = doc
    return out


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
        return charimport.list_characters(con, fresh=bool(a.get('fresh')))
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
        return pob.compare(con, _ref(a, 'a_'), _ref(a, 'b_'))
    finally:
        con.close()


def t_read_rare(a):
    return gamedata.read_item(a['base'], [m for m in a['mods'].splitlines() if m.strip()] if isinstance(a['mods'], str)
                              else a['mods'])


S = lambda **p: {'type': 'object', 'properties': p}  # noqa: E731
STR, NUM, BOOL = {'type': 'string'}, {'type': 'number'}, {'type': 'boolean'}

TOOLS = [
    ('poe2_status', 'Toolkit status: current league, how much price/exchange history is stored, builds in vault.',
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
     'a_pob_code and b_build_id / b_pob_code.', S(a_build_id=NUM, a_pob_code=STR, b_build_id=NUM, b_pob_code=STR),
     t_compare),
    ('poe2_read_rare', 'Read a rare item: tier (T1 = best) and roll % of each mod, plus a quality summary. '
     'base = base type (e.g. "Vile Robe"), mods = one mod per line.', S(base=STR, mods=STR) | {'required': ['base', 'mods']},
     t_read_rare),
    ('poe2_build_planner',
     "Put a build into Path of Exile 2's in-game Build Planner (GGG's documented .build file; the game shows the "
     'passive path, skills + supports to cut and gear-slot hints, and reloads the file by itself when it changes). '
     'Give build_id (vault) or pob_code. notes (optional object) adds hover text in game: {"description": str, '
     '"passives": {node name: text}, "skills": {gem name: text}, "slots": {"Helmet"|"Ring 1"|...: text}}; text may '
     'use the game markup e.g. "<green>{take before maps}". Without write it returns a preview; write=true saves '
     '"PoE2 Toolkit - <name>.build" (the first write ever needs confirm=true after asking the player). '
     "list=true shows the folder; remove=<file> deletes one of the toolkit's own files. Tip: several PoB trees "
     'titled "Level 30", "Level 60"... become a levelling route.',
     S(build_id=NUM, pob_code=STR, name=STR, notes={'type': 'object'}, include_gear=BOOL, write=BOOL, confirm=BOOL,
       list=BOOL, remove=STR), t_build_planner),
    ('poe2_trade_link', 'Make an official trade-site search link (by unique name and/or base type) to open in a browser.',
     S(name=STR, type=STR, league=STR), t_trade_link),
]
TOOL_MAP = {t[0]: t for t in TOOLS}


def send(obj):
    sys.stdout.buffer.write((json.dumps(obj, ensure_ascii=False) + '\n').encode('utf-8'))
    sys.stdout.buffer.flush()


def handle(msg):
    method, mid = msg.get('method'), msg.get('id')
    if mid is None:
        return
    if method == 'initialize':
        send({'jsonrpc': '2.0', 'id': mid, 'result': {
            'protocolVersion': (msg.get('params') or {}).get('protocolVersion') or PROTOCOL_VERSION,
            'capabilities': {'tools': {}},
            'serverInfo': {'name': 'poe2', 'version': config.VERSION},
            'instructions': (
                "PoE 2 Toolkit: the player's own Path of Exile 2 companion, meant to be used through you. Start with "
                'poe2_status (league, data freshness) and read their profile defaults (class / ascendancy) from it. '
                'Answer with real numbers from the tools, explain them plainly, and put the matching view on their '
                'dashboard with poe2_show (charts, tables, build cost, upgrades, compares, character pages) while you '
                'explain. Their characters: poe2_my_characters / poe2_import_character (only when asked; reuses an '
                'import for 15 min). Goal they usually care about: reaching the top 1% (poe2_top1). '
                'Rules: read-only toward the game; data from poe.ninja economy, GGG public exchange history, their '
                'Build Vault, their game log. Never call poe.ninja builds/profile APIs or the trade API; use '
                'poe2_trade_link for trade searches. Roll-dependent uniques are priced at the cheapest roll and rares '
                'at an estimated craft cost: say so.')}})
    elif method == 'tools/list':
        send({'jsonrpc': '2.0', 'id': mid, 'result': {'tools': [
            {'name': n, 'description': d, 'inputSchema': s} for n, d, s, _ in TOOLS]}})
    elif method == 'tools/call':
        p = msg.get('params') or {}
        tool = TOOL_MAP.get(p.get('name'))
        if not tool:
            send({'jsonrpc': '2.0', 'id': mid, 'error': {'code': -32602, 'message': 'Unknown tool'}})
            return
        try:
            text, err = json.dumps(tool[3](p.get('arguments') or {}), indent=1, ensure_ascii=False, default=str), False
        except net.NetError as e:
            text, err = str(e), True
        except Exception as e:
            text, err = f'{type(e).__name__}: {e}', True
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
