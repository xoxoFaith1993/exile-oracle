"""Command line for the PoE 2 toolkit:
    python cli.py status | refresh | price <name> | movers [hours] | builds
    python cli.py watch-overlay [minutes]   wait for the next item sent with the overlay's Ask Claude button, print
                                            it and exit (a Claude Code chat runs this in the background to get the
                                            item straight into the chat; default: wait up to 55 minutes)"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import server  # noqa: E402  (reuses the MCP tool functions)


def main(argv):
    cmd = argv[0] if argv else 'status'
    if cmd == 'status':
        out = server.t_status({})
    elif cmd == 'refresh':
        out = server.t_refresh({'max_hours': 48})
    elif cmd == 'price':
        out = server.t_price({'query': ' '.join(argv[1:])})
    elif cmd == 'movers':
        out = server.t_movers({'hours': float(argv[1]) if len(argv) > 1 else 24})
    elif cmd == 'builds':
        out = server.t_vault_list({})
    elif cmd == 'watch-overlay':
        return watch_overlay(float(argv[1]) if len(argv) > 1 else 55)
    else:
        print(__doc__)
        return 1
    print(json.dumps(out, indent=1, ensure_ascii=False, default=str))
    return 0


def watch_overlay(minutes):
    """Block until a new item arrives in the Ask Claude list, then print it for the waiting Claude chat."""
    import time
    from poe2kit import overlaysrv
    first = overlaysrv.inbox(1)
    seen = first[0]['ts'] if first else 0
    end = time.time() + minutes * 60
    while time.time() < end:
        items = [i for i in overlaysrv.inbox(5) if i['ts'] > seen]
        if items:
            it = items[0]
            t = it.get('trade') or {}
            short = {'sent': 'from the PoE 2 price check overlay (Ask Claude)', 'item_text': it['item_text'],
                     'headline': it.get('headline'), 'poe_ninja': it.get('ninja'),
                     'trade': {k: t.get(k) for k in ('total', 'low_div', 'median_div', 'searched_for')} |
                              {'cheapest': [f"{l['amount']} {l['currency']} (ilvl {l.get('ilvl')})"
                                            for l in (t.get('listings') or [])[:10]]},
                     'craft_estimate': it.get('craft_estimate'), 'ex_per_div': it.get('ex_per_div'),
                     'next': 'Answer the player in the chat (keep / sell for how much / craft / use in their build; '
                             'poe2_whatif for build fit), then start this watcher again.'}
            print(json.dumps(short, indent=1, ensure_ascii=False, default=str))
            return 0
        time.sleep(1)
    print(json.dumps({'sent': None, 'next': 'Nothing sent in this window: start the watcher again to keep listening.'}))
    return 0


if __name__ == '__main__':
    code = main(sys.argv[1:])
    if os.environ.get('POE2KIT_PAUSE'):
        input('\nPress Enter to close...')
    sys.exit(code)
