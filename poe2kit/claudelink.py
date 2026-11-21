"""Optional "Connect to Claude": registers the toolkit's Claude tools (server.py, an MCP server that only reads the
local database) with the Claude desktop app, so a player who has Claude can ask it about their own data. Nothing is
sent anywhere by the toolkit itself; Claude only sees what its tools return when the player asks.
The desktop app's config is backed up before every change."""

import json
import os
import shutil
import sys
import time

from . import config

NAME = 'poe2'


def _desktop_dirs():
    """Where the Claude desktop app keeps its config. The Store-style packaged app keeps it in its private
    LocalCache folder (programs running outside Claude don't see it at %APPDATA%); the classic installer uses
    %APPDATA%\\Claude. Packaged locations first."""
    import glob
    if os.name != 'nt':   # Linux: Claude desktop (where available) keeps its config in ~/.config/Claude
        return [os.path.join(os.environ.get('XDG_CONFIG_HOME') or os.path.join(os.path.expanduser('~'), '.config'),
                             'Claude')]
    local = os.environ.get('LOCALAPPDATA') or ''
    dirs = [os.path.join(p, 'LocalCache', 'Roaming', 'Claude')
            for p in glob.glob(os.path.join(local, 'Packages', 'Claude_*'))]
    dirs.append(os.path.join(os.environ.get('APPDATA') or '', 'Claude'))
    return dirs


def _desktop_config():
    dirs = _desktop_dirs()
    for d in dirs:
        if os.path.exists(os.path.join(d, 'claude_desktop_config.json')):
            return os.path.join(d, 'claude_desktop_config.json')
    for d in dirs:   # installed but never configured: the package folder, else %APPDATA%
        if os.path.isdir(os.path.dirname(os.path.dirname(os.path.dirname(d)))) and 'Packages' in d or os.path.isdir(d):
            return os.path.join(d, 'claude_desktop_config.json')
    return os.path.join(dirs[-1], 'claude_desktop_config.json')


def _python():
    from . import osutil
    return osutil.console_python()   # a console Python: MCP talks over stdin/stdout


def server_entry():
    return {'command': _python(), 'args': [os.path.join(config.ROOT, 'server.py')]}


def status():
    p = _desktop_config()
    installed = os.path.isdir(os.path.dirname(p)) or 'Packages' in p
    registered = False
    if os.path.exists(p):
        try:
            registered = NAME in (json.load(open(p, encoding='utf-8')).get('mcpServers') or {})
        except (OSError, ValueError):
            pass
    e = server_entry()
    return {'desktop_installed': installed, 'registered': registered, 'config': p,
            'claude_code_command': f'claude mcp add {NAME} --scope user -- "{e["command"]}" "{e["args"][0]}"',
            'note': 'Optional. Restart Claude after connecting. Claude reads your toolkit data only when you ask it.'}


def _write(cfg):
    p = _desktop_config()
    os.makedirs(os.path.dirname(p), exist_ok=True)
    if os.path.exists(p):
        shutil.copy2(p, p + time.strftime('.backup-%Y%m%d-%H%M%S'))
    with open(p, 'w', encoding='utf-8') as f:
        json.dump(cfg, f, indent=2)


def _read():
    p = _desktop_config()
    try:
        return json.load(open(p, encoding='utf-8'))
    except (OSError, ValueError):
        return {}


def connect():
    cfg = _read()
    cfg.setdefault('mcpServers', {})[NAME] = server_entry()
    _write(cfg)
    return status()


def disconnect():
    cfg = _read()
    if NAME in (cfg.get('mcpServers') or {}):
        del cfg['mcpServers'][NAME]
        _write(cfg)
    return status()
