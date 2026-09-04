/* EarthSystem — browser application
   Talks to the local Python server; all engineering is done server-side. */
'use strict';

/* ------------------------------------------------------------------ utils */
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const V = id => { const e = $('#' + id); return e ? e.value : ''; };
const N = (id, d = 0) => { const v = parseFloat(V(id)); return isFinite(v) ? v : d; };
const NB = (id) => { const v = parseFloat(V(id)); return isFinite(v) ? v : null; };
const C = id => { const e = $('#' + id); return e ? e.checked : false; };
const set = (id, v) => { const e = $('#' + id); if (e) { if (e.type === 'checkbox') e.checked = !!v; else e.value = v; } };

function fmt(v, d) {
  if (v === null || v === undefined || v === '') return '—';
  if (typeof v === 'boolean') return v ? '✔' : '✘';
  if (typeof v !== 'number') return String(v);
  if (!isFinite(v)) return '—';
  const a = Math.abs(v);
  if (d !== undefined) return v.toLocaleString(undefined, { minimumFractionDigits: d, maximumFractionDigits: d });
  if (v === 0) return '0';
  if (a >= 1e6 || a < 1e-4) return v.toExponential(3);
  if (a >= 1000) return v.toLocaleString(undefined, { maximumFractionDigits: 1 });
  if (a >= 100) return v.toFixed(1);
  if (a >= 10) return v.toFixed(2);
  if (a >= 1) return v.toFixed(3);
  return v.toFixed(4);
}
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

function toast(msg, kind = '') {
  const d = document.createElement('div');
  d.className = 'toast ' + kind;
  d.innerHTML = esc(msg);
  $('#toast').appendChild(d);
  setTimeout(() => { d.style.opacity = 0; setTimeout(() => d.remove(), 300); }, kind === 'err' ? 7000 : 3200);
}

async function api(path, payload) {
  const r = await fetch(path, {
    method: payload === undefined ? 'GET' : 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: payload === undefined ? undefined : JSON.stringify(payload)
  });
  const j = await r.json().catch(() => ({ error: 'Invalid response from the server.' }));
  if (!r.ok || j.error) throw new Error(j.error || ('HTTP ' + r.status));
  return j;
}

function busy(btn, on) {
  if (!btn) return;
  btn.disabled = on;
  if (on) { btn.dataset.html = btn.innerHTML; btn.innerHTML = '<span class="spinner"></span> working…'; }
  else if (btn.dataset.html) btn.innerHTML = btn.dataset.html;
}

async function run(btn, fn) {
  busy(btn, true);
  try { await fn(); }
  catch (e) { toast(e.message || String(e), 'err'); console.error(e); }
  finally { busy(btn, false); }
}

/* -------------------------------------------------------------- rendering */
function kpis(el, items) {
  $('#' + el).innerHTML = items.map(k =>
    `<div class="kpi ${k.state || ''}"><div class="v">${k.value}</div><div class="l">${k.label}</div></div>`).join('');
}
function rows(list) {
  return `<table class="data"><thead><tr><th>Quantity</th><th>Symbol</th><th style="text-align:right">Value</th><th>Unit</th><th>Basis</th></tr></thead><tbody>` +
    list.filter(Boolean).map(r =>
      `<tr><td>${esc(r[0])}</td><td class="sym">${r[1] ?? ''}</td><td class="n">${typeof r[2] === 'number' ? fmt(r[2]) : esc(r[2])}</td><td class="muted small">${esc(r[3] ?? '')}</td><td class="src">${esc(r[4] ?? '')}</td></tr>`
    ).join('') + '</tbody></table>';
}
function checksHtml(list, narrative, crossCheck) {
  let head = '';
  if (narrative) {
    const ok = !list || list.every(c => c.passed !== false);
    head = `<div class="verdictbox ${ok ? 'ok' : 'bad'}">
      <div class="vhead"><span class="badge ${ok ? 'ok' : 'bad'}">${ok ? 'COMPLIES' : 'DOES NOT COMPLY'}</span></div>
      <p>${esc(narrative)}</p></div>`;
  }
  if (!list || !list.length) return head + '<div class="empty">No criteria evaluated.</div>';
  const rows = list.map((c, i) => {
    const ok = c.passed !== false;
    let m = '—';
    if (typeof c.value === 'number' && typeof c.limit === 'number' && c.limit)
      m = fmt((c.limit - c.value) / c.limit * 100, 1) + ' %';
    else if (typeof c.margin_pct === 'number') m = fmt(c.margin_pct, 1) + ' %';
    const hasWhy = c.meaning || c.verdict || c.driver || (c.remedy && c.remedy.length) || c.headroom;
    const why = !hasWhy ? '' : `
      <tr class="whyrow" id="why-${i}-${Math.random().toString(36).slice(2, 7)}" hidden>
        <td colspan="6"><div class="why">
          ${c.verdict ? `<p class="vsum"><b>${ok ? 'Why it passes' : 'Why it fails'}:</b> ${esc(c.verdict)}</p>` : ''}
          ${c.driver ? `<p><b>What drives the number:</b> ${esc(c.driver)}</p>` : ''}
          ${c.meaning ? `<p class="mean"><b>What the criterion means:</b> ${esc(c.meaning)}</p>` : ''}
          ${c.headroom ? `<p><b>Margin:</b> ${esc(c.headroom)}</p>` : ''}
          ${(c.remedy && c.remedy.length) ? `<div><b>How to fix it</b><ol>${c.remedy.map(r => `<li>${esc(r)}</li>`).join('')}</ol></div>` : ''}
        </div></td></tr>`;
    return `<tr class="crow${hasWhy ? ' has-why' : ''}">
        <td>${hasWhy ? '<span class="twist">▸</span>' : ''}${esc(c.name)}${c.note ? `<div class="muted small">${esc(c.note)}</div>` : ''}</td>
        <td class="n">${typeof c.value === 'number' ? fmt(c.value) : '—'} ${esc(c.unit || '')}</td>
        <td class="n">${typeof c.limit === 'number' ? fmt(c.limit) : '—'} ${esc(c.unit || '')}</td>
        <td class="n">${m}</td>
        <td><span class="badge ${ok ? 'ok' : 'bad'}">${ok ? 'PASS' : 'FAIL'}</span></td>
        <td class="muted small">${hasWhy ? 'why ▾' : ''}</td>
      </tr>${why}`;
  }).join('');
  const cc = crossCheck ? `<div class="note info" style="margin-top:10px">${esc(crossCheck)}</div>` : '';
  return head + `<table class="data checks"><thead><tr><th>Criterion</th><th style="text-align:right">Value</th>
    <th style="text-align:right">Limit</th><th>Margin</th><th>Result</th><th></th></tr></thead>
    <tbody>${rows}</tbody></table>${cc}
    <div class="hint">Click any row to see why it passed or failed, what drives the number, and how to change it.</div>`;
}

// expand / collapse the explanation under a criterion
document.addEventListener('click', e => {
  const row = e.target.closest('tr.crow.has-why');
  if (!row) return;
  const why = row.nextElementSibling;
  if (!why || !why.classList.contains('whyrow')) return;
  why.hidden = !why.hidden;
  const t = row.querySelector('.twist');
  if (t) t.textContent = why.hidden ? '\u25b8' : '\u25be';
  row.classList.toggle('open', !why.hidden);
});

/* ------------------------------------------------------------------ plots */
function css(v) { return getComputedStyle(document.body).getPropertyValue(v).trim(); }
function baseLayout(extra) {
  const ink = css('--ink'), ink2 = css('--ink-2'), line = css('--line');
  return Object.assign({
    paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)',
    font: { family: 'Segoe UI, Inter, sans-serif', size: 11.5, color: ink2 },
    margin: { l: 62, r: 22, t: 26, b: 52 },
    xaxis: { gridcolor: line, zerolinecolor: line, linecolor: line, title: { font: { color: ink } } },
    yaxis: { gridcolor: line, zerolinecolor: line, linecolor: line, title: { font: { color: ink } } },
    legend: { orientation: 'h', y: -0.2, font: { size: 11 } },
    hovermode: 'closest'
  }, extra || {});
}
const PLOTS = {};
function plot(id, traces, layout) {
  const cfg = { displaylogo: false, responsive: true, toImageButtonOptions: { format: 'png', scale: 2 } };
  Plotly.react(id, traces, baseLayout(layout), cfg);
  PLOTS[id] = true;
}
const PAL = ['#0f6b8a', '#c0322b', '#0b7a45', '#a8630a', '#6d4aa8', '#2b7fa8'];

/* ------------------------------------------------------------------ state */
const S = { meta: null, soil: null, fault: null, conductor: null, grid: null, bem: null, building: null, lightning: null, sysgnd: null };
const INPUT_IDS = () => $$('#main input, #main select, #main textarea').filter(e => e.id);

function snapshot() {
  const inputs = {};
  INPUT_IDS().forEach(e => inputs[e.id] = e.type === 'checkbox' ? e.checked : e.value);
  return {
    app: 'EarthSystem', version: 1, saved: new Date().toISOString(),
    name: V('projName'), inputs,
    tables: { soil: soilRows(), bem: BEM_ITEMS, building: BUILD_ITEMS },
    results: S
  };
}
function restore(p) {
  if (!p || !p.inputs) return;
  set('projName', p.name || '');
  Object.entries(p.inputs).forEach(([k, v]) => set(k, v));
  if (p.tables) {
    if (p.tables.soil) { $('#soilTable tbody').innerHTML = ''; p.tables.soil.forEach(r => soilAdd(r.spacing, r.rho)); }
    if (p.tables.bem) { BEM_ITEMS = p.tables.bem; renderBem(); }
    if (p.tables.building) { BUILD_ITEMS = p.tables.building; renderBuild(); }
  }
  Object.assign(S, p.results || {});
  toast('Project loaded.', 'ok');
}

function markNav(page, ok) {
  const el = $(`.navitem[data-page="${page}"]`);
  if (!el) return;
  el.classList.remove('done', 'failed');
  el.classList.add(ok === false ? 'failed' : 'done');
}

/* ------------------------------------------------------------------- nav  */
$$('.navitem').forEach(it => it.addEventListener('click', () => {
  $$('.navitem').forEach(x => x.classList.remove('active'));
  $$('.page').forEach(x => x.classList.remove('active'));
  it.classList.add('active');
  $('#page-' + it.dataset.page).classList.add('active');
  setTimeout(() => Object.keys(PLOTS).forEach(id => { const d = $('#' + id); if (d && d.offsetParent) Plotly.Plots.resize(d); }), 60);
}));
document.addEventListener('click', e => {
  const t = e.target.closest('.tab'); if (!t) return;
  const wrap = t.parentElement;
  $$('.tab', wrap).forEach(x => x.classList.remove('active'));
  t.classList.add('active');
  const scope = wrap.parentElement;
  $$('.tabpane', scope).forEach(p => p.classList.remove('active'));
  const pane = $('#pane-' + t.dataset.t, scope); if (pane) pane.classList.add('active');
  setTimeout(() => Object.keys(PLOTS).forEach(id => { const d = $('#' + id); if (d && d.offsetParent) Plotly.Plots.resize(d); }), 60);
});

$('#btnTheme').addEventListener('click', () => {
  const dark = document.body.dataset.theme === 'dark';
  document.body.dataset.theme = dark ? '' : 'dark';
  localStorage.setItem('es-theme', dark ? '' : 'dark');
  Object.keys(PLOTS).forEach(id => { const d = $('#' + id); if (d && d.data) Plotly.relayout(d, baseLayout()); });
});
document.body.dataset.theme = localStorage.getItem('es-theme') || '';

/* ============================================================= 1. SOIL === */
function soilAdd(a = '', r = '') {
  const tr = document.createElement('tr');
  tr.innerHTML = `<td><input type="number" step="0.1" value="${a}"></td>
                  <td><input type="number" step="0.1" value="${r}"></td>
                  <td><button class="ghost" title="Remove">✕</button></td>`;
  tr.querySelector('button').onclick = () => tr.remove();
  $('#soilTable tbody').appendChild(tr);
}
function soilRows() {
  return $$('#soilTable tbody tr').map(tr => {
    const i = $$('input', tr);
    return { spacing: parseFloat(i[0].value), rho: parseFloat(i[1].value) };
  }).filter(r => isFinite(r.spacing) && isFinite(r.rho));
}
$('#soilAdd').onclick = () => soilAdd();
$('#soilClear').onclick = () => $('#soilTable tbody').innerHTML = '';
$('#soilDemo').onclick = () => {
  $('#soilTable tbody').innerHTML = '';
  [[1, 320], [1.5, 245], [2, 182], [3, 162], [4, 168], [6, 182], [9, 198], [12, 214], [16, 228], [20, 236]]
    .forEach(([a, r]) => soilAdd(a, r));
  toast('Example Wenner traverse loaded.');
};
$('#soilInput').onchange = () => {
  $('#soilCol2').textContent = V('soilInput') === 'rho' ? 'ρₐ (Ω·m)' : 'R (Ω)';
};

$('#soilRun').onclick = e => run(e.target, async () => {
  const rr = soilRows();
  if (rr.length < 3) throw new Error('At least three measurement points are needed.');
  const key = V('soilInput');
  const payload = {
    array: V('soilArray'),
    rows: rr.map(r => key === 'rho' ? { a: r.spacing, s: r.spacing, rho: r.rho, d: 1 }
      : { a: r.spacing, s: r.spacing, R: r.rho, d: 1 }),
    grid_depth: N('soilDepth', 0.5), rod_length: N('soilRod', 0),
    equivalent_method: V('soilEquiv')
  };
  const d = await api('/api/soil/invert', payload);
  S.soil = d; markNav('soil', true);
  kpis('soilKpis', [
    { value: fmt(d.rho1) + ' <small>Ω·m</small>', label: 'Upper layer ρ₁' },
    { value: fmt(d.rho2) + ' <small>Ω·m</small>', label: 'Lower layer ρ₂' },
    { value: fmt(d.h) + ' <small>m</small>', label: 'Layer thickness h' },
    { value: fmt(d.K, 3), label: 'Reflection factor K' },
    { value: fmt(d.rms_pct, 2) + ' %', label: 'RMS fit error', state: d.rms_pct < 8 ? 'ok' : 'bad' },
    { value: fmt(d.equivalent.rho_equivalent) + ' <small>Ω·m</small>', label: 'Equivalent uniform ρ' }
  ]);
  plot('soilPlot', [
    { x: d.spacings, y: d.measured, mode: 'markers', name: 'Measured', marker: { size: 9, color: PAL[1] } },
    { x: d.curve_x, y: d.curve_y, mode: 'lines', name: 'Two-layer fit', line: { width: 2.5, color: PAL[0] } }
  ], {
    xaxis: { type: 'log', title: { text: 'Electrode spacing (m)' }, gridcolor: css('--line') },
    yaxis: { title: { text: 'Apparent resistivity ρₐ (Ω·m)' }, gridcolor: css('--line') }
  });
  $('#soilOut').innerHTML = rows([
    ['Upper-layer resistivity', 'ρ₁', d.rho1, 'Ω·m', 'Two-layer least-squares inversion'],
    ['Lower-layer resistivity', 'ρ₂', d.rho2, 'Ω·m', ''],
    ['Upper-layer thickness', 'h', d.h, 'm', ''],
    ['Reflection factor', 'K', d.K, '–', 'K = (ρ₂ − ρ₁)/(ρ₂ + ρ₁)'],
    ['RMS fit error', 'ε', d.rms_pct, '%', ''],
    ['Arithmetic average of ρₐ', 'ρ̄', d.uniform_average, 'Ω·m', 'For comparison only'],
    ['Electrode penetration', '—', d.equivalent.penetration, 'm', ''],
    ['Equivalent uniform resistivity', 'ρ', d.equivalent.rho_equivalent, 'Ω·m', d.equivalent.note]
  ]) + `<table class="data"><thead><tr><th>a (m)</th><th style="text-align:right">Measured ρₐ</th><th style="text-align:right">Fitted ρₐ</th><th style="text-align:right">Δ (%)</th></tr></thead><tbody>` +
    d.spacings.map((a, i) => `<tr><td class="n">${fmt(a)}</td><td class="n">${fmt(d.measured[i])}</td><td class="n">${fmt(d.fitted[i])}</td><td class="n">${fmt(d.residual_pct[i], 2)}</td></tr>`).join('') +
    `</tbody></table><div class="note info">The two-layer model is fitted by minimising the relative
     error over all spacings (IEEE Std 81-2012 §8.5). Use the equivalent uniform resistivity for the
     closed-form IEEE 80 equations, and the layered model itself for the numerical solver.</div>`;
  toast('Soil model fitted.', 'ok');
});

/* ============================================================ 2. FAULT === */
$('#fMode').onchange = () => {
  const m = V('fMode');
  $('#fSourceBox').style.display = m === 'source' ? '' : 'none';
  $('#fImpBox').style.display = m === 'impedance' ? '' : 'none';
};
$('#fRun').onclick = e => run(e.target, async () => {
  const mode = V('fMode');
  const p = {
    Un_kV: N('fUn', 20), c: N('fC', 1.1), mode: mode === 'direct' ? 'impedance' : mode,
    tf: N('fTf', .5), ts: N('fTs', .5), tc: N('fTf', .5), frequency: N('fFreq', 50),
    Sf: N('fSf', 1), Cp: N('fCp', 1)
  };
  if (mode === 'source') {
    p.Sk_MVA = N('fSk', 500); p.xr_source = N('fXR', 10);
    p.X0_factor = N('fX0', 3); p.R0_factor = N('fR0', 1);
    if (N('fTS', 0) > 0) p.transformer = { Sr_MVA: N('fTS'), ukr_pct: N('fTZ', 10) };
  } else {
    p.Z1 = { r: N('fZ1r'), x: N('fZ1x') };
    p.Z0 = { r: N('fZ0r'), x: N('fZ0x') };
  }
  if (NB('f3I0') !== null) p.three_I0_kA = NB('f3I0');
  const d = await api('/api/fault', p);
  S.fault = d; markNav('fault', true);
  kpis('fKpis', [
    { value: fmt(d.line_to_earth.Ik1_kA) + ' <small>kA</small>', label: 'Line-to-earth fault Iₖ₁″' },
    { value: fmt(d.three_phase.Ik_kA) + ' <small>kA</small>', label: 'Three-phase fault Iₖ″' },
    { value: fmt(d.Df, 4), label: 'Decrement factor D_f' },
    { value: fmt(d.Ig_kA) + ' <small>kA</small>', label: 'Symmetrical grid current I_g' },
    { value: fmt(d.IG_kA) + ' <small>kA</small>', label: 'Maximum grid current I_G' },
    { value: fmt(d.thermal.Ith_kA) + ' <small>kA</small>', label: 'Thermal equivalent I_th' }
  ]);
  $('#fOut').innerHTML = rows([
    ['Nominal voltage', 'Uₙ', d.Un_kV, 'kV', ''],
    ['Line-to-earth fault current', 'Iₖ₁″', d.line_to_earth.Ik1_kA, 'kA', d.line_to_earth.formula],
    ['Zero-sequence current', '3I₀', d.three_I0_kA, 'kA', ''],
    ['Three-phase fault current', 'Iₖ″', d.three_phase.Ik_kA, 'kA', d.three_phase.formula],
    ['Peak short-circuit current', 'i_p', d.three_phase.ip_kA, 'kA', 'κ = ' + fmt(d.three_phase.kappa, 3)],
    ['X/R at the fault', 'X/R', d.line_to_earth.xr_ratio, '–', ''],
    ['DC time constant', 'T_a', d.decrement.Ta, 's', 'T_a = X/(2πfR)'],
    ['Decrement factor', 'D_f', d.Df, '–', d.decrement.formula],
    ['Split factor', 'S_f', d.Sf, '–', d.split.note || d.split.formula],
    ['Growth factor', 'C_p', d.Cp, '–', ''],
    ['Symmetrical grid current', 'I_g', d.Ig_kA, 'kA', 'I_g = S_f · C_p · 3I₀'],
    ['Maximum grid current', 'I_G', d.IG_kA, 'kA', d.grid.formula],
    ['Thermal equivalent current', 'I_th', d.thermal.Ith_kA, 'kA', d.thermal.formula]
  ]) + `<div class="formula">I_G = D_f · S_f · C_p · 3I₀ = ${fmt(d.Df, 4)} × ${fmt(d.Sf, 3)} × ${fmt(d.Cp, 2)} × ${fmt(d.three_I0_kA)} kA = <b>${fmt(d.IG_kA)} kA</b></div>`;
  // decrement curve
  const tf = [], df = [];
  for (let i = 0; i < 80; i++) {
    const t = 0.02 * Math.pow(10, i / 79 * 2.2);
    const Ta = d.decrement.xr_ratio / (2 * Math.PI * d.decrement.f);
    tf.push(t); df.push(Math.sqrt(1 + Ta / t * (1 - Math.exp(-2 * t / Ta))));
  }
  plot('fPlot', [
    { x: tf, y: df, mode: 'lines', name: 'D_f', line: { width: 2.5, color: PAL[0] } },
    { x: [d.tf], y: [d.Df], mode: 'markers', name: 'design point', marker: { size: 11, color: PAL[1] } }
  ], {
    xaxis: { type: 'log', title: { text: 'Fault duration t_f (s)' }, gridcolor: css('--line') },
    yaxis: { title: { text: 'Decrement factor D_f' }, gridcolor: css('--line') }
  });
  toast('Fault current calculated.', 'ok');
});

/* ======================================================= 3. CONDUCTOR === */
$('#cRun').onclick = e => run(e.target, async () => {
  const [inst, ins] = V('cIecInst').split('|');
  const [corr, mech] = V('cProt').split('|');
  const p = {
    I_kA: N('cI', 1), tc: N('cT', .5), Df: N('cDf', 1), Ta: N('cTa', 40),
    material: V('cMat'), joint: V('cJoint') || null,
    iec_material: V('cIecMat'), insulation: ins, installation: inst,
    corrosion_protected: corr === '1', mechanically_protected: mech === '1'
  };
  if (N('cSline', 0) > 0) p.S_line_mm2 = N('cSline');
  const d = await api('/api/conductor', p);
  S.conductor = d; markNav('conductor', true);
  const ie = d.ieee80;
  kpis('cKpis', [
    { value: fmt(ie.area_mm2) + ' <small>mm²</small>', label: 'IEEE 80 minimum area' },
    { value: fmt(d.iec.area_mm2) + ' <small>mm²</small>', label: 'IEC 60364 adiabatic area' },
    { value: fmt(d.selected_mm2) + ' <small>mm²</small>', label: 'Selected standard size', state: 'ok' },
    { value: fmt(ie.diameter_mm) + ' <small>mm</small>', label: 'Equivalent diameter' },
    { value: fmt(ie.area_kcmil) + ' <small>kcmil</small>', label: 'IEEE 80 area (kcmil)' }
  ]);
  $('#cOut').innerHTML = rows([
    ['Material', '—', ie.material, '', 'IEEE Std 80-2013 Table 1'],
    ['Design current', 'I', ie.I_kA, 'kA', 'includes D_f = ' + fmt(ie.Df, 3)],
    ['Duration', 't_c', ie.tc, 's', ''],
    ['Maximum temperature', 'T_m', ie.Tm, '°C', V('cJoint') ? 'limited by the joint type' : 'material fusing temperature'],
    ['Ambient temperature', 'T_a', ie.Ta, '°C', ''],
    ['IEEE 80 minimum area', 'A', ie.area_mm2, 'mm²', ie.formula],
    ['IEC adiabatic area', 'S', d.iec.area_mm2, 'mm²', d.iec.formula],
    ['IEC k factor', 'k', d.iec.k, '–', d.iec.k_label],
    ['Minimum buried size (copper)', '—', d.min_buried.copper_mm2, 'mm²', d.min_buried.formula],
    ['Minimum buried size (steel)', '—', d.min_buried.steel_mm2, 'mm²', ''],
    d.pe && ['Protective conductor', 'S_PE', d.pe.area_mm2, 'mm²', d.pe.rule],
    d.bonding && ['Main protective bonding', '—', d.bonding.main_bonding_mm2, 'mm²', d.bonding.formula],
    d.bonding && ['Supplementary bonding (exposed–extraneous)', '—', d.bonding.supplementary_exposed_extraneous_mm2, 'mm²', ''],
    ['Selected standard size', 'A_std', d.selected_mm2, 'mm²', 'largest of the criteria above'],
    ['Conductor diameter for the grid modules', 'd', d.diameter_m, 'm', '']
  ]) + `<div class="formula">A = I / √( (TCAP·10⁻⁴)/(t_c·α_r·ρ_r) · ln[(K₀+T_m)/(K₀+T_a)] )</div>`;
  // area vs duration
  const ts = [], as1 = [], as2 = [];
  for (let i = 0; i < 60; i++) {
    const t = 0.05 * Math.pow(10, i / 59 * 1.8);
    ts.push(t);
    as1.push(ie.area_mm2 * Math.sqrt(t / ie.tc));
    as2.push(d.iec.area_mm2 * Math.sqrt(t / d.iec.t_s));
  }
  plot('cPlot', [
    { x: ts, y: as1, mode: 'lines', name: 'IEEE 80', line: { width: 2.5, color: PAL[0] } },
    { x: ts, y: as2, mode: 'lines', name: 'IEC 60364 adiabatic', line: { width: 2.5, color: PAL[1], dash: 'dash' } },
    { x: [ie.tc], y: [d.selected_mm2], mode: 'markers', name: 'selected', marker: { size: 11, color: PAL[2] } }
  ], {
    xaxis: { type: 'log', title: { text: 'Fault duration (s)' }, gridcolor: css('--line') },
    yaxis: { title: { text: 'Required area (mm²)' }, gridcolor: css('--line') }
  });
  toast('Conductor sized.', 'ok');
});

/* ============================================================= 4. GRID === */
function gridPayload() {
  return {
    rho: N('gRho', 100), rho_s: N('gRhoS', 0), hs: N('gHs', 0.1), ts: N('gTs', .5),
    body_weight: parseInt(V('gBody')), IG_kA: N('gIG', 1),
    Lx: N('gLx', 70), Ly: N('gLy', 70), D: N('gD', 7), h: N('gH', .5), d: N('gd', .01),
    n_rods: parseInt(V('gNr')) || 0, Lr: N('gLr', 0), d_rod: N('gDr', .016),
    rods_on_perimeter: C('gPerim'), shape: V('gShape'), r_method: V('gRMeth')
  };
}
function renderGrid(d) {
  S.grid = d; markNav('grid', d.passed);
  const t = d.tolerable, m = d.mesh;
  kpis('gKpis', [
    { value: fmt(d.Rg) + ' <small>Ω</small>', label: 'Grid resistance R_g' },
    { value: fmt(d.GPR) + ' <small>V</small>', label: 'Ground potential rise' },
    { value: fmt(m.Em) + ' <small>V</small>', label: 'Mesh voltage E_m', state: m.Em <= t.E_touch ? 'ok' : 'bad' },
    { value: fmt(t.E_touch) + ' <small>V</small>', label: 'Tolerable touch' },
    { value: fmt(m.Es) + ' <small>V</small>', label: 'Step voltage E_s', state: m.Es <= t.E_step ? 'ok' : 'bad' },
    { value: fmt(t.E_step) + ' <small>V</small>', label: 'Tolerable step' }
  ]);
  $('#gChecks').innerHTML = checksHtml(d.checks, d.narrative) +
    '';
  const g = d.geometry, r = d.resistance;
  $('#gOut').innerHTML = rows([
    ['Grid area', 'A', g.A, 'm²', ''],
    ['Conductors in x / y', 'N_x / N_y', g.Nx + ' / ' + g.Ny, '–', ''],
    ['Horizontal conductor length', 'L_C', g.Lc, 'm', ''],
    ['Total rod length', 'L_R', g.LR, 'm', ''],
    ['Total buried length', 'L_T', g.LT, 'm', ''],
    ['Perimeter', 'L_p', g.Lp, 'm', ''],
    ['Sverak resistance', 'R_g', r.sverak.Rg, 'Ω', r.sverak.formula],
    ['Schwarz resistance', 'R_g', r.schwarz.Rg, 'Ω', r.schwarz.formula],
    ['  · grid component', 'R₁', r.schwarz.R1, 'Ω', ''],
    ['  · rod-bed component', 'R₂', r.schwarz.R2, 'Ω', ''],
    ['  · mutual component', 'R_m', r.schwarz.Rm, 'Ω', ''],
    ['Resistance used', '—', r.chosen, '', ''],
    ['Ground potential rise', 'GPR', d.GPR, 'V', 'GPR = I_G · R_g'],
    ['Geometric factor', 'n', m.n, '–', `n_a=${fmt(m.n_a, 3)}, n_b=${fmt(m.n_b, 3)}, n_c=${fmt(m.n_c, 3)}, n_d=${fmt(m.n_d, 3)}`],
    ['Mesh factor', 'K_m', m.Km, '–', 'Eq. (81)'],
    ['Correction factor', 'K_ii', m.Kii, '–', m.has_perimeter_rods ? 'rods on the perimeter → K_ii = 1' : 'Eq. (82)'],
    ['Depth factor', 'K_h', m.Kh, '–', 'Eq. (83)'],
    ['Irregularity factor', 'K_i', m.Ki, '–', 'Eq. (89)'],
    ['Step factor', 'K_s', m.Ks, '–', 'Eq. (94)'],
    ['Effective mesh length', 'L_M', m.LM, 'm', m.note],
    ['Effective step length', 'L_S', m.LS, 'm', 'L_S = 0.75·L_C + 0.85·L_R'],
    ['Mesh (touch) voltage', 'E_m', m.Em, 'V', 'Eq. (85)'],
    ['Step voltage', 'E_s', m.Es, 'V', 'Eq. (92)'],
    ['Surface derating factor', 'C_s', t.Cs, '–', 'Eq. (27)'],
    ['Tolerable body current', 'I_B', t.Ib, 'A', `${t.body_weight} kg criterion`],
    ['Tolerable touch voltage', 'E_touch', t.E_touch, 'V', ''],
    ['Tolerable step voltage', 'E_step', t.E_step, 'V', '']
  ]);
  // layout
  const tr = [];
  (d.layout?.conductors || []).forEach((c, i) => tr.push({
    x: [c[0][0], c[1][0]], y: [c[0][1], c[1][1]], mode: 'lines',
    line: { color: PAL[0], width: 2 }, showlegend: i === 0, name: 'Grid conductor', hoverinfo: 'skip'
  }));
  const rods = d.layout?.rods || [];
  if (rods.length) tr.push({
    x: rods.map(p => p[0]), y: rods.map(p => p[1]), mode: 'markers',
    marker: { size: 9, color: PAL[1], symbol: 'circle' }, name: `Ground rods (${rods.length})`
  });
  const pad = Math.max(g.Lx, g.Ly) * 0.08 + 2;
  plot('gPlotLay', tr, {
    xaxis: { title: { text: 'x (m)' }, scaleanchor: 'y', gridcolor: css('--line'), range: [-pad, g.Lx + pad] },
    yaxis: { title: { text: 'y (m)' }, gridcolor: css('--line'), range: [-pad, g.Ly + pad] },
    title: { text: `${fmt(g.Lx)} × ${fmt(g.Ly)} m, D = ${fmt(g.D)} m, L_T = ${fmt(g.LT)} m`, font: { size: 12 } }
  });
}
$('#gRun').onclick = e => run(e.target, async () => renderGrid(await api('/api/ieee80/design', gridPayload())));
$('#gPull').onclick = () => {
  if (S.soil) set('gRho', fmt(S.soil.equivalent.rho_equivalent, 1));
  if (S.fault) { set('gIG', fmt(S.fault.IG_kA, 4)); set('gTs', S.fault.ts); }
  if (S.conductor) set('gd', S.conductor.diameter_m.toFixed(4));
  toast('Inputs pulled from the earlier modules.');
};
$('#gOpt').onclick = e => run(e.target, async () => {
  const p = gridPayload(); p.D_min = 1.5; p.D_step = 0.5;
  const d = await api('/api/ieee80/optimise', p);
  if (d.sweep && d.sweep.length) {
    const sw = d.sweep;
    plot('gPlotSweep', [
      { x: sw.map(s => s.D), y: sw.map(s => s.Em), mode: 'lines+markers', name: 'Mesh voltage E_m', line: { color: PAL[0], width: 2.5 } },
      { x: sw.map(s => s.D), y: sw.map(s => s.E_touch), mode: 'lines', name: 'Tolerable touch', line: { color: PAL[0], dash: 'dot' } },
      { x: sw.map(s => s.D), y: sw.map(s => s.Es), mode: 'lines+markers', name: 'Step voltage E_s', line: { color: PAL[1], width: 2.5 } },
      { x: sw.map(s => s.D), y: sw.map(s => s.E_step), mode: 'lines', name: 'Tolerable step', line: { color: PAL[1], dash: 'dot' } }
    ], {
      xaxis: { title: { text: 'Conductor spacing D (m)' }, gridcolor: css('--line') },
      yaxis: { title: { text: 'Voltage (V)' }, gridcolor: css('--line') }
    });
    $$('#gTabs .tab').forEach(x => x.classList.remove('active'));
    $('#gTabs .tab[data-t="gsweep"]').classList.add('active');
    $$('#page-grid .tabpane').forEach(x => x.classList.remove('active'));
    $('#pane-gsweep').classList.add('active');
  }
  if (d.found) {
    set('gD', d.best.D);
    if (d.best.n_rods) { set('gNr', d.best.n_rods); if (N('gLr') <= 0) set('gLr', 3); }
    renderGrid(d.best.result);
    toast(`Compliant design found: ${d.best.strategy} (D = ${d.best.D} m${d.best.n_rods ? ', ' + d.best.n_rods + ' rods' : ''}).`, 'ok');
  } else {
    toast(d.note || 'No compliant design found in the search range.', 'err');
  }
});

/* ======================================================== 5. NUMERICAL === */
let BEM_ITEMS = [];
const BEM_DEF = {
  grid: { kind: 'grid', Lx: 70, Ly: 70, D: 7, depth: 0.5, radius: 0.005, x0: 0, y0: 0 },
  rod: { kind: 'rod', x: 0, y: 0, top_depth: 0.5, length: 3, radius: 0.008 },
  ring: { kind: 'ring', cx: 0, cy: 0, r: 10, depth: 0.6, radius: 0.005, n_sides: 32 },
  rectangle: { kind: 'rectangle', x0: 0, y0: 0, Lx: 12, Ly: 8, depth: 0.6, radius: 0.005 },
  conductor: { kind: 'conductor', p1: [0, 0, 0.6], p2: [20, 0, 0.6], radius: 0.005 }
};
function renderBem() {
  const tb = $('#nTable tbody'); tb.innerHTML = '';
  BEM_ITEMS.forEach((it, i) => {
    const tr = document.createElement('tr');
    const flds = Object.keys(it).filter(k => k !== 'kind').map(k => {
      const v = it[k];
      const inp = Array.isArray(v)
        ? `<input data-i="${i}" data-k="${k}" value="${v.join(',')}">`
        : `<input type="number" step="any" data-i="${i}" data-k="${k}" value="${v}">`;
      return `<span class="pfield"><label>${k}</label>${inp}</span>`;
    }).join('');
    tr.innerHTML = `<td><b>${it.kind}</b></td><td><div class="pgrid">${flds}</div></td><td><button class="ghost">✕</button></td>`;
    tr.querySelector('button').onclick = () => { BEM_ITEMS.splice(i, 1); renderBem(); };
    $$('input', tr).forEach(inp => inp.onchange = () => {
      const k = inp.dataset.k;
      BEM_ITEMS[i][k] = inp.value.includes(',') ? inp.value.split(',').map(Number) : parseFloat(inp.value);
    });
    tb.appendChild(tr);
  });
  if (!BEM_ITEMS.length) tb.innerHTML = '<tr><td colspan="3" class="muted small" style="padding:14px">No elements yet — add a grid, rod or ring.</td></tr>';
}
$$('#page-numerical [data-add]').forEach(b => b.onclick = () => {
  BEM_ITEMS.push(JSON.parse(JSON.stringify(BEM_DEF[b.dataset.add]))); renderBem();
});
$('#nFromGrid').onclick = () => {
  const g = gridPayload();
  BEM_ITEMS = [{ kind: 'grid', Lx: g.Lx, Ly: g.Ly, D: g.D, depth: g.h, radius: g.d / 2, x0: 0, y0: 0 }];
  if (g.n_rods > 0 && g.Lr > 0) {
    const per = 2 * (g.Lx + g.Ly);
    for (let i = 0; i < g.n_rods; i++) {
      const s = per * i / g.n_rods;
      let x, y;
      if (s < g.Lx) { x = s; y = 0; }
      else if (s < g.Lx + g.Ly) { x = g.Lx; y = s - g.Lx; }
      else if (s < 2 * g.Lx + g.Ly) { x = 2 * g.Lx + g.Ly - s; y = g.Ly; }
      else { x = 0; y = per - s; }
      BEM_ITEMS.push({ kind: 'rod', x: +x.toFixed(2), y: +y.toFixed(2), top_depth: g.h, length: g.Lr, radius: g.d_rod / 2 });
    }
  }
  set('nRho1', g.rho); set('nIG', (g.IG_kA * 1000).toFixed(0));
  renderBem(); toast('Geometry built from the IEEE 80 grid.');
};
$('#nRun').onclick = e => run(e.target, async () => {
  if (!BEM_ITEMS.length) throw new Error('Add at least one electrode element.');
  const p = {
    rho1: N('nRho1', 100), IG: N('nIG', 1000), items: BEM_ITEMS,
    segment_length: N('nSeg', 3), nx: parseInt(V('nRes')) || 61, ny: parseInt(V('nRes')) || 61,
    step_distance: N('nStep', 1)
  };
  if (NB('nRho2') !== null && NB('nHl') !== null) { p.rho2 = NB('nRho2'); p.h_layer = NB('nHl'); }
  if (S.grid) p.limits = { E_touch: S.grid.tolerable.E_touch, E_step: S.grid.tolerable.E_step };
  const d = await api('/api/bem', p);
  S.bem = d; markNav('numerical', d.checks ? d.checks.every(c => c.passed) : true);
  const lim = p.limits || {};
  kpis('nKpis', [
    { value: fmt(d.Rg) + ' <small>Ω</small>', label: 'Earth resistance R_g' },
    { value: fmt(d.GPR) + ' <small>V</small>', label: 'Ground potential rise' },
    { value: fmt(d.touch_max) + ' <small>V</small>', label: 'Max touch voltage', state: lim.E_touch ? (d.touch_max <= lim.E_touch ? 'ok' : 'bad') : '' },
    { value: fmt(d.step_max) + ' <small>V</small>', label: 'Max step voltage', state: lim.E_step ? (d.step_max <= lim.E_step ? 'ok' : 'bad') : '' },
    { value: d.segments, label: 'Segments solved' },
    { value: fmt(d.total_length) + ' <small>m</small>', label: 'Buried length' }
  ]);
  const sc = css('--line');
  const heat = (z, name) => ([{
    x: d.surface.x, y: d.surface.y, z, type: 'contour', colorscale: 'Viridis',
    contours: { coloring: 'heatmap', showlabels: true, labelfont: { size: 9, color: '#fff' } },
    colorbar: { title: { text: name, side: 'right' }, thickness: 14 }
  }]);
  const geoTraces = d.geometry.map((s, i) => ({
    x: [s.p1[0], s.p2[0]], y: [s.p1[1], s.p2[1]], mode: 'lines',
    line: { color: '#fff', width: 1.2 }, showlegend: false, hoverinfo: 'skip', opacity: .55
  }));
  plot('nPlotSurf', heat(d.surface.V, 'V').concat(geoTraces), {
    xaxis: { title: { text: 'x (m)' }, scaleanchor: 'y', gridcolor: sc },
    yaxis: { title: { text: 'y (m)' }, gridcolor: sc }
  });
  plot('nPlotTouch', heat(d.surface.touch, 'U_T (V)').concat(geoTraces), {
    xaxis: { title: { text: 'x (m)' }, scaleanchor: 'y', gridcolor: sc },
    yaxis: { title: { text: 'y (m)' }, gridcolor: sc }
  });
  Plotly.react('nPlot3d', [{
    x: d.surface.x, y: d.surface.y, z: d.surface.V, type: 'surface',
    colorscale: 'Viridis', contours: { z: { show: true, usecolormap: true, project: { z: true } } },
    colorbar: { title: { text: 'V' }, thickness: 14 }
  }], baseLayout({
    scene: {
      xaxis: { title: 'x (m)' }, yaxis: { title: 'y (m)' }, zaxis: { title: 'Potential (V)' },
      camera: { eye: { x: 1.5, y: -1.6, z: 1.1 } }
    }, margin: { l: 0, r: 0, t: 10, b: 0 }
  }), { displaylogo: false, responsive: true });
  PLOTS['nPlot3d'] = true;
  const pr = d.profile;
  plot('nPlotProf', [
    { x: pr.s, y: pr.V, mode: 'lines', name: 'Surface potential', line: { color: PAL[0], width: 2.5 } },
    { x: pr.s, y: pr.touch, mode: 'lines', name: 'Touch voltage', line: { color: PAL[1], width: 2.5 } },
    { x: pr.s, y: pr.step, mode: 'lines', name: `Step voltage (${pr.step_distance} m)`, line: { color: PAL[2], width: 2.5 } },
    lim.E_touch ? { x: [pr.s[0], pr.s[pr.s.length - 1]], y: [lim.E_touch, lim.E_touch], mode: 'lines', name: 'Tolerable touch', line: { color: PAL[1], dash: 'dot' } } : null,
    lim.E_step ? { x: [pr.s[0], pr.s[pr.s.length - 1]], y: [lim.E_step, lim.E_step], mode: 'lines', name: 'Tolerable step', line: { color: PAL[2], dash: 'dot' } } : null
  ].filter(Boolean), {
    xaxis: { title: { text: 'Distance along the traverse (m)' }, gridcolor: sc },
    yaxis: { title: { text: 'Voltage (V)' }, gridcolor: sc }
  });
  plot('nPlotCur', [{
    x: d.current.map(c => c.x), y: d.current.map(c => c.y), mode: 'markers',
    marker: {
      size: 8, color: d.current.map(c => c.I), colorscale: 'Plasma', showscale: true,
      colorbar: { title: { text: 'I (A)' }, thickness: 14 }
    },
    text: d.current.map(c => `${c.tag}<br>I = ${fmt(c.I)} A<br>J = ${fmt(c.density)} A/m²`), hoverinfo: 'text'
  }], {
    xaxis: { title: { text: 'x (m)' }, scaleanchor: 'y', gridcolor: sc },
    yaxis: { title: { text: 'y (m)' }, gridcolor: sc }
  });
  const g3 = { x: [], y: [], z: [] };
  d.geometry.forEach(s => { g3.x.push(s.p1[0], s.p2[0], null); g3.y.push(s.p1[1], s.p2[1], null); g3.z.push(-s.p1[2], -s.p2[2], null); });
  Plotly.react('nPlotGeo', [{ ...g3, type: 'scatter3d', mode: 'lines', line: { color: PAL[0], width: 4 }, name: 'Electrodes' }],
    baseLayout({ scene: { xaxis: { title: 'x (m)' }, yaxis: { title: 'y (m)' }, zaxis: { title: 'z (m, down −)' }, aspectmode: 'data' }, margin: { l: 0, r: 0, t: 10, b: 0 } }),
    { displaylogo: false, responsive: true });
  PLOTS['nPlotGeo'] = true;

  $('#nOut').innerHTML = checksHtml(d.checks, d.narrative, d.cross_check) + rows([
    ['Soil model', '—', d.soil, '', ''],
    ['Discretised segments', 'N', d.segments, '–', ''],
    ['Total buried length', 'L', d.total_length, 'm', ''],
    ['Injected current', 'I_G', d.IG, 'A', ''],
    ['Earth resistance', 'R_g', d.Rg, 'Ω', 'R_g = GPR / I_G'],
    ['Ground potential rise', 'GPR', d.GPR, 'V', ''],
    ['Maximum touch voltage', 'U_T', d.touch_max, 'V', `at x = ${fmt(d.touch_at[0])} m, y = ${fmt(d.touch_at[1])} m`],
    ['Maximum step voltage', 'U_S', d.step_max, 'V', `at x = ${fmt(d.step_at[0])} m, y = ${fmt(d.step_at[1])} m`],
    ['Minimum segment current', '—', d.I_min, 'A', ''],
    ['Maximum segment current', '—', d.I_max, 'A', '']
  ]) + (d.probes && d.probes.length ? `<h4 style="margin:12px 0 6px">Reference points</h4>
    <table class="data"><thead><tr><th>Point</th><th style="text-align:right">x</th><th style="text-align:right">y</th><th style="text-align:right">Potential (V)</th><th style="text-align:right">Touch (V)</th></tr></thead><tbody>` +
    d.probes.map(q => `<tr><td>${esc(q.label)}</td><td class="n">${fmt(q.x)}</td><td class="n">${fmt(q.y)}</td><td class="n">${fmt(q.V)}</td><td class="n">${fmt(q.touch)}</td></tr>`).join('') +
    '</tbody></table>' : '') +
    (S.grid && d.probes?.[0] ? `<div class="note info">Direct comparison — IEEE 80 closed-form mesh voltage
      <b>${fmt(S.grid.mesh.Em)} V</b> against the numerical corner-mesh touch voltage
      <b>${fmt(d.probes[0].touch)} V</b>: a difference of
      <b>${fmt((d.probes[0].touch / S.grid.mesh.Em - 1) * 100, 1)} %</b>.</div>` : '');
  toast('Numerical solution complete.', 'ok');
});

/* ========================================================= 6. BUILDING === */
let BUILD_ITEMS = [];
const BUILD_DEF = {
  rod: { type: 'rod', L: 3, d: 0.016 },
  rods_parallel: { type: 'rods_parallel', L: 3, d: 0.016, n: 3, s: 6 },
  strip: { type: 'strip', L: 20, w: 0.03, h: 0.7 },
  ring: { type: 'ring', radius: 6, d: 0.01, h: 0.7 },
  plate: { type: 'plate', area: 1, h: 1.0 },
  foundation: { type: 'foundation', volume_m3: 400 },
  mesh: { type: 'mesh', area: 200, total_length: 120, h: 0.7 }
};
function renderBuild() {
  const tb = $('#bTable tbody'); tb.innerHTML = '';
  BUILD_ITEMS.forEach((it, i) => {
    const tr = document.createElement('tr');
    const flds = Object.keys(it).filter(k => k !== 'type' && k !== '_R').map(k =>
      `<span class="pfield"><label>${k}</label><input type="number" step="any" data-i="${i}" data-k="${k}" value="${it[k]}"></span>`).join('');
    tr.innerHTML = `<td><b>${it.type}</b></td><td><div class="pgrid">${flds}</div></td><td class="n">${it._R !== undefined ? fmt(it._R) : '—'}</td><td><button class="ghost">✕</button></td>`;
    tr.querySelector('button').onclick = () => { BUILD_ITEMS.splice(i, 1); renderBuild(); };
    $$('input', tr).forEach(inp => inp.onchange = () => { BUILD_ITEMS[i][inp.dataset.k] = parseFloat(inp.value); });
    tb.appendChild(tr);
  });
  if (!BUILD_ITEMS.length) tb.innerHTML = '<tr><td colspan="4" class="muted small" style="padding:14px">No electrodes yet.</td></tr>';
}
$$('#page-building [data-badd]').forEach(b => b.onclick = () => {
  BUILD_ITEMS.push(JSON.parse(JSON.stringify(BUILD_DEF[b.dataset.badd]))); renderBuild();
});
$('#bDev').onchange = () => {
  const rcd = V('bDev') === 'rcd';
  $('#bCurveBox').style.display = V('bDev') === 'mcb' ? '' : 'none';
  $('#bRatingU').textContent = rcd ? 'A (IΔn)' : 'A';
  if (rcd && N('bRating') > 5) set('bRating', 0.03);
};
$('#bRun').onclick = e => run(e.target, async () => {
  if (!BUILD_ITEMS.length) throw new Error('Add at least one earth electrode.');
  const p = {
    system: V('bSys'), U0: N('bU0', 230), rho: N('bRho', 100),
    electrodes: BUILD_ITEMS.map(it => { const o = { ...it }; delete o._R; return o; }),
    device: { kind: V('bDev'), rating_A: N('bRating', 32), curve: V('bCurve') },
    circuit: V('bCircuit'), Z_line: N('bZl', 0), Z_pe: N('bZpe', 0),
    Z_source: N('bZs', 0), UL: N('bUL', 50)
  };
  const d = await api('/api/building', p);
  S.building = d; markNav('building', d.passed);
  d.electrodes.forEach((r, i) => { if (BUILD_ITEMS[i]) BUILD_ITEMS[i]._R = r.R; });
  renderBuild();
  kpis('bKpis', [
    { value: fmt(d.RA) + ' <small>Ω</small>', label: 'Electrode resistance R_A' },
    { value: fmt(d.Zs) + ' <small>Ω</small>', label: 'Earth-fault loop Z_s' },
    { value: fmt(d.device.Ia) + ' <small>A</small>', label: 'Operating current I_a' },
    { value: fmt(d.disconnection.t) + ' <small>s</small>', label: 'Max disconnection time' },
    { value: fmt(d.touch_voltage.Ut) + ' <small>V</small>', label: 'Prospective touch voltage', state: d.touch_voltage.Ut <= N('bUL', 50) ? 'ok' : 'bad' },
    { value: (d.rcd?.selected_mA ? fmt(d.rcd.selected_mA) + ' <small>mA</small>' : '—'), label: 'Largest permissible RCD' }
  ]);
  $('#bChecks').innerHTML = checksHtml(d.checks, d.narrative);
  const si = d.system_info || {};
  $('#bOut').innerHTML = `<div class="note info"><b>${esc(si.name || d.system)}</b> — ${esc(si.description || '')}
      <br><b>Fault path:</b> ${esc(si.fault_path || '')} <br><b>Protection:</b> ${esc(si.protection || '')}</div>` +
    rows([
      ['Voltage to earth', 'U₀', d.U0, 'V', ''],
      ['Soil resistivity', 'ρ', d.rho, 'Ω·m', ''],
      ['Combined electrode resistance', 'R_A', d.RA, 'Ω', `${d.combination.n} electrode(s) in parallel`],
      ['Earth-fault loop impedance', 'Z_s', d.Zs, 'Ω', ''],
      ['Operating current', 'I_a', d.device.Ia, 'A', d.device.basis],
      ['Maximum disconnection time', 't', d.disconnection.t, 's', d.disconnection.rule],
      ['Prospective touch voltage', 'U_t', d.touch_voltage.Ut, 'V', d.touch_voltage.formula],
      d.rcd && ['Maximum permissible IΔn', 'IΔn', d.rcd.max_IdN * 1000, 'mA', 'R_A · IΔn ≤ ' + fmt(N('bUL', 50)) + ' V'],
      d.rcd && ['30 mA additional protection acceptable', '—', d.rcd.additional_protection_30mA, '', 'IEC 60364-4-41 §415.1']
    ]) + `<table class="data"><thead><tr><th>Electrode</th><th style="text-align:right">R (Ω)</th><th>Formula</th></tr></thead><tbody>` +
    d.electrodes.map(el => `<tr><td>${esc(el.type)}</td><td class="n">${fmt(el.R)}</td><td class="src">${esc(el.formula || el.error || '')}</td></tr>`).join('') + '</tbody></table>';
  // sensitivity: R vs rho
  const rr = [], RR = [];
  for (let i = 0; i < 40; i++) { rr.push(10 + i * 25); }
  const scale = d.RA / Math.max(d.rho, 1e-6);
  rr.forEach(r => RR.push(scale * r));
  plot('bPlot', [
    { x: rr, y: RR, mode: 'lines', name: 'R_A', line: { color: PAL[0], width: 2.5 } },
    { x: [d.rho], y: [d.RA], mode: 'markers', name: 'design point', marker: { size: 11, color: PAL[1] } },
    d.checks[0]?.RA_max ? { x: [rr[0], rr[rr.length - 1]], y: [d.checks[0].RA_max, d.checks[0].RA_max], mode: 'lines', name: 'R_A,max', line: { color: PAL[1], dash: 'dot' } } : null
  ].filter(Boolean), {
    xaxis: { title: { text: 'Soil resistivity (Ω·m)' }, gridcolor: css('--line') },
    yaxis: { title: { text: 'Electrode resistance R_A (Ω)' }, gridcolor: css('--line') }
  });
  toast('Installation assessed.', 'ok');
});
$('#bSize').onclick = e => run(e.target, async () => {
  const target = parseFloat(prompt('Target electrode resistance (Ω):', '10'));
  if (!isFinite(target)) return;
  const d = await api('/api/rods-required', { rho: N('bRho', 100), target_R: target, L: 3, d: 0.016, s: 6 });
  modal('Rod requirement', `<p>With 3 m × 16 mm rods at 6 m spacing in ${fmt(N('bRho', 100))} Ω·m soil:</p>` +
    rows([['Single-rod resistance', 'R₁', d.R_single, 'Ω', 'Dwight'],
    ['Rods required', 'n', d.n, '–', ''],
    ['Resulting resistance', 'R_n', d.R, 'Ω', 'includes mutual coupling'],
    ['Target achieved', '—', d.achieved, '', d.note || '']]));
});

/* ======================================================== 7. LIGHTNING === */
$('#lRun').onclick = e => run(e.target, async () => {
  const p = {
    lps_class: V('lCls'), rho: N('lRho', 100), area: N('lArea', 100), perimeter: N('lPer', 40),
    arrangement: V('lArr'), d: N('lD', .01), h: N('lH', .5), rod_d: N('lRodD', .016),
    separation_length: N('lLen', 10), separation_material: V('lMat')
  };
  if (NB('lVol') !== null) p.foundation_volume = NB('lVol');
  const d = await api('/api/lightning', p);
  S.lightning = d; markNav('lightning', d.passed);
  const e2 = d.earth, dc = d.down_conductors;
  const l1 = typeof e2.l1 === 'number' ? e2.l1 : e2.l1?.l1;
  kpis('lKpis', [
    { value: 'Class ' + d.lps_class, label: 'Protection level' },
    { value: fmt(l1) + ' <small>m</small>', label: 'Minimum length l₁' },
    { value: fmt(e2.R_total) + ' <small>Ω</small>', label: 'Earthing resistance', state: e2.R_total <= 10 ? 'ok' : 'bad' },
    { value: dc.n_down, label: 'Down-conductors' },
    { value: fmt(d.separation.s) + ' <small>m</small>', label: 'Separation distance s' },
    { value: dc.rolling_sphere + ' <small>m</small>', label: 'Rolling-sphere radius' }
  ]);
  $('#lChecks').innerHTML = checksHtml(d.checks, d.narrative);
  const sup = e2.supplementary;
  $('#lOut').innerHTML = rows([
    ['LPS class', '—', d.lps_class, '', 'IEC 62305-3 Table 1'],
    ['Air-termination mesh size', '—', dc.mesh_size, '', 'IEC 62305-3 Table 2'],
    ['Rolling-sphere radius', 'r', dc.rolling_sphere, 'm', ''],
    ['Down-conductor spacing (typical)', '—', dc.typical_spacing, 'm', 'IEC 62305-3 Table 4'],
    ['Number of down-conductors', 'n', dc.n_down, '–', ''],
    ['Actual spacing achieved', '—', dc.actual_spacing, 'm', ''],
    ['Minimum electrode length', 'l₁', l1, 'm', 'IEC 62305-3 Figure 3'],
    ['Arrangement', '—', e2.arrangement, '', ''],
    e2.mean_radius !== undefined && ['Ring mean radius', 'r_e', e2.mean_radius, 'm', 'requirement r_e ≥ l₁'],
    e2.ring_length !== undefined && ['Ring conductor length', '—', e2.ring_length, 'm', ''],
    e2.n_electrodes !== undefined && ['Number of electrodes', 'n', e2.n_electrodes, '–', 'minimum 2'],
    e2.L_used !== undefined && ['Length of each electrode', 'L', e2.L_used, 'm', 'required ≥ ' + fmt(e2.L_required) + ' m'],
    ['Earthing resistance', 'R_E', e2.R_total, 'Ω', (e2.resistance || e2.each || {}).formula || ''],
    ['Separation distance', 's', d.separation.s, 'm', d.separation.formula],
    ['  · k_i / k_c / k_m', '—', `${d.separation.ki} / ${fmt(d.separation.kc, 2)} / ${d.separation.km}`, '', '']
  ]) + (sup ? `<div class="note"><b>Supplementary electrodes required.</b> ${esc(sup.note)}
      Add ${fmt(sup.horizontal_each)} m horizontally, or ${fmt(sup.vertical_each)} m vertically, at each down-conductor.</div>` : '') +
    `<div class="note info">${esc(d.bonding_note)}</div>`;
  const meta = S.meta;
  const xs = [], series = {};
  for (let r = 100; r <= 3000; r += 50) xs.push(r);
  ['I', 'II', 'III', 'IV'].forEach((cl, i) => {
    const ys = xs.map(r => {
      const X = meta.lps_l1.rho, Y = meta.lps_l1.l1[cl];
      if (r <= X[0]) return Y[0];
      for (let k = 0; k < X.length - 1; k++) if (r <= X[k + 1]) return Y[k] + (r - X[k]) / (X[k + 1] - X[k]) * (Y[k + 1] - Y[k]);
      return Y[Y.length - 1];
    });
    series[cl] = { x: xs, y: ys, mode: 'lines', name: 'Class ' + cl, line: { width: cl === d.lps_class ? 3.5 : 2, color: PAL[i] } };
  });
  plot('lPlot', Object.values(series).concat([{ x: [d.rho], y: [l1], mode: 'markers', name: 'design point', marker: { size: 12, color: PAL[1] } }]), {
    xaxis: { title: { text: 'Soil resistivity (Ω·m)' }, gridcolor: css('--line') },
    yaxis: { title: { text: 'Minimum length l₁ (m)' }, gridcolor: css('--line') }
  });
  toast('Earth termination designed.', 'ok');
});

/* =========================================================== 8. SYSGND === */
$('#sRun').onclick = e => run(e.target, async () => {
  const p = {
    V_ll_kV: N('sV', 6.6), frequency: N('sF', 50), cable_km: N('sCab', 0),
    C0_uF_per_km: N('sC0', .25), overhead_km: N('sOh', 0), motors_kVA: N('sMot', 0),
    transformers_kVA: N('sTx', 0), continuity_critical: C('sCont'), ln_loads: C('sLn'),
    method: V('sMeth'), I_target_A: N('sIt', 400), t_rating_s: N('sTr', 10)
  };
  if (NB('sX1') !== null) { p.X1 = NB('sX1'); p.X0 = NB('sX0'); p.R0 = NB('sR0') || 0; }
  const d = await api('/api/system-grounding', p);
  S.sysgnd = d; markNav('sysgnd', true);
  const m = d.methods[d.method] || {};
  kpis('sKpis', [
    { value: esc(m.name || d.method), label: 'Grounding method' },
    { value: fmt(d.three_IC0) + ' <small>A</small>', label: 'Charging current 3·I_C0' },
    { value: d.R_ohm ? fmt(d.R_ohm) + ' <small>Ω</small>' : (d.X_ohm ? fmt(d.X_ohm) + ' <small>Ω</small>' : '—'), label: 'Neutral impedance' },
    { value: fmt(d.I_R || d.I_target || 0) + ' <small>A</small>', label: 'Earth-fault current' },
    { value: d.effective ? (d.effective.effectively_grounded ? 'Yes' : 'No') : '—', label: 'Effectively grounded', state: d.effective ? (d.effective.effectively_grounded ? 'ok' : 'bad') : '' }
  ]);
  $('#sOut').innerHTML = (d.recommendation ? `<div class="note info"><b>Recommended: ${esc(m.name)}</b><ul style="margin:6px 0 0;padding-inline-start:18px">${d.recommendation.reasons.map(r => '<li>' + esc(r) + '</li>').join('')}</ul></div>` : '') +
    rows([
      ['System voltage', 'U', N('sV'), 'kV', ''],
      ['Cable charging component', '—', d.charging.cable_component, 'A', ''],
      ['Motor allowance', '—', d.charging.motor_component, 'A', 'IEEE Std 142 Table 1'],
      ['Transformer allowance', '—', d.charging.transformer_component, 'A', ''],
      ['Total charging current', '3·I_C0', d.three_IC0, 'A', d.charging.formula],
      ['Line-to-neutral voltage', 'V_LN', d.V_ln, 'V', ''],
      d.R_ohm && ['Neutral resistor', 'R_N', d.R_ohm, 'Ω', d.formula],
      d.X_ohm && ['Neutral reactor', 'X_N', d.X_ohm, 'Ω', d.formula],
      d.I_R && ['Resistor current', 'I_R', d.I_R, 'A', 'must be ≥ 3·I_C0'],
      d.total_fault_current && ['Total earth-fault current', 'I_f', d.total_fault_current, 'A', ''],
      d.continuous_power_W && ['Continuous rating', 'P', d.continuous_power_W, 'W', d.rating_note],
      d.power_W && ['Short-time rating', 'P', d.power_W, 'W', `${fmt(N('sTr'))} s duty`],
      d.energy_kJ && ['Energy', 'E', d.energy_kJ, 'kJ', ''],
      d.effective && ['X₀/X₁', '—', d.effective.X0_over_X1, '–', 'must be ≤ 3'],
      d.effective && ['R₀/X₁', '—', d.effective.R0_over_X1, '–', 'must be ≤ 1'],
      d.effective && ['Coefficient of grounding', 'COG', d.effective.coefficient_of_grounding, '–', d.effective.note]
    ]);
  $('#sTable').innerHTML = `<table class="data"><thead><tr><th>Method</th><th>Fault current</th><th>Advantages</th><th>Limitations</th></tr></thead><tbody>` +
    Object.entries(d.methods).map(([k, v]) => `<tr${k === d.method ? ' style="background:var(--accent-soft)"' : ''}>
      <td><b>${esc(v.name)}</b><div class="muted small">${esc(v.typical)}</div></td>
      <td class="small">${esc(v.fault_current)}</td><td class="small">${esc(v.pros)}</td>
      <td class="small">${esc(v.cons)}</td></tr>`).join('') + '</tbody></table>';
  toast('System grounding evaluated.', 'ok');
});

/* =========================================================== 9. REPORT === */
const FIGS = [
  ['soilPlot', 'Apparent resistivity — measured and fitted two-layer model'],
  ['fPlot', 'Decrement factor versus fault duration'],
  ['cPlot', 'Required conductor area versus fault duration'],
  ['gPlotLay', 'Earth grid layout'],
  ['gPlotSweep', 'Mesh and step voltage versus conductor spacing'],
  ['nPlotSurf', 'Earth-surface potential distribution'],
  ['nPlotTouch', 'Touch voltage distribution'],
  ['nPlotProf', 'Potential, touch and step voltage along a traverse'],
  ['bPlot', 'Electrode resistance versus soil resistivity'],
  ['lPlot', 'Minimum electrode length versus soil resistivity']
];
function reportSections() {
  const map = [['soil', 'Soil model'], ['fault', 'Fault current'], ['conductor', 'Conductor sizing'],
  ['grid', 'Substation grid (IEEE 80)'], ['bem', 'Numerical analysis'], ['building', 'Buildings & homes'],
  ['lightning', 'Lightning earth termination'], ['sysgnd', 'System grounding']];
  $('#rSections').innerHTML = '<table class="data"><tbody>' + map.map(([k, n]) =>
    `<tr><td>${n}</td><td style="width:90px"><span class="badge ${S[k] ? 'ok' : 'warn'}">${S[k] ? 'included' : 'not run'}</span></td></tr>`).join('') + '</tbody></table>';
}
async function collectFigures() {
  if (!C('rFigs')) return [];
  const out = [];
  for (const [id, cap] of FIGS) {
    const el = $('#' + id);
    if (!el || !el.data || !el.data.length) continue;
    try {
      const url = await Plotly.toImage(el, { format: 'png', width: 1100, height: 620, scale: 1.6 });
      out.push({ data: url, caption: cap });
    } catch (e) { /* skip */ }
  }
  return out;
}
function reportData(figs) {
  const d = {
    meta: {
      project: V('rProject') || V('projName'), client: V('rClient'), engineer: V('rEngineer'),
      reference: V('rRef'), revision: V('rRev'), date: V('rDate')
    },
    notes: V('rNotes'), figures: figs
  };
  if (S.soil) d.soil = { ...S.soil, rho_equivalent: S.soil.equivalent.rho_equivalent };
  if (S.fault) d.fault = { Un_kV: S.fault.Un_kV, three_I0_kA: S.fault.three_I0_kA, Sf: S.fault.Sf, Df: S.fault.Df, Cp: S.fault.Cp, Ig_kA: S.fault.Ig_kA, IG_kA: S.fault.IG_kA, ts: S.fault.ts, tc: S.fault.tc };
  if (S.conductor) d.conductor = S.conductor.ieee80;
  if (S.grid) d.grid = S.grid;
  if (S.bem) d.bem = S.bem;
  if (S.building) d.building = S.building;
  if (S.lightning) d.lightning = S.lightning;
  if (S.sysgnd) d.sysgnd = S.sysgnd;
  return d;
}
let LAST_REPORT = '';
$('#rBuild').onclick = e => run(e.target, async () => {
  const figs = await collectFigures();
  const r = await api('/api/report', { lang: V('rLang'), data: reportData(figs), filename: `report_${V('rLang')}.html` });
  LAST_REPORT = r.html;
  $('#rFrame').srcdoc = r.html;
  reportSections();
  toast('Report generated and saved to the outputs folder.', 'ok');
});
$('#rPrint').onclick = () => {
  if (!LAST_REPORT) return toast('Generate the report first.', 'err');
  const w = window.open('', '_blank');
  w.document.write(LAST_REPORT); w.document.close();
  setTimeout(() => w.print(), 700);
};
$('#rDownload').onclick = () => {
  if (!LAST_REPORT) return toast('Generate the report first.', 'err');
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([LAST_REPORT], { type: 'text/html' }));
  a.download = (V('projName') || 'earthing') + '_report_' + V('rLang') + '.html';
  a.click();
};

/* ========================================================== project I/O == */
$('#btnExport').onclick = () => {
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([JSON.stringify(snapshot(), null, 2)], { type: 'application/json' }));
  a.download = (V('projName') || 'earthsystem_project') + '.json';
  a.click();
};
$('#fileImport').onchange = ev => {
  const f = ev.target.files[0]; if (!f) return;
  const fr = new FileReader();
  fr.onload = () => { try { restore(JSON.parse(fr.result)); } catch (e) { toast('Could not read that file.', 'err'); } };
  fr.readAsText(f); ev.target.value = '';
};
$('#btnSaveProj').onclick = e => run(e.target, async () => {
  const name = V('projName') || prompt('Project name:', 'project');
  if (!name) return;
  set('projName', name);
  await api('/api/project/save', { name, data: snapshot() });
  toast('Saved to the projects folder.', 'ok');
});
$('#btnLoadProj').onclick = e => run(e.target, async () => {
  const l = await api('/api/project/list');
  if (!l.projects.length) return toast('No saved projects yet.');
  modal('Open project', '<table class="data"><tbody>' + l.projects.map(p =>
    `<tr><td>${esc(p.name)}</td><td class="muted small">${new Date(p.modified * 1000).toLocaleString()}</td>
     <td><button data-open="${esc(p.name)}">Open</button></td></tr>`).join('') + '</tbody></table>');
  $$('#modalBody [data-open]').forEach(b => b.onclick = async () => {
    const r = await api('/api/project/load', { name: b.dataset.open });
    restore(r.data); closeModal();
  });
});

/* ------------------------------------------------------------------ modal */
function modal(title, html) { $('#modalTitle').textContent = title; $('#modalBody').innerHTML = html; $('#modal').classList.add('on'); }
function closeModal() { $('#modal').classList.remove('on'); }
$('#modalClose').onclick = closeModal;
$('#modal').onclick = e => { if (e.target.id === 'modal') closeModal(); };

/* ------------------------------------------------------------------- init */
/* ------------------------------------------------- markdown → HTML (small) */
function md(src) {
  const esc2 = t => t.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  const inline = t => esc2(t)
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\*\*([^*]+)\*\*/g, '<b>$1</b>')
    .replace(/(^|[\s(])\*([^*]+)\*/g, '$1<i>$2</i>')
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
  const lines = src.split('\n');
  const out = [];
  let i = 0, listType = null;
  const closeList = () => { if (listType) { out.push(`</${listType}>`); listType = null; } };
  while (i < lines.length) {
    const L = lines[i];
    if (/^```/.test(L)) {                                   // fenced block
      closeList();
      const buf = [];
      i++;
      while (i < lines.length && !/^```/.test(lines[i])) buf.push(lines[i++]);
      i++;
      out.push(`<pre class="mdcode">${esc2(buf.join('\n'))}</pre>`);
      continue;
    }
    if (/^\s*\|/.test(L) && /^\s*\|[\s:|-]+\|\s*$/.test(lines[i + 1] || '')) {
      closeList();
      const cells = r => r.trim().replace(/^\||\|$/g, '').split('|').map(c => c.trim());
      const head = cells(L);
      i += 2;
      const body = [];
      while (i < lines.length && /^\s*\|/.test(lines[i])) body.push(cells(lines[i++]));
      out.push(`<table class="mdtable"><thead><tr>${head.map(h => `<th>${inline(h)}</th>`).join('')}</tr></thead><tbody>` +
        body.map(r => `<tr>${r.map(c => `<td>${inline(c)}</td>`).join('')}</tr>`).join('') + '</tbody></table>');
      continue;
    }
    let m;
    if ((m = L.match(/^(#{1,4})\s+(.*)$/))) {
      closeList();
      const lvl = m[1].length;
      const id = 'h-' + m[2].toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
      out.push(`<h${lvl} id="${id}">${inline(m[2])}</h${lvl}>`);
    } else if (/^\s*[-*]\s+/.test(L)) {
      if (listType !== 'ul') { closeList(); out.push('<ul>'); listType = 'ul'; }
      out.push(`<li>${inline(L.replace(/^\s*[-*]\s+/, ''))}</li>`);
    } else if (/^\s*\d+\.\s+/.test(L)) {
      if (listType !== 'ol') { closeList(); out.push('<ol>'); listType = 'ol'; }
      out.push(`<li>${inline(L.replace(/^\s*\d+\.\s+/, ''))}</li>`);
    } else if (/^>\s?/.test(L)) {
      closeList();
      out.push(`<blockquote>${inline(L.replace(/^>\s?/, ''))}</blockquote>`);
    } else if (/^\s*---+\s*$/.test(L)) {
      closeList(); out.push('<hr>');
    } else if (L.trim() === '') {
      closeList();
    } else {
      const buf = [L];
      while (i + 1 < lines.length && lines[i + 1].trim() !== '' &&
             !/^([#>`]|\s*[-*]\s|\s*\d+\.\s|\s*\|)/.test(lines[i + 1])) buf.push(lines[++i]);
      closeList();
      out.push(`<p>${inline(buf.join(' '))}</p>`);
    }
    i++;
  }
  closeList();
  return out.join('\n');
}

async function loadTheory() {
  const host = $('#theoryBody');
  if (host.dataset.loaded) return;
  host.innerHTML = '<div class="empty"><span class="spinner"></span> Loading…</div>';
  try {
    const src = await (await fetch((window.ES ? window.ES.base : '') + 'docs/THEORY.md')).text();
    host.innerHTML = `<div class="doc">${md(src)}</div>`;
    host.dataset.loaded = '1';
    const toc = $$('#theoryBody h2').map(h => `<a href="#${h.id}" data-go="${h.id}">${esc(h.textContent)}</a>`);
    $('#theoryToc').innerHTML = toc.join('');
    $$('#theoryToc a').forEach(a => a.onclick = ev => {
      ev.preventDefault();
      const t = $('#' + a.dataset.go);
      if (t) t.scrollIntoView({ behavior: 'smooth', block: 'start' });
      $$('#theoryToc a').forEach(x => x.classList.remove('on'));
      a.classList.add('on');
    });
  } catch (e) {
    host.innerHTML = `<div class="note">The theory document could not be loaded
      (${esc(e.message)}). It is also available as <code>docs/THEORY.md</code> in the
      application folder.</div>`;
  }
}

async function init() {
  try {
    if (window.ES && window.ES.ready) await window.ES.ready;
    S.meta = await api('/api/meta');
  } catch (e) {
    toast('The calculation engine is not available: ' + (e.message || e), 'err');
    return;
  }
  if (window.ES && window.ES.mode === 'browser') {
    $('#npWarn').style.display = '';
    $('#npWarn').className = 'badge info';
    $('#npWarn').textContent = 'running in your browser (Pyodide) — nothing is uploaded';
    $('#btnSaveProj').style.display = 'none';
    $('#btnLoadProj').style.display = 'none';
  }
  $('#ver').textContent = 'v' + S.meta.version;
  if (!S.meta.have_numpy) $('#npWarn').style.display = '';
  $('#cMat').innerHTML = S.meta.materials.map(m =>
    `<option value="${m.key}"${m.key === 'cu_hard' ? ' selected' : ''}>${esc(m.name)} — ${m.conductivity}% IACS</option>`).join('');
  $('#gSurfSel').innerHTML = S.meta.surface_materials.map(s =>
    `<option value="${s.rho_wet}|${s.rho_dry}">${esc(s.name)}</option>`).join('');
  $('#gSurfSel').onchange = () => {
    const [wet] = V('gSurfSel').split('|').map(Number);
    if (wet > 0) set('gRhoS', wet);
  };
  $('#sfChips').innerHTML = S.meta.split_factor_guide.map(g =>
    `<span class="chip" data-sf="${g.Sf}">${esc(g.case)} → ${g.Sf}</span>`).join('');
  $$('#sfChips .chip').forEach(c => c.onclick = () => {
    set('fSf', c.dataset.sf);
    $$('#sfChips .chip').forEach(x => x.classList.remove('on'));
    c.classList.add('on');
  });
  $('.navitem[data-page="about"]').addEventListener('click', loadTheory);
  $('#soilDemo').click();
  BEM_ITEMS = [JSON.parse(JSON.stringify(BEM_DEF.grid))];
  BUILD_ITEMS = [JSON.parse(JSON.stringify(BUILD_DEF.rod))];
  renderBem(); renderBuild(); reportSections();
  $('#rDate').value = new Date().toISOString().slice(0, 10);
  $('#bDev').onchange();
  $('#fMode').onchange();
}
init();
