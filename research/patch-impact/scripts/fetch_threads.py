"""Step 1b: fetch the first post of every thread in GGG's PoE 2 patch-notes forum (public, no login) and parse it
into lines with their section heading. Times on the logged-out forum are US Pacific (checked against Steam's UTC
timestamps for 0.5.2-0.5.4b and the 0.1.0 launch), converted here to UTC with US DST rules (stdlib only).

Output: cache/forum/patches_raw.json  [{thread, title, url, posted_pacific, date_utc, lines:[{section,text,parent}]}]
Usage: python fetch_threads.py"""
import datetime as dt
import html
import json
import os
import re
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, 'cache', 'forum')
UA = {'User-Agent': 'poe2-personal-toolkit/0.3 (patch research)'}


def us_pacific_to_utc(s):
    """'Jun 18, 2026, 4:30:00 PM' (America/Los_Angeles) -> aware UTC datetime."""
    t = dt.datetime.strptime(s.strip(), '%b %d, %Y, %I:%M:%S %p')
    y = t.year
    # DST: 2nd Sunday of March 02:00 -> 1st Sunday of November 02:00 (US rules since 2007)
    mar = dt.datetime(y, 3, 8)
    dst_start = mar + dt.timedelta(days=(6 - mar.weekday()) % 7, hours=2)
    nov = dt.datetime(y, 11, 1)
    dst_end = nov + dt.timedelta(days=(6 - nov.weekday()) % 7, hours=2)
    off = 7 if dst_start <= t < dst_end else 8
    return (t + dt.timedelta(hours=off)).replace(tzinfo=dt.timezone.utc)


def get(tid):
    p = os.path.join(CACHE, 'threads', f'{tid}.html')
    if os.path.exists(p):
        return open(p, encoding='utf-8').read(), False
    body = urllib.request.urlopen(urllib.request.Request(f'https://www.pathofexile.com/forum/view-thread/{tid}',
                                                         headers=UA), timeout=60).read().decode('utf-8')
    open(p, 'w', encoding='utf-8').write(body)
    return body, True


def clean(x):
    x = re.sub(r'<[^>]+>', ' ', x)
    return re.sub(r'\s+', ' ', html.unescape(x)).strip()


def parse_post(s):
    """first post body -> lines with section and parent (nested <li>)."""
    j = s.find('<div class="content">', s.find('forumTable'))
    k = s.find('<div class="posted-by">', j)
    body = s[j:k]
    date = re.search(r'<span class="post_date">([^<]+)</span>', s[k:k + 2000])
    lines, section, stack = [], 'General', []
    # tokenise on li / ul / headings / strong
    pos = 0
    for m in re.finditer(r'<(/?)(li|ul|h\d|strong|b)\b[^>]*>', body):
        tag, closing = m.group(2), m.group(1) == '/'
        seg = body[pos:m.start()]
        pos = m.end()
        if stack and stack[-1] is not None and not closing and tag in ('ul', 'li'):
            # text that belongs to the open li before a nested list
            stack[-1]['text'] += ' ' + seg
        elif stack and stack[-1] is not None:
            stack[-1]['text'] += ' ' + seg
        elif tag in ('h3', 'h2', 'h4', 'strong', 'b') and closing:
            t = clean(seg)
            if t and len(t) < 120:
                section = t
        elif not stack or stack[-1] is None:
            t = clean(seg)
            if t and len(t) > 25 and tag not in ('strong', 'b', 'h3', 'h2', 'h4'):
                lines.append({'section': section, 'text': t, 'parent': None, 'depth': 0})
        if tag == 'li' and not closing:
            parent = next((x for x in reversed(stack) if x is not None), None)
            node = {'section': section, 'text': '', 'parent': parent['text_clean'] if parent and 'text_clean' in parent else (clean(parent['text'])[:200] if parent else None),
                    'depth': sum(1 for x in stack if x is not None)}
            if parent is not None:
                parent['text_clean'] = clean(parent['text'])[:200]
            stack.append(node)
            lines.append(node)
        elif tag == 'li' and closing:
            while stack:
                x = stack.pop()
                if x is not None:
                    break
    out = []
    for x in lines:
        t = clean(x['text'])
        if t:
            out.append({'section': x['section'], 'text': t, 'parent': x['parent'], 'depth': x['depth']})
    return out, date.group(1) if date else None


def main():
    os.makedirs(os.path.join(CACHE, 'threads'), exist_ok=True)
    threads = json.load(open(os.path.join(CACHE, 'forum_threads.json'), encoding='utf-8'))
    out = []
    for i, t in enumerate(threads):
        try:
            s, fetched = get(t['thread'])
        except Exception as e:
            print('ERR', t['thread'], t['title'], e)
            time.sleep(5)
            continue
        lines, date = parse_post(s)
        date = date or t['posted_forum_time']
        out.append({'thread': t['thread'], 'title': t['title'],
                    'url': f"https://www.pathofexile.com/forum/view-thread/{t['thread']}",
                    'posted_pacific': date, 'date_utc': us_pacific_to_utc(date).strftime('%Y-%m-%dT%H:%M:%SZ'),
                    'lines': lines})
        if fetched:
            print(i, t['title'], len(lines))
            time.sleep(3)
    out.sort(key=lambda x: x['date_utc'])
    json.dump(out, open(os.path.join(CACHE, 'patches_raw.json'), 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
    print(len(out), 'posts,', sum(len(x['lines']) for x in out), 'lines')


if __name__ == '__main__':
    main()
