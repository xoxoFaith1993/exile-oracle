"""Fail-safes (the author, 2026-11-21: "We need fail safes for absolutely everything ... user-friendly").

Every error that reaches a player goes through explain(): it says in plain words what happened, that their data is
safe, and what to do next. The technical detail is kept for reports and for Claude, never as the headline.
release/chaos_test.py runs every Claude tool and dashboard call with no internet, an empty data folder, no Path of
Building and nonsense input, and fails if a raw Python error would reach the player."""

import re

from . import net

NEXT = 'Your data is safe. Try again in a moment; if it keeps happening, ask the Oracle to run the doctor (poe2_doctor) ' \
       'or use Settings, Report an issue.'


def explain(e):
    """An exception -> {'error': plain words, 'detail': technical, 'kind': short tag}."""
    detail = f'{type(e).__name__}: {e}'
    if isinstance(e, net.NetError):
        return {'error': str(e), 'detail': detail, 'kind': 'offline'}
    import socket
    import urllib.error
    import zlib
    import binascii
    if isinstance(e, (urllib.error.URLError, socket.timeout, ConnectionError, TimeoutError)):
        return {'error': "Can't reach the internet right now (or that site is down). Exile Oracle keeps working with "
                         'what it already saved; try this again when you are online.', 'detail': detail, 'kind': 'offline'}
    if isinstance(e, (zlib.error, binascii.Error)) or 'decompress' in str(e):
        return {'error': "That Path of Building code couldn't be read: it is incomplete or not a PoB code. Copy it "
                         'again (Path of Building: Import/Export, Generate, Copy), or paste a pobb.in link.',
                'detail': detail, 'kind': 'input'}
    msg = str(e)
    if isinstance(e, (ValueError, TypeError)) and re.search(r"int\(\)|float\(\)|could not convert|invalid literal|NoneType", msg):
        return {'error': "Something that should be a number or an id was missing or wasn't one. Check what you "
                         'entered (or pick it again from the list).', 'detail': detail, 'kind': 'input'}
    if isinstance(e, ValueError) and msg and len(msg) < 200 and not re.search(r'[\[\]{}]|Error', msg):
        return {'error': msg[0].upper() + msg[1:], 'detail': detail, 'kind': 'input'}   # our own plain messages
    if isinstance(e, FileNotFoundError):
        return {'error': 'A file this part needs is missing (a fresh install still setting up, or a data update that '
                         "didn't finish). " + NEXT, 'detail': detail, 'kind': 'missing'}
    return {'error': "This part hit a problem it didn't expect. " + NEXT, 'detail': detail, 'kind': 'bug'}


def for_ai(e):
    """The same, written for the AI app (Claude, ChatGPT, Gemini) as a tool result."""
    x = explain(e)
    return (f"{x['error']}\n[for you, the assistant: {x['detail']}. Tell the player in one plain line (not the "
            "technical part), then work around it: another tool, saved data, or ask them. If it repeats, call "
            "poe2_doctor.]")
