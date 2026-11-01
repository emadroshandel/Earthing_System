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

/* Module 11 — construction drawings.  The drawing set is produced by
   earthsys/drawings.py from the results already held in S; this file only
   gathers the title block and the drafting options, and shows the sheets. */
(function () {
  'use strict';
  const SHEETS = [['101', 'Earth grid layout plan'], ['102', 'Typical installation sections'],
    ['201', 'Earth pit and test link'], ['202', 'Main earthing terminal'], ['301', 'Connection details'],
    ['302', 'Equipment bonding details'], ['303', 'Conductor selection chart'],
    ['401', 'Lightning earth termination'], ['501', 'Earthing schematics'], ['901', 'Bill of materials']];
  let LAST = null, CUR = 0;
  const EXCLUDED = new Set();

  function b64Blob(b64, type) {
    const bin = atob(b64), n = bin.length, u = new Uint8Array(n);
    for (let i = 0; i < n; i++) u[i] = bin.charCodeAt(i);
    return new Blob([u], { type });
  }
  function save(blob, name) {
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob); a.download = name; a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 4000);
  }
  function nn(id) { const v = parseFloat(V(id)); return isFinite(v) ? v : null; }

  function sheetList() {
    const has = k => !!S[k];
    const avail = {
      '101': has('grid') || has('bem'), '102': has('grid') || has('bem'),
      '401': has('lightning') || has('airterm'), '501': has('building') || has('sysgnd')
    };
    $('#dSheets').innerHTML = '<table class="data"><tbody>' +
      '<tr><td><input type="checkbox" checked disabled></td><td>000</td><td>Register, notes, legend, verification</td><td></td></tr>' +
      SHEETS.map(([c, t]) => {
        const ok = avail[c] === undefined ? true : avail[c];
        return `<tr><td><input type="checkbox" data-sheet="${c}" ${EXCLUDED.has(c) ? '' : 'checked'} ${ok ? '' : 'disabled'}></td>
          <td>${c}</td><td>${esc(t)}</td><td>${ok ? '' : '<span class="badge warn">needs its module</span>'}</td></tr>`;
      }).join('') + '</tbody></table>';
    $$('#dSheets [data-sheet]').forEach(cb => cb.onchange = () => {
      if (cb.checked) EXCLUDED.delete(cb.dataset.sheet); else EXCLUDED.add(cb.dataset.sheet);
    });
  }

  function payload() {
    const meta = {
      owner: V('dOwner'), designer: V('dDesigner'), project: V('dProject') || V('rProject') || V('projName'),
      location: V('dLocation'), prefix: V('dPrefix') || 'ES-DWG', rev: V('dRev') || '0',
      rev_desc: V('dRevDesc'), status: V('dStatus'), drawn: V('dDrawn'), checked: V('dChecked'),
      approved: V('dApproved'), date: V('dDate'), size: V('dSize'), engineer: V('rEngineer')
    };
    const equipment = {
      transformer: nn('dEqTx') || 0, neutral: nn('dEqN') || 0, arrester: nn('dEqSA') || 0,
      switchgear: nn('dEqSG') || 0, structure: nn('dEqSt') || 0, lv_panel: nn('dEqLV') || 0,
      motor: nn('dEqM') || 0, cable_tray: nn('dEqCT') || 0, pipe: nn('dEqP') || 0,
      fence: C('dFence') && (S.grid || S.bem) ? 1 : 0
    };
    const options = {
      joint: V('dJoint'), electrode_duty: V('dDuty') || 'auto', fence: C('dFence') && !!(S.grid || S.bem),
      fence_offset: nn('dFenceOff'), fence_bond_m: nn('dFenceBond'), rod_section_m: nn('dRodSec'),
      test_pits: nn('dPits'), met_ways: nn('dMetWays'), wastage_pct: nn('dWaste'), equipment,
      sheets: SHEETS.map(s => s[0]).filter(c => !EXCLUDED.has(c))
    };
    if (V('dCond')) options.conductor_mm2 = +V('dCond');
    if (V('dRodMat')) options.rod_material = V('dRodMat');
    if (V('dHousing')) options.pit_housing = V('dHousing');
    /* results without the heavy plotting arrays the drawings never use */
    const results = {};
    ['grid', 'bem', 'conductor', 'fault', 'earthpit', 'building', 'lightning', 'airterm', 'sysgnd'].forEach(k => {
      if (!S[k]) return;
      const o = { ...S[k] };
      ['surface', 'touch_map', 'profile', 'grid_V', 'map', 'field', 'spheres', 'envelope', 'view'].forEach(x => delete o[x]);
      results[k] = o;
    });
    if (S.bem) {
      results.bem = { _in: { items: (S.bem._in && S.bem._in.items) || (typeof BEM_ITEMS !== 'undefined' ? BEM_ITEMS : []) } };
      /* the numerical verdict is the governing one: plain solution and every study on the same model (1.8.2) */
      const g = S.governing && S.governing.model_key === S.bem.model_key ? S.governing : null;
      if (g && g.passed !== null && g.passed !== undefined) {
        results.bem.passed = g.passed;
        results.bem.governing_note = g.note;
        results.bem.studies_used = g.studies_used;
      } else if (S.bem.checks && S.bem.checks.length) {
        results.bem.passed = S.bem.checks.every(c => c.passed);
      }
    }
    return { meta, options, results };
  }

  function show(i) {
    if (!LAST) return;
    CUR = i;
    $$('#dTabs .tab').forEach((t, k) => t.classList.toggle('active', k === i));
    const z = +V('dZoom') || 100;
    $('#dView').innerHTML = `<div style="width:${z}%;min-width:${z}%">${LAST.sheets[i].svg}</div>`;
    const svg = $('#dView svg');
    if (svg) { svg.removeAttribute('width'); svg.removeAttribute('height'); svg.style.width = '100%'; svg.style.height = 'auto'; svg.style.display = 'block'; }
  }

  function render(r) {
    LAST = r;
    const bad = r.checks.filter(c => c.status === 'FAIL').length;
    kpis('dKpis', [
      { value: r.sheets.length, label: 'Sheets' },
      { value: r.conductor.size + ' <small>mm²</small>', label: 'Earth conductor drawn' },
      { value: r.bom.length, label: 'Bill of materials items' },
      { value: bad ? bad + ' FAIL' : 'all OK', label: 'Design-rule verification', state: bad ? 'bad' : 'ok' }
    ]);
    $('#dTabs').innerHTML = r.sheets.map((s, i) =>
      `<div class="tab" data-i="${i}" title="${esc(s.title)}">${esc(s.number.split('-').pop())}</div>`).join('');
    $$('#dTabs .tab').forEach(t => t.addEventListener('click', () => show(+t.dataset.i)));
    show(Math.min(CUR, r.sheets.length - 1));
    $('#dChecks').innerHTML = '<table class="data"><thead><tr><th>Item</th><th>Required</th><th>Drawn</th><th></th><th>Reference</th></tr></thead><tbody>' +
      r.checks.map(c => `<tr><td>${esc(c.item)}</td><td>${esc(c.required)}</td><td>${esc(c.actual)}</td>
        <td><span class="badge ${c.status === 'OK' ? 'ok' : c.status === 'FAIL' ? 'bad' : 'info'}">${esc(c.status)}</span></td>
        <td class="src">${esc(c.ref)}</td></tr>`).join('') + '</tbody></table>';
    $('#dBom').innerHTML = '<table class="data"><thead><tr><th>#</th><th>Description</th><th>Standard</th><th>Qty</th><th>Unit</th></tr></thead><tbody>' +
      r.bom.map(b => `<tr><td>${esc(b[0])}</td><td>${esc(b[1])}</td><td class="src">${esc(b[2])}</td>
        <td class="n">${esc(b[3])}</td><td>${esc(b[4])}</td></tr>`).join('') + '</tbody></table>';
    markNav('drawings', !bad);
  }

  $('#dRun').onclick = e => run(e.target, async () => {
    const p = payload();
    const r = await api('/api/drawings', p);
    render(r);
    toast(`${r.sheets.length} sheets generated` + (r.saved_to ? ' and saved to the outputs folder.' : '.'), 'ok');
  });
  $('#dPdf').onclick = () => {
    if (!LAST) return toast('Generate the drawings first.', 'err');
    save(b64Blob(LAST.pdf_b64, 'application/pdf'), LAST.filename + '_drawings.pdf');
  };
  $('#dZip').onclick = () => {
    if (!LAST) return toast('Generate the drawings first.', 'err');
    save(b64Blob(LAST.zip_b64, 'application/zip'), LAST.filename + '_drawing_set.zip');
  };
  $('#dSvg').onclick = () => {
    if (!LAST) return toast('Generate the drawings first.', 'err');
    const s = LAST.sheets[CUR];
    save(new Blob([s.svg], { type: 'image/svg+xml' }), s.number + '.svg');
  };
  $('#dZoom').oninput = () => show(CUR);
  $('.navitem[data-page="drawings"]').addEventListener('click', () => {
    sheetList();
    if (!V('dDate')) set('dDate', new Date().toISOString().slice(0, 10));
    if (!V('dProject') && V('projName')) set('dProject', V('projName'));
  });
  sheetList();
})();
