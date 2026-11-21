"""Connectors: Exile Oracle's tools (server.py, a standard MCP server) in other AI apps besides Claude.

- ChatGPT: the ChatGPT desktop app and the Codex CLI share ~/.codex/config.toml ([mcp_servers.poe2]).
  Untested by the author (no ChatGPT): marked "untested" until someone confirms it.
- Gemini CLI: ~/.gemini/settings.json ("mcpServers": {"poe2": {...}}).
Claude has its own module (claudelink). Each connect / disconnect only touches our own entry."""

import json
import os
import re
import shutil

from . import claudelink

NAME = 'poe2'
HOME = os.path.expanduser('~')
CODEX = os.path.join(HOME, '.codex', 'config.toml')
GEMINI = os.path.join(HOME, '.gemini', 'settings.json')
BEGIN, END = '# --- Exile Oracle (added by the app) ---', '# --- end Exile Oracle ---'


def _toml_str(s):
    return '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"'


def _codex_block():
    e = claudelink.server_entry()
    return '\n'.join([BEGIN, f'[mcp_servers.{NAME}]', f'command = {_toml_str(e["command"])}',
                      'args = [' + ', '.join(_toml_str(a) for a in e['args']) + ']', END]) + '\n'


def _codex_text():
    try:
        with open(CODEX, encoding='utf-8') as f:
            return f.read()
    except OSError:
        return ''


def _strip_ours(text):
    return re.sub(re.escape(BEGIN) + r'.*?' + re.escape(END) + r'\n?', '', text, flags=re.S)


def _gemini_cfg():
    try:
        with open(GEMINI, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def status():
    codex_text = _codex_text()
    gem = _gemini_cfg()
    return {
        'chatgpt': {'name': 'ChatGPT (desktop app / Codex)', 'tested': False,
                    'found': os.path.isdir(os.path.dirname(CODEX)) or bool(shutil.which('codex')),
                    'connected': BEGIN in codex_text or f'[mcp_servers.{NAME}]' in codex_text, 'file': CODEX,
                    'how': 'Restart the ChatGPT desktop app (or Codex) after connecting; then ask it about your character.'},
        'gemini': {'name': 'Gemini CLI', 'tested': False,
                   'found': os.path.isdir(os.path.dirname(GEMINI)) or bool(shutil.which('gemini')),
                   'connected': NAME in (gem.get('mcpServers') or {}), 'file': GEMINI,
                   'how': 'Start a new gemini session after connecting; /mcp lists the Exile Oracle tools.'},
    }


def connect(target):
    if target == 'chatgpt':
        text = _strip_ours(_codex_text())
        if f'[mcp_servers.{NAME}]' in text:
            return {'ok': False, 'why': f'{CODEX} already has a [mcp_servers.{NAME}] entry you added yourself.'}
        os.makedirs(os.path.dirname(CODEX), exist_ok=True)
        with open(CODEX, 'w', encoding='utf-8') as f:
            f.write(text.rstrip() + ('\n\n' if text.strip() else '') + _codex_block())
        return {'ok': True, 'status': status()}
    if target == 'gemini':
        cfg = _gemini_cfg()
        cfg.setdefault('mcpServers', {})[NAME] = dict(claudelink.server_entry(), trust=False)
        os.makedirs(os.path.dirname(GEMINI), exist_ok=True)
        with open(GEMINI, 'w', encoding='utf-8') as f:
            json.dump(cfg, f, indent=2)
        return {'ok': True, 'status': status()}
    raise ValueError('unknown connector')


def disconnect(target):
    if target == 'chatgpt':
        text = _codex_text()
        if BEGIN in text:
            with open(CODEX, 'w', encoding='utf-8') as f:
                f.write(_strip_ours(text))
        return {'ok': True, 'status': status()}
    if target == 'gemini':
        cfg = _gemini_cfg()
        if NAME in (cfg.get('mcpServers') or {}):
            cfg['mcpServers'].pop(NAME)
            with open(GEMINI, 'w', encoding='utf-8') as f:
                json.dump(cfg, f, indent=2)
        return {'ok': True, 'status': status()}
    raise ValueError('unknown connector')
