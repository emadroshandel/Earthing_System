/* EarthSystem — dual-mode boot.
 *
 * The same interface runs two ways:
 *
 *   server mode   python server.py serves this page and answers /api/* over HTTP
 *   browser mode  the page is opened from GitHub Pages with no server at all;
 *                 Pyodide runs the identical earthsys package inside the browser
 *                 and window.fetch is patched so that /api/* calls it directly
 *
 * app.js never learns which one it is in.
 */
'use strict';

window.ES = (function () {
  const isFile = location.protocol === 'file:';
  // In server mode the app is served from the site root; on GitHub Pages it
  // lives in /<repo>/web/, so assets one level up need a "../" prefix.
  const inWebFolder = /\/web\/?$/.test(location.pathname) ||
    /\/web\/index\.html$/.test(location.pathname);
  const base = inWebFolder ? '../' : '';

  return {
    base,
    mode: 'unknown',
    asset: p => base + p,
    ready: null,
  };
})();

(function () {
  const MODULES = [
    '__init__.py', 'materials.py', 'soil.py', 'conductor.py', 'faultcurrent.py',
    'ieee80.py', 'bem.py', 'iec60364.py', 'iec62305.py', 'ieee142.py',
    'airterm.py', 'reasoning.py', 'report.py', 'api.py',
  ];
  const PYODIDE = 'https://cdn.jsdelivr.net/pyodide/v0.28.3/full/';

  function splash(msg, sub, pct) {
    let el = document.getElementById('boot');
    if (!el) {
      el = document.createElement('div');
      el.id = 'boot';
      el.innerHTML = `<div class="bootbox">
        <div class="bootlogo">⏚</div>
        <h2>EarthSystem</h2>
        <p id="bootmsg"></p>
        <div class="bootbar"><i id="bootbar"></i></div>
        <p class="bootsub" id="bootsub"></p></div>`;
      document.body.appendChild(el);
    }
    if (msg) document.getElementById('bootmsg').textContent = msg;
    if (sub !== undefined) document.getElementById('bootsub').textContent = sub;
    if (pct !== undefined) document.getElementById('bootbar').style.width = pct + '%';
  }

  function done() {
    const el = document.getElementById('boot');
    if (el) { el.style.opacity = '0'; setTimeout(() => el.remove(), 350); }
  }

  async function haveServer() {
    if (location.protocol === 'file:') return false;
    try {
      const r = await fetch('api/health', { method: 'GET' });
      if (!r.ok) return false;
      const j = await r.json();
      return !!j.ok;
    } catch (e) { return false; }
  }

  async function bootPyodide() {
    splash('Starting the calculation engine in your browser…',
           'This happens once; the files are then cached by the browser.', 5);

    await new Promise((res, rej) => {
      const s = document.createElement('script');
      s.src = PYODIDE + 'pyodide.js';
      s.onload = res; s.onerror = () => rej(new Error('Could not load Pyodide.'));
      document.head.appendChild(s);
    });

    splash('Loading Python…', 'about 10 MB, once', 20);
    const py = await loadPyodide({ indexURL: PYODIDE });

    splash('Loading numpy…', 'needed by the boundary-element solver', 45);
    await py.loadPackage('numpy');

    splash('Loading the EarthSystem engine…', '', 70);
    py.FS.mkdirTree('/home/pyodide/earthsys');
    const texts = await Promise.all(MODULES.map(async m => {
      const r = await fetch(window.ES.asset('earthsys/' + m));
      if (!r.ok) throw new Error('Missing earthsys/' + m);
      return [m, await r.text()];
    }));
    for (const [name, src] of texts) {
      py.FS.writeFile('/home/pyodide/earthsys/' + name, src);
    }

    splash('Starting up…', '', 90);
    await py.runPythonAsync(`
import sys, json
sys.path.insert(0, "/home/pyodide")
import earthsys.api as _api

def _call(path, payload_json):
    try:
        payload = json.loads(payload_json or "{}")
        return json.dumps(_api.dispatch(path, payload), allow_nan=False)
    except KeyError:
        return json.dumps({"error": "Unknown endpoint " + path})
    except Exception as exc:                     # surfaced in the interface
        return json.dumps({"error": "%s: %s" % (type(exc).__name__, exc)})
`);
    const call = py.globals.get('_call');

    // Patch fetch so app.js keeps talking to "/api/..." exactly as before.
    const nativeFetch = window.fetch.bind(window);
    window.fetch = async (input, init) => {
      const url = typeof input === 'string' ? input : (input && input.url) || '';
      const i = url.indexOf('/api/');
      if (i === -1) return nativeFetch(input, init);
      const path = url.slice(i).split('?')[0];
      if (path === '/api/health') {
        return new Response(JSON.stringify({ ok: true, browser: true }),
                            { status: 200, headers: { 'Content-Type': 'application/json' } });
      }
      const body = (init && init.body) || '{}';
      const out = call(path, body);
      let parsed;
      try { parsed = JSON.parse(out); } catch (e) { parsed = { error: 'Bad engine response.' }; }
      return new Response(out, {
        status: parsed && parsed.error ? 400 : 200,
        headers: { 'Content-Type': 'application/json' },
      });
    };

    window.ES.mode = 'browser';
    splash('Ready', '', 100);
    setTimeout(done, 250);
  }

  window.ES.ready = (async () => {
    if (await haveServer()) {
      window.ES.mode = 'server';
      return;
    }
    try {
      await bootPyodide();
    } catch (err) {
      splash('The calculation engine could not start.',
             (err && err.message) || String(err), 100);
      const b = document.getElementById('boot');
      if (b) b.classList.add('failed');
      throw err;
    }
  })();
})();
