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

/* Earthing System 1.8.0 — the studies added to pages 1, 2, 5 and 7:
   robust and multi-traverse soil fits, the shield-wire ladder and fault-
   location sweep, the convergence / seasonal / uncertainty studies, the
   non-equipotential power-frequency solution, grid optimisation, the
   fall-of-potential test, IEC 62305-2 risk and IEC 62305-4 SPD checks.
   Loaded after app.js and uses its helpers ($, V, N, NB, C, set, api, run,
   rows, checksHtml, plot, fmt, esc, S, BEM_ITEMS, renderBem, PAL, css, toast). */
'use strict';

/* "name: x0, y0, x1, y1[, limit]" per line */
function parseZones(text) {
  return String(text || '').split('\n').map(l => l.trim()).filter(Boolean).map((l, i) => {
    let name = `Zone ${i + 1}`, rest = l;
    const c = l.indexOf(':');
    if (c >= 0) { name = l.slice(0, c).trim() || name; rest = l.slice(c + 1); }
    const v = rest.split(',').map(t => parseFloat(t));
    if (v.length < 4 || v.slice(0, 4).some(x => !isFinite(x)))
      throw new Error(`Touch zone "${l}": give it as name: x0, y0, x1, y1 (metres).`);
    const z = { name, x0: v[0], y0: v[1], x1: v[2], y1: v[3] };
    if (isFinite(v[4])) z.limit = v[4];
    return z;
  });
}
/* "x, y; x, y; …" (or one point per line) */
function parsePoints(text) {
  const t = String(text || '').trim();
  if (!t) return null;
  const pts = t.split(/[;\n]/).map(s => s.trim()).filter(Boolean).map(s => s.split(',').map(Number));
  if (pts.some(p => p.length < 2 || !isFinite(p[0]) || !isFinite(p[1])))
    throw new Error('Give each point of the route as x, y, separated by semicolons.');
  if (pts.length < 2) throw new Error('A route path needs at least two points.');
  return pts.map(p => [p[0], p[1]]);
}
/* number pairs or triples, one per line */
function parsePairs(text, what) {
  const t = String(text || '').trim();
  if (!t) return null;
  return t.split('\n').map(s => s.trim()).filter(Boolean).map(s => {
    const v = s.split(/[,\s]+/).filter(Boolean).map(Number);
    if (v.length < 2 || !isFinite(v[0]) || !isFinite(v[1])) throw new Error(`${what}: "${s}" is not a pair of numbers.`);
    return v;
  });
}

function bemPayload(extra) {
  if (!BEM_ITEMS.length) throw new Error('Add at least one electrode element on this page first.');
  const p = {
    rho1: N('nRho1', 100), IG: N('nIG', 1000), items: BEM_ITEMS,
    segment_length: N('nSeg', 3), nx: Math.min(parseInt(V('nRes')) || 41, 41),
    step_distance: N('nStep', 1), grade_ends: C('nGrade'), zones: parseZones(V('nZones'))
  };
  if (NB('nRho2') !== null && NB('nHl') !== null) { p.rho2 = NB('nRho2'); p.h_layer = NB('nHl'); }
  if (NB('nRho3') !== null || NB('nH2') !== null) { p.rho3 = NB('nRho3'); p.h_layer2 = NB('nH2'); }
  if (NB('nRho4') !== null || NB('nH3') !== null) { p.rho4 = NB('nRho4'); p.h_layer3 = NB('nH3'); }
  if (NB('nRhoV') !== null) { p.rho_v = NB('nRhoV'); p.x_v = N('nXv', 0); p.y_v = N('nYv', 0); p.angle_v = N('nAngV', 0); }
  if (S.grid) p.limits = { E_touch: S.grid.tolerable.E_touch, E_step: S.grid.tolerable.E_step };
  return Object.assign(p, extra || {});
}
const pct = (v, d = 1) => (v === null || v === undefined || !isFinite(v)) ? '—' : fmt(v, d) + ' %';

/* ------------------------------------------------------------ page 1 soil */
(function () {
  const th = $('#soilCol4');
  if (th) th.dataset.help = 'Optional: the name of the traverse a reading belongs to (N–S, E–W, T1 …). '
    + 'Readings from all traverses are fitted together; each traverse with three or more readings is also '
    + 'fitted on its own, and the program reports how far they disagree — lateral variation that no '
    + 'layered model can represent.';
})();

window.esSoilExtras = function (d) {
  let h = '';
  const R = d.robust;
  if (R && R.excluded && R.excluded.length) {
    h += `<div class="note warn"><b>Readings set aside.</b> ${esc(R.note)}</div>
      <table class="data"><thead><tr><th>#</th><th style="text-align:right">Spacing (m)</th><th style="text-align:right">Measured ρₐ</th>
      <th style="text-align:right">Refitted model</th><th style="text-align:right">Δ (%)</th></tr></thead><tbody>` +
      R.excluded.map(e => `<tr><td>${e.index}</td><td class="n">${fmt(e.spacing)}</td><td class="n">${fmt(e.measured)}</td><td class="n">${fmt(e.model)}</td><td class="n">${fmt(e.residual_pct, 1)}</td></tr>`).join('') +
      '</tbody></table>';
    try {
      Plotly.addTraces('soilPlot', [{ x: R.excluded.map(e => e.spacing), y: R.excluded.map(e => e.measured), mode: 'markers',
        name: 'Set aside', marker: { size: 11, symbol: 'x', color: PAL[1] } }]);
    } catch (e) { /* plot not ready */ }
  } else if (R && R.applied) {
    h += `<div class="note info"><b>Robust fit.</b> ${esc(R.note)}</div>`;
  }
  const T = d.traverses;
  if (T) {
    const ok = T.fits.filter(f => f.fitted);
    h += `<h4 style="margin:12px 0 6px">Traverses fitted separately (two layers)</h4>
      <table class="data"><thead><tr><th>Traverse</th><th style="text-align:right">Readings</th><th style="text-align:right">ρ₁ (Ω·m)</th>
      <th style="text-align:right">ρ₂ (Ω·m)</th><th style="text-align:right">h (m)</th><th style="text-align:right">RMS (%)</th></tr></thead><tbody>` +
      T.fits.map(f => f.fitted
        ? `<tr><td>${esc(f.name)}</td><td class="n">${f.n}</td><td class="n">${fmt(f.rho1)}</td><td class="n">${fmt(f.rho2)}</td><td class="n">${fmt(f.h)}</td><td class="n">${fmt(f.rms_pct, 2)}</td></tr>`
        : `<tr><td>${esc(f.name)}</td><td class="n">${f.n}</td><td colspan="4" class="muted">fewer than three readings — not fitted alone</td></tr>`).join('') +
      '</tbody></table>' + (T.note ? `<div class="note ${T.lateral ? 'warn' : 'info'}"><b>Lateral variation.</b> ${esc(T.note)}</div>` : '');
    try {
      Plotly.addTraces('soilPlot', ok.map((f, i) => ({ x: f.curve_x, y: f.curve_y, mode: 'lines',
        name: 'Traverse ' + f.name, line: { width: 1.3, dash: 'dot', color: PAL[(i + 3) % PAL.length] } })));
    } catch (e) { /* plot not ready */ }
  }
  if (h) $('#soilOut').insertAdjacentHTML('beforeend', h);
};

/* ---------------------------------------------- page 2: shield-wire ladder */
$('#swRun').onclick = e => run(e.target, async () => {
  const p = {
    Un_kV: N('fUn', 20), c: N('fC', 1.1), f: N('fFreq', 50), Rg: N('swRg', 0.5), line_km: N('swLen', 20),
    span_km: N('swSpan', 0.3), Rt: N('swRt', 15), R_remote: N('swRrem', 0.5), rho: N('swRho', 100),
    sw_r_km: N('swR', 0.33), sw_gmr: N('swGmr', 0.004), d_phase_sw: N('swD', 8),
    Z1_local: V('swZ1s') || null, Z0_local: V('swZ0s') || null, Z1_remote: V('swZ1r') || null,
    Z0_remote: V('swZ0r') || null, Z1_line: V('swZ1l') || null, Z0_line: V('swZ0l') || null,
    Z_other: V('swZo') || null, Df: S.fault ? S.fault.Df : 1,
    spans_km: V('swSpans').trim() || null, Rt_list: V('swRts').trim() || null,
    other_lines: V('swOthers').trim() ? V('swOthers').trim().split('\n').map(r => r.trim()).filter(Boolean) : null,
    n_wires: N('swN', 1), d_sw: N('swDsw', 10),
    parallel_lines: V('swPar').trim() ? V('swPar').trim().split('\n').map(r => r.trim()).filter(Boolean) : null
  };
  const d = await api('/api/fault/sweep', p);
  S.faultsweep = d;
  const st = d.station, w = d.worst;
  $('#swOut').innerHTML = `<div class="note ${w.node ? 'warn' : 'info'}">${esc(d.note)}</div>` + rows([
    ['Shield wire self impedance', 'z_s', `${fmt(d.zs_km.re, 3)} + j${fmt(d.zs_km.im, 3)}`, 'Ω/km', 'Carson, earth return'],
    ['Mutual impedance to the phase', 'z_m', `${fmt(d.zm_km.re, 3)} + j${fmt(d.zm_km.im, 3)}`, 'Ω/km', `coupling factor |z_m/z_s| = ${fmt(d.coupling_k, 3)}`],
    ['Ladder input impedance', '|Z|', d.Z_ladder, 'Ω', `${d.n_spans} spans; infinite ladder ${fmt(d.Z_infinite, 3)} Ω${(d.parallel_lines || []).length ? '; the faulted line alone' : ''}`],
    d.n_wires > 1 ? ['Shield wires on the line', 'n', d.n_wires, '', 'one bundle with their mutual impedance'] : null,
    (d.parallel_lines || []).length ? ['Parallel lines in the corridor', 'n', d.parallel_lines.length, '',
      d.parallel_lines.map(q => `${q.name}: ${fmt(q.separation)} m, ${q.n_wires} wire(s)`).join('; ') + '; solved as one coupled network'] : null,
    d.Z_other_total ? ['Other lines and neutrals in parallel', '|Z_o|', d.Z_other_total, 'Ω', (d.other_lines || []).map(o => `${o.name}: ${fmt(o.Z, 3)} Ω`).join('; ')] : null,
    ['Fault in the station: fault current', 'I_f', st.If_kA, 'kA', ''],
    ['Fault in the station: grid current', 'I_g', st.Ig_kA, 'kA', `S_f = ${fmt(st.Sf, 3)} of I_f`],
    ['Largest grid current', 'I_g,max', w.Ig_kA, 'kA', d.governs],
    ['Design grid current', 'I_G = D_f·I_g,max', d.IG_design_kA, 'kA', `D_f = ${fmt(d.Df, 3)} from the results above`]
  ]) + `<div class="rowbtns"><button id="swUse" class="ghost">Use S_f = ${fmt(w.Sf, 3)} (the governing case) above</button></div>`;
  $('#swUse').onclick = () => { set('fSf', +w.Sf.toFixed(4)); toast('Split factor set — recalculate the fault current.'); };
  plot('swPlot', [
    { x: d.rows.map(r => r.x_km), y: d.rows.map(r => r.Ig_kA), mode: 'lines+markers', name: 'Grid current I_g', line: { color: PAL[1], width: 2.5 }, marker: { size: 5 } },
    { x: d.rows.map(r => r.x_km), y: d.rows.map(r => r.If_kA), mode: 'lines', name: 'Fault current I_f', line: { color: PAL[0], width: 1.6, dash: 'dot' } },
    { x: d.rows.map(r => r.x_km), y: d.rows.map(r => r.I_local_kA), mode: 'lines', name: "This station's contribution", line: { color: PAL[2], width: 1.6, dash: 'dash' } }
  ], {
    xaxis: { title: { text: 'Fault distance from the station (km)' }, gridcolor: css('--line') },
    yaxis: { title: { text: 'Current (kA)' }, gridcolor: css('--line') }
  });
  toast('Ladder solved.', 'ok');
});

/* ------------------------------------------------- page 5: main-run extras */
window.esBemExtras = function (d) {
  let h = '';
  (d.warnings || []).forEach(w => { h += `<div class="note warn"><b>Discretisation.</b> ${esc(w)}</div>`; });
  if (d.zones && d.zones.length) {
    h += `<h4 style="margin:12px 0 6px">Touch zones</h4><table class="data"><thead><tr><th>Zone</th><th style="text-align:right">Touch (V)</th>
      <th style="text-align:right">at x, y (m)</th><th style="text-align:right">Limit (V)</th></tr></thead><tbody>` +
      d.zones.map(z => `<tr><td>${esc(z.name)}</td><td class="n">${fmt(z.touch_max)}</td><td class="n">${fmt(z.touch_at[0])}, ${fmt(z.touch_at[1])}</td><td class="n">${fmt(z.limit || (S.grid ? S.grid.tolerable.E_touch : null))}</td></tr>`).join('') +
      '</tbody></table>';
  }
  h += `<div class="note info">Touch voltage is the largest ${d.touch_region === 'zones' ? 'within the touch zones'
    : 'where a person on the soil is within 1 m of buried metal or inside a mesh'}; step voltage is the largest over one step in the
    worst direction (${fmt(d.step_direction_deg, 0)}° from +x here). Both maxima are refined to 0.02 m from the plot-grid candidates, so
    they do not depend on the surface grid resolution.${d.graded ? ' Segments are refined towards every conductor end.' : ''}</div>`;
  $('#nOut').insertAdjacentHTML('beforeend', h);
};

/* --------------------------------------- page 5: accuracy and soil studies */
$('#nConv').onclick = e => run(e.target, async () => {
  const d = await api('/api/bem/convergence', bemPayload());
  S.convergence = d; window.esRefreshGoverning();
  $('#nStudyOut').innerHTML = `<div class="note ${d.converged ? 'info' : 'warn'}"><b>Convergence.</b> ${esc(d.note)}</div>` +
    `<table class="data"><thead><tr><th>Quantity</th><th style="text-align:right">h = ${fmt(d.h)} m</th><th style="text-align:right">h/2</th>
     <th style="text-align:right">Change</th><th style="text-align:right">Estimated converged</th></tr></thead><tbody>` +
    [['R_g (Ω)', 'Rg'], ['GPR (V)', 'GPR'], ['Touch (V)', 'touch'], ['Step (V)', 'step']].map(([n, k]) =>
      `<tr><td>${n}</td><td class="n">${fmt(d[k].coarse)}</td><td class="n">${fmt(d[k].fine)}</td><td class="n">${pct(d[k].change_pct, 2)}</td><td class="n">${fmt(d[k].extrapolated)}</td></tr>`).join('') +
    `</tbody></table><div class="hint">Segments solved: ${d.segments[0]} and ${d.segments[1]}.</div>`;
  Plotly.purge('nStudyPlot');
  toast('Convergence check done.', 'ok');
});

$('#nSeason').onclick = e => run(e.target, async () => {
  const s = { dry_factor: N('nDryF', 2), dry_depth: N('nDryD', 1) };
  if (NB('nFrR') !== null && NB('nFrD') !== null) { s.frozen_rho = NB('nFrR'); s.frozen_depth = NB('nFrD'); }
  const d = await api('/api/bem/seasonal', bemPayload({ seasonal: s }));
  S.seasonal = d; window.esRefreshGoverning();
  const lim = S.grid ? S.grid.tolerable : {};
  $('#nStudyOut').innerHTML = `<div class="note info"><b>Seasonal soil.</b> ${esc(d.note)}</div>` +
    `<table class="data"><thead><tr><th>Case</th><th>Soil (Ω·m / m)</th><th style="text-align:right">R_g (Ω)</th><th style="text-align:right">GPR (V)</th>
     <th style="text-align:right">Touch (V)</th><th style="text-align:right">Step (V)</th></tr></thead><tbody>` +
    d.cases.map(c => `<tr><td>${esc(c.name)}</td><td class="small">${c.rho.map(r => fmt(r, 0)).join(' / ')}${c.h.length ? ' — ' + c.h.map(t => fmt(t, 2)).join(' / ') : ''}</td>
      <td class="n">${fmt(c.Rg)}</td><td class="n">${fmt(c.GPR)}</td>
      <td class="n" style="${lim.E_touch && c.touch > lim.E_touch ? 'color:var(--bad)' : ''}">${fmt(c.touch)}</td>
      <td class="n" style="${lim.E_step && c.step > lim.E_step ? 'color:var(--bad)' : ''}">${fmt(c.step)}</td></tr>`).join('') +
    `</tbody></table><div class="hint">Worst case: touch — ${esc(d.worst.touch)}; step — ${esc(d.worst.step)}; R_g — ${esc(d.worst.Rg)}.</div>`;
  plot('nStudyPlot', ['Rg', 'touch', 'step'].map((k, i) => ({
    x: d.cases.map(c => c.name), y: d.cases.map(c => c[k] / d.cases[0][k]), type: 'bar',
    name: { Rg: 'R_g', touch: 'Touch', step: 'Step' }[k], marker: { color: PAL[i] }
  })), {
    yaxis: { title: { text: 'Relative to the measured soil' }, gridcolor: css('--line') }, barmode: 'group'
  });
  toast('Seasonal cases solved.', 'ok');
});

const ciTxt = (d, k) => (d.ci95 && d.ci95[k]) ? `95 % confidence ${fmt(100 * d.ci95[k][0], 0)}–${fmt(100 * d.ci95[k][1], 0)} %` : '';
$('#nMc').onclick = e => run(e.target, async () => {
  if (!S.soil) throw new Error('Fit the soil model on page 1 first: the uncertainty comes from its covariance.');
  const n = Math.round(N('nMcN', 20));
  toast(`Solving ${n} soil models — this takes a while.`);
  const d = await api('/api/bem/montecarlo', bemPayload({ soil_fit: S.soil, samples: n, sampling: V('nMcMethod') || 'lhs' }));
  S.montecarlo = d; window.esRefreshGoverning();
  const lim = S.grid ? S.grid.tolerable : {};
  const row = (lab, k, u) => `<tr><td>${lab}</td><td class="n">${fmt(d.stats[k].p05)}</td><td class="n">${fmt(d.stats[k].p50)}</td><td class="n">${fmt(d.stats[k].p95)}</td><td class="muted small">${u}</td></tr>`;
  $('#nStudyOut').innerHTML = `<div class="note info"><b>Soil uncertainty.</b> ${esc(d.note)}</div>` +
    `<table class="data"><thead><tr><th>Quantity</th><th style="text-align:right">5 %</th><th style="text-align:right">median</th><th style="text-align:right">95 %</th><th>Unit</th></tr></thead><tbody>` +
    row('Earth resistance R_g', 'Rg', 'Ω') + row('GPR', 'GPR', 'V') + row('Touch voltage', 'touch', 'V') + row('Step voltage', 'step', 'V') +
    '</tbody></table>' + (d.p_pass !== null && d.p_pass !== undefined ? rows([
      ['Probability touch ≤ limit', 'P_T', pct(100 * d.p_touch, 0), '', (lim.E_touch ? `E_touch = ${fmt(lim.E_touch)} V; ` : '') + ciTxt(d, 'p_touch')],
      ['Probability step ≤ limit', 'P_S', pct(100 * d.p_step, 0), '', (lim.E_step ? `E_step = ${fmt(lim.E_step)} V; ` : '') + ciTxt(d, 'p_step')],
      ['Probability both are met', 'P', pct(100 * d.p_pass, 0), '', `${d.n} samples; ` + ciTxt(d, 'p_pass')]
    ]) : '<div class="hint">Run the grid page for the tolerable voltages to get the probability of compliance.</div>');
  plot('nStudyPlot', [
    { x: d.samples.map(s => s.touch), type: 'histogram', name: 'Touch', marker: { color: PAL[1] }, opacity: 0.75 },
    lim.E_touch ? { x: [lim.E_touch, lim.E_touch], y: [0, d.n / 3], mode: 'lines', name: 'Tolerable touch', line: { color: PAL[1], dash: 'dot' } } : null
  ].filter(Boolean), {
    xaxis: { title: { text: 'Touch voltage (V)' }, gridcolor: css('--line') },
    yaxis: { title: { text: 'Samples' }, gridcolor: css('--line') }
  });
  toast('Uncertainty study done.', 'ok');
});

/* --------------------------------- page 5: non-equipotential power frequency */
$('#pfRun').onclick = e => run(e.target, async () => {
  const fe = parsePairs(V('pfFeeds'), 'Injection points') || [[0, 0, 1]];
  const feeds = fe.map(v => ({ x: v[0], y: v[1], share: isFinite(v[2]) ? v[2] : 1 }));
  const d = await api('/api/bem/powerfreq', bemPayload({ metal: V('pfMetal'), f: N('pfF', 50), feeds }));
  S.powerfreq = d; window.esRefreshGoverning();
  $('#pfOut').innerHTML = `<div class="note ${d.significant ? 'warn' : 'info'}">${esc(d.note)}</div>` +
    (d.warnings || []).map(w => `<div class="note warn"><b>Discretisation.</b> ${esc(w)}</div>`).join('') + rows([
    ['Earth impedance at the feed', '|Z|', d.Z.abs, 'Ω', `${fmt(d.Z.re, 4)} + j${fmt(d.Z.im, 4)} Ω, ${d.metal}, ${fmt(d.f)} Hz`],
    ['Earth resistance, equipotential', 'R_g', d.Rg_equipotential, 'Ω', 'all metal at one potential'],
    ['GPR at the feed point', 'GPR', d.GPR_feed, 'V', `equipotential ${fmt(d.GPR_equipotential)} V`],
    ['Lowest metal potential', 'V_min', d.V_node_min, 'V', `${pct(100 * d.V_min_over_feed, 0)} of the feed point`],
    ['Maximum touch voltage', 'U_T', d.touch_max, 'V', `equipotential ${fmt(d.equipotential.touch_max)} V; at ${fmt(d.touch_at[0])}, ${fmt(d.touch_at[1])} m`],
    ['Maximum step voltage', 'U_S', d.step_max, 'V', `equipotential ${fmt(d.equipotential.step_max)} V`],
    ['Segments', 'N', d.segments, '', `${d.nodes} nodes`]
  ].concat(d.two_scale ? [['Leakage segments (two-scale)', 'N_f', d.two_scale.fine_segments, '',
      `${fmt(d.two_scale.fine_length, 3)} m for the leakage and the surface; metal potentials from ${d.two_scale.coarse_segments} segments of ${fmt(d.two_scale.coarse_length, 3)} m; fine current ${fmt(d.two_scale.current_balance, 3)} of I_G before scaling`]] : [])) + ((d.fences || []).length ? `<h4 style="margin:12px 0 6px">Fences</h4><table class="data"><thead><tr><th>Fence</th>
     <th style="text-align:right">Potential (V)</th><th style="text-align:right">Touch (V)</th><th>Side</th><th style="text-align:right">Equipotential touch (V)</th></tr></thead><tbody>` +
    d.fences.map(f => `<tr><td>${esc(f.name)} <span class="muted small">(${f.bonded ? 'bonded' : 'isolated'})</span></td><td class="n">${fmt(f.V_fence)}</td>
      <td class="n">${fmt(f.touch_max)}</td><td>${esc(f.side)}</td><td class="n">${fmt(f.equipotential_touch)}</td></tr>`).join('') +
    '</tbody></table>' : '') + (d.checks ? checksHtml(d.checks) : '');
  const np = d.node_potentials.filter(q => q.z < 1.5);
  plot('pfPlot', [
    { x: d.surface.x, y: d.surface.y, z: d.surface.V, type: 'contour', colorscale: 'Viridis', showscale: true,
      contours: { coloring: 'heatmap' }, colorbar: { title: { text: '|V| soil (V)' }, thickness: 12 }, name: 'Surface' },
    { x: np.map(q => q.x), y: np.map(q => q.y), mode: 'markers', name: 'Metal |V|',
      marker: { size: 6, color: np.map(q => q.V), colorscale: 'Hot', showscale: false, line: { width: 0.5, color: '#000' } },
      text: np.map(q => `${fmt(q.V)} V ∠${fmt(q.deg, 1)}°`), hoverinfo: 'text' },
    { x: d.feeds.map(f => f.x), y: d.feeds.map(f => f.y), mode: 'markers', name: 'Injection', marker: { size: 13, symbol: 'star', color: PAL[1] } }
  ], {
    xaxis: { title: { text: 'x (m)' }, scaleanchor: 'y', gridcolor: css('--line') },
    yaxis: { title: { text: 'y (m)' }, gridcolor: css('--line') }
  });
  toast('Non-equipotential solution complete.', 'ok');
});

/* ---------------------------------------------------- page 5: optimisation */
let OPT_ITEMS = null;
$('#opRun').onclick = e => run(e.target, async () => {
  if (!S.grid) throw new Error('Run the substation grid page first: the optimisation needs its tolerable touch and step voltages.');
  const p = bemPayload({
    Lx: N('opLx', 70), Ly: N('opLy', 70), depth: N('opH', 0.5), conductor_radius: N('opR', 0.005),
    rod_length: N('opRod', 3), cost_conductor: N('opCc', 1), cost_rod: N('opCr', 1.5), nx: 31
  });
  delete p.items;
  toast('Searching — each design is a full numerical solution.');
  const d = await api('/api/bem/optimise', p);
  S.optimise = d;
  OPT_ITEMS = d.items || null;
  $('#opLoad').disabled = !OPT_ITEMS;
  const b = d.best;
  $('#opOut').innerHTML = `<div class="note ${d.feasible ? 'info' : 'warn'}">${esc(d.note)}${d.saving_vs_uniform_pct ? ` Unequal spacing saves ${fmt(d.saving_vs_uniform_pct, 0)} % against the cheapest uniform grid that passes.` : ''}</div>` +
    `<table class="data"><thead><tr><th>Lines</th><th style="text-align:right">Grading</th><th style="text-align:right">Rods</th><th style="text-align:right">Conductor (m)</th>
     <th style="text-align:right">Touch (V)</th><th style="text-align:right">Step (V)</th><th style="text-align:right">Cost</th><th></th></tr></thead><tbody>` +
    d.tried.slice(0, 14).map(r => `<tr${b && r.n === b.n && r.grading === b.grading && r.rods_every === b.rods_every ? ' style="font-weight:600"' : ''}>
      <td>${r.n_x} × ${r.n_y}</td><td class="n">${fmt(r.grading, 2)}</td><td class="n">${r.rods}</td><td class="n">${fmt(r.conductor_m, 0)}</td>
      <td class="n">${fmt(r.touch)}</td><td class="n">${fmt(r.step)}</td><td class="n">${fmt(r.cost, 0)}</td><td>${r.ok ? '✓' : '✗'}</td></tr>`).join('') +
    `</tbody></table><div class="hint">${d.evaluations} numerical solutions; the cheapest ${Math.min(14, d.tried.length)} are listed, passing designs first.</div>`;
  toast(d.feasible ? 'Optimum found.' : 'No design in the range passes.', d.feasible ? 'ok' : 'err');
});
$('#opLoad').onclick = () => {
  if (!OPT_ITEMS) return;
  BEM_ITEMS = JSON.parse(JSON.stringify(OPT_ITEMS));
  renderBem();
  toast('The optimised grid is in the electrode table — solve it to see its full field.', 'ok');
};

/* --------------------------------------------- page 5: fall-of-potential */
$('#ftRun').onclick = e => run(e.target, async () => {
  const meas = parsePairs(V('ftMeas'), 'Readings');
  const d = await api('/api/earthtest', bemPayload({
    bearing: N('ftBear', 0), probe_angle: N('ftAng', 0), accuracy_pct: N('ftAcc', 2),
    measured: meas, dC_measured: NB('ftDc'), measured_from: V('ftFrom'), segment_length: Math.max(N('nSeg', 3), 3)
  }));
  S.earthtest = d;
  const cv = d.curve;
  $('#ftOut').innerHTML = `<div class="note ${d.recommended ? 'info' : 'warn'}"><b>Test plan.</b> ${esc(d.note)}</div>` +
    `<table class="data"><thead><tr><th>Current electrode</th><th style="text-align:right">Distance (m)</th><th style="text-align:right">Error at 61.8 %</th>
     <th style="text-align:right">Probe for the true value</th></tr></thead><tbody>` +
    d.sweep.map(s => `<tr${d.recommended && s.multiple === d.recommended.multiple ? ' style="font-weight:600"' : ''}><td>${fmt(s.multiple)} × D</td><td class="n">${fmt(s.dC, 0)}</td>
      <td class="n">${pct(s.error_618_pct)}</td><td class="n">${s.x_true_fraction ? pct(100 * s.x_true_fraction) + ' of the distance' : '—'}</td></tr>`).join('') +
    `</tbody></table><div class="hint">D = ${fmt(d.D, 0)} m, the largest plan dimension of the electrodes; computed resistance ${fmt(d.Rg_model, 4)} Ω;
     distances from the electrode's ${d.measured_from}.</div>` +
    (d.interpretation ? `<div class="note ${d.interpretation.rms_shape_pct <= 5 ? 'info' : 'warn'}"><b>Readings.</b> ${esc(d.interpretation.note)}</div>` : '');
  const lines = [
    { x: cv.x, y: cv.R, mode: 'lines', name: `Computed, C at ${fmt(cv.dC, 0)} m`, line: { color: PAL[0], width: 2.5 } },
    { x: [0, cv.dC], y: [cv.Rg_true, cv.Rg_true], mode: 'lines', name: 'True resistance', line: { color: PAL[2], dash: 'dot' } },
    { x: [0.618 * cv.dC, 0.618 * cv.dC], y: [0, Math.max(...cv.R)], mode: 'lines', name: '61.8 %', line: { color: PAL[3], dash: 'dash', width: 1 } }
  ];
  if (d.interpretation) {
    const k = d.interpretation.scale;
    lines.push({ x: d.interpretation.x, y: d.interpretation.R, mode: 'markers', name: 'Readings', marker: { size: 9, color: PAL[1] } });
    lines.push({ x: cv.x, y: cv.R.map(r => r * k), mode: 'lines', name: `Computed × ${fmt(k, 3)}`, line: { color: PAL[1], width: 1.5, dash: 'dot' } });
  }
  plot('ftPlot', lines, {
    xaxis: { title: { text: `Probe distance from the electrode ${d.measured_from} (m)` }, gridcolor: css('--line') },
    yaxis: { title: { text: 'Apparent resistance V/I (Ω)' }, gridcolor: css('--line') }
  });
  toast('Fall-of-potential plan ready.', 'ok');
});

/* --------------------------------------------- page 7: IEC 62305-2:2024 risk */
let RISK_CLASS = null;
const RK_OPT = {
  floor: [['concrete', 'Concrete, soil (r_t 10⁻²)'], ['marble', 'Marble, ceramic (10⁻³)'], ['gravel', 'Gravel, carpet (10⁻⁴)'], ['linoleum', 'Asphalt, linoleum, wood (10⁻⁵)']],
  fire: [['ordinary', 'Ordinary (r_f 10⁻²)'], ['low', 'Low (10⁻³)'], ['high', 'High (10⁻¹)'], ['none', 'None (0)'], ['explosion_2_22', 'Explosive zone 2/22 (10⁻³)'], ['explosion_1_21', 'Explosive zone 1/21 (10⁻¹)'], ['explosion_0_20_50', 'Explosive zone 0/20 (1)']],
  prov: [['none', 'None (r_p 1)'], ['manual', 'Extinguishers, manual alarm (0.5)'], ['automatic', 'Automatic alarm or extinguishing (0.2)']],
  loss: [['low', 'Low — private house'], ['normal', 'Normal — office, school, hotel'], ['high', 'High — hospital rooms, museum, control room'], ['very_high', 'Very high — explosion risk, life-saving equipment']],
  wire: [['', 'none'], ['different_routing', 'Unshielded, separate routes (1)'], ['same_conduit_025', 'Same conduit, ≤ 0.25 m (0.5)'], ['same_conduit_01', 'Same conduit, ≤ 0.1 m (0.2)'], ['same_cable', 'Same cable (0.01)'], ['shielded', 'Shielded or metal conduit (10⁻⁴)']]
};
const rkSel = (opts, v) => `<select>${opts.map(([k, t]) => `<option value="${k}"${k === v ? ' selected' : ''}>${t}</option>`).join('')}</select>`;
function rkZoneAdd(z = {}) {
  const tr = document.createElement('tr');
  tr.innerHTML = `<td><input type="text" value="${esc(z.name || 'Inside')}" style="width:96px"></td>
    <td><input type="number" value="${z.tz ?? 8760}" step="any" style="width:64px"></td>
    <td>${rkSel(RK_OPT.floor, z.surface || 'concrete')}</td>
    <td>${rkSel(RK_OPT.fire, z.fire_risk || 'ordinary')}</td>
    <td>${rkSel(RK_OPT.prov, z.fire_provisions || 'none')}</td>
    <td>${rkSel(RK_OPT.loss, z.loss || 'low')}</td>
    <td style="text-align:center"><input type="checkbox"${z.exposed ? ' checked' : ''}></td>
    <td style="text-align:center"><input type="checkbox"${(z.life ?? z.loss === 'very_high') ? ' checked' : ''}></td>
    <td>${rkSel(RK_OPT.wire, z.power ?? 'different_routing')}</td>
    <td>${rkSel(RK_OPT.wire, z.telecom ?? 'different_routing')}</td>
    <td><input type="number" value="${z.FT ?? ''}" step="any" placeholder="—" style="width:56px"></td>
    <td style="text-align:center"><input type="checkbox"${z.sur ? ' checked' : ''}></td>
    <td><button class="ghost" title="Remove this zone">✕</button></td>`;
  tr.querySelector('button').onclick = () => tr.remove();
  $('#rkZones tbody').appendChild(tr);
}
function rkZoneRows() {
  return $$('#rkZones tbody tr').map(tr => {
    const i = $$('input', tr), s = $$('select', tr);
    return { name: i[0].value || 'Zone', tz: +i[1].value || 0, surface: s[0].value, fire_risk: s[1].value,
             fire_provisions: s[2].value, loss: s[3].value, exposed: i[2].checked, life: i[3].checked,
             power: s[4].value, telecom: s[5].value, FT: i[4].value === '' ? null : +i[4].value, sur: i[5].checked };
  });
}
window.esRiskZones = function (rows) {
  if (!rows) return rkZoneRows();
  $('#rkZones tbody').innerHTML = '';
  rows.forEach(rkZoneAdd);
};
rkZoneAdd({ name: 'Inside', tz: 8760, FT: 1 });
$('#rkZoneAdd').onclick = () => rkZoneAdd({ name: 'Zone ' + ($$('#rkZones tbody tr').length + 1) });
$('#rkZoneDemo').onclick = () => {
  [['rkNg', 2], ['rkK', 2], ['rkL', 20], ['rkW', 40], ['rkH', 25], ['rkLoc', 'isolated'], ['rkEnv', 'suburban'],
   ['rkMat', 'reinforced'], ['rkWm', ''], ['rkTws', 1], ['rkLine', 'buried_unshielded'], ['rkLL', 100], ['rkLH', 1000],
   ['rkRs', 'unshielded'], ['rkUw', 2.5], ['rkTlc', 'fibre'], ['rkUwT', 1.5]].forEach(([k, v]) => set(k, v));
  window.esRiskZones([
    { name: 'Z1 entrance', tz: 175, surface: 'marble', fire_risk: 'none', power: '', telecom: '' },
    { name: 'Z2 roof', tz: 18, surface: 'linoleum', fire_risk: 'none', exposed: true, power: '', telecom: '' },
    { name: 'Z3 archive', tz: 440, surface: 'linoleum', fire_risk: 'high', fire_provisions: 'automatic', loss: 'normal', power: 'same_conduit_01', telecom: 'different_routing', FT: 0.05 },
    { name: 'Z4 offices', tz: 2630, surface: 'linoleum', fire_risk: 'low', fire_provisions: 'manual', loss: 'normal', power: 'same_conduit_01', telecom: 'different_routing', FT: 0.05 },
    { name: 'Z5 computer centre', tz: 2200, surface: 'linoleum', fire_risk: 'low', fire_provisions: 'automatic', loss: 'high', power: 'same_conduit_01', telecom: 'different_routing', FT: 0.05 }]);
  toast('Office building of IEC 62305-2:2024 Annex F.3 loaded (N_SG = 4).');
};
function rkPayload() {
  const lt = V('rkLine'), tl = V('rkTlc');
  const install = lt.includes('aerial') ? 'aerial' : 'buried';
  const secs = [{ length: N('rkLL', 1000), install, type: 'lv' }];
  if (N('rkLH', 0) > 0) secs.push({ length: N('rkLH', 0), install, type: 'hv' });
  const lines = [{ name: 'Power', kind: 'power', sections: secs, shielding: lt, rs: V('rkRs'), Uw: N('rkUw', 2.5) }];
  if (tl !== 'none') lines.push({ name: 'Telecom', kind: 'telecom', fibre: tl === 'fibre',
    sections: [{ length: N('rkLT', 1000), install, type: 'telecom' }], shielding: lt, rs: V('rkRs'), Uw: N('rkUwT', 1.5) });
  const zones = rkZoneRows().map(z => {
    const systems = [];
    if (z.power) systems.push({ line: 'Power', ks3: z.power });
    if (z.telecom) systems.push(tl === 'none' ? { line: null, ks3: z.telecom, Uw: N('rkUwT', 1.5), CLD: 0 }
      : tl === 'fibre' ? { line: null, ks3: z.telecom, Uw: N('rkUwT', 1.5), CLD: 1 } : { line: 'Telecom', ks3: z.telecom });
    return { name: z.name, tz: z.tz, surface: z.surface, fire_risk: z.fire_risk, fire_provisions: z.fire_provisions,
             loss: z.loss, exposed: z.exposed, life_systems: z.life, FT: z.FT, systems,
             surroundings: z.sur ? { scenario: V('rkSurScen'), spreading: V('rkSurSpread') === '1',
                                     area: V('rkSurArea'), internal: C('rkSurInt') } : null };
  });
  if (!zones.length) throw new Error('Add at least one risk zone.');
  return { NG: N('rkNg', 4), k: N('rkK', 2), L: N('rkL', 40), W: N('rkW', 20), H: N('rkH', 15), location: V('rkLoc'),
           environment: V('rkEnv'), material: V('rkMat'), mesh_width: V('rkWm') === '' ? null : N('rkWm', 0),
           ptws: N('rkTws', 1), lines, zones };
}
$('#rkRun').onclick = e => run(e.target, async () => {
  const d = await api('/api/risk', rkPayload());
  S.risk = d;
  const u = d.unprotected, c = d.choice || d.best, pr = d.protected;
  RISK_CLASS = c && c.lps !== 'none' ? c.lps : null;
  $('#rkUseCls').disabled = !RISK_CLASS;
  const ex = v => v ? v.toExponential(2) : '0';
  const lvl = (k, v) => v === 'none' ? 'none' : (k === 'lps' ? 'class ' : 'LPL ') + v;
  const zhead = u.zones.map(z => `<th style="text-align:right">${esc(z.name)}</th>`).join('');
  const comp = Object.keys(u.zones[0].components).filter(k => u.zones.some(z => z.components[k] > 0) || (pr && pr.zones.some(z => z.components[k] > 0)));
  const ztable = (r, title) => `<p class="small" style="margin:10px 0 2px"><b>${title}</b> — risk components ×10⁻⁵ per year</p>
    <div style="overflow-x:auto"><table class="data"><thead><tr><th>Component</th>${zhead}</tr></thead><tbody>` +
    comp.map(k => `<tr><td>${k}</td>${r.zones.map(z => `<td class="n">${(z.components[k] * 1e5).toFixed(3)}</td>`).join('')}</tr>`).join('') +
    (r.zones.some(z => z.surroundings) ? `<tr><td>of which surroundings (Annex E)</td>${r.zones.map(z => `<td class="n">${z.surroundings ? (z.RE * 1e5).toFixed(3) : '—'}</td>`).join('')}</tr>` : '') +
    `<tr><td><b>R</b></td>${r.zones.map(z => `<td class="n"><b class="${z.ok_R ? 'ok' : 'bad'}">${(z.R * 1e5).toFixed(3)}</b></td>`).join('')}</tr>` +
    `<tr><td>F (1/yr)</td>${r.zones.map(z => `<td class="n">${z.systems.length ? `<span class="${z.ok_F === false ? 'bad' : ''}">${z.F.toFixed(3)}</span>${z.FT ? ' / ' + z.FT : ''}` : '—'}</td>`).join('')}</tr>` +
    '</tbody></table></div>';
  $('#rkOut').innerHTML = `<div class="note ${d.needed ? 'warn' : 'info'}">${esc(d.note)}</div>` + rows([
    ['Strike-point density', 'N_SG', u.NSG, '1/km²/yr', `k·N_G, k = ${u.k}`],
    ['Collection area', 'A_D', u.AD, 'm²', 'L·W + 6H(L + W) + 9πH²'],
    ['Flashes to the structure', 'N_D', u.ND, '1/yr', 'N_SG·A_D·C_D·10⁻⁶'],
    ...u.lines.filter(l => l.NL > 0 || l.NI > 0).map(l => [`Flashes to / near the ${l.name.toLowerCase()} line`, 'N_L / N_I', `${l.NL.toPrecision(3)} / ${l.NI.toPrecision(3)}`, '1/yr', `r_I = ${l.rI ? l.rI.toFixed(0) : '—'} m`]),
    ['Largest zone risk, unprotected', 'R', ex(u.R), '1/yr', 'tolerable R_T = 10⁻⁵'],
    c ? [d.choice ? 'Protection found' : 'Closest protection (not enough alone)', '—', `LPS ${lvl('lps', c.lps)}, entrance SPDs ${lvl('', c.eb)}, coordinated SPDs ${lvl('', c.spd)}`, '', d.choice ? 'least protection meeting R_T and F_T' : 'see the note'] : null,
    pr ? ['Largest zone risk, protected', 'R', ex(pr.R), '1/yr', ''] : null
  ]) + ztable(u, 'Unprotected') + (pr ? ztable(pr, 'With the protection found') : '');
  toast('Risk assessed.', 'ok');
});
$('#rkUseCls').onclick = () => {
  if (!RISK_CLASS) return;
  set('lCls', RISK_CLASS);
  toast(`LPS class ${RISK_CLASS} set — run the earth-termination design.`);
};

/* --------------------------------------------- page 7: SPD coordination */
$('#spRun').onclick = e => run(e.target, async () => {
  const d = await api('/api/spd', {
    lpl: V('spLpl'), n_services: N('spNs', 2), conductors: N('spM', 4), Uw: N('spUw', 2.5),
    circuit_length: N('spLen', 5), Ui: N('spUi', 0), critical: C('spCrit'), phases: +V('spPh'), connection: V('spCt'),
    stages: [
      {
        name: 'Type 1 (service entrance)', type: '1', technology: V('spT1'), Up: N('spUp1', 2.5), lead: N('spLead', 0.5),
        Iimp: N('spIimp', 12.5), distance_to_next: N('spDist', 10)
      },
      { name: 'Type 2 (sub-board)', type: '2', technology: 'limiting', Up: N('spUp2', 1.3), lead: N('spLead', 0.5), In: N('spIn', 20) }
    ]
  });
  S.spd = d;
  $('#spOut').innerHTML = `<div class="note ${d.passed ? 'info' : 'warn'}">${esc(d.note)}</div>` + rows([
    ['Lightning current (LPL)', 'I', d.I_peak_kA, 'kA', `LPL ${d.lpl}`],
    ['Impulse current per conductor', 'I_imp', d.Iimp_per_conductor_kA, 'kA', 'IEC 62305-1 Annex E'],
    ...(d.simplified ? Object.entries(d.simplified.Iimp_kA).map(([m, v]) => [`Simplified I_imp at the origin, ${m}`, 'I_imp', v, 'kA', `Table C.3, ${d.simplified.connection}`]) : []),
    ...d.stages.map(s => [`Effective protection level, ${s.name}`, 'U_p/f', s.Upf, 'kV', `U_p ${fmt(s.Up)} kV + ΔU ${fmt(s.dU)} kV (0.1·${fmt(s.I_spd)} kA per m of lead)`])
  ]) + checksHtml(d.checks);
  toast('SPD check done.', d.passed ? 'ok' : 'err');
});

/* ----------------------------------------------------------------- report */
window.esStudiesForReport = function () {
  const out = {};
  ['faultsweep', 'cablesheath', 'convergence', 'seasonal', 'montecarlo', 'powerfreq', 'optimise', 'earthtest', 'risk', 'spd']
    .forEach(k => { if (S[k]) out[k] = S[k]; });
  if (out.montecarlo) out.montecarlo = { ...out.montecarlo, samples: undefined };
  if (out.powerfreq) out.powerfreq = { ...out.powerfreq, surface: undefined, node_potentials: undefined };
  if (out.earthtest) out.earthtest = { ...out.earthtest, curve: { ...out.earthtest.curve, x: undefined, R: undefined } };
  if (out.optimise) out.optimise = { ...out.optimise, items: undefined };
  if (out.risk) out.risk = { ...out.risk, combinations: undefined };
  return Object.keys(out).length ? out : null;
};

/* ------------------------------------------ page 5: governing values (1.8.2)
   The verdict of the numerical page: the largest touch, step, R_g and GPR
   from the plain solution and every study run on the same model. */
function govPayload() {
  const strip = (o, keys) => { if (!o) return o; const c = { ...o }; keys.forEach(k => delete c[k]); return c; };
  const studies = {};
  if (S.convergence) studies.convergence = S.convergence;
  if (S.seasonal) studies.seasonal = S.seasonal;
  if (S.montecarlo) studies.montecarlo = strip(S.montecarlo, ['samples']);
  if (S.powerfreq) studies.powerfreq = strip(S.powerfreq, ['surface', 'node_potentials', 'geometry']);
  return {
    bem: strip(S.bem, ['surface', 'geometry', 'current', 'profile', 'probes']),
    studies
  };
}
window.esRefreshGoverning = async function () {
  const out = $('#nGovOut');
  if (!S.bem) { S.governing = null; if (out) out.innerHTML = '<div class="hint">Run the numerical solution first.</div>'; return; }
  let g;
  try { g = await api('/api/bem/governing', govPayload()); }
  catch (e) { if (out) out.innerHTML = `<div class="note warn">${esc(e.message || String(e))}</div>`; return; }
  S.governing = g;
  if (g.passed !== null && g.passed !== undefined) markNav('numerical', g.passed);
  if (!out) return;
  const Q = g.quantities || {};
  const lab = { touch: ['Maximum touch voltage', 'U_T', 'V'], step: ['Maximum step voltage', 'U_S', 'V'],
                Rg: ['Earth resistance / impedance', 'R_g', 'Ω'], GPR: ['Ground potential rise', 'GPR', 'V'] };
  const tbl = `<table class="data"><thead><tr><th>Quantity</th><th style="text-align:right">Governing</th><th>Unit</th>
      <th>From</th><th style="text-align:right">Plain solution</th><th style="text-align:right">Change</th></tr></thead><tbody>` +
    ['touch', 'step', 'Rg', 'GPR'].filter(k => Q[k]).map(k => {
      const q = Q[k], [n, , u] = lab[k];
      return `<tr><td>${n}</td><td class="n">${fmt(q.value)}</td><td class="muted small">${u}</td>
        <td>${esc(q.label)}${q.detail ? ` <span class="muted small">(${esc(q.detail)})</span>` : ''}</td>
        <td class="n">${fmt(q.base)}</td><td class="n">${q.base ? pct(100 * (q.ratio - 1), 1) : '—'}</td></tr>`;
    }).join('') + '</tbody></table>';
  out.innerHTML = (g.checks && g.checks.length ? checksHtml(g.checks, g.note) : `<div class="note info">${esc(g.note)}</div>`) + tbl;
};

/* ------------------------------------------ page 5: DXF site drawing (1.8.4) */
(function () {
  let DXF_TEXT = null, DXF_INFO = null;
  const box = $('#dxfLayers');
  if (!box) return;
  $('#dxfFile').onchange = async e => {
    const f = e.target.files && e.target.files[0];
    if (!f) return;
    try {
      // binary DXF (1.9.5) goes as base64, an ASCII DXF as text
      const buf = new Uint8Array(await f.arrayBuffer());
      const head = String.fromCharCode(...buf.subarray(0, 18));
      if (head === 'AutoCAD Binary DXF') {
        let bin = '';
        for (let i = 0; i < buf.length; i += 0x8000) bin += String.fromCharCode(...buf.subarray(i, i + 0x8000));
        DXF_TEXT = { data_b64: btoa(bin) };
      } else {
        DXF_TEXT = { text: new TextDecoder('utf-8').decode(buf) };
      }
      DXF_INFO = await api('/api/dxf/inspect', DXF_TEXT);
    } catch (err) {
      DXF_TEXT = DXF_INFO = null; box.innerHTML = '';
      $('#dxfAdd').disabled = $('#dxfReplace').disabled = true;
      toast(err.message || String(err), 'err'); return;
    }
    const L = DXF_INFO.layers;
    box.innerHTML = `<div class="hint">${DXF_INFO.entities} entities; drawing unit: ${esc(DXF_INFO.unit)}${DXF_INFO.scale ? ` (${DXF_INFO.scale} m per unit)` : ' — give the scale below'}.</div>
      <table class="data"><thead><tr><th>Layer</th><th>Contents</th><th>Import as</th></tr></thead><tbody>` +
      Object.keys(L).map(k => {
        const c = L[k], parts = [];
        if (c.lines) parts.push(`${c.lines} lines`); if (c.polylines) parts.push(`${c.polylines} polylines`);
        if (c.arcs) parts.push(`${c.arcs} arcs`); if (c.circles) parts.push(`${c.circles} circles`);
        if (c.points) parts.push(`${c.points} points / blocks`);
        return `<tr><td>${esc(k)}</td><td class="small">${parts.join(', ')}</td><td><select data-layer="${esc(k)}">` +
          ['conductor', 'rod', 'fence', 'ignore'].map(o => `<option value="${o}"${o === c.suggest ? ' selected' : ''}>${o}</option>`).join('') +
          '</select></td></tr>';
      }).join('') + '</tbody></table>';
    $('#dxfAdd').disabled = $('#dxfReplace').disabled = false;
  };
  async function load(replace) {
    if (!DXF_TEXT) return;
    const mapping = {};
    $$('#dxfLayers select').forEach(s => { mapping[s.dataset.layer] = s.value; });
    const d = await api('/api/dxf/import', {
      ...DXF_TEXT, mapping, depth: N('dxfDepth', 0.6), conductor_radius: N('dxfR', 0.005),
      rod_length: N('dxfRodL', 3), rod_radius: N('dxfRodR', 0.008),
      scale: NB('dxfScale'), to_origin: C('dxfOrigin'), fence: { bonded: C('dxfBond') }
    });
    if (replace) BEM_ITEMS = [];
    d.items.forEach(it => BEM_ITEMS.push(it));
    renderBem();
    const c = d.counts;
    $('#dxfOut').innerHTML = `<div class="note info">Imported ${c.conductors} conductor pieces, ${c.rings} rings, ${c.rods} rods and
      ${c.fences} fences at ${d.scale} m per drawing unit${C('dxfOrigin') ? `; the drawing was moved by ${fmt(-d.origin[0])}, ${fmt(-d.origin[1])} units so that its lower-left corner is at the origin` : ''}.</div>`;
    toast('DXF geometry added to the electrode table.', 'ok');
  }
  $('#dxfAdd').onclick = e => run(e.target, () => load(false));
  $('#dxfReplace').onclick = e => run(e.target, () => load(true));
})();

/* --------------------------------------------- page 2: cable sheaths (1.8.5) */
$('#csRun') && ($('#csRun').onclick = e => run(e.target, async () => {
  const p = {
    If_kA: N('csIf', 10), length_km: N('csLen', 3), R_A: N('csRA', 0.5), R_B: N('csRB', 1),
    r_sheath_km: N('csRs', 0.5), r_armour_km: NB('csRar'), r_mean: N('csRm', 0.03),
    formation: V('csForm'), spacing: N('csS', 0.09), n_circuits: N('csN', 1),
    joints: V('csBond') === 'cross_bonded' ? null : (V('csJ').trim() || null), R_joint: NB('csRj'),
    bonding: V('csBond'), fault_at: V('csAt'),
    rho: N('csRho', 100), f: N('fFreq', 50), source_beyond: C('csBeyond'),
    minor_km: V('csBond') === 'cross_bonded' ? V('csMinor').trim() : null,
    faulted_phase: +V('csPh'), circuit_sep: N('csSep', 0.5)
  };
  const d = await api('/api/cable/sheath', p);
  S.cablesheath = d;
  const xb = d.bonding === 'cross_bonded';
  $('#csOut').innerHTML = `<div class="note info">${esc(d.note)}</div>` + rows([
    ...(xb ? [] : [
      ['Sheath self impedance (all sheaths)', 'z_s', `${fmt(d.zs_km[0], 3)} + j${fmt(d.zs_km[1], 3)}`, 'Ω/km', 'Carson, earth return'],
      ['Core-to-sheath mutual impedance', 'z_m', `${fmt(d.zm_km[0], 3)} + j${fmt(d.zm_km[1], 3)}`, 'Ω/km', `reduction factor |1 − z_m/z_s| = ${fmt(d.reduction_factor, 3)}`]]),
    ['Current returning in the sheaths', 'I_s', d.I_sheath_kA, 'kA', xb ? `largest in one sheath ${fmt(d.I_sheath_max_kA, 3)} kA` : ''],
    ['Current into the soil at the faulted end', 'I_g', d.Ig_kA, 'kA', `split factor S_f = ${fmt(d.Sf, 3)}`],
    ['Earth potential rise at A', 'GPR_A', d.GPR_A, 'V', ''],
    ['Earth potential rise at B', 'GPR_B', d.GPR_B, 'V', ''],
    ...(d.joints || []).map((j, i) => [`${xb ? 'Major joint' : 'Joint'} ${i + 1} at ${fmt(j.x_km, 2)} km`, 'V_j', j.V, 'V', `${fmt(j.I_earth_A)} A into its electrode`]),
    ...(d.link_boxes || []).map((l, i) => [`Link box ${i + 1} at ${fmt(l.x_km, 2)} km`, 'V_lb', l.V_max, 'V', `to remote earth; ${fmt(l.V_across_max)} V across the sectionalising joint`])
  ]) + `<div class="rowbtns"><button id="csUse" class="ghost">Use S_f = ${fmt(d.Sf, 3)} above</button></div>`;
  $('#csUse').onclick = () => { set('fSf', +d.Sf.toFixed(4)); toast('Split factor set — recalculate the fault current.'); };
  toast('Sheath return solved.', 'ok');
}));
