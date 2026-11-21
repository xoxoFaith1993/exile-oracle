"""Turn game stat ids + values into the game's own English wording, from its stat description files (.csd).
Original reader for the format (UTF-16 text):

    description
    	2 stat_a stat_b
    	2                                  <- number of English variants
    		1|# # "{0}% increased X"          <- one range per stat, the text, then handlers
    		#|-1 # "{0}% reduced X" negate 1
    	lang "German"                      <- other languages follow; skipped

Ranges: '#' any, 'a|b' (either side may be '#'), '!0' not zero, or a single number. Handlers we apply: negate,
divide_by_one_hundred, per_minute_to_per_second, milliseconds_to_seconds, divide_by_ten_0dp; others are left as is.
"""

import os
import re

_files = {}
TAG = re.compile(r'\[([^\]|]+)\|([^\]]+)\]')


def _parse(path):
    text = open(path, 'rb').read().decode('utf-16-le', errors='replace')
    out = {}
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        if lines[i].strip().startswith('description'):
            head = lines[i + 1].strip().split()
            try:
                n = int(head[0])
            except (ValueError, IndexError):
                i += 1
                continue
            ids = head[1:1 + n]
            try:
                count = int(lines[i + 2].strip())
            except (ValueError, IndexError):
                i += 1
                continue
            variants = []
            for j in range(count):
                ln = lines[i + 3 + j].strip()
                m = re.match(r'^(.*?)"(.*)"(.*)$', ln)
                if not m:
                    continue
                ranges = m.group(1).split()
                handlers = m.group(3).split()
                variants.append((ranges, m.group(2), handlers))
            key = tuple(ids)
            out.setdefault(key, variants)
            for sid in ids:
                out.setdefault(('#by_stat', sid), key)
            i += 3 + count
        else:
            i += 1
    return out


def _load(path):
    if path not in _files:
        _files[path] = _parse(path) if os.path.exists(path) else {}
    return _files[path]


def _match(rng, v):
    if rng == '#':
        return True
    if rng.startswith('!'):
        try:
            return v != float(rng[1:])
        except ValueError:
            return True
    if '|' in rng:
        lo, hi = rng.split('|', 1)
        return (lo == '#' or v >= float(lo)) and (hi == '#' or v <= float(hi))
    try:
        return v == float(rng)
    except ValueError:
        return True


def _apply(handlers, vals):
    vals = list(vals)
    k = 0
    while k < len(handlers):
        h = handlers[k]
        arg = handlers[k + 1] if k + 1 < len(handlers) and handlers[k + 1].isdigit() else None
        idx = int(arg) - 1 if arg else None
        if idx is not None and 0 <= idx < len(vals):
            if h == 'negate':
                vals[idx] = -vals[idx]
            elif h == 'divide_by_one_hundred':
                vals[idx] = vals[idx] / 100
            elif h == 'per_minute_to_per_second':
                vals[idx] = vals[idx] / 60
            elif h == 'milliseconds_to_seconds':
                vals[idx] = vals[idx] / 1000
            elif h == 'divide_by_ten_0dp':
                vals[idx] = round(vals[idx] / 10)
        k += 2 if arg else 1
    return vals


def _fmt(text, vals):
    def num(v):
        return str(int(v)) if float(v).is_integer() else f'{v:.2f}'.rstrip('0').rstrip('.')

    def rep(m):
        i = int(m.group(1))
        v = vals[i] if i < len(vals) else 0
        return ('+' if v >= 0 else '') + num(v) if m.group(2) == ':+d' else num(v)
    out = re.sub(r'\{(\d+)(:\+?d)?\}', rep, text)
    out = TAG.sub(r'\2', out)
    return re.sub(r'\[([^\]|]+)\]', r'\1', out).replace('\\n', '\n')


def describe(stats, files):
    """stats: {stat_id: value}. files: .csd paths in priority order. Returns English lines; unknown stats as
    'stat_id: value' so nothing is silently dropped."""
    left = dict(stats)
    lines = []
    for path in files:
        d = _load(path)
        for sid in list(left):
            if sid not in left:
                continue
            key = d.get(('#by_stat', sid))
            if not key:
                continue
            vals = [left.get(s, 0) for s in key]
            for ranges, text, handlers in d[key]:
                if len(ranges) >= len(vals) and all(_match(r, v) for r, v in zip(ranges, vals)):
                    if text.strip():
                        lines.append(_fmt(text, _apply(handlers, vals)))
                    break
            for s in key:
                left.pop(s, None)
    lines += [f'{s}: {v}' for s, v in left.items() if v]
    return lines
