"""Assemble league-start-deep.json from analysis.json + groups.json + the hand-checked findings below.
Usage: python -I build_final.py <analysis.json> <groups.json> <out league-start-deep.json>"""
import json, sys

A = json.load(open(sys.argv[1], encoding='utf-8'))
G = json.load(open(sys.argv[2], encoding='utf-8'))
OUT = sys.argv[3]
SH = {'Fate of the Vaal': 'FotV', 'Runes of Aldur': 'RoA', 'Forbidden Rites': 'FR'}

# ---------- hourly curves (price in Divine, volume-weighted within the hour; thin hours included, see units) ----------
hourly, units = {}, {}
for n, rec in A['items'].items():
    if n == 'Divine Orb':
        continue
    for lg, r in rec['leagues'].items():
        hourly.setdefault(n, {})[lg] = {int(h): v for h, v in r['hourly_div'].items()}
        if 'units_hourly' in r:
            units.setdefault(n, {})[lg] = {int(h): v for h, v in r['units_hourly'].items()}
rate_curves = {SH[lg]: {'ex_per_div': b['div_ex_hourly'], 'chaos_per_div': b['chaos_per_div_hourly']} for lg, b in A['base'].items()}
liq = {SH[lg]: q for lg, q in A['liquidity'].items()}
peaks = {}
for n, rec in A['items'].items():
    for lg, r in rec['leagues'].items():
        if r.get('thin') or n == 'Divine Orb':
            continue
        peaks.setdefault(n, {'category': rec['category']})[lg] = {
            'peak_L': r['peak_L'], 'peak_div': r['peak_div'], 'bottom_L': r['bottom_L'], 'bottom_div': r['bottom_div'],
            'first_trade_L': r['first_trade_L'], 'usable_liquidity_L': r['usable_liquidity_L'],
            'band_median_div': r['band_median_div'], 'day3_div': r['day3_div'], 'day6_div': r['day6_div']}

# ---------- early buys (computed: up >=30% from L12-24 to day 6-7 in every league that has data) ----------
KEEP = {"Omen of Light", "Orb of Annulment", "Ancient Collarbone", "Ancient Jawbone", "Ancient Rib", "Preserved Cranium",
        "Uncut Skill Gem (Level 20)", "Uncut Skill Gem (Level 1)", "Hinekora's Lock", "Perfect Chaos Orb", "Victorious Fate",
        "Deadly Fate", "Vaal Armourer's Infuser", "Soul Core of Tacati", "Omen of Chaotic Quantity", "Omen of Amelioration",
        "Uncut Spirit Gem (Level 14)", "Uncut Spirit Gem (Level 19)", "Uncut Spirit Gem (Level 20)", "Uncut Spirit Gem (Level 8)",
        "Greater Essence of Opulence", "Rakiata's Flow", "Dialla's Desire", "Garukhan's Resolve", "Rigwald's Ferocity",
        "Architect's Orb", "Fracturing Orb", "Omen of Secret Compartments", "Amanamu's Tithe", "Masterwork Rune"}
NOTE = {
    "Soul Core of Tacati": "Peaks about day 10, then falls 58-83% by day 42 (market-trends). Sell by day 10-14.",
    "Fracturing Orb": "RoA had no L12-24 data and fell 81% from L36 to day 6 (5.4 -> 1.0 Div). Patch-sensitive.",
    "Amanamu's Tithe": "Very volatile (FotV d3 8.5 -> d6 1.3 Div). Speculative.",
    "Omen of Secret Compartments": "Cheap and thin early; large % but small absolute value.",
    "Uncut Skill Gem (Level 1)": "Surprise riser, 3/3: FR 0.056 Div (L3-8) -> 0.51 Div by day 6.",
    "Rakiata's Flow": "Lineage gems rise only when meta. Which ones are meta in 1.0 is unknown until patch notes.",
    "Dialla's Desire": "Meta lineage gem; see Rakiata's Flow note.",
    "Garukhan's Resolve": "Meta lineage gem; see Rakiata's Flow note.",
    "Rigwald's Ferocity": "Meta lineage gem; see Rakiata's Flow note.",
    "Hinekora's Lock": "Rises to 1,100-2,000 Div by day 42 (market-trends). 0.5.1 hotfix briefly disabled a Lock crafting source on day 6.",
    "Orb of Annulment": "A campaign drop that RISES: sell later (peak days 10-21 per market-trends).",
    "Omen of Light": "Day 6-7 in Div: FotV 1.79, RoA 4.6, FR 3.3; keeps rising to day 42-56.",
}
eb = []
for r in A['early_buys']:
    if r['item'] not in KEEP:
        continue
    hh = r.get('half_gain_reached_L', {})
    first_half = min(hh.values()) if hh else None
    buy_by = 24 if first_half and first_half < 36 else (48 if first_half and first_half < 60 else 72)
    conf = 'high' if r['leagues'] == 3 and min(r['gain_pct_by_day6'].values()) >= 50 else ('medium' if r['leagues'] >= 2 else 'low')
    if r['item'] in ('Amanamu\'s Tithe', 'Omen of Secret Compartments', 'Fracturing Orb', 'Masterwork Rune'):
        conf = 'low'
    eb.append({'item': r['item'], 'category': r['category'], 'buy_by_hour': buy_by,
               'typical_gain_pct_by_day7': r['median_gain_pct'],
               'gain_pct_by_day6_7_per_league': r['gain_pct_by_day6'],
               'price_div_L12_24': r['early_div_L12_24'], 'half_of_gain_reached_at_L': hh,
               'confidence': conf, 'note': NOTE.get(r['item'], '')})
eb.sort(key=lambda x: ({'high': 0, 'medium': 1, 'low': 2}[x['confidence']], -x['typical_gain_pct_by_day7']))

# ---------- sell windows (from groups.json bands; see report section 3) ----------
SW = [
    ('Exalted Orb (as a store of value)', 'convert to Divine as soon as you hold spare Ex: L3-20 most of all',
     'Ex in Div L3-8 -> L60-72: -64% / -65% / -64%; -72 to -85% by day 6-7. Div:Ex rises fastest L4-19 (+35-61% per 6 h).', 'high'),
    ('Divine Orb', 'never sell for Ex in L0-24; hold',
     'Ex per Div L3-8 -> L18-24: 35 -> 75 (FotV), 25 -> 51 (RoA), 41 -> 70 (FR); 146 / 87 / 262 by day 6-7.', 'high'),
    ('Chaos Orb', 'hold over Ex; vs Div it is a coin flip in 72 h, better by day 6 in 0.5 leagues',
     'Chaos in Div L3-8 -> L60-72: -62% / -64% / +51%; by day 6-7: -67% / +28% / +176%. In Ex: 1.42 -> 1.9, 1.05 -> 4.8, 1.53 -> 25.1 Ex by day 6-7.', 'medium'),
    ('Greater-tier orbs (Greater Exalted, Regal, Chaos, Jeweller\'s, Transmutation, Augmentation)', 'L3-12 (sell on first exchange access)',
     'Group median 2.0-2.9x its L12-24 price at L3-12; 0.14-0.29x by day 6-7 (3/3). Greater Jeweller\'s -91 to -97% L3-8 -> day 6-7.', 'high'),
    ('Essences: Lesser, normal, Greater, Perfect', 'L3-12',
     'Group medians 1.7-3.1x the L12-24 price in L3-12; 0.23-0.69x by day 6-7 (3/3). E.g. Greater Essence of Abrasion RoA 0.50 Div (13.7 Ex) at L3-8 -> 0.013 Div at day 6-7.', 'high'),
    ('Essences: special (Hysteria, Horror, Delirium, Insanity, Abyss, Breach)', 'hold to day 6+ (sell later)',
     'Day 6-7: 1.58x (FotV), 0.53x (RoA), 2.45x (FR); Essence of Delirium 8-24x by day 42 (market-trends).', 'medium'),
    ('Basic campaign currency (Regal, Alchemy, Transmutation, Augmentation, Artificer\'s, Lesser Jeweller\'s, Whetstone)', 'L3-24',
     'Group median 3.2x (FotV) / 1.36x (RoA) / 1.04x (FR) at L3-8 vs L12-24. By day 6-7: Lesser Jeweller\'s -96 to -98%, Artificer\'s -61 to -77%, Alchemy -45 to -89%.', 'medium'),
    ('Gemcutter\'s Prism', 'L3-12 (FR), L36-48 (FotV/RoA), before day 3 in all',
     'FR 0.090 Div at L3-8 -> 0.018 at day 6-7 (-80%); FotV -73%, RoA -51%.', 'medium'),
    ('Orb of Annulment', 'do NOT sell in 72 h; sell days 10-21',
     'L3-8 -> day 6-7 in Div: +45% / +180% / +400%; peaks days 10-42 (market-trends).', 'high'),
    ('Orb of Chance', 'L48-72',
     'Rises to L60-72 (0.09 / 0.20 / 0.07 Div), then -45% / -5% / -25% by day 6-7; peaks days 2-4 per market-trends.', 'medium'),
    ('Glassblower\'s Bauble, Armourer\'s Scrap', 'L36-72',
     'Both rise from L3-12 to L36-72 in Div in 3/3 (Armourer\'s Scrap 2-5x), then fall a little by day 6-7.', 'medium'),
    ('Sink / rare currency (Hinekora\'s Lock, Mirror, Architect\'s, Vaal infusers, Fracturing, Core Destabiliser)', 'hold (sell from day 7, mostly weeks 5-8)',
     'Group median 1.96-2.89x its L12-24 price by L60-72 and 2.6-7.0x by day 6-7 (3/3).', 'high'),
    ('Omens: top crafting (Light, Whittling, Annulment, Erasure, Crystallisation, Abyssal Echoes)', 'hold; sell week 5-8',
     'Day 6-7 vs L12-24: 2.04x / 1.0x / 3.15x; Omen of Light +410% / +136% / +235%.', 'high'),
    ('Omens: other (Liege, Putrefaction, Necromancy, Exaltation ones)', 'L3-12',
     'Group median 1.3-2.6x at L8-12 (FR 2.6x at L3-8). Omen of the Liege -98% / -98% / -99% from L8-12 to day 6-7.', 'high'),
    ('Runes: Greater', 'L3-24', 'L3-12 premium in FotV (2.1x); day 6-7 0.16-0.31x in 3/3.', 'high'),
    ('Runes: Lesser and normal', 'L3-12 or hold; no crash', 'L3-8 premium 1.3-2.8x in FotV/RoA, none in FR; day 6-7 0.85-1.44x.', 'low'),
    ('Runes: named / special', 'L8-36', 'Small premium L8-18 (1.1-1.3x); day 6-7 0.41-0.93x.', 'medium'),
    ('Uncut skill gems L16-19', 'L3-12', 'L3-12 1.85-3.0x of L12-24; day 6-7 0.25-0.37x (3/3).', 'high'),
    ('Uncut skill gem L20', 'hold to day 6-14', 'Day 6-7 3.5x / 6.8x / 4.0x the L12-24 price; peaks days 6-14 (market-trends).', 'high'),
    ('Uncut skill gems L1-15', 'L3-8 or hold', 'L3-8 1.2-2.5x; day 6-7 0.75-1.52x. Level 1 is a 3/3 riser (+42% / +440% / +800% L3-8 -> day 6-7).', 'low'),
    ('Uncut spirit gems L14-20', 'hold', 'Day 6-7 1.34-2.7x the L12-24 price (3/3); up 5-110x by day 42 (market-trends).', 'high'),
    ('Uncut support gems', 'any time in L3-48; sell before day 3', 'Flat L3-72 (0.9-1.2x); day 6-7 0.56-0.72x.', 'medium'),
    ('Lineage support gems (non-meta)', 'L8-36', 'Group median day 6-7 0.30-0.52x of L12-24; non-meta ones -52 to -99%.', 'high'),
    ('Lineage support gems (meta, e.g. Rakiata\'s Flow, Garukhan\'s, Dialla\'s, Uul-Netol\'s)', 'hold (weeks 2-6)', 'Rakiata\'s Flow +262% / +218% / +204% by day 6-7.', 'medium'),
    ('Liquid emotions: Diluted', 'L3-18', 'L3-18 1.1-2.6x; day 6-7 0.05-0.15x (3/3). Diluted Liquid Ire -98% / -86% / -97%.', 'high'),
    ('Liquid emotions: Ancient (0.5 leagues)', 'L18-36', 'Peak L18-36, then -95% by day 6-7 (2/2).', 'medium'),
    ('Liquid emotions: Concentrated / Potent', 'hold to day 3, then check', 'Day 3: 1.95x / 3.56x / 1.02x; day 6-7 1.89x / 5.2x / 0.56x.', 'low'),
    ('Catalysts (normal)', 'L48-72', 'Peak L48-72 at 1.3-1.46x; day 6-7 0.75-1.24x. Refined catalysts are risers (market-trends).', 'medium'),
    ('Fragments & boss keys (Crisis fragments, Kulemak\'s Invitation, Simulacrum, Fates...)', 'L48-day 3 for common ones; hold Fates',
     'Group median 1.2-1.6x at L48-day 3; mixed by day 6-7. Fates +45 to +336% (hold).', 'low'),
    ('Splinters & shards (Breach, Simulacrum)', 'L8-12', 'About 2x at L8-12 in 2/3, then 0.66-1.15x.', 'low'),
    ('Soul cores: common', 'hold to about day 10 (2/3)', 'Day 6-7: 1.34x / 2.79x / 0.72x; Tacati peaks day 10 (market-trends).', 'medium'),
    ('Abyss bones: Gnawed', 'L3-12', 'L3-8 1.5-2.6x; day 6-7 0.35-0.46x (3/3).', 'high'),
    ('Abyss bones: Preserved Rib / Jawbone', 'L3-24', 'Preserved Rib -55 to -62% L12-24 -> day 6-7; Preserved Jawbone -69 to -87%.', 'high'),
    ('Abyss bones: Ancient, and Preserved Cranium/Collarbone', 'hold', 'Ancient group 3.3x / 3.3x / 6.8x by day 6-7; Cranium +110 / +211 / +1,875%.', 'high'),
    ('League-mechanic currency of the new league (e.g. Verisium, Alloys, Fluxes, Idols in their launch)', 'L3-18', 'Verisium 3.6x at L3-8 then -57 to -88% by day 6-7; Alloys/Fluxes 1.1-1.6x early, 0.5-0.9x by day 6-7. Inference: the new 1.0 league currency will likely follow.', 'medium'),
]
sell_windows = [{'item_or_group': a, 'best_hours': b, 'why': c, 'confidence': d} for a, b, c, d in SW]

# ---------- community tips vs data ----------
CT = [
    ("Rush the campaign/maps; the first hours of a fresh economy make the most currency per hour",
     "Timesaver 0.5.5 league-start guide [seller] (S30); Timesaver 1.0 guide (S31)", "partly",
     "Campaign-drop groups sell for 1.4-3.1x their L12-24 price at L3-12 (essences, Greater orbs, Gnawed bones). But the exchange is thin: traded value is 1-7% of the L48-72 level before L12 and 25% only at L25-31. Endgame items first trade at L10-20, so only racers are in maps that early.",
     "medium"),
    ("Don't use Exalted/Chaos/Divine during the campaign in a trade league", "ZiggyD, Maxroll levelling guide, Sep 2026 (S20)", "confirmed",
     "Spending them on your own gear early wastes them: Div:Ex doubles L4 -> L18-24 (3/3), and Greater-tier orbs are worth 2-3x more at L3-12 than at L24+.", "high"),
    ("Buy your levelling uniques, resistances and MS boots with Exalts", "ZiggyD, Maxroll (S20); Maxroll levelling-uniques page (S21)", "partly",
     "Paying in Ex is right: Ex loses 64-65% of its Div value L3-8 -> L60-72. But common levelling uniques are dearest on day 1-2: HC FR day 2 Wanderlust 0.20 Div vs 0.034 later, Tabula 4.9 vs 0.96 (outof.games, S22; HC, thin). Buy only what speeds you up.",
     "medium"),
    ("Sell clean rare bases, uncut gems and bulk basic currency in hours 8-24", "Timesaver FR guide [seller] (S30)", "partly",
     "Basic currency: L3-8 premium 3.2x (FotV) and 1.36x (RoA), none in FR. Uncut skill gems L16-19: 1.9-3.0x early, -63 to -75% by day 6-7 (confirmed). Uncut skill L20 and spirit gems L14+ rise instead (contradicted for them). Rare bases: no data.",
     "medium"),
    ("An item sold on day 1 fetches about 3x its day-10 price", "Timesaver via KamiLabs, Sep 2026 (S32)", "partly",
     "True only for the crash group. Greater essences are at 0.23-0.34x of their L12-24 price by day 6-7, and at L3-12 they were 2.8-3.1x that price, so about 10x. The risers do the opposite: sink currency is 2.6-7x and top omens 1-3x by day 6-7.",
     "high"),
    ("Farm Exalted + Chaos first, convert to Divine later", "Timesaver 1.0 league-start guide [seller] (S31)", "contradicted",
     "Converting LATER loses: Ex per Div rose 35 -> 98 (FotV), 25 -> 72 (RoA), 41 -> 114 (FR) from L3-8 to L60-72. Convert as you go.",
     "high"),
    ("Sell Exalted for Divines on a schedule / hold early Divines, spend Exalts", "Timesaver 'Economy cooked' 0.5.5 [seller] (S33); Timesaver FR guide (S30)", "confirmed",
     "Div:Ex never fell more than about 11% in any 6 h window in L4-72, and rose up to 61% in 6 h (FotV L8-14). Its fastest rise is L4-19 in all three launches.",
     "high"),
    ("Keep your liquidity in Chaos, not Exalts", "EODGamerz 0.5 market analysis (S34); techsngames (S35)", "partly",
     "Chaos beat Ex in all three launches by day 6-7 (1 Chaos = 1.9 / 4.8 / 25 Ex, from 1.4 / 1.05 / 1.5 at L3-8). Against Div, Chaos lost 62-64% in 72 h in FotV and RoA and gained 51% in FR. By day 6-7 it gained in RoA and FR only.",
     "medium"),
    ("Don't buy gear in the first 48 h / wait a few days, early prices are inflated", "Switchblade Gaming (S8, low trust); Timesaver (S33) [seller]", "partly",
     "On the exchange it holds for the crash group: Greater Jeweller's is -80% by L60-72 and -97% by day 6-7. It's wrong for risers, so buy those early: sink currency 2-3x by L60-72, Omen of Light +136 to +410% by day 6-7. Uniques: only HC snapshots, which show early premiums.",
     "medium"),
    ("Don't buy Z until the weekend", "the player's example; no published PoE 2 source found", "partly",
     "All three launches started on a Friday, so the weekend is about L28-76, and liquidity is highest L60-72 (Monday daytime UTC). The crash group is far cheaper by then: Greater-tier orbs at 0.38-0.59x their L12-24 price. The risers are dearer, so for those, waiting costs you.",
     "medium"),
    ("Prices are chaotic in the first 48 h; avoid panic-buying", "Seller guide snippets (S36) [seller]", "confirmed",
     "Within-hour Div:Ex high/low gap was 20-140% in L3-10 and first stayed under 15% at L18 (FotV) and L23 (RoA). Fewer than about 1,000 markets were active before L12.",
     "high"),
    ("Park wealth in omens (Light/Whittling); buy Hinekora's Lock early while cheap", "Mirror Tier video summary, May 2026 (S37)", "confirmed",
     "Omen of Light in Div, L12-24 -> day 6-7: +410% / +136% / +235%. Hinekora's Lock: +199% (RoA), +897% (FR), and 17 -> 60 Div in FotV from L24-36. Whittling is 2/3 only (RoA -18%).",
     "high"),
    ("Sell essences early", "common advice (Timesaver, Maxroll currency guide S23)", "confirmed",
     "Common, Greater and Perfect essences: best band L3-12 in 3/3, and 0.23-0.69x by day 6-7.", "high"),
    ("Don't stop to craft gear you'll replace within an hour / don't craft early", "Timesaver FR guide (S30)", "partly",
     "Crafting inputs are dearest in L3-12 (Greater orbs 2-2.9x, Greater essences 2.8-3.1x), so using them early is costly. Crafting to sell (boots, amulets) can't be checked from exchange data.",
     "medium"),
    ("Craft-and-sell movement-speed boots / belts / amulets on day 1", "IGGM 0.4 boots guide [seller] (S38); ConquestCapped [seller] (S39); SaVeQ and LilBotQ video titles (S40)", "unverifiable",
     "No public data on rare-item sale prices. Seller claims: T1 MS boots 0.3-0.5 Div, good ones 6-10+ Div (0.4, Dec 22 2025).", "low"),
    ("Clear every campaign Ritual on night 1", "KamiLabs FR first-night plan (S32)", "unverifiable",
     "No drop data. 'Omens: other' sold for 2.6x their L12-24 price at L3-8 in FR, so early campaign omens are worth selling fast.", "low"),
    ("Save Tribute in campaign Ritual clusters for the boss unique shop (Mageblood chance)", "Timesaver Mageblood guide 0.5.5 [seller] (S41)", "unverifiable",
     "0.5.5-specific; no data. Day-1 Mageblood/Headhunter video titles exist (Fubgun, Spicysushi).", "low"),
    ("Start with one mechanic and commit your first atlas points (Ritual / Expedition first)", "techsngames (S35); GamesFuze (S42); ConquestCapped [seller] (S39)", "unverifiable",
     "The exchange shows prices, not income per hour. Mechanic outputs differ: Expedition Logbook rose in RoA (0.21 -> 1.68 Div L24-36 -> day 6-7) but crashed in FR (2.28 -> 0.25).", "low"),
    ("Flip on the Currency Exchange early", "GGG forum thread (S43); Nex video title (S40); Maxroll flipping guide (S18)", "partly",
     "Wide early spreads (20-140% within an hour, L3-10) mean margins exist. But fills are slow in that window (1-7% of Sunday volume), and executable spreads can't be measured from public data.", "low"),
    ("Rush to Act 4 for the exchange / trade hideout", "EODGamerz 0.5 (S34); GGG 0.3.0b patch notes (S44)", "confirmed",
     "The exchange unlocks per league at Act 4 (0.3.0b). The first trades appear 2-3 h after launch in all three launches, and the first hours carry the biggest premiums.", "high"),
    ("Common uniques are only expensive on day 1; then 'set in stone'", "Maxroll levelling-uniques page (S21)", "partly",
     "HC FR day 2 vs later: Wanderlust 0.20 -> 0.034 Div, Goldrim 0.40 -> 0.088, Astramentis 4.0 -> 0.44 (S22). HC is thin, and no softcore day-1 data exists.", "low"),
    ("Hold Chaos for trading until you run T8+", "techsngames (S35)", "partly", "Same evidence as the Chaos tip above.", "low"),
]
community_tips = [{'tip': a, 'source': b, 'verdict': c, 'evidence': d, 'confidence': e} for a, b, c, d, e in CT]

# ---------- plan ----------
PLAN = [
    {'from_hour': 0, 'to_hour': 3,
     'actions': ['Race the campaign. Pick up every currency item, essence, rune, uncut gem and omen; skip gear you will replace.',
                 'Do not spend Exalted, Chaos, Divine, Greater/Perfect orbs, essences or Annulments on your own items.',
                 'Pick a league-start build that does not need any trade to work.'],
     'sell': [], 'keep': ['everything (the exchange is not open to you yet)'],
     'why': 'No trades at all before L2-3 in any launch. The exchange unlocks per league at Act 4 (0.3.0b, S44). Campaign mats are worth the most in the next 9 hours.'},
    {'from_hour': 3, 'to_hour': 12,
     'actions': ['At first exchange access (Act 4), sell the crash group at once, in small lots (the market is thin).',
                 'Swap every spare Exalted Orb for Divines right away. Never sell a Divine for Ex now.',
                 'Buy only what speeds up the campaign (MS boots, a weapon upgrade, a key levelling unique), paying in Ex.'],
     'sell': ['Greater-tier orbs (Greater Exalted/Regal/Chaos/Jeweller\'s/Transmutation/Augmentation)',
              'Lesser, normal, Greater and Perfect essences', 'Lesser Jeweller\'s Orb, Regal, Alchemy, Artificer\'s, Transmutation, Augmentation',
              'Gnawed Abyss bones, Preserved Rib/Jawbone', 'Diluted liquid emotions', 'Uncut skill gems level 16-19',
              'weak omens (Liege, Putrefaction, Necromancy, Exaltation omens)', 'Greater runes', 'the new league\'s own basic currency',
              "Gemcutter's Prism (FR-style early premium)"],
     'keep': ['Divine Orbs', 'Chaos Orbs (better than Ex)', 'Orb of Annulment', 'Orb of Chance (sell L48-72)',
              "Glassblower's Bauble, Armourer's Scrap (rise to L36-72)", 'Uncut Skill Gem level 1 and 20, Uncut Spirit gems level 14+',
              'Perfect Exalted / Perfect Chaos', 'top crafting omens'],
     'why': 'Crash-group medians are 1.4-3.1x their L12-24 Div price here, and 0.14-0.46x by day 6-7 (3/3). Ex per Div rises 40-61% per 6 h in L4-19. Ex loses 64-65% of its Div value by L60-72.'},
    {'from_hour': 12, 'to_hour': 24,
     'actions': ['Keep converting Ex to Div as it comes in (Div:Ex still +23-39% per 6 h in RoA/FR at L11-19).',
                 'Finish the campaign. First maps for fast players (endgame items first trade at L10-20).',
                 'Sell the rest of the crash group before L24; spreads tighten under 15% around L18-23.'],
     'sell': ['remaining Greater essences, Greater runes, Greater orbs', 'non-meta lineage gems (by L36)',
              'Ancient liquid emotions if the league has them (peak L18-36)', 'Breach/Simulacrum splinters (L8-12 premium in 0.5)'],
     'keep': ['endgame risers you loot: Ancient Abyss bones, Preserved Cranium/Collarbone, top omens, Fates, Hinekora\'s Lock',
              'Uncut Skill Gem (Level 20)', 'special essences (Hysteria/Horror/Delirium/Insanity)', 'Refined catalysts'],
     'why': 'Group bands: crash items are at 0.9-1.0x at L18-24 and keep falling. Risers are at 1.0x here and 2-7x by day 6-7.'},
    {'from_hour': 24, 'to_hour': 48,
     'actions': ['Mapping and atlas. Put early atlas points into the one mechanic you farm, and farm for value (no data on which mechanic; see the report).',
                 'With spare Divines, buy risers you will need or hold: Omen of Light, Orb of Annulment, Ancient bones, Uncut Skill Gem (Level 20), Uncut Spirit gems level 14+, Victorious/Deadly Fate.',
                 'List bigger lots in the 13:00-18:00 UTC peak (liquidity index at least 0.9 vs at most 0.45 at 21:00-01:00 UTC).'],
     'sell': ['normal catalysts (best L48-72)', 'common fragments and boss keys (L48-day 3)', 'named/special runes (by L36)', 'Uncut support gems (before day 3)'],
     'keep': ['the riser list', 'Chaos rather than Ex'],
     'why': 'Liquidity reaches 50% of the L48-72 level at L37-39, so sells now fill. Risers bought here gained a median +100-400% by day 6-7 (early_buys). Div:Ex grows more slowly (about 1-2% per hour).'},
    {'from_hour': 48, 'to_hour': 72,
     'actions': ['Sunday-Monday is the most liquid window of the first 3 days (L60-72 at 1.0-1.5x the L48-72 mean). Do your bulk selling and big buys here.',
                 'Read every hotfix. In past launches the first farm nerfs and drop-rate changes came on days 3-6 (0.4.0b L76, 0.5.0b Hotfix 13 L106, 0.5.1 L146, 0.5.5b L150). Sell a broken farm\'s output before then.',
                 'Start storing unique prices daily (no exchange data exists for uniques).'],
     'sell': ['Orb of Chance (peak about L48-72)', 'normal catalysts', 'Concentrated liquid emotions if they rose (mixed 2/3)', 'anything left from the crash group'],
     'keep': ['sink currency (Hinekora\'s, Architect\'s, Vaal infusers, Fracturing)', 'top omens', 'Annulment (sell days 10-21)',
              'common soul cores (sell about day 10)', 'Uncut Skill Gem (Level 20) (sell days 6-14)', 'meta lineage gems'],
     'why': 'Liquidity peaks L60-72. FotV Div:Ex dipped about 10% at L54-72, the only fall in the 72 h window. Sink currency is at 1.96-2.89x by L60-72 and still rising (2.6-7x by day 6-7).'},
]

GEAR = {
    'summary': 'Gear and uniques never go through the Currency Exchange, so there are no GGG curves. Everything here is from guide/tracker snapshots (see sources); treat as low-medium confidence.',
    'levelling_uniques': [
        'Maxroll levelling list (0.5.4): Wanderlust, Bushwhack, Thrillsteel, Death Rush, Surefooted Sigil, Astramentis, Thief\'s Torment, Birthright Buckle, Greymake, Glowswarm, Midnight Braid, Goldrim, Tabula Rasa and others (S21).',
        'Maxroll says cheap staples (Wanderlust, Glowswarm, Luminous Pace, Crown of the Victor, Revered Resin) are affordable any time, while Tabula Rasa, Thief\'s Torment and high-attribute Astramentis are expensive early and drop later (S21, fetched).',
        'Day-2 HC Forbidden Rites (Sep 6 2026) vs SC FR about week 11: Wanderlust 0.20 -> 0.034 Div, Goldrim 0.40 -> 0.088, Thrillsteel 0.50 -> 0.16, Tabula Rasa 4.9 -> 0.96, Astramentis 4.0 -> 0.44, Ingenuity 0.097 -> 0.033 (outof.games, S22; HC is thinner and dearer than SC).',
        'Inference: pay for levelling uniques in Exalts (Ex is the fastest-losing currency) and only for ones that shorten the campaign; Div-priced levelling uniques are cheaper from day 3-4.'],
    'early_rare_gear': [
        'Campaign targets: movement speed boots at levels 16/33/46 (15/20/25%), capped resistances and 25-30% MS boots for maps, +skill-level weapons for casters (Maxroll, S20).',
        'Mid-patch prices (0.5.2, Jun 2026): ilvl 82 boots with 30% MS + a resistance about 1 Ex (Maxroll crafting guide, S24). Not a day-1 price.',
        '0.4 day-10 seller claim (Dec 22 2025): T1 35% MS boots with weak other mods sell for 0.3-0.5 Div, good life/res/ES finishes 6-7 Div, top tier 10+ Div; 10 bases + omens cost about 1.5-3 Div (IGGM [seller], S38).',
        'No dated day-1 prices were found for +level caster weapons, physical weapons or resistance jewellery.'],
    'chase_uniques_week1': [
        'Headhunter: 78 Div (HC FR day 2, Sep 6 2026) -> 11.2 Div (SC FR now); 60 Div SC RoA on Jul 24 2026; 0.2 about 40+ Div two weeks in (S22, S25).',
        'Mageblood: 374 Div (HC FR day 2) -> 110 Div (SC FR now); 230 Div SC RoA Jul 24 2026 (S22).',
        'Kalandra\'s Touch: 27 Div (HC FR day 2) -> 1.8 Div now (S22).',
        'Day-1 Mageblood/Headhunter drops were possible in 0.5.5 from campaign Ritual unique shops (video titles by Fubgun and Spicysushi, S40).',
        'Pattern (inference, low): chase uniques are dearest in week 1 in Div terms and fall as copies enter; buy build-defining uniques after day 4-5 unless they unlock a farm.'],
    'unique_price_behaviour': [
        'Seller guides: "prices are chaos in the first 48 hours", "most items normalise or drop in the second week" (S36, low).',
        'No published PoE 2 source for "wait until the weekend"; the exchange data supports it only for the crash group.'],
    'one_point_zero': [
        '1.0 launches Dec 11 2026 (PST). The hour is not announced; past launches were 11:00 PST (0.4) and 13:00 PDT (0.5, 0.5.5), i.e. 19:00-20:00 UTC (S45-S48).',
        'New league "Conquerors of Wraeclast". Castle treasuries are the only source of new reforging materials (Crimson Iron, Infused Blood) (S46, S49).',
        'Acts 5 and 6 are added, so the campaign is longer and map entry will likely come later than L10-20. Uniques now drop in the Acts (S46, S50).',
        '1.0 is a new challenge league with a fresh economy (GGG FAQ wording, S47).'],
}

RISKS = [
    {'date': '2025-12-13 ~02:40 UTC (0.4, L~8)', 'what': 'Hotfix 4 deleted every Cartographer\'s Chisel and Engineer\'s Orb on next login (they could drop by bug).', 'source': 'GGG forum 3885885 (S51)'},
    {'date': '2025-12-15 ~23:30 UTC (0.4, L~76)', 'what': '0.4.0b: more Tablet drops; gold vendor values fixed; Oisin\'s Oath added to the exchange.', 'source': 'GGG forum 3890041 (S51)'},
    {'date': '2025-12-18 ~21:30 UTC (0.4, L~146)', 'what': '0.4.0c: Temple rooms buffed, past-Temple benches take currency home; the temple boom that was nerfed on Jan 3 2026 (day ~22).', 'source': 'GGG forum 3893204; PCGamesN (S6)'},
    {'date': '2026-05-31 ~05:25 UTC (0.5, L~33)', 'what': '0.5.0b Hotfix 2: +10-15% Waystone quantity from map bosses on four atlas nodes.', 'source': 'GGG forum 3937394 (S51)'},
    {'date': '2026-06-02 (0.5, L~78)', 'what': 'Ritual reroll cost reduction capped at 90%.', 'source': 'GGG forum 3943212 (S51)'},
    {'date': '2026-06-03 ~05:55 UTC (0.5, L~106)', 'what': '0.5.0b Hotfix 13: major Temple nerf (a hidden mod made every pack rare).', 'source': 'GGG forum 3945385 (S51)'},
    {'date': '2026-06-04 ~22:30 UTC (0.5, L~146)', 'what': '0.5.1: Elite Abyss monsters lower damage, loot and XP; Kulemak atlas-point fix.', 'source': 'GGG forum 3949197 (S51)'},
    {'date': '2026-06-05 (0.5, day 6-7)', 'what': 'Runeforging un-fracture exploit closed; Hinekora\'s Lock remnant crafting disabled, then a guaranteed-Lock bug fixed.', 'source': 'GGG forum 3949984, 3951282, 3951518 (S51)'},
    {'date': '2026-09-04 (0.5.5, L~1-4)', 'what': 'Atzoatl Map Device disabled for about 3.5 h because of crashes.', 'source': 'GGG forum 4001277, 4001331 (S51)'},
    {'date': '2026-09-06 (0.5.5, L~40-50)', 'what': 'Trial of Chaos ascendancy-point exploit and Ocean Expedition 3-site bug fixed.', 'source': 'GGG forum 4002255, 4002328 (S51)'},
    {'date': '2026-09-11 ~01:40 UTC (0.5.5, L~150)', 'what': '0.5.5b: more Expedition, Temple and Delirium Tablet drops.', 'source': 'GGG forum 4004106 (S51)'},
    {'date': 'pattern', 'what': 'No rollbacks or bans for legal farming in any of the three windows. Big balance changes land on days 3-6; the 72 h window has mostly crash fixes.', 'source': 'S51'},
]

SOURCES = [
    ('S1 GGG public Currency Exchange history API (hourly digests)', 'https://web.poecdn.com/api/currency-exchange/poe2/<unix hour>'),
    ('S2 Exile Oracle DB (ls_price days 0-6, read-only)', 'file:<data folder>/data/poe2kit.db'),
    ('S3 Earlier research: market-trends.md / .json', 'research/market/market-trends.md'),
    ('S6 PCGamesN: temple diminishing returns (0.4)', 'https://www.pcgamesn.com/path-of-exile-2/patch-notes-temple-diminishing-returns'),
    ('S8 Switchblade Gaming: PoE 2 economy guide (low trust)', 'https://www.switchbladegaming.com/path-of-exile-2/economy-guide-4/'),
    ('S18 Maxroll: Flipping with the Currency Exchange', 'https://maxroll.gg/poe2/resources/flipping-with-the-currency-exchange'),
    ('S20 Maxroll (ZiggyD): Comprehensive League Start Leveling Guide', 'https://maxroll.gg/poe2/getting-started/comprehensive-league-start-leveling-guide'),
    ('S21 Maxroll: The Best Leveling Uniques', 'https://maxroll.gg/poe2/meta/the-best-leveling-uniques'),
    ('S22 outof.games PoE 2 economy pages (Headhunter, Mageblood, Wanderlust, Tabula Rasa, etc.)', 'https://outof.games/realms/poe2/economy/unique-accessories/'),
    ('S23 Maxroll: Currency Guide', 'https://maxroll.gg/poe2/resources/currency-guide'),
    ('S24 Maxroll: How to Craft in PoE 2', 'https://maxroll.gg/poe2/resources/how-to-craft-in-path-of-exile-2'),
    ('S25 Prima Games: Most expensive items in Dawn of the Hunt (via mirror)', 'https://primagames.com/tips/most-expensive-items-in-path-of-exile-2-dawn-of-the-hunt'),
    ('S30 Timesaver: Forbidden Rites league start guide 0.5.5 [seller]', 'https://timesaver.gg/blog/poe2-forbidden-rites-league-start-guide-0-5-5'),
    ('S31 Timesaver: 1.0 league start currency guide [seller]', 'https://timesaver.gg/blog/poe2-1-0-league-start-currency-guide'),
    ('S32 KamiLabs: Forbidden Rites league start, first night', 'https://kami-labs.fr/en/path-of-exile-2/forbidden-rites-league-start-plan-jour-1/'),
    ('S33 Timesaver: Economy cooked? 0.5.5 [seller]', 'https://timesaver.gg/blog/poe2-economy-cooked-what-currency-worth-farming-maps-0-5-5'),
    ('S34 Gistly summary of EODGamerz "Market focused analysis of 0.5 patch notes"', 'https://gist.ly/youtube-summarizer/path-of-exile-2-05-league-market-profit-guide'),
    ('S35 techsngames: PoE 2 currency farming guide 2026', 'https://techsngames.com/path-of-exile-2-currency-farming/'),
    ('S36 Timesaver: trade prices wrong, Standard vs league [seller]', 'https://timesaver.gg/blog/poe2-trade-prices-wrong-standard-vs-league-forbidden-rites-0-5-5'),
    ('S37 Gistly summary of Mirror Tier "How top players get fully geared on league start"', 'https://gist.ly/youtube-summarizer/poe2-league-start-farm-craft-and-beat-inflation'),
    ('S38 IGGM: 0.4 currency by crafting boots [seller]', 'https://www.iggm.com/news/poe-2-patch-0-4-0-how-to-get-currency-by-crafting-boots'),
    ('S39 ConquestCapped: how to farm Divine Orbs in 0.5 [seller]', 'https://conquestcapped.com/guides/path-of-exile-2/poe-2-currency-farming/'),
    ('S40 poebuilds.cc farming/top lists by league (YouTube titles)', 'https://www.poebuilds.cc/poe2/farming/top?league=rites'),
    ('S41 Timesaver: Mageblood from campaign rituals 0.5.5 [seller]', 'https://timesaver.gg/blog/poe2-mageblood-campaign-rituals-unique-shop-0-5-5'),
    ('S42 GamesFuze: how to get more Divines in RotA', 'https://gamesfuze.com/guides/how-to-get-more-divines-in-path-of-exile-return-of-the-ancients/'),
    ('S43 GGG forum: How to make currency in PoE2?', 'https://www.pathofexile.com/forum/view-thread/3863804'),
    ('S44 GGG forum: 0.3.0b patch notes (exchange unlock per league at Act 4)', 'https://www.pathofexile.com/forum/view-thread/3840893'),
    ('S45 Steam: The Last of the Druids launches soon (0.4 launch time)', 'https://store.steampowered.com/news/app/2694490/view/1818752592125334'),
    ('S46 Steam: Path of Exile 2 Full Release on December 11 PST', 'https://store.steampowered.com/news/app/2694490/view/1848664643347683'),
    ('S47 Steam: Forbidden Rites FAQ (launch 1PM PDT; fresh economy wording)', 'https://store.steampowered.com/news/app/2694490/view/1842212951308718'),
    ('S48 Steam: Return of the Ancients launches soon (0.5 launch time)', 'https://store.steampowered.com/news/app/2694490/view/1833968530889810'),
    ('S49 poe-vault: Conquerors of Wraeclast explained', 'https://www.poe-vault.com/poe2/news/conquerors-of-wraeclast-explained-path-of-exile-2s-1-0-league-has-you-raise-an-army'),
    ('S50 Inven Global: Jonathan Rogers interview (Nov 18 2026)', 'https://www.invenglobal.com/articles/28823/jonathan-rogers-poe2s-official-launch-goal-is-1-million-players'),
    ('S51 GGG PoE 2 patch-notes forum (all hotfix threads of the first two weeks)', 'https://www.pathofexile.com/forum/view-forum/2212'),
    ('S52 Steam: Return of the Ancients two-week recap', 'https://store.steampowered.com/news/app/2694490/view/1835236783568632'),
    ('S53 PCGamesN: RotA makes Divine Orbs more common', 'https://www.pcgamesn.com/path-of-exile-2/return-of-the-ancients-divine-orbs'),
    ('S54 GGG forum: 0.5.5d patch notes', 'https://www.pathofexile.com/forum/view-thread/4008534'),
    ('S55 Gistly summary: fastest Spear Twister levelling (3h31m to maps)', 'https://gist.ly/youtube-summarizer/path-of-exile-2-fastest-spear-twister-leveling-guide'),
    ('S56 GGG forum (PoE 1): advice for obtaining currency during league start (2019)', 'https://www.pathofexile.com/forum/view-thread/2511170'),
    ('S57 Maxroll (PoE 1 3.30): League Start Alch & Go', 'https://maxroll.gg/poe/currency/league-start-alch-and-go'),
    ('S58 poe-vault: This PoE2 trading trick could save your Divines', 'https://www.poe-vault.com/poe2/news/this-poe2-trading-trick-could-save-your-divines'),
    ('S59 outof.games / poe2db economy pages used for uncut-gem volume context', 'https://poe2db.tw/us/Economy_Uncut_Gems'),
]

doc = {
    'meta': {
        'made': '2026-11-21', 'report': 'league-start-deep.md',
        'hour_axis': 'L = hours since the official launch (FotV 2025-12-12 19:00 UTC, RoA 2026-05-29 20:00 UTC, FR 2026-09-04 20:00 UTC). GGG digest ids are unix hours; taken as the start of the hour covered (undocumented, +-1 h). L = app ls_price offset_h + 4 (FotV) or + 3 (RoA, FR).',
        'price_method': 'Per hour and item: volume-weighted price on each market against Exalted, Divine and Chaos, converted at that hour\'s Div:Ex and Chaos:Ex, combined weighted by Exalt value traded; then divided by that hour\'s Ex per Div. Day 3 and day 6-7 come from the app\'s ls_price (offset 72-95 and 144-167).',
        'coverage': '231 hourly digests fetched (L-1..L76 per league, 2.5 s apart), cached in scripts/cache. ls_price already held hours 0-167 as derived prices but no raw markets and nothing before the app\'s start_hour.',
        'leagues': {'FotV': 'Fate of the Vaal 0.4', 'RoA': 'Runes of Aldur 0.5', 'FR': 'Forbidden Rites 0.5.5'},
        'caveats': ['Single hours of thin items are noisy; peaks/bottoms use a 3-hour volume-weighted smoothing and ignore hours with <5% of the item\'s peak units.',
                    'Values of exactly 1.0 Ex in L3-10 are often 1:1 minimum trades, not real prices.',
                    'volume_traded units are undocumented; liquidity is a relative index (value traded per hour vs the L48-72 mean).',
                    'Exchange items only. No uniques or rares.'],
    },
    'rate_curves': rate_curves,
    'liquidity': liq,
    'hourly_curves': hourly,
    'hourly_units': units,
    'item_peaks': peaks,
    'groups': G['groups'],
    'campaign_loot_prices': G['campaign_loot'],
    'sell_windows': sell_windows,
    'early_buys': eb,
    'fast_fallers': A['fallers'][:40],
    'plan_72h': PLAN,
    'community_tips': community_tips,
    'gear_notes': GEAR,
    'risks_week1': RISKS,
    'sources': [{'title': t, 'url': u} for t, u in SOURCES],
}
json.dump(doc, open(OUT, 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
print('items in hourly_curves:', len(hourly), 'early buys:', len(eb), 'tips:', len(community_tips))
for e in eb:
    print(e['item'], e['buy_by_hour'], e['typical_gain_pct_by_day7'], e['gain_pct_by_day6_7_per_league'], e['confidence'], e['half_of_gain_reached_at_L'])
