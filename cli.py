"""Command line for the PoE 2 toolkit: python cli.py status | refresh | price <name> | movers [hours] | builds"""

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
    else:
        print(__doc__)
        return 1
    print(json.dumps(out, indent=1, ensure_ascii=False, default=str))
    return 0


if __name__ == '__main__':
    code = main(sys.argv[1:])
    if os.environ.get('POE2KIT_PAUSE'):
        input('\nPress Enter to close...')
    sys.exit(code)
