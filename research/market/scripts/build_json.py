"""Write research/market/market-trends.json: hand-checked patterns + strategies + sources, plus compact price
curves (in Divine) for key items, from the series built by analyse.py.
Usage: python -I build_json.py <series.json> <out market-trends.json>"""
import json, sys

SER, OUT = sys.argv[1], sys.argv[2]
ACC = '2026-11-21'
CX = 'GGG Currency Exchange history, sampled by Exile Oracle research (S1/S2)'

KEY = ["Exalted Orb", "Chaos Orb", "Greater Exalted Orb", "Perfect Exalted Orb", "Greater Chaos Orb",
       "Perfect Chaos Orb", "Fracturing Orb", "Orb of Annulment", "Hinekora's Lock", "Mirror of Kalandra",
       "Perfect Jeweller's Orb", "Greater Jeweller's Orb", "Vaal Orb", "Orb of Chance", "Greater Orb of Transmutation",
       "Architect's Orb", "Crystallised Corruption", "Vaal Armourer's Infuser", "Simulacrum", "Simulacrum Splinter",
       "Breach Splinter", "Breachstone", "Refined Sibilant Catalyst", "Omen of Light", "Omen of Whittling",
       "Omen of Sinistral Annulment", "Omen of Dextral Erasure", "Omen of Chaotic Quantity", "Omen of the Liege",
       "Uncut Skill Gem (Level 20)", "Uncut Spirit Gem (Level 20)", "Uncut Support Gem (Level 5)", "Uhtred's Exodus",
       "Atziri's Allure", "Victorious Fate", "Deadly Fate", "Preserved Cranium", "Preserved Rib", "Ancient Collarbone",
       "Essence of Delirium", "Diluted Liquid Ire", "Soul Core of Tacati"]

# phase: 'day 1-3' (league days 0-2), 'week 1' (days 3-6), 'week 2-3' (days 7-21), 'week 4+' (day 22 on)
# typical_change_pct: change of the price measured in DIVINE ORBS over that phase (median of the 3 launches unless
# stated). Leagues: FotV = Fate of the Vaal (0.4), RoA = Runes of Aldur (0.5), FR = Forbidden Rites (0.5.5).
P = [
    # --- base currency ratios ---
    ("Divine:Exalted ratio", "day 1-3", "up", 60, "high",
     "Ex per Div d0->d2: FotV 67->102, RoA 41->66, FR 54->107 (S1)."),
    ("Divine:Exalted ratio", "week 1", "up", 45, "high",
     "d2->d6: FotV 102->146, RoA 66->87, FR 107->262 (S1). Playbook div_rate agrees (S3)."),
    ("Divine:Exalted ratio", "week 2-3", "up", 130, "high",
     "d6->d21: FotV 146->339 (peak 403 on d14), RoA 87->235, FR 262->502 (S1). Seller-site snapshots for FR: ~740 on Oct 5 (d31), ~807 Oct 16 (S10)."),
    ("Divine:Exalted ratio", "week 4+", "up then down", -30, "medium",
     "Peak: FotV d14 (403), RoA d42 (553), FR d42 (709). From peak to the last sample: FotV -25% (302 d70), RoA -32% (375 d70), FR -34% (468 d77) (S1)."),
    ("Exalted Orb (priced in Div)", "week 1", "down", -55, "high",
     "Ex value in Div d0->d6: FotV -54%, RoA -53%, FR -79%; d0->d28: -83%, -89%, -92% (S1)."),
    ("Chaos Orb (priced in Div)", "week 1", "up", 50, "medium",
     "Chaos in Div d0->d6: FotV -40% (exception), RoA +51%, FR +173%. Chaos per Div: RoA 26->18, FR 29->10.5 (S1). Web: FR ~20 Chaos/Div Sep 5, 10.8 Oct 5 (S10)."),
    ("Chaos Orb (priced in Div)", "week 2-3", "up", 40, "medium",
     "d6->d21: FotV +6%, RoA +68%, FR +42%. In Ex terms a Chaos went 1.9 -> 57 Ex in FR (d0->d14) (S1)."),
    ("Chaos Orb (priced in Div)", "week 4+", "flat", -10, "medium",
     "RoA 0.092->0.123 Div (d21->d70), FR 0.139->0.087 (d21->d77), FotV rises 0.014->0.038 (S1)."),
    # --- higher-tier and crafting currency ---
    ("Greater Exalted / Greater Jeweller's / Lesser Jeweller's", "week 1", "down", -75, "high",
     "Greater Exalted d0->d21: -93%, -93%, -96%. Greater Jeweller's d0->d14: -99%, -97%, -96% (S1). Already a playbook sell-day-1 item (S3)."),
    ("Low-tier crafting orbs (Transmutation/Augmentation lines, Regal, Alchemy, Chance)", "week 2-3", "down", -85, "high",
     "Greater Transmutation d0->d42: -99/-98/-97%. Orb of Chance rises for 2-4 days, then -89 to -96% by d42 (S1)."),
    ("Perfect Exalted Orb", "week 1", "up", 60, "medium",
     "d0->d6: FotV +4%, RoA +84%, FR +62%; d0->d42: FotV -56%, RoA +91%, FR +136% (S1). Holds value in 0.5 leagues."),
    ("Perfect Chaos Orb", "week 2-3", "up", 400, "medium",
     "d0->d21: FotV +27%, RoA +423%, FR +567%; FR reached 12-13 Div by d70-77 (S1)."),
    ("Perfect Jeweller's Orb", "week 2-3", "down", -60, "high",
     "d0->d28: -85%, -73%, -83% (S1). 0.5 cut Perfect jeweller/exaltation drop rates (S12, low) but the price still fell."),
    ("Orb of Annulment", "week 1", "up", 200, "high",
     "d0->d6: FotV +90%, RoA +222%, FR +389%. Peaks: FotV d10 (0.21 Div), RoA d42 (0.63), FR d21 (0.61) (S1)."),
    ("Orb of Annulment", "week 4+", "down", -45, "medium",
     "FR d21->d77: -66%; RoA d42->d70: -25%; FotV flat (S1)."),
    ("Fracturing Orb", "week 2-3", "up", 300, "medium",
     "d0->d42: FotV 0.09->24.7 Div (Immured Fury bug in 0.4, S11/S13), RoA 1.6->9.2, FR 3.1->4.9 then 8-9 late. Very patch-sensitive (S1)."),
    ("Hinekora's Lock", "week 2-3", "up", 400, "high",
     "Div price d1->d42: FotV 18->1,180, RoA 62->1,250, FR 83->1,700 (20-66x); flat after week 6 (S1)."),
    ("Mirror of Kalandra", "week 4+", "up", 40, "high",
     "Div price d2->d42: FotV 194->6,730, RoA 387->5,310, FR 985->5,410; ~4,500-9,000 Div late (S1). Web: ~4,000 Div (0.4, S7), 5,316 Div FR Oct 5 (S10)."),
    ("Corruption / sink currency (Architect's Orb, Crystallised Corruption, Vaal Infusers)", "week 2-3", "up", 200, "high",
     "Architect's d0->d42: 11x, 53x, 67x; Crystallised Corruption 12x, 16x, 45x; Vaal Armourer's Infuser 20x, 15x, 8x (S1)."),
    # --- omens ---
    ("Top crafting omens (Whittling, Light, Sinistral/Dextral Annulment and Erasure)", "week 1", "up", 100, "high",
     "Omen of Sinistral Annulment d1->d6: FotV +88%, RoA +4%, FR +482%; Whittling d0->d6: FotV +171%, RoA -28%, FR +262% (S1)."),
    ("Top crafting omens (Whittling, Light, Sinistral/Dextral Annulment and Erasure)", "week 4+", "up", 100, "high",
     "d21->d42: Whittling +427%/+100%/+104%; Light +349%/+9%/-18%, then +130% by d56 in FR. Whittling d0->d42 = 49x / 3x / 15x (S1). Seller sites disagree on whether omens are dear or cheap in week 1 (S9)."),
    ("Weak / niche omens (Liege, Putrefaction, Sinistral Necromancy)", "day 1-3", "down", -80, "high",
     "Omen of the Liege d0->d2: -82%, -84%, -82%; d0->d42 -98% to -99% (S1)."),
    ("Omen of Chaotic Quantity", "week 1", "up then flat", 470, "medium",
     "d0->d6: 4x, 6x, 26x; FR peaked d6-21 (0.55-0.64 Div) and fell to 0.34 by d77 (S1)."),
    # --- other groups ---
    ("Soul cores (common, e.g. Tacati)", "week 1", "up", 700, "high",
     "Tacati d0->peak d10: 11x, 8.6x, 3.3x (S1)."),
    ("Soul cores (common, e.g. Tacati)", "week 2-3", "down", -75, "high",
     "Tacati from the d10 peak to d42: -83%, -76%, -58%. The playbook lists it as 'hold' (+752% by d7). Sell by day 10-14 (S1, S3)."),
    ("Soul cores (category median)", "week 4+", "mixed", 0, "low",
     "Category median d21->d56: FotV +120%, RoA -70%, FR -27% (S1)."),
    ("Delirium liquid emotions (Diluted / low tiers / Ancient Diluted)", "day 1-3", "down", -80, "high",
     "Diluted Liquid Ire d0->d2: -83%, -54%, -88%; d0->d14 -99/-96/-97%. Delirium category d0->d42 median: -27%, -98%, -95% (S1)."),
    ("Essences (common, Greater)", "week 2-3", "down", -40, "high",
     "Essences category d0->d42 median: FotV +38%, RoA -90%, FR -89%; Greater Essence of Grounding -93/-98/-97% (S1)."),
    ("Rare essences (Essence of Delirium, Perfect Essence of the Infinite)", "week 4+", "up", 300, "high",
     "Essence of Delirium d0->d42: 12x, 8x, 24x; Perfect Essence of the Infinite d0->d42 +92/+543/+476% (S1)."),
    ("Runes (category)", "day 1-3", "down", -30, "high",
     "Category median d0->d2: -28%, -25%, -35%; d0->d42: -53% in all three leagues (S1)."),
    ("Runes (category)", "week 4+", "up", 60, "medium",
     "Median d21->d56: FotV +220%, RoA +53%, FR +50%. Recovery is concentrated in specific runes, not across the board (S1)."),
    ("Lineage support gems: chase / meta (e.g. Uhtred's Exodus)", "week 2-3", "up", 360, "high",
     "Uhtred's Exodus d1->d42: FotV 1.1->59 Div, RoA 7->335, FR 14->280 (still 457 at d77). Atziri's Allure FR 0.17->3 (S1)."),
    ("Lineage support gems: non-meta", "day 1-3", "down", -35, "high",
     "Category median d0->d2: -30/-37/-41%; d0->d42 median -37/-93/-74%; e.g. Tecrod's Revenge, Arakaali's Lust -95 to -100% (S1)."),
    ("Uncut Spirit Gems (level 7+)", "week 2-3", "up", 90, "high",
     "Level 20 d1->d42: FotV 110x, RoA 5.4x, FR 5.7x (FR 12.3 Div at d77). Level 14-15: +800-1,100% d0->d42 (S1)."),
    ("Uncut Skill Gem (Level 20)", "week 1", "up", 300, "high",
     "d0->d6: 3.3x, 7.2x, 4x. After that it differs by league: FotV -77% d6->d56, RoA flat, FR +67% (S1)."),
    ("Uncut low-level Support / Skill gems (Level 1-5, 18)", "week 2-3", "down", -75, "high",
     "Uncut Support (Level 5) d0->d14: -82/-82/-74%; Uncut Skill (Level 18) d0->d42 -96/-99/-95% (S1)."),
    ("Ultimatum pinnacle fragments (Victorious / Deadly / Cowardly Fate)", "week 4+", "up", 500, "high",
     "Victorious Fate d0->d42: 42x, 29x, 53x; still rising to d56-70 in FotV/FR (S1)."),
    ("Breach catalysts (Refined)", "week 2-3", "up", 350, "high",
     "Refined Sibilant d1->d42: RoA 44x, FR 42x; Refined catalysts week1->week6: +400 to +1,100% (S1). Since 0.5.0 they come only from the Genesis Tree (S4)."),
    ("Breachstone / Breach splinters", "week 4+", "mixed", 50, "low",
     "FR Breachstone 0.73->2.8 (d42)->4.5 Div (d70); RoA 0.59->0.38 (-36%). Breach Splinter d0->d42: FR 10x, FotV 4.6x, RoA flat (S1)."),
    ("Simulacrum (Delirium pinnacle)", "week 2-3", "mixed", 0, "low",
     "RoA 6.75 (d1) -> 2.2 (d21); FR 2.9 -> 2.1 (d42), then 4.7 (d56) (S1)."),
    ("Abyss: Preserved Cranium", "week 2-3", "up", 170, "high",
     "d0->d42: 19x, 71x, 88x; FR peaked 33 Div at d56 (S1)."),
    ("Abyss: Preserved Rib / Gnawed bones", "week 1", "down", -50, "high",
     "Preserved Rib d0->d6: -57/-63/-48%; d0->d42 -94/-100/-98% (S1)."),
    ("Abyss: Ancient bones (Collarbone, Rib, Jawbone)", "week 4+", "up (unless a patch adds supply)", 60, "medium",
     "Ancient Collarbone d21->d42: FotV +252%, RoA +59%, FR -7%; d0->d42: FotV 52x, FR 6.7x. RoA rose 11x to d14, then fell -88% in a week (13 -> 1.6 Div) after 0.5.3 (Jun 18, RoA d20) let the Vessel of Kulemak drop Ancient bones (S1, S4)."),
    ("Verisium (RoA mechanic currency)", "week 2-3", "down (RoA) / flat (FR)", -30, "low",
     "Category median d6->d21: RoA -61%, FR +2%; d0->d42: RoA -63%, FR -56% (S1)."),
    ("Exchange liquidity (traded volume index)", "week 4+", "down", -75, "medium",
     "Exalted units per hourly digest, from the peak: FR peak d4, -86% by d42, -98% by d77; RoA peak d21, -65% d42, -93% d70; FotV peak d28, -81% d70. Divine volume peaks later (d21-42). Unit semantics of the digest not documented; use as a relative index (S1)."),
    ("Patch-driven supply shock (any item)", "week 2-3", "down", -80, "medium",
     "Examples: RoA Ancient Collarbone -88% in 7 days after 0.5.3 (S1, S4); 0.4.0d Immured Fury fix expected to lower Fracturing (S13, seller); 0.4 temple diminishing returns (Jan 3 2026) cut temple yields from 'hundreds of Div' to ~20 (S6)."),
]

STRATS = [
    ("day 1-3", "Swap spare Exalted Orbs into Divines (and in 0.5-style leagues Chaos) as soon as you have them; keep only the Ex you will spend this week.",
     "Ex lost 53-79% of its Divine value by day 6 and 83-92% by day 28 in all three launches. Chaos gained 50-170% vs Div in week 1 of both 0.5 leagues.", "high"),
    ("day 1-3", "Sell the crash group the same day you loot it: low-tier essences, Diluted/low liquid emotions, Greater/Lesser Jeweller's, Greater Exalted, low-tier runes, weak omens (Liege, Putrefaction), low Uncut Support gems, Preserved Ribs, non-meta lineage gems.",
     "These fell 80-99% in Divine terms by week 2-6 in 3/3 leagues. The day 1-7 list is in playbook.json; this extends it to week 6.", "high"),
    ("day 1-3", "Do NOT sell the appreciating group early unless you need the currency for your farming setup: top crafting omens, Hinekora's Lock, Architect's Orb, Crystallised Corruption, Vaal Infusers, Preserved Cranium, Trialmaster Fates, Refined catalysts, Uncut Spirit gems level 7+, chase lineage gems, Essence of Delirium.",
     "Each rose 5x-90x in Divine terms from day 1 to day 42 in at least 2 of 3 leagues (most in 3/3).", "high"),
    ("day 1-3", "Spend early currency on what speeds up your farming (league-start build, atlas progress, tablets). Don't buy luxury or speculative gear in the first 48 hours.",
     "Unique prices are 'most irrational in the first 72 hours' (S8, low). Fubgun: rush the atlas, sell tradeables at once, play a build that clears pinnacles for 10 Div or less (S14, S15). Inference: early farming speed compounds; a 5x hold return on a few Div is smaller than a faster atlas.", "medium"),
    ("week 1", "Sell the week-1 spikes into peak demand around days 5-14: common soul cores (Tacati), Uncut Skill Gem (Level 20), Omen of Chaotic Quantity, Orb of Chance (days 2-4).",
     "Tacati peaked on d10 (3-11x day 0) and then lost 58-83% by d42. Uncut Skill 20 rose 3-7x by d6, then fell or went flat in 2 of 3 leagues. Chaotic Quantity peaked d6-21.", "high"),
    ("week 1", "Buy the Divine-denominated inputs you'll need later (fragments for bossing, Hinekora's Lock, top omens for your craft) in week 1 rather than week 4+.",
     "Fates, Hinekora's Lock and the top omens went up 20-50x in Div between day 1 and day 42. Buying early is cheaper even after counting the risk.", "medium"),
    ("week 2-3", "Bulk-sell and list big items during weeks 2-3, when the exchange is most liquid.",
     "Exalted volume peaked d4-d28 and Divine volume d21-42. By week 6-10 exchange volume is down 65-98% from its peak, so fills get slow and prices thin out.", "medium"),
    ("week 2-3", "Run Orb of Annulment and Fracturing as farm targets/sales in weeks 2-3, not late.",
     "Annulment peaked d10-21 (3-6x day 0) and was down 25-66% by week 10. Fracturing is volatile and patch-driven.", "medium"),
    ("week 2-3", "Watch every patch for 'now also drops from X' lines. Sell the item before the patch goes live or right after.",
     "0.5.3 added Ancient bones to the Vessel of Kulemak, and Ancient Collarbone fell 88% within a week (RoA). GGG nerfs strong loops within ~1-2 weeks and doesn't roll back wealth (S6, S16).", "high"),
    ("week 2-3", "Be first to a new or broken-but-legal farm and farm it hard in its first days, then switch.",
     "0.4 temple farming paid up to hundreds of Div per run until the Jan 3 diminishing-returns change. Early farmers kept their wealth (S6, S5). Gear prices jumped 70-90 -> 200 Div in a day after the temple videos (S5).", "medium"),
    ("week 4+", "Sell held appreciating items between about day 35 and day 60: omens, Hinekora's Lock, Fates, Cranium, chase lineage gems, spirit gems.",
     "Most of these peaked or plateaued around d42-56 and some fell after (FotV Omen of Light 34.5 -> 18.7 Div d56->d70). Liquidity falls fast after week 6.", "medium"),
    ("week 4+", "Late in the league, hold Exalted for spending and Divines for saving; don't over-convert into Divines after about week 6.",
     "Div:Ex fell 25-34% from its peak by the last sample in all three leagues, so Ex recovers some value late.", "medium"),
    ("week 4+", "Spend or convert everything before the league ends. The 1.0 launch is a fresh economy.",
     "End-of-league value doesn't carry to a new league. The 1.0 launch is reported for Dec 11 2026 (S17), not Dec 4.", "high"),
    ("any", "Flip on the Currency Exchange only on liquid pairs, with tight ratios and small size. The real 'flip' is the time trend (Ex->Div/Chaos early; hold appreciating items to week 5-8).",
     "Maxroll measured flips worth ~10-20% margin per cycle on catalysts in 0.2 (S18). Our hourly digests show ~10% intra-hour ratio ranges on liquid pairs (Chaos/Div, Omen of Light/Div) but the public data has no order book, so the real spread can't be measured. The week-1 Ex->Div trend alone was worth 2-5x.", "medium"),
]

SOURCES = [
    ("S1 GGG Currency Exchange history (public hourly digests; 20 sampled hours, days 10-70 of three leagues)", "https://web.poecdn.com/api/currency-exchange/poe2"),
    ("S2 Exile Oracle local DB: ls_price (days 0-6 of 3 launches), ex_price (Forbidden Rites days 63-77)", "file:<data folder>/data/poe2kit.db"),
    ("S3 Exile Oracle league-start playbook (datapack/playbook.json)", "datapack/playbook.json"),
    ("S4 GGG patch notes 0.5.0-0.5.4b (official Steam announcements, stored in app DB)", "https://store.steampowered.com/news/app/2694490"),
    ("S5 Gamepressure: players complain about the death of the new season (temples, Dec 29 2025)", "https://www.gamepressure.com/newsroom/poe-2-players-complain-about-the-death-of-the-new-season-all-beca/z78b67"),
    ("S6 PCGamesN: temple diminishing-returns patch notes", "https://www.pcgamesn.com/path-of-exile-2/patch-notes-temple-diminishing-returns"),
    ("S7 PoE forum: 800 Divines for Gear? (Dec 2025)", "https://www.pathofexile.com/forum/view-thread/3900276"),
    ("S8 Switchblade Gaming: PoE 2 economy guide", "https://www.switchbladegaming.com/path-of-exile-2/economy-guide-4/"),
    ("S9 outof.games PoE 2 economy tracker (Omen of Light)", "https://outof.games/realms/poe2/economy/omens/omen-of-light/"),
    ("S10 timesaver.gg: Divine/Exalted value end of league 740:1 (seller site)", "https://timesaver.gg/blog/poe2-divine-exalted-value-end-of-league-740-to-1"),
    ("S11 timesaver.gg: Divine:Exalted rate Forbidden Rites 0.5.5 (seller site)", "https://timesaver.gg/blog/poe2-divine-exalted-exchange-rate-forbidden-rites-0-5-5"),
    ("S12 PCGamesN: Return of the Ancients makes Divine Orbs more common", "https://www.pcgamesn.com/path-of-exile-2/return-of-the-ancients-divine-orbs"),
    ("S13 iGGM: patch 0.4.0d economy changes (seller site)", "https://www.iggm.com/news/poe-2-patch-0-4-0d-will-bring-economy-changes"),
    ("S14 vortexgaming: Fubgun 0.5 league start plan (secondhand summary)", "https://vortexgaming.io/en/postdetail/985241"),
    ("S15 kami-labs: league start tier list 0.5.5 (Fubgun's criteria)", "https://kami-labs.fr/en/path-of-exile-2/tier-list-league-start-poe2-0-5-5/"),
    ("S16 PCGamer: director on temple exploiters", "https://pcgamer.com/games/rpg/path-of-exile-2-director-says-players-exploiting-system-to-become-in-game-millionaires-ruined-christmas-for-me-and-joked-that-hes-lost-all-sympathy-for-everyone-who-took-advantage-of-it/"),
    ("S17 RPG Site: PoE 2 1.0 full release on December 11", "https://www.rpgsite.net/news/21188-path-exile-2-reaches-its-10-full-release-on-december-11"),
    ("S18 Maxroll: Flipping with the Currency Exchange", "https://maxroll.gg/poe2/resources/flipping-with-the-currency-exchange"),
    ("S19 iGGM: PoE 2 1.0 curb inflation (0.3 ratio history; seller site)", "https://www.iggm.com/news/poe-2-1-0-curb-inflation-keep-new-players-around"),
    ("S20 MMOGah: PoE currency price history (PoE 1 RMT decay; seller site, snippet only)", "https://www.mmogah.com/news/poe/poe-currency-price-history"),
    ("S21 PCGamesN: 0.2.0g patch notes (loot buff)", "https://www.pcgamesn.com/path-of-exile-2/update-020g-patch-notes"),
    ("S22 Sportskeeda: Breach nerfed in Dawn of the Hunt", "https://sportskeeda.com/mmo/breach-getting-nerfed-path-exile-2-dawn-the-hunt-ggg-confirms"),
    ("S23 Gamepressure: Ritual exploit fixed (0.2.0d)", "https://www.gamepressure.com/newsroom/ritual-exploit-in-poe2-is-fixed-now-according-to-patch-notes-deve/z17cb5"),
    ("S24 PoE forum thread 3669686 (0.1: 1 Div = 99 ex, Dec 2024)", "https://www.pathofexile.com/forum/view-thread/3669686/page/2"),
]

ser = json.load(open(SER, encoding='utf-8'))['series']
curves, ratios = {}, {}
for lg, days in ser.items():
    ratios[lg] = {d: {'ex_per_div': round(v['div_ex'], 1),
                      'chaos_per_div': round(v['chaos_per_div'], 2) if v['chaos_per_div'] else None}
                  for d, v in days.items()}
    for n in KEY:
        for d, v in days.items():
            x = v['items'].get(n)
            if x and x[0]:
                curves.setdefault(n, {}).setdefault(lg, {})[d] = round(x[0], 6 if x[0] < 0.01 else 4)

out = {
    'made': ACC,
    'about': ('Exile Oracle market research R7. Prices in Divine Orbs. Leagues: Fate of the Vaal (0.4, start '
              '2025-12-12), Runes of Aldur (0.5, 2026-05-29), Forbidden Rites (0.5.5, 2026-09-04). Day 0 = first 24 h '
              'on the exchange. Days 0-6 are daily medians; days 10-70 are single sampled hours (12:00 after the day '
              'mark); Forbidden Rites days 63-77 are daily medians from the app\'s own sync. Exchange items only: '
              'no unique items. typical_change_pct is the change in DIVINE terms over the phase (median of the '
              'leagues in the evidence unless stated; where the evidence quotes a longer window, e.g. d0->d6, the pct follows it, so read the evidence).'),
    'phases': {'day 1-3': 'league days 0-2', 'week 1': 'days 3-6', 'week 2-3': 'days 7-21', 'week 4+': 'day 22 on'},
    'patterns': [dict(item_group=g, phase=ph, direction=dr, typical_change_pct=pct, confidence=c, evidence=e)
                 for g, ph, dr, pct, c, e in P],
    'strategies': [dict(phase=ph, action=a, why=w, confidence=c) for ph, a, w, c in STRATS],
    'sources': [dict(title=t, url=u, accessed=ACC) for t, u in SOURCES],
    'ratios': ratios,
    'curves_div': curves,
    'caveats': [
        'Days 10-70 are one hour each: single-hour noise of +-20% is normal on thin items.',
        'The digest volume fields have no documented units; liquidity numbers are a relative index only.',
        'Runes of Aldur days 108-119 come from after Forbidden Rites opened and are thin.',
        'Seller-site numbers (timesaver, iggm, mmogah, aoeah) are low confidence and are used only to cross-check.',
        'Unique items (chase uniques) are not on the exchange, so no curve for them here.',
    ],
}
json.dump(out, open(OUT, 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
print(len(P), 'patterns', len(STRATS), 'strategies', len(curves), 'curves')
