/* EarthSystem — air-termination page, and the section drawings on the
 * existing pages.
 *
 * Loaded after app.js.  It does two things:
 *
 *   1. runs the "Air termination & protection zone" page (IEC 62305-3
 *      clause 5.2 — rolling sphere, protective angle and mesh methods),
 *   2. hooks the calculate buttons of the other pages so that a scale
 *      section of what was just calculated is drawn beside the numbers.
 *
 * It reaches the shared helpers ($, run, api, kpis, checksHtml, S, …) through
 * the global scope, so nothing in app.js had to be restructured.
 */
'use strict';

(function () {

  const A = id => document.getElementById(id);
  const NUM = (id, d) => { const e = A(id); const v = e ? parseFloat(e.value) : NaN; return isFinite(v) ? v : d; };
  const STR = id => { const e = A(id); return e ? e.value : ''; };
  const CHK = id => { const e = A(id); return e ? e.checked : false; };

  /* ============================================ air-termination page ==== */

  let AIR = [];      // vertical air terminations: {x, y, height, base}
  const AIR_DEF = () => ({ x: 0, y: 0, height: 2, base: '' });

  function renderAir() {
    const tb = A('aTable') && A('aTable').querySelector('tbody');
    if (!tb) return;
    tb.innerHTML = '';
    AIR.forEach((it, i) => {
      const tr = document.createElement('tr');
      tr.innerHTML =
        `<td><input type="number" step="0.5" value="${it.x}" data-k="x"></td>
         <td><input type="number" step="0.5" value="${it.y}" data-k="y"></td>
         <td><input type="number" step="0.5" value="${it.height}" data-k="height"></td>
         <td><input type="number" step="0.5" value="${it.base}" placeholder="auto" data-k="base"></td>
         <td><button class="ghost" title="Remove">✕</button></td>`;
      tr.querySelectorAll('input').forEach(inp => {
        inp.oninput = () => {
          const v = inp.value;
          it[inp.dataset.k] = (inp.dataset.k === 'base' && v === '') ? '' : parseFloat(v);
        };
      });
      tr.querySelector('button').onclick = () => { AIR.splice(i, 1); renderAir(); };
      tb.appendChild(tr);
    });
    if (!AIR.length)
      tb.innerHTML = '<tr><td colspan="5" class="muted small">No air terminations — '
        + 'add one, or use a layout button below.</td></tr>';
  }

  /* Ready-made layouts: what an engineer actually reaches for first. */
  function layout(kind) {
    const W = NUM('aW', 20), D = NUM('aD', 15), H = NUM('aH', 10);
    if (kind === 'corners') {
      AIR = [
        { x: -W / 2, y: -D / 2, height: 1, base: '' },
        { x: W / 2, y: -D / 2, height: 1, base: '' },
        { x: W / 2, y: D / 2, height: 1, base: '' },
        { x: -W / 2, y: D / 2, height: 1, base: '' }
      ];
    } else if (kind === 'corners_centre') {
      layout('corners');
      AIR.push({ x: 0, y: 0, height: 2, base: '' });
    } else if (kind === 'masts') {
      const d = Math.max(W, D) * 0.75 + 6;
      const hm = Math.max(H + 8, 12);
      AIR = [{ x: -d, y: 0, height: hm, base: 0 }, { x: d, y: 0, height: hm, base: 0 }];
    } else if (kind === 'single') {
      AIR = [{ x: 0, y: 0, height: 3, base: '' }];
    }
    renderAir();
  }

  function airPayload() {
    const terms = AIR.filter(t => isFinite(t.x) && isFinite(t.height) && t.height > 0)
      .map(t => {
        const o = { x: t.x, y: isFinite(t.y) ? t.y : 0, height: t.height };
        if (t.base !== '' && isFinite(t.base)) o.base = t.base;
        return o;
      });
    const p = {
      lps_class: STR('aCls') || 'III',
      structure: { width: NUM('aW', 0), height: NUM('aH', 0), depth: NUM('aD', 0) },
      roof_depth: NUM('aD', 0),
      terminals: terms
    };
    const ref = A('aRef') && A('aRef').value;
    if (ref !== '' && isFinite(parseFloat(ref))) p.reference_plane = parseFloat(ref);
    const mesh = A('aMesh') && A('aMesh').value;
    if (mesh !== '' && isFinite(parseFloat(mesh))) p.mesh = parseFloat(mesh);
    if (CHK('aCat') && terms.length >= 2) {
      const xs = terms.map(t => t.x);
      const lo = terms[xs.indexOf(Math.min(...xs))];
      const hi = terms[xs.indexOf(Math.max(...xs))];
      const zl = (isFinite(lo.base) ? lo.base : 0) + lo.height;
      const zh = (isFinite(hi.base) ? hi.base : 0) + hi.height;
      const sag = NUM('aCatSag', 0);
      p.catenaries = [{ x0: lo.x, z0: zl, x1: hi.x, z1: zh - sag },
      { x0: hi.x, z0: zh, x1: (lo.x + hi.x) / 2, z1: (zl + zh) / 2 - sag }];
    }
    return p;
  }

  function renderAirResult(d) {
    S.airterm = d;
    markNav('airterm', d.passed);
    const t0 = (d.terminals || [])[0] || {};
    kpis('aKpis', [
      { value: fmt(d.R) + ' <small>m</small>', label: 'Rolling sphere radius R' },
      { value: fmt(d.mesh_size) + ' <small>m</small>', label: 'Mesh size for the class' },
      { value: fmt(t0.r_protected) + ' <small>m</small>', label: 'r_p of the tallest run' },
      {
        value: (d.plan && d.plan.covered_fraction != null
          ? fmt(100 * d.plan.covered_fraction, 1) + ' <small>%</small>' : '—'),
        label: 'Plan coverage',
        state: d.plan && d.plan.covered_fraction >= 0.999 ? 'ok' : 'bad'
      },
      {
        value: String(d.exposed_count || 0), label: 'Exposed points',
        state: (d.exposed_count || 0) === 0 ? 'ok' : 'bad'
      },
      { value: String(d.mesh ? d.mesh.n_down : '—'), label: 'Down-conductors needed' }
    ]);
    A('aChecks').innerHTML = checksHtml(d.checks, d.narrative, d.method_note);

    const det = [];
    (d.terminals || []).forEach((t, i) => {
      det.push([`Termination ${i + 1} — position`, 'x', t.x, 'm', 'input']);
      det.push([`Termination ${i + 1} — tip height`, 'z', t.tip, 'm', 'base + height']);
      det.push([`Termination ${i + 1} — above the protected plane`, 'h', t.above_reference, 'm',
        'IEC 62305-3 A.2']);
      det.push([`Termination ${i + 1} — protected radius`, 'r_p', t.r_protected, 'm',
        'r_p = √(2Rh − h²)']);
      if (t.protective_angle && t.protective_angle.applicable)
        det.push([`Termination ${i + 1} — protective angle`, 'α',
          t.protective_angle.alpha, '°', 'IEC 62305-3 Figure 1']);
    });
    (d.spans || []).forEach((s, i) => {
      det.push([`Span ${i + 1} — spacing`, 'd', s.d, 'm', 'geometry']);
      if (s.sag != null) det.push([`Span ${i + 1} — sphere sag`, 'p', s.sag, 'm',
        'p = R − √(R² − (d/2)²)']);
      det.push([`Span ${i + 1} — protected height at mid-span`, 'z', s.protected_height, 'm',
        'numerical roll']);
      if (s.max_span) det.push([`Span ${i + 1} — largest permissible spacing`, 'd_max',
        s.max_span, 'm', 'sphere just reaches the plane']);
    });
    if (d.mesh) {
      det.push(['Mesh conductors across', 'n_x', d.mesh.conductors_x, '-', 'Annex A.3']);
      det.push(['Mesh conductors along', 'n_y', d.mesh.conductors_y, '-', 'Annex A.3']);
      det.push(['Mesh conductor length', 'L', d.mesh.total_length, 'm', 'Annex A.3']);
      det.push(['Down-conductor spacing', 's', d.mesh.actual_down_spacing, 'm', 'Table 4']);
    }
    A('aOut').innerHTML = (typeof window.rows === 'function') ? window.rows(det) : '';

    SEC.rollingSphere('aPlotRS', d);
    SEC.zonePlan('aPlotPlan', d);
    SEC.protectiveAngle('aPlotPA', d);
    SEC.meshPlan('aPlotMesh', d);
    toast('Protection zone evaluated.', 'ok');
  }

  function wireAirPage() {
    if (!A('page-airterm')) return;
    AIR = [
      { x: -10, y: -7.5, height: 1, base: '' },
      { x: 10, y: -7.5, height: 1, base: '' },
      { x: 10, y: 7.5, height: 1, base: '' },
      { x: -10, y: 7.5, height: 1, base: '' }
    ];
    renderAir();
    A('aAdd').onclick = () => { AIR.push(AIR_DEF()); renderAir(); };
    document.querySelectorAll('#page-airterm [data-layout]').forEach(b =>
      b.onclick = () => layout(b.dataset.layout));
    A('aPull').onclick = () => {
      const c = STR('lCls'); if (c) A('aCls').value = c;
      const area = NUM('lArea', 0), per = NUM('lPer', 0);
      if (area > 0 && per > 0) {
        /* recover a rectangle from the plan area and perimeter */
        const s = per / 2, disc = s * s - 4 * area;
        if (disc >= 0) {
          const w = (s + Math.sqrt(disc)) / 2, dp = (s - Math.sqrt(disc)) / 2;
          A('aW').value = w.toFixed(1); A('aD').value = dp.toFixed(1);
        }
      }
      toast('Class and plan taken from the lightning earth page.', 'ok');
    };
    A('aRun').onclick = e => run(e.target, async () =>
      renderAirResult(await api('/api/airterm', airPayload())));
  }

  /* =========================================== sections on other pages == */

  function chain(id, fn) {
    const el = A(id);
    if (!el) return;
    const prev = el.onclick;
    el.onclick = async function (ev) {
      if (prev) { try { await prev.call(this, ev); } catch (err) { /* handled upstream */ } }
      try { fn(); } catch (err) { console.error('section draw failed', id, err); }
    };
  }

  function drawSoil() {
    const d = S.soil;
    if (!d) return;
    const sp = d.spacings || [];
    SEC.soil('soilSection', {
      rho1: d.rho1, rho2: d.rho2, h1: d.h,
      rhoEq: d.equivalent && d.equivalent.rho_equivalent,
      depth: NUM('soilDepth', 0.5), rodLen: NUM('soilRod', 0),
      aMax: sp.length ? Math.max.apply(null, sp) : null
    });
  }

  function drawGrid() {
    const d = S.grid;
    if (!d) return;
    SEC.gridSection('gSection', {
      rho: NUM('gRho', 100), rhoS: NUM('gRhoS', 0), hs: NUM('gHs', 0.1),
      Lx: NUM('gLx', 70), D: NUM('gD', 7), h: NUM('gH', 0.5), d: NUM('gd', 0.01),
      nRod: parseInt(STR('gNr')) || 0, Lr: NUM('gLr', 0), dr: NUM('gDr', 0.016),
      Em: d.mesh && d.mesh.Em, Es: d.mesh && d.mesh.Es, GPR: d.GPR
    });
  }

  /* BEM_ITEMS and BUILD_ITEMS are declared with `let` at the top level of
     app.js, so they live in the global lexical scope and never appear on
     `window`; they have to be read by name. */
  const bemItems = () => (typeof BEM_ITEMS !== 'undefined' && BEM_ITEMS) || [];
  const buildItems = () => (typeof BUILD_ITEMS !== 'undefined' && BUILD_ITEMS) || [];

  function drawBem() {
    const items = bemItems();
    if (!items.length) { DRAW.clear('nSection'); return; }
    SEC.bemSection('nSection', items, {
      rho1: NUM('nRho1', 100), rho2: NUM('nRho2', NaN), h1: NUM('nHl', NaN),
      IG: NUM('nIG', NaN)
    });
  }

  let BUILD_SEL = 0;
  function drawBuilding() {
    const items = buildItems();
    if (!items.length) { DRAW.clear('bSection'); return; }
    const i = Math.min(Math.max(0, BUILD_SEL), items.length - 1);
    const res = S.building && S.building.electrodes && S.building.electrodes[i];
    SEC.electrode('bSection', items[i], res && res.R, NUM('bRho', 100));
    const sel = A('bSectionSel');
    if (sel) {
      sel.innerHTML = items.map((it, k) =>
        `<option value="${k}"${k === i ? ' selected' : ''}>${k + 1}. ${it.type}</option>`).join('');
      sel.onchange = () => { BUILD_SEL = parseInt(sel.value) || 0; drawBuilding(); };
    }
  }

  /* ============================================= report figure capture == */

  /* The report takes its figures in reading order, mixing the Plotly charts
     with the drawings.  This replaces the capture in app.js so the sections
     land in the right place rather than all at the end. */
  const FIGURES = [
    ['svg', 'soilSection', 'Soil model — section through the fitted strata'],
    ['plot', 'soilPlot', 'Apparent resistivity — measured and fitted two-layer model'],
    ['plot', 'fPlot', 'Decrement factor versus fault duration'],
    ['plot', 'cPlot', 'Required conductor area versus fault duration'],
    ['svg', 'gSection', 'Earth grid — section through the switchyard'],
    ['plot', 'gPlotLay', 'Earth grid layout'],
    ['plot', 'gPlotSweep', 'Mesh and step voltage versus conductor spacing'],
    ['svg', 'nSection', 'Numerical model — electrodes in the soil section'],
    ['plot', 'nPlotSurf', 'Earth-surface potential distribution'],
    ['plot', 'nPlotTouch', 'Touch voltage distribution'],
    ['plot', 'nPlotProf', 'Potential, touch and step voltage along a traverse'],
    ['svg', 'bSection', 'Earth electrode — section'],
    ['plot', 'bPlot', 'Electrode resistance versus soil resistivity'],
    ['plot', 'lPlot', 'Minimum electrode length versus soil resistivity'],
    ['svg', 'aPlotRS', 'Rolling sphere — protected volume in elevation'],
    ['svg', 'aPlotPlan', 'Protected area — plan'],
    ['svg', 'aPlotPA', 'Protective angle'],
    ['svg', 'aPlotMesh', 'Mesh air termination — plan']
  ];

  window.collectFigures = async function () {
    const want = A('rFigs');
    if (want && !want.checked) return [];
    const out = [];
    for (const [kind, id, cap] of FIGURES) {
      const el = A(id);
      if (!el) continue;
      try {
        if (kind === 'plot') {
          if (!el.data || !el.data.length) continue;
          out.push({
            data: await Plotly.toImage(el, { format: 'png', width: 1100, height: 620, scale: 1.6 }),
            caption: cap
          });
        } else {
          if (!DRAW.has(id)) continue;
          out.push({ data: await DRAW.toPNG(id, 2), caption: cap });
        }
      } catch (e) { /* a figure that will not render is simply left out */ }
    }
    return out;
  };

  /* ==================================================== theme and boot == */

  const themeBtn = A('btnTheme');
  if (themeBtn) themeBtn.addEventListener('click', () => setTimeout(() => DRAW.redrawAll(), 30));

  function boot() {
    wireAirPage();
    chain('soilRun', drawSoil);
    chain('gRun', drawGrid);
    chain('gOpt', drawGrid);
    chain('nRun', drawBem);
    chain('nFromGrid', drawBem);
    chain('bRun', drawBuilding);
    chain('bSize', drawBuilding);
    /* the geometry tables change without a calculation, so redraw on edit */
    document.querySelectorAll('#page-numerical [data-add], #page-numerical #nFromGrid')
      .forEach(b => { const prev = b.onclick; b.onclick = () => { if (prev) prev(); setTimeout(drawBem, 0); }; });
    const nt = A('nTable');
    if (nt) nt.addEventListener('input', () => setTimeout(drawBem, 120));
    const bt = A('bTable');
    if (bt) bt.addEventListener('input', () => setTimeout(drawBuilding, 120));
    document.querySelectorAll('#page-building [data-badd]').forEach(b => {
      const prev = b.onclick;
      b.onclick = () => { if (prev) prev(); BUILD_SEL = buildItems().length - 1; drawBuilding(); };
    });
    setTimeout(() => { drawBuilding(); drawBem(); }, 800);
  }

  if (document.readyState === 'loading')
    document.addEventListener('DOMContentLoaded', boot);
  else boot();

})();
