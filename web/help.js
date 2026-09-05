/* EarthSystem — on-demand field explanations.
 *
 * Every input that needs one carries its explanation in a <div class="fh">
 * inside the field, and a small ? badge on the label. The text is hidden
 * until it is asked for:
 *
 *   hover the badge or the label   the explanation appears beside it
 *   click the badge                it stays until dismissed, so it can be read
 *   Esc, or a click elsewhere      dismisses a pinned one
 *   "Explain all" in the top bar   puts every explanation back inline
 *
 * The same tooltip serves the geometry tables, where each parameter carries
 * its explanation in a data-help attribute rather than a sibling element.
 *
 * Keeping the text in the markup rather than in a JavaScript table means it
 * stays in one readable place, and a translation only has to touch the HTML.
 */
'use strict';

(function () {

  const DELAY_BADGE = 90;      // hovering the badge is a deliberate act
  const DELAY_LABEL = 320;     // sweeping across a label is usually not

  let tip = null;
  let pinned = null;           // the trigger whose tip is held open
  let timer = null;

  function el() {
    if (tip) return tip;
    tip = document.createElement('div');
    tip.id = 'fieldtip';
    tip.setAttribute('role', 'tooltip');
    tip.hidden = true;
    tip.innerHTML = '<div class="ft-arrow"></div><div class="ft-body"></div>';
    document.body.appendChild(tip);
    /* a pinned tip must survive a click inside itself, so it can be read
       and its text selected */
    tip.addEventListener('mousedown', e => e.stopPropagation());
    return tip;
  }

  /* Where the explanation for a trigger lives. */
  function textFor(node) {
    if (node.dataset && node.dataset.help) return node.dataset.help;
    const holder = node.closest('[data-help]');
    if (holder) return holder.dataset.help;
    const field = node.closest('.field');
    const fh = field && field.querySelector('.fh');
    return fh ? fh.innerHTML : '';
  }

  function place(anchor) {
    const t = el();
    const a = anchor.getBoundingClientRect();
    t.hidden = false;
    t.style.left = '0px';
    t.style.top = '0px';
    const w = t.offsetWidth, h = t.offsetHeight;
    const vw = document.documentElement.clientWidth;
    const vh = document.documentElement.clientHeight;

    /* prefer below the anchor; flip above when there is no room */
    let top = a.bottom + 9;
    let below = true;
    if (top + h > vh - 8 && a.top - h - 9 > 8) { top = a.top - h - 9; below = false; }

    /* keep the box on screen, then point the arrow back at the anchor */
    let left = a.left + a.width / 2 - w / 2;
    left = Math.max(8, Math.min(left, vw - w - 8));

    t.style.left = Math.round(left) + 'px';
    t.style.top = Math.round(top) + 'px';
    t.classList.toggle('above', !below);
    const arrow = t.querySelector('.ft-arrow');
    const ax = Math.max(12, Math.min(a.left + a.width / 2 - left, w - 12));
    arrow.style.left = Math.round(ax) + 'px';
  }

  function show(anchor, html) {
    if (!html) return;
    const t = el();
    t.querySelector('.ft-body').innerHTML = html;
    t.classList.remove('pinned');
    place(anchor);
  }

  function hide(force) {
    if (pinned && !force) return;
    pinned = null;
    if (tip) { tip.hidden = true; tip.classList.remove('pinned'); }
  }

  function later(fn, ms) { clearTimeout(timer); timer = setTimeout(fn, ms); }

  /* ---------------------------------------------------------- triggers  */

  function triggerFor(target) {
    if (!target || !target.closest) return null;
    const badge = target.closest('.qm');
    if (badge) return { node: badge, delay: DELAY_BADGE };
    const dh = target.closest('[data-help]');
    if (dh) return { node: dh, delay: DELAY_BADGE };
    /* hovering the label of a field that has an explanation counts too */
    const label = target.closest('.field > label');
    if (label && label.parentElement.querySelector('.fh'))
      return { node: label.querySelector('.qm') || label, delay: DELAY_LABEL };
    return null;
  }

  document.addEventListener('mouseover', e => {
    if (pinned) return;
    const t = triggerFor(e.target);
    if (!t) return;
    later(() => show(t.node, textFor(t.node)), t.delay);
  });

  document.addEventListener('mouseout', e => {
    if (pinned) return;
    const t = triggerFor(e.target);
    if (!t) return;
    const to = e.relatedTarget;
    if (to && (to.closest('#fieldtip') || triggerFor(to))) return;
    clearTimeout(timer);
    later(() => hide(), 120);
  });

  /* clicking the badge pins the explanation open */
  document.addEventListener('click', e => {
    const badge = e.target.closest && e.target.closest('.qm');
    if (!badge) return;
    e.preventDefault();          // the badge sits inside a <label>
    e.stopPropagation();
    if (pinned === badge) { hide(true); return; }
    pinned = null;
    show(badge, textFor(badge));
    pinned = badge;
    el().classList.add('pinned');
  });

  document.addEventListener('mousedown', e => {
    if (!pinned) return;
    if (e.target.closest && (e.target.closest('#fieldtip') || e.target.closest('.qm'))) return;
    hide(true);
  });

  document.addEventListener('keydown', e => {
    if (e.key === 'Escape') { hide(true); return; }
    const badge = e.target.closest && e.target.closest('.qm');
    if (!badge) return;
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      badge.click();
    }
  });

  /* a badge reached by keyboard shows its explanation without a click */
  document.addEventListener('focusin', e => {
    const badge = e.target.closest && e.target.closest('.qm');
    if (badge && !pinned) show(badge, textFor(badge));
  });
  document.addEventListener('focusout', e => {
    if (e.target.closest && e.target.closest('.qm') && !pinned) hide();
  });

  /* a scroll or a page change would leave the tip stranded */
  window.addEventListener('scroll', () => hide(true), true);
  window.addEventListener('resize', () => hide(true));

  /* ------------------------------------------------------- explain all  */

  const btn = document.getElementById('btnHelp');
  if (btn) {
    const apply = on => {
      document.body.classList.toggle('helpall', on);
      btn.classList.toggle('on', on);
      btn.title = on ? 'Show the explanations only on hover'
        : 'Show every explanation inline, instead of on hover';
    };
    apply(localStorage.getItem('es-help') === 'all');
    btn.addEventListener('click', () => {
      const on = !document.body.classList.contains('helpall');
      localStorage.setItem('es-help', on ? 'all' : 'hover');
      apply(on);
      hide(true);
      if (window.DRAW) setTimeout(() => DRAW.redrawAll(), 30);
    });
  }

})();
