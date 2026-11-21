"""Print the markdown tables used in forecast-model.md from forecast-model.json (so the report can be regenerated).
Usage: python -I tables.py <forecast_dir> > tables.md"""
import json, math, os, sys

ROOT = sys.argv[1]
M = json.load(open(os.path.join(ROOT, 'forecast-model.json'), encoding='utf-8'))
B = M['backtest']
R = M['research']
H = ['1', '3', '7', '14']


def pct(x, mult=1, fmt='{:.0f}%'):
    return '-' if x is None else fmt.format(x * mult)


def row(s):
    if not s:
        return '| - | - | - | - | - | - | - | - |'
    e = s['median_abs_error_pct']
    trend = '-' if e['last_week_trend'] is None else f"{e['last_week_trend']:.0f}% (model {e['model_on_trend_subset']:.0f}%)"
    return (f"| {s['n']:,} | {pct(s['coverage_50'], 100)} | {pct(s['coverage_80'], 100)} | "
            f"{e['model']:.0f}% | {e['no_change']:.0f}% | {trend} | "
            f"{pct(s['direction_hit_rate_when_model_calls_10pct_move'], 100)} | "
            f"{pct(s['pinball_skill_vs_no_change'], 100, '{:+.0f}%')} |")


HEAD = ('| n | inside 25-75 (want 50%) | inside 10-90 (want 80%) | median error: model | no change | last-week trend '
        '(model on same cases) | direction right when model calls a >=10% move | pinball skill vs no-change |\n'
        '|---|---|---|---|---|---|---|---|')


def table(title, getter, keys, label='horizon'):
    print(f'\n**{title}**\n')
    print(f'| {label} ' + HEAD.split('\n')[0] + '\n|---' + HEAD.split('\n')[1])
    for k in keys:
        s = getter(k)
        print(f'| {k} ' + row(s))


table('All held-out cases (leave-one-launch-out)', lambda h: B['per_horizon'][h], H)
table('Liquid + medium items only', lambda h: B['per_horizon_liquid_or_medium'][h], H)
for h in ('1', '7'):
    table(f'{h}-day horizon by league phase (days)', lambda k: B['by_phase'][h][k], list(B['by_phase'][h]), 'days')
    table(f'{h}-day horizon by liquidity', lambda k: B['by_liquidity'][h][k], list(B['by_liquidity'][h]), 'liquidity')
    table(f'{h}-day horizon by held-out launch', lambda k: B['by_league'][h][k], list(B['by_league'][h]), 'launch')
table('7-day horizon by category', lambda k: B['by_category']['7'][k], list(B['by_category']['7']), 'category')
table('7-day horizon by the confidence label forecast() gave', lambda k: B['by_confidence']['7'][k], list(B['by_confidence']['7']), 'confidence')
table('Transfer test: Hardcore launches (final model, never trained on HC)', lambda h: B['hardcore_transfer'][h], H)
table('Transfer test: legacy leagues (Standard, old leagues after the next launch; late-league drift)', lambda h: B['legacy_leagues'][h], H)
for v, t in B.get('ablations', {}).items():
    table(f'Ablation {v}', lambda h: t[h]['all'], H)
    table(f'Ablation {v}, liquid items', lambda h: (t[h]['by_liquidity'] or {}).get('liquid'), H)

print('\n**Calibration: share of held-out outcomes below each forecast quantile**\n')
print('| horizon | below p10 | below p25 | below median | below p75 | below p90 |\n|---|---|---|---|---|---|')
for h in H:
    c = B['per_horizon'][h]['calibration']
    print(f'| {h} d | ' + ' | '.join(f"{c[k] * 100:.0f}%" for k in ('p10', 'p25', 'p50', 'p75', 'p90')) + ' |')

print('| horizon | tier | days 0-20 up / down | days 21-48 up / down | day 49+ up / down |\n|---|---|---|---|---|')
for h in H:
    for t, ms in M['momentum'][h].items():
        print(f'| {h} d | {t} | ' + ' | '.join(f"{m['beta_up']:+.2f} / {m['beta_down']:+.2f}" for m in ms) + ' |')

print('\n**Typical surprise size (scale s, all items, in % of price)**\n')
print('| horizon | ' + ' | '.join(H) + ' |\n|---|---|---|---|---|')
print('| s | ' + ' | '.join(f"{(math.exp(M['global']['scale'][h]) - 1) * 100:.0f}%" for h in H) + ' |')

print('\n**Trend continuation (7 days back vs 7 days ahead)**\n')
print('| group | same sign, raw | n | same sign vs typical path | n |\n|---|---|---|---|---|')
for k, v in sorted(R['trend_continuation'].items()):
    print(f"| {k} | {pct(v['raw_same_sign_rate'], 100)} | {v['n']:,} | "
          f"{pct(v['vs_typical_same_sign_rate'], 100)} | {v['n_vs_typical']:,} |")

print('\n**Autocorrelation of surprises**\n')
print('| series | value |\n|---|---|')
for k, v in sorted(R['autocorr'].items()):
    print(f'| {k} | {v} |')

print('\n**After a 1-day spike or crash (>= 2.5x the item\'s usual 1-day surprise and >= 30%)**\n')
print('| event | n | median share given back in 7 days | half or more reversed | kept going |\n|---|---|---|---|---|')
for k, v in sorted(R['spike_reversion'].items(), key=lambda kv: -kv[1]['n']):
    if v['n'] >= 40:
        print(f"| {k} | {v['n']:,} | {v['median_share_given_back_in_7d'] * 100:.0f}% | "
              f"{v['share_of_events_half_reversed'] * 100:.0f}% | {v['share_of_events_extended'] * 100:.0f}% |")

print('\n**Shock days (many items with a lasting level shift on the same league day)**\n')
print('| launch | day | items | usual per day | share up | biggest |\n|---|---|---|---|---|---|')
for s in sorted(R['shock_days'], key=lambda s: -s['items_with_lasting_jump'])[:30]:
    print(f"| {s['league']} | {s['day']} | {s['items_with_lasting_jump']} | {s['baseline_per_day']} | {s['share_up']:.0%} | "
          f"{'; '.join(s['top'][:4])} |")
print(f"\npost-shock scale ratio: {R['post_shock_scale_ratio']}")
print('\n**Spread of the 7-day drift between launches (robust SD of ln change, median over items)**\n')
print('| day | ' + ' | '.join(str(k) for k in R['cross_launch_sd_of_7d_drift_by_day']) + ' |')
print('|---' * (1 + len(R['cross_launch_sd_of_7d_drift_by_day'])) + '|')
print('| sd | ' + ' | '.join(str(v) for v in R['cross_launch_sd_of_7d_drift_by_day'].values()) + ' |')

print('\n**Category typical paths (median price relative to day 1)**\n')
days = ['0', '3', '7', '14', '28', '42', '56', '84']
print('| category | items | ' + ' | '.join('d' + d for d in days) + ' |\n|---' * 1 + '|---' * (len(days) + 1) + '|')
for c, e in sorted(M['category_paths'].items()):
    tp = e.get('typical_path', {})
    print(f"| {c} | {e.get('n_items', 0)} | " + ' | '.join(f"{tp[d]:.2g}x" if d in tp else '-' for d in days) + ' |')
