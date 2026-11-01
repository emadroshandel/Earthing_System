/*
 * Earthing System — earthing system design to IEEE 80, IEC 60364, IEC 62305 and IEEE 142.
 * Copyright (C) 2026 Emad Roshandel
 *
 * This program is free software: you can redistribute it and/or modify it under
 * the terms of the GNU General Public License as published by the Free Software
 * Foundation, either version 3 of the License, or (at your option) any later
 * version.
 *
 * This program is distributed in the hope that it will be useful, but WITHOUT ANY
 * WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
 * PARTICULAR PURPOSE. See the GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License along with
 * this program. If not, see <https://www.gnu.org/licenses/>.
 */

/* The calculation engine of the browser mode, in a background thread (1.9.0).
 *
 * boot.js starts this worker and sends it {type: 'init', pyodide, files}: the
 * Pyodide address and the absolute addresses of the earthsys modules.  The
 * worker loads Python, numpy and the package, then answers
 * {type: 'call', id, path, body} with {type: 'result', id, out}, out being the
 * JSON text that server.py would have sent.  Calls are answered one at a time
 * in the order they arrive, as the server answers them; the page stays
 * responsive meanwhile because none of this runs on its thread.
 */
'use strict';

let call = null;

function progress(msg, sub, pct) {
  self.postMessage({ type: 'progress', msg, sub, pct });
}

async function init(m) {
  progress('Loading Python…', 'about 10 MB, once', 20);
  importScripts(m.pyodide + 'pyodide.js');
  const py = await loadPyodide({ indexURL: m.pyodide });

  progress('Loading numpy…', 'needed by the boundary-element solver', 45);
  await py.loadPackage('numpy');

  progress('Loading the Earthing System engine…', '', 70);
  py.FS.mkdirTree('/home/pyodide/earthsys');
  const texts = await Promise.all(m.files.map(async ([name, url]) => {
    const r = await fetch(url);
    if (!r.ok) throw new Error('Missing earthsys/' + name);
    return [name, await r.text()];
  }));
  for (const [name, src] of texts) py.FS.writeFile('/home/pyodide/earthsys/' + name, src);

  progress('Starting up…', '', 90);
  await py.runPythonAsync(m.bootstrap);
  call = py.globals.get('_call');
}

self.onmessage = async ev => {
  const m = ev.data || {};
  if (m.type === 'init') {
    try {
      await init(m);
      self.postMessage({ type: 'ready' });
    } catch (err) {
      self.postMessage({ type: 'failed', error: (err && err.message) || String(err) });
    }
    return;
  }
  if (m.type === 'call') {
    let out;
    if (!call) {
      out = JSON.stringify({ error: 'The calculation engine is still starting.' });
    } else {
      try { out = call(m.path, m.body); }
      catch (err) { out = JSON.stringify({ error: 'Engine error: ' + ((err && err.message) || err) }); }
    }
    self.postMessage({ type: 'result', id: m.id, out });
  }
};
