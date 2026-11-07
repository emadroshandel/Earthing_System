/* Earthing System — page sections (1.11.0)
 *
 * The long pages are split into sections. Each section is shown on its own, so a page
 * never has to be scrolled to discover what it holds:
 *  - the side menu lists the sections of the open page under its entry;
 *  - a section bar under the page heading lists them again, numbered, and stays in view;
 *  - a short line under the bar says what the section does and what it takes from the others;
 *  - Previous / Next buttons at the foot of each section walk through the page in order.
 *
 * An element of a page belongs to a section through data-sub="key" (several keys, space
 * separated, put it in more than one section). Elements without data-sub show in every
 * section. A two-column layout whose one column has nothing to show becomes one column,
 * and the forms of a lone card then flow into several columns.
 *
 * Nothing is removed from the page: hidden sections keep their inputs and results, the
 * project file, the report and the drawings read them as before.
 */
(function () {
  'use strict';
  const $ = (q, r = document) => r.querySelector(q);
  const $$ = (q, r = document) => Array.from(r.querySelectorAll(q));
  const esc = s => String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

  const MODEL = 'nsolve';
  const SUBS = {
    fault: [
      { key: 'fsrc', label: 'Fault current & split factor',
        desc: 'Symmetrical fault current, X/R, decrement factor and the share of it that flows into the grid.' },
      { key: 'fsw', label: 'Shield wires & fault location',
        desc: 'The shield-wire ladder of each line: how much of the fault current returns through the towers, swept along the line.' },
      { key: 'fcs', label: 'Cable sheaths',
        desc: 'The part of the earth-fault current that returns through the sheaths and screens of cables.' }
    ],
    numerical: [
      { key: MODEL, label: 'Model & solve',
        desc: 'The soil, the current and the buried electrodes, solved for the resistance, the surface potential and the touch and step voltages. Every other section of this page starts from this model.' },
      { key: 'ntp', label: 'Transferred potential', uses: 'the soil, the current and the electrodes',
        desc: 'The potential carried out of the station by a pipe, rail, cable screen or earth wire (IEEE Std 80 §17.3).' },
      { key: 'nlr', label: 'Lightning response', uses: 'the soil and the electrodes',
        desc: 'The transient potential rise and impulse impedance of the electrodes under first and subsequent strokes.' },
      { key: 'nacc', label: 'Accuracy & soil studies', uses: 'the soil, the current and the electrodes', feeds: true,
        desc: 'Mesh convergence, dry and frozen seasons, and the spread of the result over the uncertainty of the soil model.' },
      { key: 'nimp', label: 'Conductor impedance', uses: 'the soil, the current and the electrodes', feeds: true,
        desc: 'The non-equipotential solution: the grid conductors’ own impedance and the points where the current enters.' },
      { key: 'nopt', label: 'Grid optimisation', uses: 'the soil and the current',
        desc: 'The cheapest grid spacing and number of perimeter rods that keeps the touch and step voltages within their limits.' },
      { key: 'nfop', label: 'Fall-of-potential test', uses: 'the soil and the electrodes',
        desc: 'Plans the site test of the earth resistance, and checks measured readings against the model.' }
    ],
    building: [
      { key: 'bmain', label: 'Installation & electrodes',
        desc: 'The supply system, the protective device and the earth electrodes, checked against IEC 60364 / BS 7671.' },
      { key: 'bpit', label: 'Earth pit',
        desc: 'An electrode set in low-resistivity backfill: the pit, the backfill and a group of pits.' }
    ],
    lightning: [
      { key: 'lterm', label: 'Earth termination',
        desc: 'The earth termination of the lightning protection system: minimum electrode lengths and the impulse behaviour.' },
      { key: 'lrisk', label: 'Risk assessment',
        desc: 'IEC 62305-2 risk management: whether protection is needed and which LPS class it takes. The class found can be passed to the earth termination.' },
      { key: 'lspd', label: 'Surge protection (SPD)',
        desc: 'Selection and coordination of the surge protective devices, IEC 62305-4.' }
    ]
  };
  const title = page => {
    const it = $(`.navitem[data-page="${page}"]`);
    if (!it) return page;
    const c = it.cloneNode(true);
    c.querySelectorAll('.n, .dot, .sr-only, .chev').forEach(x => x.remove());
    return c.textContent.trim();
  };

  const store = {
    get(page) { try { return localStorage.getItem('es.sub.' + page); } catch (e) { return null; } },
    set(page, key) { try { localStorage.setItem('es.sub.' + page, key); } catch (e) { /* storage off */ } }
  };
  const current = {};

  const CHEV = '<svg class="ico" viewBox="0 0 24 24" aria-hidden="true" focusable="false" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 6l6 6-6 6"/></svg>';
  const PREV = '<svg class="ico" viewBox="0 0 24 24" aria-hidden="true" focusable="false" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 6l-6 6 6 6"/></svg>';

  function build(page, subs) {
    const sec = $('#page-' + page), item = $(`.navitem[data-page="${page}"]`);
    if (!sec || !item) return;
    const name = title(page);

    /* side menu: the sections under the page's entry */
    item.classList.add('hassub');
    const chev = document.createElement('span');
    chev.className = 'chev'; chev.setAttribute('aria-hidden', 'true'); chev.innerHTML = CHEV;
    item.insertBefore(chev, item.querySelector('.dot'));
    const sr = document.createElement('span');
    sr.className = 'sr-only'; sr.textContent = `, ${subs.length} sections`;
    item.insertBefore(sr, item.querySelector('.navstate'));
    const grp = document.createElement('div');
    grp.className = 'subnav'; grp.id = 'subnav-' + page;
    grp.setAttribute('role', 'group'); grp.setAttribute('aria-label', `Sections of ${name}`);
    grp.innerHTML = subs.map((s, i) =>
      `<button type="button" class="subitem" data-page="${page}" data-sub="${s.key}"><span class="sn" aria-hidden="true">${i + 1}</span><span class="sl">${esc(s.label)}</span></button>`).join('');
    item.after(grp);

    /* section bar under the page heading */
    const bar = document.createElement('nav');
    bar.className = 'subbar'; bar.setAttribute('aria-label', `Sections of ${name}`);
    bar.innerHTML = `<ol>${subs.map((s, i) =>
      `<li><button type="button" class="subtab" data-page="${page}" data-sub="${s.key}"><span class="sn" aria-hidden="true">${i + 1}</span>${esc(s.label)}</button></li>`).join('')}</ol>`;
    const intro = document.createElement('p');
    intro.className = 'subintro';
    const head = sec.querySelector('.pagehead');
    head.after(bar); bar.after(intro);

    /* previous / next at the foot */
    const pager = document.createElement('nav');
    pager.className = 'subpager'; pager.setAttribute('aria-label', `Previous and next section of ${name}`);
    sec.appendChild(pager);
  }

  function relayout(sec) {
    $$('.cols', sec).forEach(c => {
      const cols = Array.from(c.children);
      cols.forEach(col => {
        if (col.classList.contains('subhide')) return;
        const kids = Array.from(col.children);
        col.classList.toggle('subempty', kids.length > 0 && kids.every(k => k.classList.contains('subhide')));
      });
      const shown = cols.filter(col => !col.classList.contains('subhide') && !col.classList.contains('subempty'));
      c.classList.toggle('solo', shown.length === 1);
    });
    /* the first thing below the bar loses its top rule */
    $$('.subfirst', sec).forEach(x => x.classList.remove('subfirst'));
    const first = Array.from(sec.children).find(x =>
      !x.matches('.pagehead, .subbar, .subintro, .subpager') && !x.classList.contains('subhide'));
    if (first) first.classList.add('subfirst');
  }

  function resizePlots() {
    setTimeout(() => {
      if (window.Plotly) $$('.js-plotly-plot').forEach(d => { if (d.offsetParent) { try { Plotly.Plots.resize(d); } catch (e) { /* not drawn yet */ } } });
      window.dispatchEvent(new Event('resize'));
    }, 60);
  }

  function show(page, key, opts = {}) {
    const subs = SUBS[page], sec = $('#page-' + page);
    if (!subs || !sec) return;
    const i0 = subs.findIndex(s => s.key === key);
    const i = i0 < 0 ? 0 : i0, s = subs[i];
    current[page] = s.key; store.set(page, s.key);
    if (sec.classList.contains('active')) writeHash(page, s.key);

    $$('[data-sub]', sec).forEach(el => {
      if (el.closest('.subbar, .subpager, .subintro')) return;
      el.classList.toggle('subhide', !el.dataset.sub.split(/\s+/).includes(s.key));
    });
    relayout(sec);

    const mark = el => {
      const on = el.dataset.sub === s.key;
      el.classList.toggle('active', on);
      if (on) el.setAttribute('aria-current', 'true'); else el.removeAttribute('aria-current');
    };
    $$(`.subitem[data-page="${page}"]`).forEach(mark);
    $$('.subtab', sec).forEach(mark);
    /* on a phone the bar scrolls sideways: keep the current section in it */
    const at = $('.subtab.active', sec), ol = at && at.closest('ol');
    if (ol && ol.scrollWidth > ol.clientWidth) {
      const l = at.offsetLeft - ol.offsetLeft;
      if (l < ol.scrollLeft || l + at.offsetWidth > ol.scrollLeft + ol.clientWidth) ol.scrollLeft = Math.max(0, l - 12);
    }

    /* what this section does, and where its inputs come from */
    const intro = $('.subintro', sec);
    let h = `<b>${esc(s.label)}.</b> ${esc(s.desc || '')}`;
    if (s.uses) {
      h += ` <span class="subuses">Uses ${esc(s.uses)} of <button type="button" class="linkbtn" data-page="${page}" data-sub="${MODEL}">${esc(subs[0].label)}</button>${s.feeds ? '; its results also enter the governing values there' : ''}.</span>`;
    }
    intro.innerHTML = h;

    const pager = $('.subpager', sec);
    const prev = subs[i - 1], next = subs[i + 1];
    pager.innerHTML =
      (prev ? `<button type="button" class="ghost" data-page="${page}" data-sub="${prev.key}">${PREV}<span><small>Previous</small>${esc(prev.label)}</span></button>` : '<span></span>') +
      `<span class="pos" aria-hidden="true">${i + 1} / ${subs.length}</span>` +
      (next ? `<button type="button" class="ghost nextbtn" data-page="${page}" data-sub="${next.key}"><span><small>Next</small>${esc(next.label)}</span>${CHEV}</button>` : '<span></span>');

    if (opts.focus) {
      const main = $('#main');
      if (main) main.scrollTop = 0;
      const tgt = $('.subintro', sec);
      tgt.tabIndex = -1; tgt.focus({ preventScroll: true });
    }
    resizePlots();
  }

  function go(page, key, focus) {
    const item = $(`.navitem[data-page="${page}"]`);
    if (item && !item.classList.contains('active')) {
      current[page] = key; /* the page handler below shows this one */
      item.click();
    } else if (window.esA11y && window.esA11y.closeDrawer) {
      window.esA11y.closeDrawer();
    }
    show(page, key, { focus });
  }

  function init() {
    Object.entries(SUBS).forEach(([page, subs]) => build(page, subs));

    /* a page opened from the menu shows the section last used on it */
    $$('.navitem').forEach(it => it.addEventListener('click', () => {
      const page = it.dataset.page;
      if (SUBS[page]) show(page, current[page] || store.get(page) || SUBS[page][0].key);
    }));

    /* the menu entries, the section bar, the pager and the "uses" links */
    document.addEventListener('click', e => {
      const b = e.target.closest('.subitem, .subtab, .subpager button, .subintro .linkbtn');
      if (!b || !b.dataset.sub) return;
      go(b.dataset.page, b.dataset.sub, true);
    });

    /* arrow keys move along the section bar */
    $$('.subbar').forEach(bar => bar.addEventListener('keydown', e => {
      const list = $$('.subtab', bar), i = list.indexOf(document.activeElement);
      if (i < 0) return;
      let j = null;
      if (e.key === 'ArrowRight') j = (i + 1) % list.length;
      else if (e.key === 'ArrowLeft') j = (i - 1 + list.length) % list.length;
      else if (e.key === 'Home') j = 0;
      else if (e.key === 'End') j = list.length - 1;
      if (j === null) return;
      e.preventDefault(); list[j].focus();
    }));

    Object.keys(SUBS).forEach(page => show(page, store.get(page) || SUBS[page][0].key));

    /* the address names the page and section (#numerical/ntp), so a view can be
       bookmarked, shared with a student, or reopened after a reload */
    $$('.navitem').forEach(it => it.addEventListener('click', () => {
      const page = it.dataset.page;
      writeHash(page, SUBS[page] ? current[page] : null);
    }));
    window.addEventListener('hashchange', readHash);
    readHash();
  }

  function writeHash(page, key) {
    const h = '#' + page + (key ? '/' + key : '');
    if (location.hash !== h) { try { history.replaceState(null, '', h); } catch (e) { /* file:// */ } }
  }
  function readHash() {
    const m = /^#([a-z0-9]+)(?:\/([a-z0-9]+))?$/i.exec(location.hash || '');
    if (!m) return;
    const item = $(`.navitem[data-page="${m[1]}"]`);
    if (!item) return;
    if (m[2] && SUBS[m[1]] && SUBS[m[1]].some(s => s.key === m[2])) current[m[1]] = m[2];
    if (!item.classList.contains('active')) item.click();
    else if (SUBS[m[1]]) show(m[1], current[m[1]]);
  }

  /* for other scripts: show the section that holds an element, e.g. before scrolling to it */
  window.esSections = {
    show: (page, key) => go(page, key, false),
    reveal(el) {
      const sec = el && el.closest('.page');
      if (!sec) return;
      const holder = el.closest('[data-sub]:not(.subtab)');
      if (holder) show(sec.id.replace('page-', ''), holder.dataset.sub.split(/\s+/)[0]);
    }
  };

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
