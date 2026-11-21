"""Value every strategy in strategies.py with the per-phase exchange prices (prices_by_phase.json) and write
research/farming/farming-returns.json.

Method (also written into the JSON's 'method'):
  net_lg   = sum(per_hour x price) - sum(inputs_per_hour x price)   for each league whose prices cover >= 80% of
             the basket (by value at that league's own week-2-3 prices or the nearest phase available)
  low  = 0.45 x (min_lg  net + fixed outputs at their LOW value  + raw-div LOW  - fixed cost HIGH)
  mid  = 0.70 x (median  net + fixed outputs at their MID value  + raw-div MID  - fixed cost MID)
  high = 1.00 x (max_lg  net + fixed outputs at their HIGH value + jackpots + raw-div HIGH - fixed cost LOW)
  0.45 / 0.70 / 1.00 = a normal player's pace against the source's pace (creators are fast and lucky).
  Phases before a strategy's 'earliest' are null.
Usage (repo root): python research/farming/scripts/build.py"""
import fnmatch, json, os, statistics, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from strategies import META, NERFS, STRATEGIES  # noqa: E402

PHASES = ['d0-2', 'week1', 'wk2-3', 'wk4-8', 'late']
PHASE_LABEL = {'d0-2': 'day 0-2', 'week1': 'week 1 (days 3-9)', 'wk2-3': 'weeks 2-3 (days 10-24)',
               'wk4-8': 'weeks 4-8 (days 25-59)', 'late': 'late (day 60+)'}
EFF = {'low': 0.45, 'mid': 0.70, 'high': 1.0}
P = json.load(open(os.path.join(HERE, 'prices_by_phase.json'), encoding='utf-8'))['phases']
LEAGUES = list(P)


def price(lg, ph, item):
    tbl = P[lg].get(ph, {})
    if '*' in item:
        xs = [v[0] for n, v in tbl.items() if fnmatch.fnmatch(n, item)]
        return statistics.median(xs) if xs else None
    v = tbl.get(item)
    return v[0] if v else None


def ref_price(lg, item):
    for ph in ['wk2-3', 'week1', 'wk4-8', 'late', 'd0-2']:
        p = price(lg, ph, item)
        if p:
            return p
    for other in LEAGUES:
        p = price(other, 'wk2-3', item)
        if p:
            return p
    return 0


def basket(s, lg, ph):
    """(net div/h at source pace, coverage, unpriced items) for one league and phase."""
    outs = dict(s.get('per_hour', {}))
    outs.update(s.get('basket', {}))
    tot_ref = sum(c * ref_price(lg, i) for i, c in outs.items())
    got = got_ref = 0.0
    missing = []
    for i, c in outs.items():
        p = price(lg, ph, i)
        if p is None:
            missing.append(i)
            continue
        got += c * p
        got_ref += c * ref_price(lg, i)
    cost = 0.0
    for i, c in s.get('inputs_per_hour', {}).items():
        p = price(lg, ph, i)
        if p is None:
            # an input that isn't on that league's exchange: use the nearest known price
            p = ref_price(lg, i)
        cost += c * p
    cov = got_ref / tot_ref if tot_ref else 1.0
    return got - cost, got, cost, cov, missing


def fixed_vals(d):
    lo = sum(c * v[0] for c, v in d.values())
    hi = sum(c * v[1] for c, v in d.values())
    return lo, (lo + hi) / 2, hi


def value(s):
    res, by_lg = {}, {}
    f_lo, f_mid, f_hi = fixed_vals(s.get('fixed', {}))
    j_lo, j_mid, j_hi = fixed_vals(s.get('jackpot', {}))
    raw = s.get('raw_div_per_hour', [0, 0])
    c_early, c_late = s.get('fixed_cost_div', [0, 0])
    has_basket = bool(s.get('per_hour') or s.get('basket'))
    start = PHASES.index(s['earliest'])
    for k, ph in enumerate(PHASES):
        if k < start:
            res[ph] = None
            continue
        # fixed costs (tablets, sagas, waystones) = [price when the source recorded it, late Forbidden Rites price].
        # Early phases: the recorded price +-25%; week 4+: anywhere between recorded and late.
        if ph in ('d0-2', 'week1', 'wk2-3'):
            c_lo, c_hi = c_early * 0.8, c_early * 1.25
        else:
            c_lo, c_hi = c_early, c_late
        nets = {}
        for lg in s.get('leagues', LEAGUES):
            net, gross, cost, cov, miss = basket(s, lg, ph)
            if has_basket and cov < 0.8:
                continue
            nets[lg] = net
            by_lg.setdefault(lg, {})[ph] = {'net_div_h_source_pace': round(net, 2), 'gross': round(gross, 2),
                                            'exchange_inputs': round(cost, 2), 'coverage': round(cov, 2),
                                            'unpriced': miss}
        if has_basket and not nets:
            res[ph] = None
            continue
        vals = list(nets.values()) or [0.0]
        lo = EFF['low'] * (min(vals) + f_lo + raw[0] - c_hi)
        mid = EFF['mid'] * (statistics.median(vals) + f_mid + (raw[0] + raw[1]) / 2 - (c_lo + c_hi) / 2)
        hi = EFF['high'] * (max(vals) + f_hi + j_hi + raw[1] - c_lo)
        res[ph] = {'low': round(lo, 1), 'mid': round(mid, 1), 'high': round(hi, 1),
                   'source_pace_median': round(statistics.median(vals) + f_mid + (raw[0] + raw[1]) / 2 - (c_lo + c_hi) / 2, 1),
                   'leagues_priced': [lg.split()[0] for lg in nets] if has_basket else []}
    return res, by_lg


def label_of(s):
    return {'session': 'community claim (counts from one recorded session) valued with GGG exchange data',
            'model': 'drop-table model (community samples) valued with GGG exchange data',
            'claim': 'community claim ranges (no counts), discounted for pace',
            'estimate': 'estimate (no measured source)'}[s['kind']]


def mech_key(s):
    t = (s['mechanic'] + ' ' + s['name']).lower()
    for key in ['temple', 'Sacred Bloom', 'boss', 'Ritual', 'Expedition', 'Delirium', 'Breach', 'Abyss', 'Sekhemas',
                'Ultimatum', 'Essences', 'Strongboxes', 'Rogue exiles', 'Base mapping']:
        if key.lower() in t:
            return key
    return None


def main():
    out = []
    for s in STRATEGIES:
        dph, by_lg = value(s)
        mk = mech_key(s)
        meta = list(META.get(mk, []))
        nerfs = list(NERFS.get(mk, []))
        if mk == 'Sacred Bloom':
            nerfs = NERFS['Ritual']
        if mk == 'boss' and 'Kulemak' in s['name']:
            meta = META['Abyss'][1:] + meta
        outputs = []
        for i, c in s.get('per_hour', {}).items():
            outputs.append({'item': i, 'per_map_or_hour': f'{c:g} per hour', 'per_map': round(c / s['maps_per_hour'], 3) if s.get('maps_per_hour') else None,
                            'per_run': round(c / s['runs_per_hour'], 3) if s.get('runs_per_hour') else None,
                            'source': s['source']['url'], 'label': 'estimate' if s['kind'] == 'estimate' else 'community claim',
                            'priced_by': 'GGG Currency Exchange'})
        for i, c in s.get('basket', {}).items():
            outputs.append({'item': i, 'per_map_or_hour': f'{c:g} per hour', 'source': s['source']['url'], 'label': 'estimate',
                            'priced_by': 'GGG Currency Exchange (median of matching names)'})
        for grp, lab in (('fixed', 'community claim'), ('jackpot', 'community claim (single lucky drop, high scenario only)')):
            for i, (c, (lo, hi)) in s.get(grp, {}).items():
                outputs.append({'item': i, 'per_map_or_hour': f'{c:g} per hour', 'source': s['source']['url'], 'label': lab,
                                'priced_by': f'not on the exchange: {lo}-{hi} div (farmofexile: when recorded / late Forbidden Rites)'})
        if s.get('raw_div_per_hour'):
            r = s['raw_div_per_hour']
            outputs.append({'item': 'mixed currency (Divine-equivalent)', 'per_map_or_hour': f'{r[0]}-{r[1]} div per hour',
                            'source': s['source']['url'], 'label': 'community claim' if s['kind'] == 'claim' else 'estimate',
                            'priced_by': 'as claimed; flat across phases'})
        out.append({
            'name': s['name'], 'mechanic': s['mechanic'], 'kind': s['kind'], 'number_label': label_of(s),
            'source_session': s['source'],
            'pace': {k: s[k] for k in ('maps_per_hour', 'runs_per_hour') if s.get(k)},
            'outputs': outputs,
            'inputs_per_hour': [{'item': i, 'count': c, 'priced_by': 'GGG Currency Exchange'} for i, c in s.get('inputs_per_hour', {}).items()],
            'investment': s['investment'] + (f" Fixed costs: {s['fixed_cost_div'][0]}-{s['fixed_cost_div'][1]} div/h ({s.get('fixed_note', '')})".rstrip(' ()') if any(s.get('fixed_cost_div', [0, 0])) else ''),
            'requirements': s['requirements'] | {'label': 'estimate (rules of thumb from guides and creator Path of Building snapshots)'},
            'earliest_phase': s['earliest'],
            'leagues_used': s.get('leagues', LEAGUES), 'leagues_note': s.get('leagues_note'),
            'div_per_hour': dph,
            'div_per_hour_label': 'estimate: community drop counts x GGG exchange prices (data-backed) x pace factor; net of inputs',
            'div_per_hour_by_league': by_lg,
            'unpriced_upside': s.get('unpriced_upside'),
            'community_claims': s.get('claims', []),
            'meta_history': meta,
            'nerfs': nerfs,
            'confidence': s['confidence'],
            'caveat': s.get('caveat'),
        })
    best = {}
    for ph in PHASES:
        rows = [(x['div_per_hour'][ph]['mid'], x['name'], x['div_per_hour'][ph]) for x in out if x['div_per_hour'][ph]]
        rows.sort(reverse=True)
        best[ph] = [{'name': n, 'low': v['low'], 'mid': v['mid'], 'high': v['high']} for _, n, v in rows[:6]]
    doc = {
        'made': time.strftime('%Y-%m-%d'),
        'about': 'Exile Oracle farming returns: what each endgame strategy drops, what that is worth in Divines per hour '
                 'in each league phase (priced with GGG Currency Exchange history of Fate of the Vaal 0.4, Runes of Aldur 0.5 '
                 'and Forbidden Rites 0.5.5), what it needs from the character, and how GGG treated it.',
        'phases': PHASE_LABEL,
        'method': {
            'prices': 'Median Divine price of each exchange item per phase and league: days 0-6 from the app DB ls_price '
                      '(hourly), days 10-70 from 54 sampled GGG hourly digests (2 per day: 10,14,21,28,35,42,49,56,70), '
                      'Forbidden Rites days 63-77 from the app DB ex_price. Volume-weighted pair ratios (poe2kit.leaguestart).',
            'fixed_costs': 'fixed_cost_div [recorded, late]: weeks 0-3 use recorded x0.8-1.25, week 4+ ranges recorded..late (tablet prices rose 2-10x in Forbidden Rites).',
            'value': 'net per league = outputs x price - exchange inputs x price, at the source\'s pace; leagues where under 80% '
                     'of the basket is priced are skipped. low = 0.45 x (worst league, low fixed values, high costs); '
                     'mid = 0.70 x (median league, mid values); high = 1.0 x (best league, high values, jackpots, low costs).',
            'efficiency': EFF,
            'labels': {'data-backed': 'prices (GGG exchange)', 'community claim': 'drop counts and div/h from creators, guides, sellers',
                       'estimate': 'pace factors, requirements, fixed costs, claim-only strategies'},
        },
        'best_by_phase': best,
        'strategies': out,
        'sources': SOURCES,
        'caveats': CAVEATS,
    }
    json.dump(doc, open(os.path.join(HERE, '..', 'farming-returns.json'), 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
    for ph in PHASES:
        print(ph, [(b['name'][:38], b['low'], b['mid'], b['high']) for b in best[ph]])


SOURCES = [
    {'id': 'GGG-EX', 'title': 'GGG public Currency Exchange history (hourly digests)', 'url': 'https://web.poecdn.com/api/currency-exchange/poe2/<unix hour>', 'kind': 'official data', 'note': '54 hours fetched 2026-11-21 at 2.5 s spacing; cache in scripts/cache'},
    {'id': 'DB', 'title': 'Exile Oracle DB (read-only): ls_price, ex_price, patch_notes', 'url': '<data folder>/data/poe2kit.db', 'kind': 'official data (derived)'},
    {'id': 'FOE', 'title': 'farmofexile.com PoE 2 strategy pages (creator sessions + boss models, methodology)', 'url': 'https://farmofexile.com/poe2', 'kind': 'community (creator videos parsed, then checked)'},
    {'id': 'FOE-M', 'title': 'farmofexile methodology', 'url': 'https://farmofexile.com/poe2/news/methodology', 'kind': 'community'},
    {'id': 'PN', 'title': 'Official patch notes, pathofexile.com forum (0.1.0 to 0.5.5h)', 'url': 'https://www.pathofexile.com/forum/view-forum/2212', 'kind': 'official'},
    {'id': 'PN-055', 'title': '0.5.5 patch notes', 'url': 'https://www.pathofexile.com/forum/view-thread/4000864', 'kind': 'official'},
    {'id': 'PN-055c', 'title': '0.5.5c patch notes', 'url': 'https://www.pathofexile.com/forum/view-thread/4006357', 'kind': 'official'},
    {'id': 'PN-055d', 'title': '0.5.5d patch notes', 'url': 'https://www.pathofexile.com/forum/view-thread/4008534', 'kind': 'official'},
    {'id': 'PN-050', 'title': '0.5.0 content update notes', 'url': 'https://www.pathofexile.com/forum/view-thread/3932540', 'kind': 'official'},
    {'id': 'PN-050bHF13', 'title': '0.5.0b hotfix 13 (temple)', 'url': 'https://www.pathofexile.com/forum/view-thread/3945385', 'kind': 'official'},
    {'id': 'PN-053', 'title': '0.5.3 patch notes', 'url': 'https://www.pathofexile.com/forum/view-thread/3968601', 'kind': 'official'},
    {'id': 'PN-054b', 'title': '0.5.4b patch notes', 'url': 'https://www.pathofexile.com/forum/view-thread/3980516', 'kind': 'official'},
    {'id': 'PN-040cHF13', 'title': '0.4.0c hotfix 13 (temple diminishing returns)', 'url': 'https://www.pathofexile.com/forum/view-thread/3901755', 'kind': 'official'},
    {'id': 'PN-040eHF2', 'title': '0.4.0e hotfix 2 (Amanamu\'s Void omens)', 'url': 'https://www.pathofexile.com/forum/view-thread/3912620', 'kind': 'official'},
    {'id': 'PN-020g', 'title': '0.2.0g loot changes', 'url': 'https://www.pathofexile.com/forum/view-thread/3774660', 'kind': 'official'},
    {'id': 'PN-011', 'title': '0.1.1 patch notes', 'url': 'https://www.pathofexile.com/forum/view-thread/3696353', 'kind': 'official'},
    {'id': 'PCGN-T', 'title': 'PCGamesN: temple diminishing-returns patch (Jan 3 2026)', 'url': 'https://www.pcgamesn.com/path-of-exile-2/patch-notes-temple-diminishing-returns', 'kind': 'news'},
    {'id': 'FB-T', 'title': 'finalboss.io: Vaal Temple nerf cuts huge drops', 'url': 'https://finalboss.io/poe-2s-vaal-temple-nerf-cuts-huge-drops', 'kind': 'news'},
    {'id': 'GP-T', 'title': 'Gamepressure: players complain about the death of the season (Dec 29 2025)', 'url': 'https://www.gamepressure.com/newsroom/poe-2-players-complain-about-the-death-of-the-new-season-all-beca/z78b67', 'kind': 'news'},
    {'id': 'MMO-T', 'title': 'Mein-MMO: GGG turns off the loot tap (temple hotfix, Jun 3 2026)', 'url': 'https://mein-mmo.de/en/developers-of-path-of-exile-2-have-overdone-it-now-turning-off-the-loot-tap-for-players,1570848/', 'kind': 'news'},
    {'id': 'PCGN-DIV', 'title': 'PCGamesN: Return of the Ancients makes Divines more common', 'url': 'https://www.pcgamesn.com/path-of-exile-2/return-of-the-ancients-divine-orbs', 'kind': 'news'},
    {'id': 'PB', 'title': 'poebuilds.cc farming index (YouTube farming video titles per league, with Path of Building snapshots)', 'url': 'https://www.poebuilds.cc/poe2/farming', 'kind': 'community (YouTube titles = creator claims)'},
    {'id': 'MAX-FLIP', 'title': 'Maxroll: flipping with the Currency Exchange', 'url': 'https://maxroll.gg/poe2/resources/flipping-with-the-currency-exchange', 'kind': 'guide'},
    {'id': 'MAX-TEMPLE', 'title': 'Maxroll: Vaal Temple / Atziri farming (0.5.5)', 'url': 'https://maxroll.gg/poe2/currency/vaal-temple-atziri-farming', 'kind': 'guide'},
    {'id': 'MAX-SEK', 'title': 'Maxroll: Trial of the Sekhemas', 'url': 'https://maxroll.gg/poe2/resources/trial-of-the-sekhemas', 'kind': 'guide'},
    {'id': 'TS-054', 'title': 'timesaver.gg 0.5.4 currency farming tier list [seller]', 'url': 'https://timesaver.gg/blog/poe2-0-5-4-currency-farming-tier-list', 'kind': 'seller'},
    {'id': 'TS-DPS', 'title': 'timesaver.gg T15 DPS requirement 0.5.5 [seller]', 'url': 'https://timesaver.gg/blog/poe2-t15-dps-requirement-0-5-5', 'kind': 'seller'},
    {'id': 'AOE-TOC', 'title': 'aoeah 0.5.5 Trial of Chaos guide [seller]', 'url': 'https://www.aoeah.com/news/4783--poe-2-055-trial-of-chaos-guide-best-mods-drops--farm-strategy', 'kind': 'seller'},
    {'id': 'AOE-ESS', 'title': 'aoeah 0.5 essence farming [seller]', 'url': 'https://www.aoeah.com/news/4627', 'kind': 'seller'},
    {'id': 'AOE-TEMPLE', 'title': 'aoeah 0.5 temple guide [seller]', 'url': 'https://www.aoeah.com/news/4609', 'kind': 'seller'},
    {'id': 'MTMMO', 'title': 'mtmmo 0.5.5 currency farm strats [seller]', 'url': 'https://www.mtmmo.com/news/2324--poe-2-055-forbidden-rites-best-currency-farm-strats-atlas--offatlas', 'kind': 'seller'},
    {'id': 'MMOEXP-TOC', 'title': 'mmoexp: 1000 divines in 50 Trial of Chaos runs [seller]', 'url': 'https://www.mmoexp.com/', 'kind': 'seller'},
    {'id': 'POEVAULT-R', 'title': 'poe-vault: is Ritual farming the best currency strategy', 'url': 'https://www.poe-vault.com/poe2/news/is-ritual-farming-the-best-currency-strategy-in-poe2-right-now', 'kind': 'news/guide'},
    {'id': 'DR', 'title': 'research/drop-rates.md/.json (repo)', 'url': 'research/drop-rates.md', 'kind': 'repo research'},
    {'id': 'MT', 'title': 'research/market/market-trends.md (repo)', 'url': 'research/market/market-trends.md', 'kind': 'repo research'},
]

CAVEATS = [
    'Drop counts come from one creator session or a community boss table per strategy. Creators are fast, well-geared and pick their best videos; the 0.45/0.70 pace factors are my estimate, not measured.',
    'Prices are real (GGG exchange), but they are past leagues\' prices: 1.0 (2026-12-11) will have its own patch changes. Re-run build.py with 1.0 prices from day 1 (the app syncs the same endpoint).',
    'Uniques (Prism of Belief, Morior Invictus, Rakiata\'s Flow, The Adorned, Ritual chase uniques) are not on the exchange: valued only at the two farmofexile price points, which are late-Forbidden-Rites values.',
    'Tablets, sagas and waystones are not on the exchange either: their cost is a fixed range per hour from the source pages; tablet prices rose 2-10x during Forbidden Rites.',
    'Market impact is ignored: a farm that floods one item (Kulemak bones, catalysts, Simulacrums) pushes that item down; 0.5.3 crashed Ancient Collarbone 88% in a week.',
    'Claim-only strategies (Trial of Chaos, Sekhemas, temple, strongboxes, rogue exiles, crafting, flipping) have no counts: their div/hour is a discounted claim range and is flat across phases.',
    'Day 0-2 values are high in Divines because Divines are cheap then, but almost nobody has the atlas for these strategies before day 3: most are null for day 0-2 on purpose.',
    'Forbidden Rites late prices (day 63-77) come from the app\'s own sync; Fate of the Vaal and Runes of Aldur late = day 70 only.',
    'Fate of the Vaal week 4-8 prices for omens, bones and Fates are 3-5x the other leagues (the temple Divine flood devalued Divines); they drive many "high" values.',
    'Community div/hour claims (YouTube titles, seller guides) run 2-5x above what the counts are worth at typical prices; see the md for the check.',
]

if __name__ == '__main__':
    main()
