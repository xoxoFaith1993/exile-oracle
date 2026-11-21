"""Group-level sell windows for the first 72 h + day 3 / day 6, and a campaign-loot price table.
Prices in Divine (normalised to each item's own L12-24 median), plus absolute Ex/Div for campaign items.
Usage: python -I groups.py series.json groups.json"""
import json, re, sqlite3, statistics as st, sys
from collections import defaultdict

SER, OUT = sys.argv[1], sys.argv[2]
S = {lg: {int(k): v for k, v in d.items()} for lg, d in json.load(open(SER, encoding='utf-8')).items()}
LGS = ['Fate of the Vaal', 'Runes of Aldur', 'Forbidden Rites']
SHORT = {'Fate of the Vaal': 'FotV', 'Runes of Aldur': 'RoA', 'Forbidden Rites': 'FR'}
OFF = {'Fate of the Vaal': 4, 'Runes of Aldur': 3, 'Forbidden Rites': 3}
con = sqlite3.connect('file:<data folder>/data/poe2kit.db?mode=ro', uri=True)
names = {k: v.get('name') for k, v in json.load(open('<data folder>/data/repoe/base_items.min.json', encoding='utf-8')).items() if v.get('name')}
lineage = {n for n, c in con.execute("SELECT DISTINCT name, category FROM price WHERE source='ninja-exchange' AND category='LineageSupportGems'")}
SPECIAL_ESS = ('Hysteria', 'Horror', 'Delirium', 'Insanity', 'the Abyss', 'the Breach')
TOP_OMENS = ('Light', 'Whittling', 'Sinistral Annulment', 'Dextral Annulment', 'Sinistral Erasure', 'Dextral Erasure',
             'Sinistral Crystallisation', 'Dextral Crystallisation', 'Abyssal Echoes')
BASIC = ['Orb of Transmutation', 'Orb of Augmentation', 'Regal Orb', 'Orb of Alchemy', 'Vaal Orb', 'Orb of Chance',
         "Artificer's Orb", "Glassblower's Bauble", "Gemcutter's Prism", "Armourer's Scrap", "Blacksmith's Whetstone",
         "Lesser Jeweller's Orb", "Arcanist's Etcher", 'Chance Shard']
GREATER = ['Greater Orb of Transmutation', 'Greater Orb of Augmentation', 'Greater Regal Orb', 'Greater Exalted Orb',
           'Greater Chaos Orb', "Greater Jeweller's Orb"]
PERFECT = ['Perfect Orb of Transmutation', 'Perfect Orb of Augmentation', 'Perfect Regal Orb', 'Perfect Exalted Orb',
           'Perfect Chaos Orb', "Perfect Jeweller's Orb"]
SINK = ['Orb of Annulment', 'Fracturing Orb', "Hinekora's Lock", 'Mirror of Kalandra', "Architect's Orb",
        'Crystallised Corruption', "Vaal Armourer's Infuser", "Vaal Blacksmith's Infuser", 'Vaal Catalysing Infuser',
        'Core Destabiliser', 'Vaal Cultivation Orb', 'Orb of Extraction', 'Ancient Infuser']


def group(n):
    if n in ('Exalted Orb', 'Divine Orb', 'Chaos Orb'):
        return None
    if n in BASIC: return 'Basic currency (campaign drops)'
    if n in GREATER: return 'Greater-tier orbs'
    if n in PERFECT: return 'Perfect-tier orbs'
    if n in SINK: return 'Sink / rare currency'
    if n in lineage: return 'Lineage support gems'
    if n.startswith('Omen of'):
        return 'Omens: top crafting' if any(n == f'Omen of {t}' for t in TOP_OMENS) else 'Omens: other'
    if 'Essence' in n:
        if any(s in n for s in SPECIAL_ESS): return 'Essences: special (Hysteria, Horror, Delirium, Insanity, Abyss, Breach)'
        if n.startswith('Lesser'): return 'Essences: Lesser'
        if n.startswith('Greater'): return 'Essences: Greater'
        if n.startswith('Perfect'): return 'Essences: Perfect'
        if n.startswith('Essence of'): return 'Essences: normal'
    if re.search(r"'s Rune of|Rune of ", n): return 'Runes: named / special'
    if n.endswith(' Rune'):
        for t in ('Lesser', 'Greater', 'Perfect'):
            if n.startswith(t): return f'Runes: {t}'
        return 'Runes: normal'
    if n.startswith('Soul Core of'): return 'Soul cores: common'
    if 'Soul Core' in n: return 'Soul cores: named'
    m = re.match(r'Uncut (Skill|Support|Spirit) Gem \(Level (\d+)\)', n)
    if m:
        k, lv = m.group(1), int(m.group(2))
        if k == 'Support': return 'Uncut support gems'
        if k == 'Skill': return 'Uncut skill gems L20' if lv == 20 else ('Uncut skill gems L16-19' if lv >= 16 else 'Uncut skill gems L1-15')
        return 'Uncut spirit gems L14-20' if lv >= 14 else 'Uncut spirit gems L4-13'
    if 'Liquid' in n:
        if n.startswith('Diluted'): return 'Liquid emotions: Diluted'
        if n.startswith('Ancient'): return 'Liquid emotions: Ancient'
        if n.startswith('Concentrated') or n.startswith('Potent'): return 'Liquid emotions: Concentrated / Potent'
        return 'Liquid emotions: plain'
    if n.endswith('Catalyst'): return 'Catalysts: Refined' if n.startswith('Refined') else 'Catalysts: normal'
    if n in ('Breach Splinter', 'Simulacrum Splinter', 'Petition Splinter', 'Runic Splinter') or n.endswith('Shard'):
        return 'Splinters & shards'
    if 'Crisis Fragment' in n or n in ("Kulemak's Invitation", 'Victorious Fate', 'Deadly Fate', 'Cowardly Fate',
                                        'Simulacrum', 'Breachstone', 'Origin Spark', 'Origin Core', 'Origin Cradle',
                                        "Raven's Reflection", 'Call of the Shadows', 'Head of the King',
                                        'An Audience with the King', 'Breachlord Sac', "Breachlord's Amalgam",
                                        "Breachlord's Rift", 'Cryptic Key') or 'Reliquary Key' in n:
        return 'Fragments & boss keys'
    if re.match(r'(Gnawed|Preserved|Ancient|Altered) (Rib|Jawbone|Collarbone|Cranium)', n): return 'Abyss bones: ' + n.split()[0]
    if n.endswith('Idol') or n.startswith('Idol of'): return 'Idols'
    if 'Verisium' in n: return 'Verisium'
    if 'Alloy' in n: return 'Alloys'
    if n.endswith('Flux') or 'Flux (' in n: return 'Fluxes'
    return None


BANDS = [(3, 8), (8, 12), (12, 18), (18, 24), (24, 36), (36, 48), (48, 60), (60, 73)]
BKEYS = [f'L{a}-{b - 1 if b == 73 else b}' for a, b in BANDS]


def raw(lg, n):
    r = {}
    for L, s in S[lg].items():
        if 0 <= L <= 72 and s.get('div_ex') and n in s.get('items', {}):
            p, u, v = s['items'][n]
            if u > 0:
                r[L] = (p / s['div_ex'], u, v / s['div_ex'], p)
    return r


ls = defaultdict(dict)
for lg in LGS:
    for off, it, pdiv, pex, u in con.execute('SELECT offset_h, item, price_div, price_ex, units FROM ls_price WHERE league=? AND offset_h BETWEEN 72 AND 167 AND price_div>0', (lg,)):
        ls[(names.get(it, it.split('/')[-1]), lg)][off] = (pdiv, u, pex)


def dayprice(n, lg, a, b, k=0):
    xs = [v[k] for off, v in ls.get((n, lg), {}).items() if a <= off <= b and v[1] >= 1]
    return st.median(xs) if xs else None


allnames = set()
for lg in LGS:
    for s in S[lg].values():
        allnames |= set(s.get('items', {}))
G = defaultdict(lambda: defaultdict(list))
members = defaultdict(set)
units = defaultdict(lambda: defaultdict(lambda: defaultdict(float)))
for n in allnames:
    g = group(n)
    if not g:
        continue
    for lg in LGS:
        r = raw(lg, n)
        ref = [p for L, (p, u, v, _) in r.items() if 12 <= L < 24]
        if len(ref) < 4:
            continue
        ref = st.median(ref)
        members[g].add(n)
        row = {}
        for (a, b), k in zip(BANDS, BKEYS):
            xs = [r[L][0] for L in range(a, b) if L in r]
            row[k] = st.median(xs) / ref if xs else None
            units[g][lg][k] += sum(r[L][2] for L in range(a, b) if L in r)  # Div value traded
        d3, d6 = dayprice(n, lg, 72, 95), dayprice(n, lg, 144, 167)
        row['day3'] = d3 / ref if d3 else None
        row['day6'] = d6 / ref if d6 else None
        G[g][lg].append(row)

res = {}
for g, lgs in sorted(G.items()):
    res[g] = {'n_items': len(members[g]), 'examples': sorted(members[g])[:8], 'leagues': {}}
    for lg, rows in lgs.items():
        med = {}
        for k in BKEYS + ['day3', 'day6']:
            xs = [r[k] for r in rows if r.get(k)]
            med[k] = round(st.median(xs), 2) if len(xs) >= max(1, len(rows) // 3) else None
        tot = sum(units[g][lg].values()) or 1
        med['value_share_pct'] = {k: round(100 * units[g][lg][k] / tot, 1) for k in BKEYS}
        med['n'] = len(rows)
        best = max((k for k in BKEYS + ['day3', 'day6'] if med.get(k)), key=lambda k: med[k])
        med['best'] = best
        res[g]['leagues'][SHORT[lg]] = med

# campaign loot table: absolute prices
CAMP = ['Divine Orb', 'Exalted Orb', 'Chaos Orb', 'Orb of Annulment', 'Regal Orb', 'Orb of Alchemy', 'Vaal Orb',
        'Orb of Chance', "Artificer's Orb", "Glassblower's Bauble", "Gemcutter's Prism", "Lesser Jeweller's Orb",
        "Greater Jeweller's Orb", 'Orb of Transmutation', 'Orb of Augmentation', "Armourer's Scrap",
        "Blacksmith's Whetstone", "Arcanist's Etcher", 'Greater Exalted Orb', 'Greater Regal Orb', 'Greater Chaos Orb',
        'Uncut Skill Gem (Level 1)', 'Uncut Skill Gem (Level 7)', 'Uncut Support Gem (Level 1)', 'Uncut Support Gem (Level 2)',
        'Uncut Support Gem (Level 3)', 'Uncut Spirit Gem (Level 4)', 'Lesser Iron Rune', 'Iron Rune', 'Greater Iron Rune',
        'Lesser Essence of Seeking', 'Essence of Abrasion', 'Essence of the Body', 'Greater Essence of Abrasion',
        'Soul Core of Tacati', 'Soul Core of Opiloti', 'Breach Splinter', 'Simulacrum Splinter', 'Diluted Liquid Ire',
        'Gnawed Jawbone', 'Gnawed Rib', 'Gnawed Collarbone', 'Preserved Rib', 'Omen of the Liege']
camp = {}
for n in CAMP:
    camp[n] = {}
    for lg in LGS:
        r = raw(lg, n)
        if not r:
            continue
        row = {}
        for (a, b), k in zip(BANDS, BKEYS):
            xs = [(r[L][0], r[L][3]) for L in range(a, b) if L in r]
            if xs:
                row[k] = {'div': float(f'{st.median(x[0] for x in xs):.3g}'), 'ex': float(f'{st.median(x[1] for x in xs):.3g}')}
        d3 = dayprice(n, lg, 72, 95), dayprice(n, lg, 72, 95, 2)
        d6 = dayprice(n, lg, 144, 167), dayprice(n, lg, 144, 167, 2)
        if d3[0]: row['day3'] = {'div': float(f'{d3[0]:.3g}'), 'ex': float(f'{d3[1]:.3g}')}
        if d6[0]: row['day6'] = {'div': float(f'{d6[0]:.3g}'), 'ex': float(f'{d6[1]:.3g}')}
        camp[n][SHORT[lg]] = row
json.dump({'groups': res, 'campaign_loot': camp, 'bands': BKEYS + ['day3', 'day6']}, open(OUT, 'w', encoding='utf-8'), indent=1)
for g, r in res.items():
    print(f"== {g} ({r['n_items']})")
    for lg, m in r['leagues'].items():
        print(f"  {lg} n{m['n']} best={m['best']} " + ' '.join(f"{k}:{m[k]}" for k in BKEYS + ['day3', 'day6']) + '  share% ' + ' '.join(str(v) for v in m['value_share_pct'].values()))
print()
for n, d in camp.items():
    print(n, ' | '.join(f"{lg}: " + ' '.join(f"{k}={v['div']}d/{v['ex']}e" for k, v in row.items() if k in ('L3-8', 'L8-12', 'L18-24', 'L36-48', 'L60-72', 'day3', 'day6')) for lg, row in d.items()))
