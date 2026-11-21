"""Tiny reader for PoE stat description files (.csd, UTF-16LE): stat ids + values -> English text.

    from csd import StatText; st = StatText([paths]); st.text(['stat_a', 'stat_b'], [10, 0])

Only the English block of each description is used. Ranges: '#', 'N', 'A|B', '!N'. Handlers supported:
negate, divide_by_one_hundred (and _2dp), per_minute_to_per_second, milliseconds_to_seconds (+_0dp/_1dp),
double, plus the {n:+d} / {n:d} formats. Markup [A|B] -> B, [A] -> A.
"""
import re

_MARK = re.compile(r'\[([^\]|]*)\|([^\]]*)\]|\[([^\]]*)\]')


def _demark(s):
    return _MARK.sub(lambda m: m.group(2) if m.group(2) is not None else m.group(3), s)


def _in(rng, v):
    if rng == '#':
        return True
    if rng.startswith('!'):
        return v != int(rng[1:])
    if '|' in rng:
        a, b = rng.split('|')
        return (a == '#' or v >= int(a)) and (b == '#' or v <= int(b))
    return v == int(rng)


class StatText:
    def __init__(self, paths):
        self.desc = {}   # tuple(stats) -> [(ranges, text, handlers)]
        self.index = {}  # stat -> list of tuple keys
        for p in paths:
            self._load(p)

    def _load(self, path):
        lines = open(path, encoding='utf-16').read().splitlines()
        i = 0
        while i < len(lines):
            if lines[i].strip() == 'description' or lines[i].startswith('description'):
                i += 1
                head = lines[i].split()
                n = int(head[0]); stats = tuple(head[1:1 + n]); i += 1
                cnt = int(lines[i].strip()); i += 1
                variants = []
                for _ in range(cnt):
                    m = re.match(r'\s*(.*?)\s*"(.*)"\s*(.*)$', lines[i])
                    i += 1
                    if not m:
                        continue
                    rngs = m.group(1).split()
                    variants.append((rngs, m.group(2), m.group(3).split()))
                if stats not in self.desc:
                    self.desc[stats] = variants
                    for s in stats:
                        self.index.setdefault(s, []).append(stats)
                continue
            i += 1

    def _fmt(self, variants, vals):
        for rngs, text, hand in variants:
            if len(rngs) != len(vals) or not all(_in(r, v) for r, v in zip(rngs, vals)):
                continue
            vv = list(vals)
            k = 0
            while k < len(hand):
                h = hand[k]
                if h == 'reminderstring':
                    k += 2; continue
                if k + 1 < len(hand) and hand[k + 1].isdigit():
                    j = int(hand[k + 1]) - 1
                    if 0 <= j < len(vv):
                        if h == 'negate':
                            vv[j] = -vv[j]
                        elif h.startswith('divide_by_one_hundred'):
                            vv[j] = vv[j] / 100
                        elif h == 'per_minute_to_per_second':
                            vv[j] = round(vv[j] / 60, 1)
                        elif h.startswith('milliseconds_to_seconds'):
                            vv[j] = vv[j] / 1000
                        elif h == 'double':
                            vv[j] = vv[j] * 2
                    k += 2; continue
                k += 1

            def rep(m):
                j = int(m.group(1)); f = m.group(2) or ''
                v = vv[j] if j < len(vv) else 0
                if isinstance(v, float) and v.is_integer():
                    v = int(v)
                return f'{v:+}' if '+' in f else f'{v}'
            return _demark(re.sub(r'\{(\d+)(?::([^}]*))?\}', rep, text))
        return None

    def text(self, stat_ids, values):
        """Return list of lines describing the given stats (stats without a description are returned raw)."""
        vals = dict(zip(stat_ids, values))
        done, out = set(), []
        for s in stat_ids:
            if s in done:
                continue
            for key in self.index.get(s, []):
                if all(k in vals or k == s for k in key):
                    line = self._fmt(self.desc[key], [vals.get(k, 0) for k in key])
                    done.update(key)
                    if line:
                        out.append(line)
                    break
            else:
                out.append(f'{s} = {vals[s]}')
                done.add(s)
        return out
