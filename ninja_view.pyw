"""View a player's poe.ninja character page inside Exile Oracle, and save their build on request.

    pythonw ninja_view.pyw <account/character path> <league slug> <league name>

Opens the ONE page the player clicked (a deep link) in a native window with a "Save this build" button on top.
Pressing it reads that page's Path of Building export (already on the page) and adds it to the vault through
the monitor. Nothing is read in the background, nothing else on poe.ninja is visited, and poe.ninja's
builds/profile API is never called (it is closed to third parties)."""

import json
import os
import sys
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

PORT = int(os.environ.get('POE2KIT_PORT', '47830'))
MONITOR = f'http://127.0.0.1:{PORT}/'

# Finds the Path of Building export on the page: poe.ninja keeps it in a field (sometimes only after its
# "Path of Building" button is pressed). Returns the longest PoB-looking value, or ''.
FIND_CODE = r'''(() => {
  const pob = v => v && v.length > 800 && /^[A-Za-z0-9_\-+/=]+$/.test(v.trim());
  const vals = [...document.querySelectorAll('input, textarea')].map(e => (e.value || '').trim()).filter(pob);
  return vals.sort((a, b) => b.length - a.length)[0] || '';
})()'''
PRESS_EXPORT = r'''(() => {
  const b = [...document.querySelectorAll('button, a')].find(e => /path of building|pob/i.test(e.textContent || ''));
  if (b) { b.click(); return true; } return false;
})()'''
BUTTON = r'''(() => {
  if (document.getElementById('eo-save')) return;
  const bar = document.createElement('div');
  bar.id = 'eo-save';
  bar.style.cssText = 'position:fixed;top:14px;right:20px;z-index:2147483647;display:flex;gap:12px;align-items:center;' +
    'background:#1c1712;border:2px solid #c9a45c;border-radius:6px;padding:12px 16px;box-shadow:0 6px 28px #000c;' +
    'font:600 16px Georgia,serif;color:#e2d6bf;max-width:calc(100vw - 40px);flex-wrap:wrap';
  bar.innerHTML = '<span style="color:#c9a45c;font-size:17px;letter-spacing:.04em">◈ Exile Oracle</span>' +
    '<button id="eo-save-btn" style="background:linear-gradient(#d8304a,#a3192e);color:#fff;border:1px solid #f07080;' +
    'border-radius:4px;padding:12px 22px;font:700 17px Georgia,serif;letter-spacing:.03em;cursor:pointer;' +
    'box-shadow:0 0 14px #c8283c88">💾 Save this build to my vault</button>' +
    '<span id="eo-save-msg" style="font:14px sans-serif;color:#e2d6bf;max-width:320px"></span>';
  document.body.appendChild(bar);
  document.getElementById('eo-save-btn').onclick = async () => {
    const m = document.getElementById('eo-save-msg'); m.textContent = 'reading the page…';
    const r = await window.pywebview.api.save();
    m.textContent = r;
  };
})()'''


class Api:
    def __init__(self, path, slug, league):
        self._path, self._slug, self._league, self._window = path, slug, league, None   # private: not exposed to the page

    def save(self):
        import time
        w = self._window
        code = w.evaluate_js(FIND_CODE)
        if not code:
            w.evaluate_js(PRESS_EXPORT)
            time.sleep(1.5)
            code = w.evaluate_js(FIND_CODE)
        if not code:
            return "Couldn't find the Path of Building export on this page."
        account, _, character = urllib.parse.unquote(self._path).rpartition('/')
        body = json.dumps({'code': code, 'character': character, 'account': account, 'league': self._league,
                           'url': page_url(self._path, self._slug)}).encode()
        try:
            req = urllib.request.Request(MONITOR + 'api/vault/from_ninja', data=body,
                                         headers={'Content-Type': 'application/json'})
            r = json.loads(urllib.request.urlopen(req, timeout=60).read())
        except Exception as e:
            return f'Could not save: {type(e).__name__}'
        return r.get('message') or ('Saved.' if r.get('ok') else (r.get('why') or 'Could not save.'))


def page_url(path, slug):
    return f'https://poe.ninja/poe2/builds/{slug}/character/{path}'


def main():
    path, slug, league = sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else ''
    url = page_url(path, slug)
    try:
        import webview
    except ImportError:
        import webbrowser
        webbrowser.open(url)
        return
    if os.name == 'nt':
        import ctypes
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('ExileOracle.Dashboard')
        except Exception:
            pass
    api = Api(path, slug, league)
    name = urllib.parse.unquote(path).rpartition('/')[2]
    w = webview.create_window(f'{name} · poe.ninja · Exile Oracle', url, js_api=api, width=1400, height=950,
                              background_color='#0c0a09', text_select=True)
    api._window = w
    w.events.loaded += lambda: w.evaluate_js(BUTTON)

    def to_front():
        """Our icon (not Python's), then in front: the background monitor opened it, and Windows would leave it
        behind the dashboard."""
        import time
        from poe2kit import osutil
        h = None
        try:
            h = int(w.native.Handle.ToInt64())
        except Exception:
            for _ in range(20):
                h = osutil.find_window(w.title)
                if h:
                    break
                time.sleep(0.15)
        if h:
            osutil.set_window_icon(h, os.path.join(HERE, 'dashboard', 'poe2kit.ico'))
            osutil.bring_to_front(h)
    w.events.shown += to_front
    from poe2kit import config
    webview.start(gui='edgechromium' if os.name == 'nt' else None, private_mode=False,
                  storage_path=os.path.join(config.HOME, 'webview'))


if __name__ == '__main__':
    main()
