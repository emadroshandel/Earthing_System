/* Earthing System — accessibility layer (1.10.0)
 * Copyright (C) 2026 Emad Roshandel — GPL-3.0-or-later
 *
 * The forms on every page are written as <label> + <input> pairs inside a
 * .field row, and many rows, tables and tab strips are built at run time.
 * Rather than edit some four hundred fields by hand, this script ties each
 * one to its label and explanation when it appears, so a screen reader
 * announces "Soil resistivity ρ, 400, Ω·m" instead of an unnamed edit box.
 *
 *  - every input/select/textarea gets a programmatic label and, where the
 *    page carries one, its ? explanation as an accessible description
 *  - table cells with inputs are named from their column header
 *  - .tabs strips become ARIA tab lists with arrow-key movement
 *  - every Plotly chart gets a figure role, a text summary and an optional
 *    data table (WCAG 1.1.1, the chart "table alternative")
 *  - the side menu turns into a drawer below 820 px
 */
(function () {
  'use strict';
  const $ = (q, r = document) => r.querySelector(q);
  const $$ = (q, r = document) => Array.from(r.querySelectorAll(q));
  let uid = 0;
  const id = (el, pre) => el.id || (el.id = `${pre}-${(++uid).toString(36)}`);
  const text = el => (el ? el.cloneNode(true) : null);
  const plain = el => {
    if (!el) return '';
    const c = text(el);
    c.querySelectorAll('.qm, .fh, input, select, textarea, button, .sr-only').forEach(x => x.remove());
    return c.textContent.replace(/\s+/g, ' ').trim();
  };
  const CONTROL = 'input:not([type=hidden]):not([type=file]), select, textarea';

  /* ------------------------------------------------------------ labels */
  function labelField(row) {
    const lab = row.querySelector(':scope > label');
    const fh = row.querySelector(':scope > .fh');
    const unit = row.querySelector(':scope > .u');
    row.querySelectorAll(':scope > ' + CONTROL.split(', ').join(', :scope > ')).forEach(inp => {
      if (inp.labels && inp.labels.length) { if (fh) describe(inp, fh); return; }
      if (lab && !lab.contains(inp)) {
        if (!lab.htmlFor) lab.htmlFor = id(inp, 'f');
        else if (lab.htmlFor !== inp.id) inp.setAttribute('aria-label', plain(lab));
        /* the ? badge inside the label would otherwise be read as part of the name */
        if (lab.querySelector('.qm') && !inp.getAttribute('aria-label')) inp.setAttribute('aria-label', plain(lab));
      }
      if (unit && unit.textContent.trim()) {
        /* "Ω·m" read straight after the value */
        describe(inp, unit, true);
      }
      if (fh) describe(inp, fh);
    });
    /* the ? badge says which field it explains */
    const qm = lab && lab.querySelector('.qm');
    if (qm && lab) qm.setAttribute('aria-label', 'Explain: ' + plain(lab));
  }
  function describe(inp, el, first) {
    const cur = (inp.getAttribute('aria-describedby') || '').split(' ').filter(Boolean);
    const i = id(el, 'd');
    if (cur.includes(i)) return;
    if (first) cur.unshift(i); else cur.push(i);
    inp.setAttribute('aria-describedby', cur.join(' '));
  }
  function labelPfield(row) {
    const lab = row.querySelector('label');
    const inp = row.querySelector(CONTROL);
    if (!lab || !inp || (inp.labels && inp.labels.length)) return;
    if (!lab.contains(inp)) lab.htmlFor = id(inp, 'p');
  }
  function labelTableInputs(table) {
    const heads = $$('thead th', table);
    if (!heads.length) return;
    $$('tbody tr', table).forEach((tr, r) => {
      Array.from(tr.children).forEach((td, c) => {
        const head = heads[c] ? plain(heads[c]) : '';
        td.querySelectorAll(CONTROL).forEach(inp => {
          if ((inp.labels && inp.labels.length) || inp.getAttribute('aria-label')) return;
          inp.setAttribute('aria-label', `${head || 'Value'}, row ${r + 1}`);
        });
        td.querySelectorAll('button').forEach(b => {
          if (!b.getAttribute('aria-label') && /^[✕×x]$/.test(b.textContent.trim()))
            b.setAttribute('aria-label', `Remove row ${r + 1}`);
        });
      });
    });
  }
  function labelLoose(root) {
    /* anything still nameless: borrow its placeholder or title, else the nearest heading */
    $$(CONTROL, root).forEach(inp => {
      if ((inp.labels && inp.labels.length) || inp.getAttribute('aria-label') || inp.getAttribute('aria-labelledby')) return;
      const t = inp.getAttribute('title') || inp.getAttribute('placeholder');
      if (t) { inp.setAttribute('aria-label', t); return; }
      const prev = inp.previousElementSibling;
      if (prev && /^(SPAN|B|STRONG|LABEL)$/.test(prev.tagName) && prev.textContent.trim()) {
        inp.setAttribute('aria-label', prev.textContent.trim()); return;
      }
      const card = inp.closest('.card');
      const h = card && card.querySelector('h3');
      if (h) inp.setAttribute('aria-label', plain(h));
    });
  }

  /* -------------------------------------------------------------- tabs */
  function wireTabs(strip) {
    strip.setAttribute('role', 'tablist');
    const tabs = $$(':scope > .tab', strip);
    const scope = strip.parentElement;
    tabs.forEach(t => {
      t.setAttribute('role', 'tab');
      const on = t.classList.contains('active');
      t.setAttribute('aria-selected', String(on));
      t.tabIndex = on ? 0 : -1;
      const pane = t.dataset.t && scope && scope.querySelector('#pane-' + t.dataset.t);
      if (pane) {
        pane.setAttribute('role', 'tabpanel');
        t.setAttribute('aria-controls', id(pane, 'tp'));
        pane.setAttribute('aria-labelledby', id(t, 'tb'));
      }
    });
    if (tabs.length && !tabs.some(t => t.tabIndex === 0)) tabs[0].tabIndex = 0;
    if (strip.dataset.a11y) return;
    strip.dataset.a11y = '1';
    strip.addEventListener('keydown', e => {
      const list = $$(':scope > .tab', strip);
      const i = list.indexOf(document.activeElement);
      if (i < 0) return;
      let j = null;
      if (e.key === 'ArrowRight' || e.key === 'ArrowDown') j = (i + 1) % list.length;
      else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') j = (i - 1 + list.length) % list.length;
      else if (e.key === 'Home') j = 0;
      else if (e.key === 'End') j = list.length - 1;
      else if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); list[i].click(); return; }
      if (j === null) return;
      e.preventDefault();
      list[j].click();
      list[j].focus();
    });
    /* whichever script switches the tab, keep the states in step */
    new MutationObserver(() => {
      $$(':scope > .tab', strip).forEach(t => {
        const on = t.classList.contains('active');
        if (t.getAttribute('aria-selected') !== String(on)) t.setAttribute('aria-selected', String(on));
        const ti = on ? 0 : -1;
        if (t.tabIndex !== ti) t.tabIndex = ti;
      });
    }).observe(strip, { subtree: true, attributes: true, attributeFilter: ['class'] });
  }

  /* ------------------------------------------------------- whole sweep */
  function sweep(root) {
    root = root || document;
    $$('.field', root).forEach(labelField);
    $$('.pfield', root).forEach(labelPfield);
    $$('table', root).forEach(labelTableInputs);
    $$('.tabs', root).forEach(wireTabs);
    $$('#theoryToc', root).forEach(n => n.setAttribute('aria-label', 'Theory contents'));
    labelLoose(root);
  }

  let pending = null;
  const later = () => { if (!pending) pending = requestAnimationFrame(() => { pending = null; sweep(document); }); };

  /* --------------------------------------------------- chart summaries */
  const fmt = v => {
    if (typeof v !== 'number' || !isFinite(v)) return String(v);
    const a = Math.abs(v);
    if (a !== 0 && (a >= 1e5 || a < 1e-3)) return v.toExponential(2);
    return +v.toPrecision(4) + '';
  };
  const range = arr => {
    let lo = Infinity, hi = -Infinity;
    const walk = a => a && a.forEach(v => Array.isArray(v) ? walk(v) : (typeof v === 'number' && isFinite(v) && (v < lo && (lo = v), v > hi && (hi = v))));
    walk(arr);
    return isFinite(lo) ? [lo, hi] : null;
  };
  const titleOf = ax => ax && (typeof ax.title === 'string' ? ax.title : ax.title && ax.title.text) || '';
  const strip = s => String(s || '').replace(/<[^>]+>/g, '').replace(/\s+/g, ' ').trim();

  function describePlot(gd) {
    if (!gd || !gd.data) return;
    const L = gd.layout || {}, sc = L.scene || {};
    const xa = strip(titleOf(L.xaxis) || titleOf(sc.xaxis)) || 'x';
    const ya = strip(titleOf(L.yaxis) || titleOf(sc.yaxis)) || 'y';
    const za = strip(titleOf(sc.zaxis));
    const card = gd.closest('.card');
    const title = card ? plain(card.querySelector('h3')) : 'Chart';
    const parts = [];
    gd.data.forEach((t, i) => {
      if (t.visible === false || t.hoverinfo === 'skip') return;
      const name = strip(t.name) || (t.type === 'contour' || t.type === 'surface' || t.type === 'heatmap' ? 'map' : `series ${i + 1}`);
      if (t.z && (t.type === 'contour' || t.type === 'surface' || t.type === 'heatmap')) {
        const r = range(t.z);
        const cb = strip(t.colorbar && titleOf(t.colorbar)) || za || 'value';
        if (r) parts.push(`${name}: ${cb} from ${fmt(r[0])} to ${fmt(r[1])} over ${xa} and ${ya}`);
        return;
      }
      const ry = range(t.y), rx = range(t.x);
      if (ry && rx) {
        const n = (t.y || []).filter(v => v !== null).length;
        parts.push(`${name}: ${n} point${n === 1 ? '' : 's'}, ${xa} ${fmt(rx[0])} to ${fmt(rx[1])}, ${ya} ${fmt(ry[0])} to ${fmt(ry[1])}`);
      }
    });
    const shown = parts.slice(0, 8);
    const extra = parts.length > shown.length ? ` and ${parts.length - shown.length} more series` : '';
    const sum = `${title}. ${shown.join('; ')}${extra}.`;
    let p = gd.nextElementSibling && gd.nextElementSibling.classList.contains('plotsum') ? gd.nextElementSibling : null;
    if (!p) {
      p = document.createElement('p');
      p.className = 'plotsum sr-only';
      gd.after(p);
    }
    p.textContent = sum;
    gd.setAttribute('role', 'figure');
    gd.setAttribute('aria-label', title);
    gd.setAttribute('aria-describedby', id(p, 'ps'));
    addTable(gd, p, xa, ya);
  }

  /* a collapsed table of the plotted series, built only when opened */
  function addTable(gd, after, xa, ya) {
    const lines = gd.data.filter(t => t.x && t.y && !t.z && t.hoverinfo !== 'skip' && t.visible !== false && (t.x.length || 0) <= 400);
    let det = after.nextElementSibling && after.nextElementSibling.classList.contains('plotdata') ? after.nextElementSibling : null;
    if (!lines.length) { if (det) det.remove(); return; }
    if (!det) {
      det = document.createElement('details');
      det.className = 'plotdata';
      det.innerHTML = '<summary>Data table</summary><div class="plotdata-body"></div>';
      after.after(det);
      det.addEventListener('toggle', () => det.open && build(det));
    }
    det._src = { gd, xa, ya };
    if (det.open) build(det);
  }
  function build(det) {
    const { gd, xa, ya } = det._src;
    const esc = s => String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
    const lines = gd.data.filter(t => t.x && t.y && !t.z && t.hoverinfo !== 'skip' && t.visible !== false && (t.x.length || 0) <= 400);
    det.querySelector('.plotdata-body').innerHTML = lines.map((t, i) => {
      const nm = strip(t.name) || `Series ${i + 1}`;
      const rows = t.x.map((x, k) => (x === null || t.y[k] === null) ? '' :
        `<tr><td class="n">${esc(fmt(x))}</td><td class="n">${esc(fmt(t.y[k]))}</td></tr>`).join('');
      return `<table class="data"><caption>${esc(nm)}</caption><thead><tr><th scope="col">${esc(xa)}</th><th scope="col">${esc(ya)}</th></tr></thead><tbody>${rows}</tbody></table>`;
    }).join('');
  }

  function hookPlotly() {
    if (!window.Plotly || Plotly.__a11y) return;
    Plotly.__a11y = true;
    ['react', 'newPlot'].forEach(fn => {
      const orig = Plotly[fn];
      Plotly[fn] = function (gd) {
        const out = orig.apply(this, arguments);
        const el = typeof gd === 'string' ? document.getElementById(gd) : gd;
        Promise.resolve(out).then(() => { try { describePlot(el); } catch (e) { console.warn(e); } });
        return out;
      };
    });
  }

  /* ------------------------------------------------- phone drawer menu */
  function drawer() {
    const btn = $('#btnNav'), nav = $('#nav'), scrim = $('#navScrim');
    if (!btn || !nav) return;
    const mq = matchMedia('(max-width: 820px)');
    const set = open => {
      document.body.classList.toggle('navopen', open);
      btn.setAttribute('aria-expanded', String(open));
      btn.setAttribute('aria-label', open ? 'Close the module menu' : 'Open the module menu');
      if (scrim) scrim.hidden = !open;
      if (mq.matches) {
        if (open) { nav.removeAttribute('inert'); $('#main').setAttribute('inert', ''); const a = nav.querySelector('[aria-current]') || nav.querySelector('button'); a && a.focus(); }
        else { nav.setAttribute('inert', ''); $('#main').removeAttribute('inert'); }
      }
    };
    const sync = () => {
      if (mq.matches) { if (!document.body.classList.contains('navopen')) nav.setAttribute('inert', ''); }
      else { nav.removeAttribute('inert'); $('#main').removeAttribute('inert'); document.body.classList.remove('navopen'); if (scrim) scrim.hidden = true; }
    };
    btn.addEventListener('click', () => set(!document.body.classList.contains('navopen')));
    if (scrim) scrim.addEventListener('click', () => { set(false); btn.focus(); });
    document.addEventListener('keydown', e => {
      if (e.key === 'Escape' && document.body.classList.contains('navopen')) { set(false); btn.focus(); }
    });
    mq.addEventListener('change', sync);
    sync();
    window.esA11y.closeDrawer = () => { if (document.body.classList.contains('navopen')) set(false); };
  }

  /* ------------------------------------------------------- public API */
  window.esA11y = {
    sweep,
    describePlot,
    pageShown(page) {
      if (this.closeDrawer) this.closeDrawer();
      const h = page && page.querySelector('.pagehead h2');
      if (h) { h.tabIndex = -1; h.focus({ preventScroll: true }); }
      $('#main') && ($('#main').scrollTop = 0);
      later();
    }
  };

  function init() {
    hookPlotly();
    /* the Explain-all toggle is a two-state button */
    const help = $('#btnHelp');
    if (help) {
      const syncHelp = () => help.setAttribute('aria-pressed', String(document.body.classList.contains('helpall')));
      syncHelp();
      new MutationObserver(syncHelp).observe(document.body, { attributes: true, attributeFilter: ['class'] });
    }
    drawer();
    sweep(document);
    /* plots drawn before this script ran */
    $$('.js-plotly-plot').forEach(describePlot);
    new MutationObserver(muts => {
      for (const m of muts) {
        for (const n of m.addedNodes) {
          if (n.nodeType === 1 && !(n.closest && n.closest('.js-plotly-plot, .drawing, svg')) &&
              (n.matches(CONTROL + ', .field, .pfield, tr, table, .tabs, .tab') || n.querySelector && n.querySelector(CONTROL + ', .tab'))) { later(); return; }
        }
      }
    }).observe($('#main') || document.body, { childList: true, subtree: true });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
})();
