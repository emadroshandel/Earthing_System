/* Earthing System — 3-D electrode view (1.10.0)
 * Copyright (C) 2026 Emad Roshandel — GPL-3.0-or-later
 * three.js 0.182.0 (MIT) is vendored in web/vendor/three, loaded via the import map.
 *
 * Draws the solved electrode system of the Numerical solver page in the soil:
 *   - every boundary-element segment as one instance of a single InstancedMesh
 *     (one draw call however many segments), coloured by leakage current
 *     density on the Plasma scale used by the 2-D current plot
 *   - the earth-surface potential as a translucent Viridis-coloured sheet,
 *     the same scale as the surface-potential map
 *   - the worst touch and step locations as markers
 * Depth is exaggerated (adjustable) because grids are tens of metres wide and
 * half a metre deep. Rendering is on demand: nothing runs between interactions.
 * If WebGL is unavailable render() returns false and the page falls back to
 * the Plotly wireframe.
 */
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

const VIRIDIS = ['#440154', '#482878', '#3e4989', '#31688e', '#26828e', '#1f9e89', '#35b779', '#6ece58', '#b5de2b', '#fde725'];
const PLASMA = ['#0d0887', '#46039f', '#7201a8', '#9c179e', '#bd3786', '#d8576b', '#ed7953', '#fb9f3a', '#fdca26', '#f0f921'];
const REDUCED = matchMedia('(prefers-reduced-motion: reduce)');

const hex = h => [parseInt(h.slice(1, 3), 16) / 255, parseInt(h.slice(3, 5), 16) / 255, parseInt(h.slice(5, 7), 16) / 255];
const SV = VIRIDIS.map(hex), SP = PLASMA.map(hex);
function ramp(stops, t, out) {
  t = Math.min(1, Math.max(0, isFinite(t) ? t : 0)) * (stops.length - 1);
  const i = Math.min(stops.length - 2, Math.floor(t)), f = t - i, a = stops[i], b = stops[i + 1];
  /* the stops are sRGB; three works in linear sRGB, so convert on the way in */
  return out.setRGB(a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f, a[2] + (b[2] - a[2]) * f, THREE.SRGBColorSpace);
}
const cssGrad = stops => `linear-gradient(90deg,${stops.join(',')})`;
const cssVar = v => getComputedStyle(document.body).getPropertyValue(v).trim() || '#888';
const fmt = v => {
  if (typeof v !== 'number' || !isFinite(v)) return '—';
  const a = Math.abs(v);
  if (a !== 0 && (a >= 1e5 || a < 1e-3)) return v.toExponential(2);
  return (+v.toPrecision(4)).toLocaleString();
};

let SUPPORT = null;
function webgl() {
  if (SUPPORT !== null) return SUPPORT;
  try {
    const c = document.createElement('canvas');
    SUPPORT = !!(window.WebGL2RenderingContext && c.getContext('webgl2'));
  } catch (e) { SUPPORT = false; }
  return SUPPORT;
}

class GridView {
  constructor(host) {
    this.host = host;
    host.innerHTML = '';
    host.dataset.three = '1';
    const wrap = this.wrap = document.createElement('div');
    wrap.className = 'g3d';
    wrap.innerHTML = `
      <div class="g3d-bar" role="toolbar" aria-label="3-D view controls">
        <button type="button" data-v="iso">Reset view</button>
        <button type="button" data-v="top">Plan</button>
        <button type="button" data-v="side">Elevation</button>
        <button type="button" data-t="surf" aria-pressed="true">Surface potential</button>
        <button type="button" data-t="soil" aria-pressed="true">Soil box</button>
        <label>Depth ×<input type="range" min="1" max="30" step="1" value="12" aria-label="Depth exaggeration"><output>12</output></label>
      </div>
      <div class="g3d-legend" aria-hidden="true">
        <div class="g3d-key"><b>Leakage current density (A/m²)</b><i style="background:${cssGrad(PLASMA)}"></i><span><em data-k="jlo"></em><em data-k="jhi"></em></span></div>
        <div class="g3d-key" data-k="vkey"><b>Earth-surface potential (V)</b><i style="background:${cssGrad(VIRIDIS)}"></i><span><em data-k="vlo"></em><em data-k="vhi"></em></span></div>
        <div class="g3d-key" data-k="mkey"><b>Markers</b><span><em>▲ worst touch</em><em>◆ worst step</em></span></div>
      </div>
      <div class="g3d-help" aria-hidden="true">Drag to rotate · right-drag to pan · wheel to zoom.
        Keyboard (click the view first): arrows rotate, + / − zoom, R resets.</div>
      <div class="g3d-tip" hidden></div>
      <p class="sr-only" aria-live="polite"></p>`;
    host.appendChild(wrap);
    this.tip = wrap.querySelector('.g3d-tip');
    this.sum = wrap.querySelector('p.sr-only');

    const r = this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: 'high-performance' });
    r.setPixelRatio(Math.min(devicePixelRatio || 1, 2));
    r.setClearColor(0x000000, 0);
    r.outputColorSpace = THREE.SRGBColorSpace;
    const cv = r.domElement;
    cv.tabIndex = 0;
    cv.setAttribute('role', 'img');
    cv.setAttribute('aria-label', '3-D view of the electrodes in the soil');
    wrap.insertBefore(cv, wrap.firstChild);

    this.scene = new THREE.Scene();
    this.camera = new THREE.PerspectiveCamera(40, 1, 0.05, 5000);
    this.camera.up.set(0, 0, 1);                       // engine axes: z up
    this.scene.add(new THREE.HemisphereLight(0xffffff, 0x404850, 2.4));
    const sun = new THREE.DirectionalLight(0xffffff, 1.4);
    sun.position.set(1, -1.5, 2);
    this.scene.add(sun);

    const c = this.controls = new OrbitControls(this.camera, cv);
    c.enableDamping = false;                           // render on demand, no idle loop
    c.screenSpacePanning = true;
    c.addEventListener('change', () => this.draw());

    this.ray = new THREE.Raycaster();
    this.ptr = new THREE.Vector2();
    this.exag = 12;
    this.show = { surf: true, soil: true };

    wrap.querySelectorAll('[data-v]').forEach(b => b.onclick = () => this.view(b.dataset.v));
    wrap.querySelectorAll('[data-t]').forEach(b => b.onclick = () => {
      const k = b.dataset.t; this.show[k] = !this.show[k];
      b.setAttribute('aria-pressed', String(this.show[k]));
      if (k === 'surf' && this.surf) { this.surf.visible = this.show.surf; wrap.querySelector('[data-k="vkey"]').style.display = this.show.surf ? '' : 'none'; }
      if (k === 'soil' && this.soil) this.soil.visible = this.show.soil;
      this.draw();
    });
    const rng = wrap.querySelector('input[type=range]'), out = wrap.querySelector('output');
    rng.oninput = () => { out.textContent = rng.value; this.exag = +rng.value; this.build(this.d, true); };
    this.rng = rng; this.out = out;

    cv.addEventListener('keydown', e => this.key(e));
    cv.addEventListener('pointermove', e => this.hover(e));
    cv.addEventListener('pointerleave', () => { this.tip.hidden = true; });

    new ResizeObserver(() => this.resize()).observe(wrap);
    new MutationObserver(() => { if (this.d) this.build(this.d, true); })
      .observe(document.body, { attributes: true, attributeFilter: ['data-theme'] });
  }

  /* ----------------------------------------------------------- scene */
  dispose(obj) {
    obj.traverse(o => {
      if (o.geometry) o.geometry.dispose();
      if (o.material) (Array.isArray(o.material) ? o.material : [o.material]).forEach(m => { if (m.map) m.map.dispose(); m.dispose(); });
    });
    if (obj.isInstancedMesh) obj.dispose();
  }

  build(d, keepCamera) {
    this.d = d;
    if (this.group) { this.scene.remove(this.group); this.dispose(this.group); }
    const g = this.group = new THREE.Group();
    const ex = this.exag;
    const geo = d.geometry || [], cur = d.current || [];
    const col = new THREE.Color();

    /* bounds */
    let x0 = Infinity, x1 = -Infinity, y0 = Infinity, y1 = -Infinity, zmax = 0;
    geo.forEach(s => [s.p1, s.p2].forEach(p => {
      x0 = Math.min(x0, p[0]); x1 = Math.max(x1, p[0]); y0 = Math.min(y0, p[1]); y1 = Math.max(y1, p[1]); zmax = Math.max(zmax, p[2]);
    }));
    const sf = d.surface;
    if (sf && sf.x && sf.y) { x0 = Math.min(x0, sf.x[0]); x1 = Math.max(x1, sf.x[sf.x.length - 1]); y0 = Math.min(y0, sf.y[0]); y1 = Math.max(y1, sf.y[sf.y.length - 1]); }
    const span = Math.max(x1 - x0, y1 - y0, 1);
    this.box = { x0, x1, y0, y1, zmax, span };

    /* electrodes: one InstancedMesh, one draw call */
    const dens = cur.map(c => c.density).filter(isFinite);
    const jlo = dens.length ? Math.min(...dens) : 0, jhi = dens.length ? Math.max(...dens) : 1;
    const rVis = Math.max(span * 0.0042, 0.03);
    const cyl = new THREE.CylinderGeometry(1, 1, 1, 10, 1);
    const mat = new THREE.MeshLambertMaterial();
    const mesh = this.mesh = new THREE.InstancedMesh(cyl, mat, Math.max(geo.length, 1));
    const m4 = new THREE.Matrix4(), q = new THREE.Quaternion(), up = new THREE.Vector3(0, 1, 0);
    const a = new THREE.Vector3(), b = new THREE.Vector3(), mid = new THREE.Vector3(), dir = new THREE.Vector3(), sc = new THREE.Vector3();
    geo.forEach((s, i) => {
      a.set(s.p1[0], s.p1[1], -s.p1[2] * ex); b.set(s.p2[0], s.p2[1], -s.p2[2] * ex);
      mid.addVectors(a, b).multiplyScalar(0.5);
      dir.subVectors(b, a); const len = dir.length() || 1e-6; dir.divideScalar(len);
      q.setFromUnitVectors(up, dir);
      const rr = Math.max(rVis, (s.r || 0));
      m4.compose(mid, q, sc.set(rr, len, rr));
      mesh.setMatrixAt(i, m4);
      const j = cur[i] ? cur[i].density : jlo;
      mesh.setColorAt(i, ramp(SP, jhi > jlo ? (j - jlo) / (jhi - jlo) : 0.5, col));
    });
    mesh.count = geo.length;
    mesh.instanceMatrix.needsUpdate = true;
    if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true;
    mesh.computeBoundingSphere();
    g.add(mesh);

    /* surface potential sheet */
    let vlo = 0, vhi = 0;
    if (sf && sf.V && sf.x.length > 1 && sf.y.length > 1) {
      const nx = sf.x.length, ny = sf.y.length;
      const pos = new Float32Array(nx * ny * 3), clr = new Float32Array(nx * ny * 3);
      vlo = Infinity; vhi = -Infinity;
      sf.V.forEach(row => row.forEach(v => { if (isFinite(v)) { vlo = Math.min(vlo, v); vhi = Math.max(vhi, v); } }));
      for (let j = 0; j < ny; j++) for (let i = 0; i < nx; i++) {
        const k = (j * nx + i) * 3, v = sf.V[j][i];
        pos[k] = sf.x[i]; pos[k + 1] = sf.y[j]; pos[k + 2] = 0;
        ramp(SV, vhi > vlo ? (v - vlo) / (vhi - vlo) : 0.5, col);
        clr[k] = col.r; clr[k + 1] = col.g; clr[k + 2] = col.b;
      }
      const idx = [];
      for (let j = 0; j < ny - 1; j++) for (let i = 0; i < nx - 1; i++) {
        const p = j * nx + i; idx.push(p, p + 1, p + nx, p + 1, p + nx + 1, p + nx);
      }
      const sg = new THREE.BufferGeometry();
      sg.setAttribute('position', new THREE.BufferAttribute(pos, 3));
      sg.setAttribute('color', new THREE.BufferAttribute(clr, 3));
      sg.setIndex(idx);
      const sm = new THREE.MeshBasicMaterial({ vertexColors: true, transparent: true, opacity: 0.42, side: THREE.DoubleSide, depthWrite: false });
      this.surf = new THREE.Mesh(sg, sm);
      this.surf.renderOrder = 2;
      this.surf.visible = this.show.surf;
      g.add(this.surf);
    } else this.surf = null;

    /* soil box outline */
    const depth = Math.max(zmax * ex * 1.25, span * 0.08);
    const bx = new THREE.BoxGeometry(x1 - x0, y1 - y0, depth);
    const edges = new THREE.EdgesGeometry(bx); bx.dispose();
    const soil = this.soil = new THREE.LineSegments(edges, new THREE.LineBasicMaterial({ color: new THREE.Color(cssVar('--ink-3')), transparent: true, opacity: 0.6 }));
    soil.position.set((x0 + x1) / 2, (y0 + y1) / 2, -depth / 2);
    soil.visible = this.show.soil;
    g.add(soil);

    /* worst touch / step markers, Okabe–Ito vermillion and blue */
    const mk = (xy, shape, color) => {
      if (!xy || !isFinite(xy[0])) return;
      const h = span * 0.035;
      const geom = shape === 'cone' ? new THREE.ConeGeometry(h * 0.45, h, 4) : new THREE.OctahedronGeometry(h * 0.45);
      const m = new THREE.Mesh(geom, new THREE.MeshLambertMaterial({ color: new THREE.Color(color) }));
      if (shape === 'cone') m.rotation.x = Math.PI;      // apex down onto the spot
      m.position.set(xy[0], xy[1], h * 0.6);
      m.renderOrder = 3;
      g.add(m);
    };
    mk(d.touch_at, 'cone', '#d55e00');
    mk(d.step_at, 'oct', '#0072b2');

    this.scene.add(g);

    /* legend and text alternative */
    const W = this.wrap, set = (k, v) => { const e = W.querySelector(`[data-k="${k}"]`); if (e) e.textContent = v; };
    set('jlo', fmt(jlo)); set('jhi', fmt(jhi)); set('vlo', fmt(vlo)); set('vhi', fmt(vhi));
    W.querySelector('[data-k="vkey"]').style.display = this.surf && this.show.surf ? '' : 'none';
    let iMax = 0; cur.forEach((c, i) => { if (c.density > (cur[iMax] || {}).density) iMax = i; });
    const cm = cur[iMax];
    this.sum.textContent = `3-D model: ${geo.length} segments, ${fmt(d.total_length)} m of buried conductor, ` +
      `depth drawn ${ex} times exaggerated. Leakage current density ranges from ${fmt(jlo)} to ${fmt(jhi)} A/m²` +
      (cm ? `, highest on the ${cm.tag || 'electrode'} at x ${fmt(cm.x)} m, y ${fmt(cm.y)} m, depth ${fmt(cm.z)} m` : '') +
      (this.surf ? `. Earth-surface potential ${fmt(vlo)} to ${fmt(vhi)} V` : '') +
      (d.touch_at ? `. Worst touch voltage ${fmt(d.touch_max)} V at x ${fmt(d.touch_at[0])}, y ${fmt(d.touch_at[1])} m` : '') +
      (d.step_at ? `; worst step voltage ${fmt(d.step_max)} V at x ${fmt(d.step_at[0])}, y ${fmt(d.step_at[1])} m.` : '.');
    this.renderer.domElement.setAttribute('aria-label', this.sum.textContent);

    if (!keepCamera) this.view('iso');
    else this.draw();
  }

  /* ---------------------------------------------------------- camera */
  view(kind) {
    const { x0, x1, y0, y1, span } = this.box;
    const cx = (x0 + x1) / 2, cy = (y0 + y1) / 2, cz = -this.box.zmax * this.exag * 0.4;
    const R = span * 1.45;
    const c = this.camera, t = this.controls.target;
    t.set(cx, cy, cz);
    if (kind === 'top') c.position.set(cx, cy - 0.001, cz + R * 1.15);
    else if (kind === 'side') c.position.set(cx, cy - R * 1.2, cz + 0.001);
    else c.position.set(cx + R * 0.6, cy - R * 0.9, cz + R * 0.38);
    c.near = span / 500; c.far = span * 50; c.updateProjectionMatrix();
    this.controls.update();
    this.draw();
  }
  key(e) {
    const c = this.controls, step = Math.PI / 24;
    const sph = new THREE.Spherical();
    const off = new THREE.Vector3().subVectors(this.camera.position, c.target);
    /* work in a y-up frame, as OrbitControls does internally */
    const toY = new THREE.Quaternion().setFromUnitVectors(this.camera.up, new THREE.Vector3(0, 1, 0));
    off.applyQuaternion(toY); sph.setFromVector3(off);
    let used = true;
    switch (e.key) {
      case 'ArrowLeft': sph.theta -= step; break;
      case 'ArrowRight': sph.theta += step; break;
      case 'ArrowUp': sph.phi = Math.max(0.05, sph.phi - step); break;
      case 'ArrowDown': sph.phi = Math.min(Math.PI - 0.05, sph.phi + step); break;
      case '+': case '=': sph.radius *= 0.85; break;
      case '-': case '_': sph.radius /= 0.85; break;
      case 'r': case 'R': this.view('iso'); e.preventDefault(); return;
      default: used = false;
    }
    if (!used) return;
    e.preventDefault();
    off.setFromSpherical(sph).applyQuaternion(toY.invert());
    this.camera.position.copy(c.target).add(off);
    c.update();
  }

  /* ----------------------------------------------------------- hover */
  hover(e) {
    if (this._hp) return;
    this._hp = requestAnimationFrame(() => {
      this._hp = null;
      if (!this.mesh || !this.d) return;
      const rc = this.renderer.domElement.getBoundingClientRect();
      this.ptr.set(((e.clientX - rc.left) / rc.width) * 2 - 1, -((e.clientY - rc.top) / rc.height) * 2 + 1);
      this.ray.setFromCamera(this.ptr, this.camera);
      let html = '';
      const hit = this.ray.intersectObject(this.mesh, false)[0];
      if (hit && hit.instanceId !== undefined) {
        const c = (this.d.current || [])[hit.instanceId], s = this.d.geometry[hit.instanceId];
        if (c) html = `<b>${c.tag || 'segment'}</b> #${hit.instanceId + 1}<br>I = ${fmt(c.I)} A · J = ${fmt(c.density)} A/m²<br>depth ${fmt(s.p1[2])}–${fmt(s.p2[2])} m`;
      } else if (this.surf && this.surf.visible) {
        const h2 = this.ray.intersectObject(this.surf, false)[0];
        if (h2) {
          const sf = this.d.surface, p = h2.point;
          const i = nearest(sf.x, p.x), j = nearest(sf.y, p.y);
          html = `Surface at x ${fmt(p.x)}, y ${fmt(p.y)} m<br>V = ${fmt(sf.V[j][i])} V` + (sf.touch ? ` · touch ${fmt(sf.touch[j][i])} V` : '');
        }
      }
      if (!html) { this.tip.hidden = true; return; }
      this.tip.innerHTML = html;
      this.tip.hidden = false;
      const x = Math.min(e.clientX - rc.left, rc.width - 200), y = Math.min(e.clientY - rc.top, rc.height - 70);
      this.tip.style.left = x + 'px'; this.tip.style.top = y + 'px';
    });
  }

  resize() {
    const w = this.wrap.clientWidth, h = this.wrap.clientHeight;
    if (!w || !h) return;                              // hidden tab: wait until shown
    this.renderer.setSize(w, h, false);
    this.camera.aspect = w / h;
    this.camera.updateProjectionMatrix();
    this.draw();
  }
  draw() {
    if (this._raf) return;
    this._raf = requestAnimationFrame(() => {
      this._raf = null;
      if (this.wrap.clientWidth) this.renderer.render(this.scene, this.camera);
    });
  }
  info() { return { calls: this.renderer.info.render.calls, triangles: this.renderer.info.render.triangles, geometries: this.renderer.info.memory.geometries }; }
}

function nearest(arr, v) {
  let lo = 0, hi = arr.length - 1;
  while (hi - lo > 1) { const m = (lo + hi) >> 1; if (arr[m] < v) lo = m; else hi = m; }
  return Math.abs(arr[lo] - v) <= Math.abs(arr[hi] - v) ? lo : hi;
}

const VIEWS = new Map();
function render(id, d) {
  if (!webgl() || !d || !d.geometry || !d.geometry.length) return false;
  const host = document.getElementById(id);
  if (!host) return false;
  try {
    if (window.Plotly && host.classList.contains('js-plotly-plot')) Plotly.purge(host);
    let v = VIEWS.get(id);
    if (!v || !host.contains(v.wrap)) { v = new GridView(host); VIEWS.set(id, v); }
    v.build(d, false);
    v.resize();
    /* app.js resizes every Plotly div on tab changes; this one is no longer Plotly */
    try { if (typeof PLOTS !== 'undefined') delete PLOTS[id]; } catch (e) { /* not ready */ }
    return true;
  } catch (e) {
    console.warn('3-D view unavailable, using the Plotly wireframe:', e);
    delete host.dataset.three;
    host.innerHTML = '';
    return false;
  }
}

window.esGrid3d = { render, views: VIEWS, reducedMotion: () => REDUCED.matches };
/* a solution restored or computed before this module finished loading */
try { if (typeof S !== 'undefined' && S.bem && S.bem.geometry) render('nPlotGeo', S.bem); } catch (e) { /* not ready */ }
