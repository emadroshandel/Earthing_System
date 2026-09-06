/* EarthSystem — the engineering drawings themselves.
 *
 * Every function here takes a host element id and a result object from one of
 * the calculation modules, and draws a scale section or plan of what the
 * numbers describe.  The drawings are not decoration: each one carries the
 * dimensions the calculation used, so a reader can check the model against
 * the site before trusting the result.
 *
 * Built on DRAW (web/draw.js).
 */
'use strict';

window.SEC = (function () {

  const m = DRAW.m;
  const num = (v, d) => (v === null || v === undefined || !isFinite(v)) ? '—'
    : (d === undefined ? String(Math.round(v * 100) / 100) : v.toFixed(d));

  /* ------------------------------------------------------------ helpers */

  /* A driven rod drawn in section, with couplers and a pointed tip. */
  function rod(s, x, zTop, len, dm, o) {
    o = o || {};
    const p = s.p;
    const w = Math.max(3.2, Math.min(9, s.dX(dm || 0.016) * 3));
    const X = s.X(x), Y0 = s.Y(zTop), Y1 = s.Y(zTop - len);
    const col = o.colour || (o.material === 'copper' ? p.copper : p.steel);
    s.push('mid', `<rect x="${(X - w / 2).toFixed(1)}" y="${Y0.toFixed(1)}" width="${w.toFixed(1)}"
      height="${Math.max(0, Y1 - Y0 - w).toFixed(1)}" rx="${(w / 2).toFixed(1)}" fill="${col}"/>`);
    /* pointed tip */
    s.push('mid', `<path d="M${(X - w / 2).toFixed(1)},${(Y1 - w).toFixed(1)}
      L${X.toFixed(1)},${Y1.toFixed(1)} L${(X + w / 2).toFixed(1)},${(Y1 - w).toFixed(1)} Z" fill="${col}"/>`);
    /* couplers every 1.5 m — how a long rod is actually driven */
    if (o.couplers !== false && len > 1.6) {
      for (let z = zTop - 1.5; z > zTop - len + 0.3; z -= 1.5) {
        const yy = s.Y(z);
        s.push('mid', `<rect x="${(X - w * .95).toFixed(1)}" y="${(yy - 2.2).toFixed(1)}"
          width="${(w * 1.9).toFixed(1)}" height="4.4" rx="1.2" fill="${p.zinc}" opacity=".95"/>`);
      }
    }
    return { w };
  }

  /* A conductor seen end-on. */
  function conductorDot(s, x, z, dm, o) {
    o = o || {};
    const r = Math.max(2.6, Math.min(7, s.dX(dm || 0.01) * 4));
    s.circleW(x, z, r, {
      fill: o.colour || s.p.copper, stroke: s.p.panel, 'stroke-width': 1
    }, 'mid');
    return r;
  }

  /* A buried tape or flat conductor seen in section, running left to right. */
  function tape(s, x0, x1, z, o) {
    o = o || {};
    const t = 4;
    s.push('mid', `<rect x="${s.X(x0).toFixed(1)}" y="${(s.Y(z) - t / 2).toFixed(1)}"
      width="${(s.X(x1) - s.X(x0)).toFixed(1)}" height="${t}" rx="1.5"
      fill="${o.colour || s.p.copper}"/>`);
  }

  /* A simple standing figure, used to show what touch and step voltage mean. */
  function person(s, x, zGround, o) {
    o = o || {};
    const p = s.p;
    const H = o.h || 1.75;                       // a person is about 1.75 m
    const X = s.X(x), G = s.Y(zGround);
    const hpx = s.Y(zGround) - s.Y(zGround + H);
    const head = hpx * 0.13, body = hpx * 0.46, leg = hpx * 0.41;
    const c = o.colour || p.ink2;
    const g = [];
    g.push(`<circle cx="${X.toFixed(1)}" cy="${(G - hpx + head).toFixed(1)}" r="${head.toFixed(1)}"
      fill="none" stroke="${c}" stroke-width="1.6"/>`);
    g.push(`<line x1="${X.toFixed(1)}" y1="${(G - hpx + head * 2).toFixed(1)}"
      x2="${X.toFixed(1)}" y2="${(G - leg).toFixed(1)}" stroke="${c}" stroke-width="1.6"/>`);
    if (o.stride) {           // walking: feet one stride apart
      const sx = s.dX(o.stride);
      g.push(`<line x1="${X.toFixed(1)}" y1="${(G - leg).toFixed(1)}"
        x2="${(X - sx / 2).toFixed(1)}" y2="${G.toFixed(1)}" stroke="${c}" stroke-width="1.6"/>`);
      g.push(`<line x1="${X.toFixed(1)}" y1="${(G - leg).toFixed(1)}"
        x2="${(X + sx / 2).toFixed(1)}" y2="${G.toFixed(1)}" stroke="${c}" stroke-width="1.6"/>`);
    } else {
      g.push(`<line x1="${X.toFixed(1)}" y1="${(G - leg).toFixed(1)}"
        x2="${(X - 4).toFixed(1)}" y2="${G.toFixed(1)}" stroke="${c}" stroke-width="1.6"/>`);
      g.push(`<line x1="${X.toFixed(1)}" y1="${(G - leg).toFixed(1)}"
        x2="${(X + 4).toFixed(1)}" y2="${G.toFixed(1)}" stroke="${c}" stroke-width="1.6"/>`);
    }
    if (o.reach) {            // arm stretched out to touch something
      const rx = s.dX(o.reach) * (o.reachDir || 1);
      g.push(`<line x1="${X.toFixed(1)}" y1="${(G - hpx + head * 2 + body * .28).toFixed(1)}"
        x2="${(X + rx).toFixed(1)}" y2="${(G - hpx + head * 2 + body * .28).toFixed(1)}"
        stroke="${c}" stroke-width="1.6"/>`);
    }
    s.push('mid', `<g>${g.join('')}</g>`);
    return { handY: G - hpx + head * 2 + body * 0.28, groundY: G, X };
  }

  /* A small plan view tucked into the corner of a section. A ring or a mesh is
     two cuts through one object in section, which is genuinely ambiguous; the
     inset says what the object is without needing a second drawing. */
  function planInset(s, draw, caption, o) {
    o = o || {};
    const R = o.r || 36;
    const cx = o.x != null ? o.x : s.W - s.P.r - R - 12;
    const cy = o.y != null ? o.y : s.P.t + R + 16;
    const p = s.p;
    s.push('front', `<rect x="${(cx - R - 12).toFixed(1)}" y="${(cy - R - 12).toFixed(1)}"
      width="${(2 * R + 24).toFixed(1)}" height="${(2 * R + 30).toFixed(1)}" rx="6"
      fill="${p.panel}" stroke="${p.line}" stroke-width="1" opacity=".95"/>`);
    draw(cx, cy, R);
    s.textPx(cx, cy + R + 15, caption,
      { anchor: 'middle', size: 10, fill: p.ink3 });
    return { cx, cy, R };
  }

  /* A double-headed annotation arrow in pixel space with a coloured label. */
  function measure(s, x1, y1, x2, y2, label, colour) {
    s.arrowDefs();
    s.push('front', `<line x1="${x1.toFixed(1)}" y1="${y1.toFixed(1)}" x2="${x2.toFixed(1)}"
      y2="${y2.toFixed(1)}" stroke="${colour}" stroke-width="1.4"
      marker-start="url(#${s.id}-arS)" marker-end="url(#${s.id}-arS)"/>`);
    s.textPx((x1 + x2) / 2 + 7, (y1 + y2) / 2 + 3.5, label,
      { size: 11, weight: 600, fill: colour, halo: true });
  }


  /* ==================================================================== 0
     The four-pin array itself — what "pin spacing" actually refers to.
     Drawn small, because it sits in the narrow input column beside the
     survey table it is explaining. */
  function fourPin(hostId, o) {
    o = o || {};
    const schl = o.array === 'schlumberger';
    const C = 1.5;                    // outer (current) pins, in units of a
    const P = schl ? 0.24 : 0.5;      // inner (potential) pins
    const X0 = -1.85, X1 = 1.85, Ytop = 0.62, Ybot = -1.55;

    DRAW.scene(hostId, {
      width: 430, height: 330, equal: true,
      xmin: X0, xmax: X1, ymin: Ybot, ymax: Ytop,
      pad: { l: 24, r: 24, t: 26, b: 84 }
    }, s => {
      const p = s.p;
      s.title(schl ? 'Schlumberger array' : 'Wenner four-pin array');
      s.bandPx(Ytop, 0, { fill: p.sky });
      s.stratum(0, Ybot, { pattern: 'soil', colour: p.soilA, line: false });

      /* the volume the reading is actually averaged over */
      s.bandPx(-0.5, -1.0, { fill: p.zoneFill });
      s.linePx(s.P.l, s.Y(-0.5), s.W - s.P.r, s.Y(-0.5),
        { stroke: p.zoneEdge, 'stroke-width': .9, 'stroke-dasharray': '4 4', opacity: .8 }, 'back');
      s.linePx(s.P.l, s.Y(-1.0), s.W - s.P.r, s.Y(-1.0),
        { stroke: p.zoneEdge, 'stroke-width': .9, 'stroke-dasharray': '4 4', opacity: .8 }, 'back');
      s.textPx(s.P.l + 4, s.Y(-0.75) + 3.5,
        schl ? 'median depth ≈ AB/4' : 'median depth ≈ a/2 to a',
        { size: 9.5, fill: p.zoneEdge, weight: 600 });

      s.groundLine(0);

      /* the current spreading from one outer pin to the other */
      const arc = (depth, op) => {
        const n = 48, pts = [];
        for (let i = 0; i <= n; i++) {
          const t = i / n;
          pts.push(`${s.X(-C + 2 * C * t).toFixed(1)},${s.Y(-depth * Math.sin(Math.PI * t)).toFixed(1)}`);
        }
        s.push('mid', `<polyline points="${pts.join(' ')}" fill="none" stroke="${p.accent}"
          stroke-width="1.1" stroke-dasharray="4 4" opacity="${op}"/>`);
      };
      [[0.30, .75], [0.62, .6], [1.00, .45], [1.34, .3]].forEach(d => arc(d[0], d[1]));

      /* the instrument, and the leads down to the pins */
      const bx0 = -0.66, bx1 = 0.66, by0 = 0.30, by1 = 0.56;
      s.rectW(bx0, by0, bx1 - bx0, by1 - by0,
        { fill: p.panel, stroke: p.ink2, 'stroke-width': 1.2, rx: 3 }, 'mid');
      s.textW((bx0 + bx1) / 2, (by0 + by1) / 2, 'earth tester',
        { anchor: 'middle', dy: 4, size: 10, fill: p.ink2 });

      const lead = (x, xEnd, colour) => s.push('mid',
        `<polyline points="${s.X(x)},${s.Y(by0)} ${s.X(xEnd)},${s.Y(0.18)} ${s.X(xEnd)},${s.Y(0.05)}"
          fill="none" stroke="${colour}" stroke-width="1.4"/>`);
      lead(bx0 + 0.06, -C, p.bad); lead(bx1 - 0.06, C, p.bad);
      lead(-0.2, -P, p.accent); lead(0.2, P, p.accent);

      /* the pins */
      const pin = (x, label, colour) => {
        s.rectW(x - 0.018, -0.11, 0.036, 0.17, { fill: colour, rx: 1 }, 'mid');
        s.textW(x, 0.06, label, { anchor: 'middle', dy: -6, size: 10.5, weight: 700, fill: colour });
      };
      pin(-C, 'C1', p.bad); pin(-P, 'P1', p.accent);
      pin(P, 'P2', p.accent); pin(C, 'C2', p.bad);

      /* what the spacing entered in the table refers to */
      if (schl) {
        s.dimH(0, C, 0, 'AB/2', { off: 30 });
        s.dimH(-P, P, 0, 'MN', { off: 54 });
      } else {
        s.dimH(-C, -P, 0, 'a', { off: 30 });
        s.dimH(-P, P, 0, 'a', { off: 30 });
        s.dimH(P, C, 0, 'a', { off: 30 });
      }

      s.note(schl
        ? 'ρₐ = π·R·(s² − (MN/2)²)/MN, with s = AB/2. Enter s in the table.'
        : 'ρₐ = 2π·a·R. Enter a in the table — one row per spacing.');
      s.note('Current enters at C1 and leaves at C2; the tester reads the voltage '
        + 'between P1 and P2. A wider spacing drives the current deeper, so each '
        + 'row of the table samples a deeper slice of ground.');
    });
  }

  /* ==================================================================== 1
     Soil model — the fitted stratigraphy and how deep the system reaches. */
  function soil(hostId, d) {
    d = d || {};
    const twoLayer = isFinite(d.h1) && d.h1 > 0 && isFinite(d.rho2);
    const h1 = twoLayer ? d.h1 : 0;
    const burial = isFinite(d.depth) ? d.depth : 0.5;
    const rodLen = isFinite(d.rodLen) ? d.rodLen : 0;
    const bottom = Math.max(h1 * 1.75, burial + rodLen + 1.5, 4);
    const Zb = Math.ceil(bottom * 2) / 2;
    const top = Zb * 0.16;
    const Wm = (Zb + top) * 2.15;

    DRAW.scene(hostId, {
      width: 920, height: 400, equal: true,
      xmin: 0, xmax: Wm, ymin: -Zb, ymax: top
    }, s => {
      const p = s.p;
      s.title('Soil model — section', twoLayer ? 'two-layer earth (IEEE Std 81 §8)' : 'uniform earth');
      s.bandPx(top, 0, { fill: p.sky });

      if (twoLayer) {
        s.stratum(0, -h1, {
          pattern: 'soil', colour: p.soilA,
          label: `Upper layer   ρ₁ = ${num(d.rho1, 0)} Ω·m   ·   h = ${m(h1)}`
        });
        s.stratum(-h1, -Zb, {
          pattern: d.rho2 > d.rho1 ? 'rock' : 'clay', colour: p.soilB, dash: '6 4',
          label: `Lower layer   ρ₂ = ${num(d.rho2, 0)} Ω·m`,
          sub: d.rho2 > d.rho1 ? 'more resistive — current is confined to the upper layer'
            : 'less resistive — current spreads into the lower layer'
        });
        s.dimV(0, -h1, Wm * 0.985, m(h1), { off: 26 });
      } else {
        s.stratum(0, -Zb, {
          pattern: 'soil', colour: p.soilA,
          label: `Uniform soil   ρ = ${num(d.rho1 || d.rhoEq, 0)} Ω·m`
        });
      }
      s.groundLine(0);

      /* the earthing system, drawn where it actually sits */
      const xc = Wm * 0.66;
      tape(s, Wm * 0.34, Wm * 0.96, -burial, {});
      [0.40, 0.53, 0.66, 0.79, 0.92].forEach(f => conductorDot(s, Wm * f, -burial, 0.012));
      s.dimV(0, -burial, Wm * 0.34, `h = ${m(burial)}`, { off: -14 });
      s.leader(Wm * 0.53, -burial, 20, 40,
        ['Buried earthing conductor']);

      if (rodLen > 0) {
        rod(s, xc, -burial, rodLen, 0.016, { material: 'steel' });
        s.dimV(-burial, -burial - rodLen, xc + Wm * 0.055, m(rodLen), { off: 22, ext: true });
        s.leader(xc, -burial - rodLen, 44, 20,
          ['Ground rod', `${m(rodLen)} below the grid`]);
      }

      if (isFinite(d.aMax) && d.aMax > 0 && d.aMax < Zb) {
        s.lineW(0, -d.aMax, Wm, -d.aMax,
          { stroke: p.accent, 'stroke-width': 1.1, 'stroke-dasharray': '3 4', opacity: .85 }, 'mid');
        s.textW(Wm * 0.02, -d.aMax, `depth of investigation of the traverse ≈ a_max = ${m(d.aMax)}`,
          { dy: -5, size: 10.5, fill: p.accent, halo: true });
      }

      const K = twoLayer ? (d.rho2 - d.rho1) / (d.rho2 + d.rho1) : null;
      if (K !== null) s.note(`Reflection factor K = (ρ₂ − ρ₁)/(ρ₂ + ρ₁) = ${num(K, 3)}`);
      if (isFinite(d.rhoEq))
        s.note(`Equivalent uniform resistivity used by the closed-form equations: ρ = ${num(d.rhoEq, 0)} Ω·m`);
      s.scalebar();
    });
  }

  /* ==================================================================== 2
     A single earth electrode, drawn to the type and size actually entered. */
  function electrode(hostId, item, R, rho) {
    const q = item || {};
    const t = q.type || 'rod';
    const F = k => parseFloat(q[k]);

    let depth = 3, Wm = 8, burial = isFinite(F('h')) ? F('h') : 0.6;

    /* work out a sensible frame for each electrode type */
    if (t === 'rod') { depth = (F('L') || 3) + 1; Wm = Math.max(4, depth * 1.9); }
    else if (t === 'rods_parallel') {
      const n = Math.max(2, F('n') || 3), sp = F('s') || 6;
      Wm = Math.min(n - 1, 3) * sp + sp; depth = (F('L') || 3) + 1.2;
    }
    else if (t === 'strip') { Wm = Math.min(F('L') || 20, 26); depth = Math.max(2, burial * 3); }
    else if (t === 'ring') { Wm = 2 * (F('radius') || 5) * 1.25; depth = Math.max(2.2, burial * 3.5); }
    else if (t === 'plate') { Wm = 5; depth = Math.max(3, burial + Math.sqrt(F('area') || 1) + 1); }
    else if (t === 'foundation') {
      const V = F('volume_m3') || F('volume') || 20;
      const side = Math.cbrt(V) * 1.5;
      const thick = Math.max(0.4, V / (side * side));
      Wm = Math.max(6, side * 1.8);
      depth = burial + thick + Math.max(1.6, thick * 0.7);
    }
    else if (t === 'mesh') { Wm = Math.min(Math.sqrt(F('area') || 100), 24); depth = Math.max(2.2, burial * 3.5); }

    const top = depth * 0.2;
    /* keep the frame proportional so the section is drawn to true scale */
    const need = (depth + top) * 2.2;
    Wm = Math.max(Wm, need * 0.45);

    DRAW.scene(hostId, {
      width: 900, height: 340, equal: true,
      xmin: -Wm / 2, xmax: Wm / 2, ymin: -depth, ymax: top
    }, s => {
      const p = s.p;
      const names = {
        rod: 'Driven rod', rods_parallel: 'Rods in parallel', strip: 'Buried tape',
        ring: 'Ring electrode', plate: 'Earth plate', foundation: 'Foundation earth electrode',
        mesh: 'Buried mesh'
      };
      s.title(names[t] || t,
        [isFinite(rho) ? `soil ρ = ${num(rho, 0)} Ω·m` : '',
         isFinite(R) ? `computed R = ${num(R, 2)} Ω` : ''].filter(Boolean).join('   ·   '));
      s.bandPx(top, 0, { fill: p.sky });
      s.stratum(0, -depth, { pattern: 'soil', colour: p.soilA });
      s.groundLine(0);

      if (t === 'rod') {
        const L = F('L') || 3, dm = (F('d') || 0.016);
        rod(s, 0, 0, L, dm);
        s.dimV(0, -L, 0, `L = ${m(L)}`, { off: Math.min(130, s.dX(Wm * 0.26)) });
        s.leader(0, -L * 0.45, -88, -22,
          [`\u00f8 ${(dm * 1000).toFixed(0)} mm`, 'copper-bonded steel']);
        s.note('R = ρ/(2πL)·[ln(8L/d) − 1]  —  IEC 60364-5-54 / BS 7430');
      }

      else if (t === 'rods_parallel') {
        const n = Math.max(2, Math.round(F('n') || 3));
        const sp = F('s') || 6, L = F('L') || 3, dm = F('d') || 0.016;
        const show = Math.min(n, 4);
        const x0 = -((show - 1) * sp) / 2;
        for (let i = 0; i < show; i++) rod(s, x0 + i * sp, 0, L, dm);
        tape(s, x0 - 0.3, x0 + (show - 1) * sp + 0.3, -0.6, {});
        s.dimH(x0, x0 + sp, 0, `s = ${m(sp)}`, { off: -20 });
        s.dimV(0, -L, x0 - sp * 0.42, `L = ${m(L)}`, { off: -8 });
        if (n > show)
          s.textW(x0 + (show - 1) * sp + sp * 0.42, -L * 0.5, `… ${n} rods in all`,
            { size: 11, fill: p.ink2, halo: true });
        s.note('Parallel rods interfere with each other; the group resistance is '
          + 'higher than R_single/n. Spacing of at least twice the rod length keeps '
          + 'the coupling small.');
      }

      else if (t === 'strip') {
        const L = F('L') || 20, w = F('w') || 0.03;
        tape(s, -Wm / 2 + 0.4, Wm / 2 - 0.4, -burial, {});
        s.dimV(0, -burial, -Wm * 0.36, `h = ${m(burial)}`, { off: -8 });
        s.dimH(-Wm / 2 + 0.4, Wm / 2 - 0.4, -burial, `L = ${m(L)}`, { off: 30 });
        s.leader(Wm * 0.18, -burial, 40, -34,
          [`tape ${(w * 1000).toFixed(0)} mm wide`, 'laid in a trench, backfilled']);
        s.note('A horizontal electrode works the surface area of the trench; '
          + 'doubling its length roughly halves the resistance only while the '
          + 'trench stays short compared with the depth of the soil layer.');
      }

      else if (t === 'ring') {
        const r = F('radius') || 5;
        conductorDot(s, -r, -burial, F('d') || 0.01);
        conductorDot(s, r, -burial, F('d') || 0.01);
        s.dimH(-r, r, -burial, `2r = ${m(2 * r)}`, { off: 34 });
        s.dimV(0, -burial, -r, `h = ${m(burial)}`, { off: -16 });
        s.leader(-r, -burial, 26, 70,
          ['Ring electrode', 'the two marks are one ring, cut on both sides']);
        planInset(s, (cx, cy, R) => {
          s.push('front', `<circle cx="${cx}" cy="${cy}" r="${R}" fill="none"
            stroke="${p.copper}" stroke-width="2"/>`);
          s.push('front', `<line x1="${cx}" y1="${cy}" x2="${(cx + R).toFixed(1)}" y2="${cy}"
            stroke="${p.ink2}" stroke-width="1"/>`);
          s.push('front', `<circle cx="${cx}" cy="${cy}" r="1.8" fill="${p.ink2}"/>`);
          s.textPx(cx + R / 2, cy - 4, `r = ${m(r)}`,
            { anchor: 'middle', size: 10, fill: p.ink2, halo: true });
        }, 'plan');
        s.note('The ring is horizontal; the section cuts it twice, once on each '
          + 'side of the structure.');
      }

      else if (t === 'plate') {
        /* a vertical plate, seen edge-on, with its face shown dashed */
        const A = F('area') || 1, side = Math.sqrt(A);
        const zt = -burial, zb = -burial - side;
        s.rectW(-0.045, zb, 0.09, side, { fill: p.copper, rx: 1 }, 'mid');
        s.rectW(-side / 2, zb, side, side,
          { fill: 'none', stroke: p.copper, 'stroke-width': 1.6, 'stroke-dasharray': '4 3' }, 'mid');
        s.dimV(zt, zb, side / 2, m(side), { off: 30 });
        s.dimH(-side / 2, side / 2, zb, m(side), { off: 28 });
        s.dimV(0, zt, -side / 2, `h = ${m(burial)}`, { off: -18 });
        s.leader(0.05, zb + side * 0.72, 84, -34,
          [`Plate ${num(A, 2)} m²`, 'edge-on; both faces', 'are in contact']);
        s.note('The plate stands vertically. Its dashed outline is the face, '
          + 'seen edge-on in this section.');
      }

      else if (t === 'foundation') {
        const V = F('volume_m3') || F('volume') || 20;
        const side = Math.cbrt(V) * 1.5, thick = Math.max(0.4, V / (side * side));
        const zt = -burial, zb = -burial - thick;
        s.rectW(-side / 2, zb, side, thick,
          { fill: s.pattern('concrete', p.concrete), stroke: p.ink3, 'stroke-width': 1 }, 'mid');
        for (let i = 0; i <= 6; i++)
          s.lineW(-side / 2 + side * i / 6, zt - 0.06, -side / 2 + side * i / 6, zb + 0.06,
            { stroke: p.steel, 'stroke-width': 1.1, opacity: .85 }, 'mid');
        s.lineW(-side / 2 + .1, zt - thick * .35, side / 2 - .1, zt - thick * .35,
          { stroke: p.steel, 'stroke-width': 1.6 }, 'mid');
        s.lineW(0, zt, 0, top * 0.7, { stroke: p.copper, 'stroke-width': 2.6 }, 'mid');
        s.leader(0, top * 0.55, 60, -6, ['Bonding conductor', 'to the main earthing terminal']);
        s.dimH(-side / 2, side / 2, zb, `${m(side)}`, { off: 26 });
        s.note(`Concrete-encased (Ufer) electrode, ${num(V, 1)} m³ of foundation. `
          + 'The reinforcement must be electrically continuous and bonded.');
      }

      else if (t === 'mesh') {
        const A = F('area') || 100, side = Math.min(Math.sqrt(A), Wm - 1);
        tape(s, -side / 2, side / 2, -burial, {});
        for (let i = 0; i <= 6; i++) conductorDot(s, -side / 2 + side * i / 6, -burial, 0.012);
        s.dimH(-side / 2, side / 2, -burial, `${m(side)} across`, { off: 32 });
        s.dimV(0, -burial, -side * 0.58, `h = ${m(burial)}`, { off: -8 });
        s.leader(side * 0.22, -burial, 44, -32,
          ['Mesh conductors', 'seen end-on; the mesh', 'runs both ways']);
      }

      s.scalebar();
    });
  }

  /* ==================================================================== 3
     Substation earth grid — surface layer, burial depth, spacing, rods, and
     what touch and step voltage actually mean on the site. */
  function gridSection(hostId, g) {
    g = g || {};
    const D = g.D || 7, h = g.h || 0.5, hs = g.hs || 0.1;
    const Lr = g.Lr || 0, Lx = g.Lx || 70;
    const bays = Math.max(3, Math.min(5, Math.floor(Lx / D)));
    const Wm = bays * D;
    const Zb = Math.max(h + Lr + 1.2, 2.4);
    const top = 3.4;

    DRAW.scene(hostId, {
      width: 920, height: 460, equal: false,
      xmin: -D * 0.45, xmax: Wm + D * 0.45, ymin: -Zb, ymax: top,
      pad: { l: 74, r: 74, t: 32, b: 70 }
    }, s => {
      const p = s.p;
      s.title('Earth grid — section through the switchyard',
        `${bays} bays of the ${m(Lx)} grid shown`);
      s.bandPx(top, 0, { fill: p.sky });

      /* surface layer over native soil */
      s.stratum(0, -hs, {
        pattern: 'gravel', colour: p.gravel, line: true,
        label: `Surface layer   ρ_s = ${num(g.rhoS, 0)} Ω·m`, at: 0.015
      });
      s.stratum(-hs, -Zb, {
        pattern: 'soil', colour: p.soilA,
        label: `Native soil   ρ = ${num(g.rho, 0)} Ω·m`, at: 0.015, anchor: 'start'
      });
      s.groundLine(0);
      s.dimV(0, -hs, Wm + D * 0.40, `h_s = ${m(hs)}`, { off: 24 });

      /* grid conductors at burial depth */
      tape(s, -D * 0.38, Wm + D * 0.38, -h, {});
      for (let i = 0; i <= bays; i++) conductorDot(s, i * D, -h, g.d || 0.01);
      s.dimH(D, 2 * D, -h, `D = ${m(D)}`, { off: 30 });
      s.dimV(0, -h, -D * 0.38, `h = ${m(h)}`, { off: -12 });

      /* perimeter rods */
      if (Lr > 0 && (g.nRod || 0) > 0) {
        [0, Wm].forEach(x => rod(s, x, -h, Lr, g.dr || 0.016));
        s.dimV(-h, -h - Lr, Wm + D * 0.40, `L_r = ${m(Lr)}`, { off: 24 });
        s.leader(0, -h - Lr, 40, 20, [`${g.nRod} rods on the perimeter`]);
      }

      /* what the two safety criteria mean, on the site */
      const colX = D * 1.5;
      s.rectW(colX - 0.09, 0, 0.18, 2.6, { fill: p.steel, rx: 2 }, 'mid');
      s.rectW(colX - 0.5, 2.6, 1.0, 0.16, { fill: p.steel, rx: 2 }, 'mid');
      s.lineW(colX, 0, colX, -h, { stroke: p.copper, 'stroke-width': 2.2 }, 'mid');
      s.textW(colX, 2.95, 'earthed structure', { anchor: 'middle', size: 10.5, fill: p.ink2, halo: true });

      const aX = colX - 1.0;
      const a = person(s, aX, 0, { reach: 1.0, reachDir: 1 });
      measure(s, s.X(aX) - 22, a.handY, s.X(aX) - 22, a.groundY,
        `E_touch${isFinite(g.Em) ? ' = ' + num(g.Em, 0) + ' V' : ''}`, p.bad);
      s.textPx(s.X(aX) - 22, s.Y(top) + 14, 'touch — hand to feet, 1 m reach',
        { anchor: 'middle', size: 10, fill: p.ink3 });

      /* the step arrow is lifted clear of the ground hatching */
      const bX = D * 3.4;
      const b = person(s, bX, 0, { stride: 1.0 });
      const stepY = b.groundY - 9;
      measure(s, s.X(bX - 0.5), stepY, s.X(bX + 0.5), stepY,
        `E_step${isFinite(g.Es) ? ' = ' + num(g.Es, 0) + ' V' : ''}`, p.warn);
      s.textPx(s.X(bX), s.Y(top) + 14, 'step — 1 m stride, foot to foot',
        { anchor: 'middle', size: 10, fill: p.ink3 });

      if (isFinite(g.GPR))
        s.note(`Ground potential rise during the fault: GPR = ${num(g.GPR, 0)} V. `
          + 'Touch and step voltage are the fractions of that rise a person can bridge.');
      s.note('The surface layer raises the resistance in series with the feet, which is '
        + 'why it lifts the tolerable voltages without changing the grid itself.');
      s.legend([
        { label: 'grid conductor', fill: p.copper },
        { label: 'ground rod', fill: p.steel },
        { label: 'surface layer', fill: p.gravel, stroke: p.ink3 }
      ], { x: 920 - 74, y: 46 });
      s.scalebar();
    });
  }

  /* ==================================================================== 4
     The numerical model's electrodes, projected into the soil section. */
  function bemSection(hostId, items, soilModel) {
    items = items || [];
    soilModel = soilModel || {};
    let xlo = Infinity, xhi = -Infinity, deep = 0;
    const rods = [], horiz = [];
    const F = (o, k, dflt) => { const v = parseFloat(o[k]); return isFinite(v) ? v : dflt; };
    items.forEach(it => {
      const k = it.kind || it.type;
      if (k === 'rod') {
        const x = F(it, 'x', 0), ztop = -F(it, 'top_depth', 0.5), L = F(it, 'length', 3);
        rods.push({ x, ztop, L });
        xlo = Math.min(xlo, x - 1.5); xhi = Math.max(xhi, x + 1.5);
        deep = Math.max(deep, -ztop + L);
      } else if (k === 'grid' || k === 'rectangle') {
        const x0 = F(it, 'x0', 0), w = F(it, 'Lx', 10), z = -F(it, 'depth', 0.5);
        const nCond = k === 'grid' ? Math.max(2, Math.round(w / F(it, 'D', 7)) + 1) : 2;
        horiz.push({ x0, x1: x0 + w, z, n: Math.min(nCond, 14) });
        xlo = Math.min(xlo, x0 - 1); xhi = Math.max(xhi, x0 + w + 1);
        deep = Math.max(deep, -z);
      } else if (k === 'ring') {
        const cx = F(it, 'cx', 0), rr = F(it, 'r', 10), z = -F(it, 'depth', 0.6);
        horiz.push({ x0: cx - rr, x1: cx + rr, z, n: 2, dashed: true });
        xlo = Math.min(xlo, cx - rr - 1); xhi = Math.max(xhi, cx + rr + 1);
        deep = Math.max(deep, -z);
      } else if (k === 'conductor') {
        const p1 = it.p1 || [0, 0, 0.6], p2 = it.p2 || [20, 0, 0.6];
        const z = -((parseFloat(p1[2]) + parseFloat(p2[2])) / 2 || 0.6);
        const a = Math.min(parseFloat(p1[0]), parseFloat(p2[0]));
        const b = Math.max(parseFloat(p1[0]), parseFloat(p2[0]));
        horiz.push({ x0: a, x1: b, z, n: 4 });
        xlo = Math.min(xlo, a - 1); xhi = Math.max(xhi, b + 1);
        deep = Math.max(deep, -z);
      }
    });
    if (!isFinite(xlo)) { xlo = -6; xhi = 6; }
    if (xhi - xlo < 4) { xlo = -6; xhi = 6; }
    const h1 = parseFloat(soilModel.h1);
    const Zb = Math.max(deep * 1.6, (isFinite(h1) ? h1 * 1.5 : 0), 4);
    const span = xhi - xlo;
    const top = Zb * 0.14;

    DRAW.scene(hostId, {
      width: 900, height: 360, equal: false,
      xmin: xlo - span * 0.05, xmax: xhi + span * 0.05, ymin: -Zb, ymax: top
    }, s => {
      const p = s.p;
      s.title('Numerical model — electrodes in the soil section',
        isFinite(h1) ? 'two-layer earth' : 'uniform earth');
      s.bandPx(top, 0, { fill: p.sky });
      if (isFinite(h1) && h1 > 0 && h1 < Zb) {
        s.stratum(0, -h1, { pattern: 'soil', colour: p.soilA, at: 0.015, label: `ρ₁ = ${num(soilModel.rho1, 0)} Ω·m` });
        s.stratum(-h1, -Zb, { pattern: 'clay', colour: p.soilB, dash: '6 4', at: 0.015, label: `ρ₂ = ${num(soilModel.rho2, 0)} Ω·m` });
        s.dimV(0, -h1, s.x1 - span * 0.02, m(h1), { off: 24 });
      } else {
        s.stratum(0, -Zb, { pattern: 'soil', colour: p.soilA, at: 0.015, label: `ρ = ${num(soilModel.rho1, 0)} Ω·m` });
      }
      s.groundLine(0);
      horiz.forEach(hz => {
        if (hz.dashed) {
          s.lineW(hz.x0, hz.z, hz.x1, hz.z,
            { stroke: p.copper, 'stroke-width': 2, 'stroke-dasharray': '5 4' }, 'mid');
        } else {
          tape(s, hz.x0, hz.x1, hz.z, {});
        }
        for (let i = 0; i < hz.n; i++)
          conductorDot(s, hz.x0 + (hz.x1 - hz.x0) * i / Math.max(1, hz.n - 1), hz.z, 0.012);
      });
      rods.forEach(r => rod(s, r.x, r.ztop, r.L, 0.016));
      if (horiz.length) {
        const hz = horiz[0];
        s.dimV(0, hz.z, hz.x0, `h = ${m(-hz.z)}`, { off: -16 });
        s.dimH(hz.x0, hz.x1, hz.z, `${m(hz.x1 - hz.x0)}`, { off: 34 });
        if (isFinite(soilModel.IG))
          s.leader((hz.x0 + hz.x1) / 2, hz.z, 30, -46,
            [`I_G = ${num(soilModel.IG, 0)} A injected`]);
      } else if (rods.length && isFinite(soilModel.IG)) {
        s.leader(rods[0].x, rods[0].ztop, 34, -40,
          [`I_G = ${num(soilModel.IG, 0)} A injected`]);
      }
      s.note('The solver discretises this metal into segments held at one potential '
        + 'and solves for the leakage current of each; the section shows what it was given.');
      s.scalebar();
    });
  }

  /* ==================================================================== 5
     Rolling sphere — the elevation that shows what is actually protected. */
  function rollingSphere(hostId, r) {
    if (!r || !r.envelope) return;
    const R = r.R;
    const env = r.envelope;
    const st = r.structure || {};
    const terms = r.terminals || [];

    /* frame: the part of the section where something is protected, padded */
    let iLo = 0, iHi = env.x.length - 1;
    for (let i = 0; i < env.z.length; i++) if (env.z[i] > 1e-6) { iLo = i; break; }
    for (let i = env.z.length - 1; i >= 0; i--) if (env.z[i] > 1e-6) { iHi = i; break; }
    let xa = env.x[iLo], xb = env.x[iHi];
    if (st.width > 0) { xa = Math.min(xa, st.x0); xb = Math.max(xb, st.x1); }
    const pad0 = Math.max((xb - xa) * 0.10, R * 0.10);
    xa -= pad0; xb += pad0;
    const spanX = xb - xa;
    const topContent = Math.max(...terms.map(t => t.tip), st.height || 0, 1);
    const ymax = Math.max(topContent * 1.32, spanX / 2.35);
    const ymin = -ymax * 0.10;

    DRAW.scene(hostId, {
      width: 940, height: 470, equal: true,
      xmin: xa, xmax: xb, ymin, ymax,
      pad: { l: 56, r: 56, t: 32, b: 56 }
    }, s => {
      const p = s.p;
      s.title(`Rolling sphere — class ${r.lps_class}`, `R = ${m(R)}`);
      const clip = s.clip();
      /* the radius is only annotated on a sphere whose centre sits comfortably
         inside the sheet, so the dimension never runs off the edge */
      const inFrame = (X, Y) => X > s.P.l + 40 && X < s.W - s.P.r - 40
        && Y > s.P.t + 34 && Y < s.H - s.P.b - 20;

      s.bandPx(ymax, 0, { fill: p.sky });
      s.stratum(0, ymin, { pattern: 'soil', colour: p.soilA, line: false });
      s.groundLine(0);

      /* the protected volume */
      const pts = [];
      for (let i = 0; i < env.x.length; i++)
        if (env.x[i] >= xa - 1 && env.x[i] <= xb + 1) pts.push([env.x[i], env.z[i]]);
      if (pts.length) {
        const poly = [[pts[0][0], 0]].concat(pts, [[pts[pts.length - 1][0], 0]]);
        s.polyW(poly, { fill: p.zoneFill, stroke: 'none' }, 'back');
        const d = pts.map((q, i) => `${(i ? 'L' : 'M')} ${s.X(q[0]).toFixed(1)} ${s.Y(q[1]).toFixed(1)}`).join(' ');
        s.push('mid', `<path d="${d}" fill="none" stroke="${p.zoneEdge}" stroke-width="1.8"/>`);
      }

      /* the sphere in a few of the positions that generated that boundary */
      const g = [];
      (r.spheres || []).forEach(sp => {
        g.push(`<ellipse cx="${s.X(sp.cx).toFixed(1)}" cy="${s.Y(sp.cz).toFixed(1)}"
          rx="${s.dX(R).toFixed(1)}" ry="${s.dY(R).toFixed(1)}" fill="${p.sphere}"
          stroke="${p.sphereEdge}" stroke-width="1.1" stroke-dasharray="6 5"/>`);
        (sp.contacts || []).forEach(c => {
          g.push(`<circle cx="${s.X(c[0]).toFixed(1)}" cy="${s.Y(c[1]).toFixed(1)}" r="3.4"
            fill="${p.sphereEdge}" stroke="${p.panel}" stroke-width="1.2"/>`);
        });
      });
      s.push('mid', `<g clip-path="${clip}">${g.join('')}</g>`);

      /* The radius is drawn once, and only on a sphere whose centre is inside
         the frame — a radius line to an off-sheet centre reads as a stray
         diagonal rather than as a dimension. */
      const sp0 = (r.spheres || []).filter(sp =>
        inFrame(s.X(sp.cx), s.Y(sp.cz)) && (sp.contacts || []).length)
        .sort((u, v) => Math.abs(s.X(u.cx) - s.W / 2) - Math.abs(s.X(v.cx) - s.W / 2))[0];
      if (sp0) {
        const c = sp0.contacts[0];
        s.push('front', `<circle cx="${s.X(sp0.cx).toFixed(1)}" cy="${s.Y(sp0.cz).toFixed(1)}"
          r="2.4" fill="${p.sphereEdge}"/>`);
        s.push('front', `<line x1="${s.X(sp0.cx).toFixed(1)}" y1="${s.Y(sp0.cz).toFixed(1)}"
          x2="${s.X(c[0]).toFixed(1)}" y2="${s.Y(c[1]).toFixed(1)}"
          stroke="${p.sphereEdge}" stroke-width="1.3"/>`);
        const mx = (s.X(sp0.cx) + s.X(c[0])) / 2, my = (s.Y(sp0.cz) + s.Y(c[1])) / 2;
        s.textPx(mx + 7, my - 4, `R = ${m(R)}`,
          { size: 11.5, weight: 700, fill: p.sphereEdge, halo: true });
      }

      /* the structure — its width is dimensioned inside the wall so that it
         cannot collide with the span dimension above the roof */
      if (st.width > 0 && st.height > 0) {
        s.rectW(st.x0, 0, st.width, st.height,
          { fill: s.pattern('concrete', p.concrete), stroke: p.ink2, 'stroke-width': 1.3 }, 'mid');
        s.dimV(0, st.height, st.x0, `H = ${m(st.height)}`, { off: -26 });
        s.dimH(st.x0, st.x1, st.height * 0.28, `${m(st.width)}`, { off: 0, ext: false });
      }

      /* the air terminations */
      const spans = (r.spans || []).filter(sn => sn.sag != null);
      terms.forEach(t => {
        s.rectW(t.x - spanX * 0.0016, t.base, spanX * 0.0032, t.height,
          { fill: p.steel, rx: 1 }, 'mid');
        s.circleW(t.x, t.tip, 3.4, { fill: p.bad, stroke: p.panel, 'stroke-width': 1.2 }, 'mid');
        /* a rod too short to dimension legibly gets a leader instead */
        if (s.dY(t.height) > 26)
          s.dimV(t.base, t.tip, t.x + spanX * 0.010, m(t.height), { off: 18, ext: false });
      });
      const shortRods = terms.filter(t => t.height > 0 && s.dY(t.height) <= 26);
      if (shortRods.length)
        s.leader(shortRods[0].x, shortRods[0].tip, -56, -78,
          [`Air termination ${m(shortRods[0].height)}`,
            shortRods.length > 1 ? `\u00d7 ${shortRods.length} at this height` : '']
            .filter(Boolean));

      /* spans and the sag between them */
      spans.forEach(sn => {
        const midx = (sn.x0 + sn.x1) / 2;
        const tipz = Math.max.apply(null,
          terms.filter(t => t.x === sn.x0 || t.x === sn.x1).map(t => t.tip));
        s.lineW(sn.x0, tipz, sn.x1, tipz,
          { stroke: p.ink3, 'stroke-width': .9, 'stroke-dasharray': '4 4' }, 'mid');
        measure(s, s.X(midx), s.Y(tipz), s.X(midx), s.Y(sn.protected_height),
          `sag ${m(sn.sag)}`, p.warn);
        s.dimH(sn.x0, sn.x1, tipz, `${m(sn.d)}`, { off: -30 });
      });

      /* what is left exposed */
      const ex = (r.exposed || []).filter(e => e.what !== 'equipment');
      if (ex.length) {
        const xs = ex.map(e => e.x);
        const z = ex[0].z;
        const xa2 = Math.min.apply(null, xs), xb2 = Math.max.apply(null, xs);
        s.lineW(xa2, z, xb2, z,
          { stroke: p.riskEdge, 'stroke-width': 4, 'stroke-linecap': 'round', opacity: .9 }, 'mid');
        s.leader(xa2 + (xb2 - xa2) * 0.78, z, 62, -70,
          [ex[0].what === 'roof edge' ? 'Roof edge exposed' : 'Not protected',
          'the sphere reaches this surface'], { colour: p.riskEdge, fill: p.riskEdge });
      }
      (r.exposed || []).filter(e => e.what === 'equipment' || e.what === undefined).forEach(e => {
        s.circleW(e.x, e.z, 4.5, { fill: 'none', stroke: p.riskEdge, 'stroke-width': 2 }, 'mid');
      });

      s.legend([
        { label: 'protected volume', fill: p.zoneFill, stroke: p.zoneEdge },
        { label: `sphere R = ${m(R)}`, fill: 'none', stroke: p.sphereEdge, dash: '4 3' },
        { label: 'strike point', fill: p.bad },
        ex.length ? { label: 'exposed surface', fill: p.riskEdge } : null
      ], { x: 940 - 58, y: 44 });
      s.note('Everything the sphere can touch is a strike point; everything it '
        + 'cannot reach is protected. The boundary is the envelope of the sphere '
        + 'resting on the terminations and on the ground.');
      s.scalebar();
    });
  }

  /* ==================================================================== 6
     Protective angle — the cone form of the same result. */
  function protectiveAngle(hostId, r) {
    if (!r) return;
    const terms = (r.terminals || []).filter(t => t.above_reference > 0);
    const ref = r.reference_plane || 0;
    const t = terms.length ? terms.reduce((a, b) => b.height > a.height ? b : a) : null;
    const pa = t && t.protective_angle;

    const h = t ? Math.max(0.5, t.above_reference) : 5;
    const alpha = pa && pa.applicable ? pa.alpha : null;
    const rp = alpha ? h * Math.tan(alpha * Math.PI / 180) : (t ? t.r_protected : 0);
    const Wm = Math.max(rp * 2.4, h * 3.2);
    /* A true-scale cone is wide and shallow, so the sheet is cut to the drawing
       rather than the drawing stretched to a fixed sheet. */
    const PADL = 58, PADR = 58, PADT = 30, PADB = 104;
    const Ztop = h * 1.5;
    const Zbot = -Ztop * 0.10;
    const H = Math.max(210, Math.min(430,
      Math.round((900 - PADL - PADR) * (Ztop - Zbot) / Wm) + PADT + PADB));

    DRAW.scene(hostId, {
      width: 900, height: H, equal: true,
      xmin: -Wm / 2, xmax: Wm / 2, ymin: Zbot, ymax: Ztop,
      pad: { l: PADL, r: PADR, t: PADT, b: PADB }
    }, s => {
      const p = s.p;
      s.title(`Protective angle — class ${r.lps_class}`,
        [alpha ? `α = ${num(alpha, 1)}° at h = ${m(h)}` : 'not applicable at this height',
         ref > 0 ? `reference plane: roof at ${m(ref)}` : 'reference plane: ground level']
          .join('   ·   '));
      s.bandPx(Ztop, 0, { fill: p.sky });
      s.stratum(0, Zbot, { pattern: 'soil', colour: p.soilA, line: false });
      s.groundLine(0);

      if (!alpha) {
        s.textPx(s.W / 2, s.H / 2,
          `h = ${m(h)} exceeds the rolling sphere radius R = ${m(r.R)}; the protective angle method is not permitted here.`,
          { anchor: 'middle', size: 12.5, fill: p.warn, weight: 600 });
        s.note('Use the rolling sphere result instead — IEC 62305-3 Table 2.');
        return;
      }

      /* the cone */
      s.polyW([[0, h], [-rp, 0], [rp, 0]],
        { fill: p.zoneFill, stroke: p.zoneEdge, 'stroke-width': 1.6 }, 'mid');
      s.rectW(-Wm * 0.0022, 0, Wm * 0.0044, h, { fill: p.steel, rx: 1 }, 'mid');
      s.circleW(0, h, 3.6, { fill: p.bad, stroke: p.panel, 'stroke-width': 1.2 }, 'mid');
      s.lineW(0, h, 0, 0, { stroke: p.ink3, 'stroke-width': .9, 'stroke-dasharray': '4 4' }, 'mid');

      /* The angle is swept from the downward vertical to the edge of the cone,
         measured on the drawing itself so the arc always matches the geometry
         that was plotted. */
      const X = s.X(0), Y = s.Y(h);
      const rpx = Math.max(34, Math.min(78, s.dY(h) * 0.5));
      const a0 = Math.PI / 2;                                  // straight down
      const a1 = Math.atan2(s.Y(0) - Y, s.X(rp) - X);           // along the cone
      s.push('front', `<path d="M ${(X + rpx * Math.cos(a0)).toFixed(1)} ${(Y + rpx * Math.sin(a0)).toFixed(1)}
        A ${rpx.toFixed(1)} ${rpx.toFixed(1)} 0 0 1 ${(X + rpx * Math.cos(a1)).toFixed(1)}
        ${(Y + rpx * Math.sin(a1)).toFixed(1)}" fill="none" stroke="${p.accent}" stroke-width="1.5"/>`);
      const am = (a0 + a1) / 2;
      s.textPx(X + rpx * 1.30 * Math.cos(am), Y + rpx * 1.30 * Math.sin(am) + 4,
        `\u03b1 = ${num(alpha, 1)}\u00b0`,
        { anchor: 'middle', size: 12.5, weight: 700, fill: p.accent, halo: true });

      s.dimV(0, h, 0, `h = ${m(h)}`, { off: -Math.min(90, s.dX(rp * 0.5)) });
      s.dimH(0, rp, 0, `r = h·tan α = ${m(rp)}`, { off: 30 });
      if (isFinite(t.r_protected))
        s.note(`Rolling sphere gives ${m(t.r_protected)} for the same termination — `
          + (t.r_protected >= rp ? 'the angle method is the more conservative of the two here.'
            : 'the angle method is the less conservative here, so the rolling sphere governs.'));
      s.note('Valid only for simple shapes and only while h ≤ R. '
        + (r.protective_angle_source || ''));
      s.scalebar();
    });
  }

  /* ==================================================================== 7
     Plan view — how much of the protected plane the terminations cover. */
  function zonePlan(hostId, r) {
    if (!r || !r.plan) return;
    const pl = r.plan;
    const W = pl.width || 0, D = pl.depth || 0;
    /* the frame has to hold the circles, not just the building */
    const reach = pl.circles.reduce((mx, c) =>
      Math.max(mx, Math.abs(c.x) + c.r, Math.abs(c.y) + c.r), 0);
    const half = Math.max(W / 2, D / 2, reach) * 1.06 + 1;

    DRAW.scene(hostId, {
      width: 760, height: 430, equal: true,
      xmin: -half, xmax: half, ymin: -half, ymax: half
    }, s => {
      const p = s.p;
      s.title('Protected area — plan',
        pl.covered_fraction != null ? `${num(100 * pl.covered_fraction, 1)} % of the plane covered` : '');

      const clip = s.clip();
      const circ = pl.circles.filter(c => c.r > 0).map(c =>
        `<ellipse cx="${s.X(c.x).toFixed(1)}" cy="${s.Y(c.y).toFixed(1)}"
           rx="${s.dX(c.r).toFixed(1)}" ry="${s.dY(c.r).toFixed(1)}" fill="${p.zoneFill}"
           stroke="${p.zoneEdge}" stroke-width="1.4" stroke-dasharray="5 4"/>`).join('');
      s.push('back', `<g clip-path="${clip}">${circ}</g>`);
      if (W > 0 && D > 0) {
        s.rectW(-W / 2, -D / 2, W, D,
          { fill: 'none', stroke: p.ink, 'stroke-width': 1.8 }, 'mid');
        s.dimH(-W / 2, W / 2, D / 2, m(W), { off: -20 });
        s.dimV(-D / 2, D / 2, -W / 2, m(D), { off: -24 });
      }
      (pl.uncovered || []).forEach(u =>
        s.circleW(u[0], u[1], 1.8, { fill: p.riskEdge, opacity: .75 }, 'mid'));
      (pl.corners || []).forEach(c =>
        s.circleW(c.x, c.y, 4.5, {
          fill: c.protected ? 'none' : p.riskFill,
          stroke: c.protected ? p.zoneEdge : p.riskEdge, 'stroke-width': 2
        }, 'mid'));
      /* r_p is the same for every termination of the same height, so it is
         dimensioned once — repeating it four times only adds clutter. */
      let labelled = false;
      pl.circles.forEach(c => {
        s.circleW(c.x, c.y, 4, { fill: p.bad, stroke: p.panel, 'stroke-width': 1.2 }, 'mid');
        if (c.r > 0 && !labelled) {
          labelled = true;
          const ux = c.x <= 0 ? -0.707 : 0.707, uy = c.y <= 0 ? -0.707 : 0.707;
          s.lineW(c.x, c.y, c.x + c.r * ux, c.y + c.r * uy,
            { stroke: p.zoneEdge, 'stroke-width': 1.2 }, 'mid');
          s.textW(c.x + c.r * ux * 0.55, c.y + c.r * uy * 0.55, `r_p = ${m(c.r)}`,
            { dy: -5, size: 11, weight: 600, fill: p.zoneEdge, halo: true, anchor: 'middle' });
        }
      });
      s.legend([
        { label: 'protected circle', fill: p.zoneFill, stroke: p.zoneEdge, dash: '4 3' },
        { label: 'air termination', fill: p.bad },
        (pl.uncovered || []).length ? { label: 'not covered', fill: p.riskEdge } : null
      ], { x: 760 - 58, y: 42 });
      s.note('Each circle is the radius one termination protects on this plane. '
        + 'The plan checks coverage; the elevation decides compliance.');
      s.scalebar();
    });
  }

  /* ==================================================================== 8
     Mesh method — the conductor layout on a flat surface. */
  function meshPlan(hostId, r) {
    if (!r || !r.mesh) return;
    const ms = r.mesh;
    const W = (r.structure && r.structure.width) || 0;
    const D = (r.structure && r.structure.depth) || 0;
    if (!(W > 0 && D > 0)) return;
    const half = Math.max(W, D) * 0.62;

    DRAW.scene(hostId, {
      width: 760, height: 420, equal: true,
      xmin: -half, xmax: half, ymin: -half * D / Math.max(W, D) - 2, ymax: half * D / Math.max(W, D) + 2
    }, s => {
      const p = s.p;
      s.title(`Mesh air termination — class ${r.lps_class}`,
        `mesh ${m(ms.mesh_required)} × ${m(ms.mesh_required)}`);
      s.rectW(-W / 2, -D / 2, W, D,
        { fill: p.panel, stroke: p.ink, 'stroke-width': 1.8, opacity: .9 }, 'back');
      for (let i = 0; i < ms.conductors_x; i++) {
        const x = -W / 2 + ms.actual_spacing_x * i;
        s.lineW(x, -D / 2, x, D / 2, { stroke: p.copper, 'stroke-width': 1.7 }, 'mid');
      }
      for (let j = 0; j < ms.conductors_y; j++) {
        const y = -D / 2 + ms.actual_spacing_y * j;
        s.lineW(-W / 2, y, W / 2, y, { stroke: p.copper, 'stroke-width': 1.7 }, 'mid');
      }
      s.dimH(-W / 2, -W / 2 + ms.actual_spacing_x, D / 2, m(ms.actual_spacing_x), { off: -20 });
      s.dimV(-D / 2, -D / 2 + ms.actual_spacing_y, -W / 2, m(ms.actual_spacing_y), { off: -24 });

      /* down-conductors round the perimeter */
      const per = 2 * (W + D), n = ms.n_down, step = per / n;
      for (let k = 0; k < n; k++) {
        let d = k * step, x, y;
        if (d < W) { x = -W / 2 + d; y = -D / 2; }
        else if (d < W + D) { x = W / 2; y = -D / 2 + (d - W); }
        else if (d < 2 * W + D) { x = W / 2 - (d - W - D); y = D / 2; }
        else { x = -W / 2; y = D / 2 - (d - 2 * W - D); }
        s.circleW(x, y, 4, { fill: p.accent, stroke: p.panel, 'stroke-width': 1.2 }, 'mid');
      }
      [[-W / 2, -D / 2], [W / 2, -D / 2], [W / 2, D / 2], [-W / 2, D / 2]].forEach(c =>
        s.circleW(c[0], c[1], 5, { fill: p.bad, stroke: p.panel, 'stroke-width': 1.3 }, 'mid'));

      s.legend([
        { label: 'mesh conductor', fill: p.copper },
        { label: `down-conductor (${n})`, fill: p.accent },
        { label: 'corner termination', fill: p.bad }
      ], { x: 760 - 58, y: 42 });
      s.note(`Total mesh conductor ≈ ${num(ms.total_length, 0)} m; down-conductors at `
        + `${m(ms.actual_down_spacing || 0)} against a typical ${m(ms.down_spacing)} for this class.`);
      s.scalebar();
    });
  }

  /* ==================================================================== 9
     Effective area under the lightning impulse — plan.

     The whole point of the picture is the difference between the electrode
     you paid for and the part of it that is carrying current while the
     front is still rising, so both are drawn to the same scale on the same
     sheet and dimensioned against each other. */
  function impulsePlan(hostId, r) {
    const imp = r && r.impulse;
    if (!imp) return;
    const rg = imp.r_geometric || 0;
    if (!(rg > 0)) return;

    const ar = imp.area;
    const models = (ar && ar.models) ? ar.models.slice() : [];
    /* injection at the centre, or out at the edge of the electrode.
       "centre" and "corner" share a first letter, so test the whole word. */
    const inj = String(imp.injection || 'centre').trim().toLowerCase();
    const edge = !(inj === 'centre' || inj === 'center' || inj === 'middle');
    const ix = edge ? -rg * 0.70 : 0, iy = edge ? -rg * 0.70 : 0;
    const half = rg * 1.20 + 2;

    DRAW.scene(hostId, {
      width: 760, height: 430, equal: true,
      xmin: -half, xmax: half, ymin: -half, ymax: half
    }, s => {
      const p = s.p;
      s.title('Effective area under the impulse — plan',
        `${num(imp.T, 2)} µs front in ${num(imp.rho, 0)} Ω·m soil, `
        + (edge ? 'injected at the edge' : 'injected at the centre'));

      /* the electrode itself */
      s.circleM(0, 0, rg, {
        fill: 'none', stroke: p.ink2, 'stroke-width': 1.6, 'stroke-dasharray': '7 5'
      }, 'mid');
      if (ar && ar.spacing > 0) {
        const g = [], sp = ar.spacing;
        for (let x = -rg; x <= rg + 1e-9; x += sp) {
          const h = Math.sqrt(Math.max(0, rg * rg - x * x));
          if (h < sp * 0.2) continue;
          g.push(`<line x1="${s.X(x).toFixed(1)}" y1="${s.Y(-h).toFixed(1)}"
                        x2="${s.X(x).toFixed(1)}" y2="${s.Y(h).toFixed(1)}"
                        stroke="${p.copper}" stroke-width=".9" opacity=".55"/>`);
          g.push(`<line x1="${s.X(-h).toFixed(1)}" y1="${s.Y(x).toFixed(1)}"
                        x2="${s.X(h).toFixed(1)}" y2="${s.Y(x).toFixed(1)}"
                        stroke="${p.copper}" stroke-width=".9" opacity=".55"/>`);
        }
        s.push('back', `<g opacity=".8">${g.join('')}</g>`);
      }

      /* the participating disc, smallest estimate shaded */
      const sorted = models.slice().sort((a, b) => a.r - b.r);
      const rmin = sorted.length ? sorted[0].r : imp.r_effective;
      s.circleM(ix, iy, rmin, {
        fill: p.zoneFill, stroke: p.zoneEdge, 'stroke-width': 1.8
      }, 'back');
      sorted.slice(1).forEach(mo => s.circleM(ix, iy, mo.r, {
        fill: 'none', stroke: p.zoneEdge, 'stroke-width': 1.1,
        'stroke-dasharray': '4 4', opacity: .8
      }, 'mid'));

      /* where the stroke current enters */
      const IX = s.X(ix), IY = s.Y(iy), bolt = 15;
      s.push('front', `<path d="M${(IX - 5).toFixed(1)},${(IY - bolt * 1.7).toFixed(1)}
        l9,0 l-5,${(bolt * .72).toFixed(1)} l7,0 l-13,${bolt.toFixed(1)} l3.5,-${(bolt * .62).toFixed(1)}
        l-6,0 Z" fill="${p.bad}" stroke="${p.panel}" stroke-width=".8"/>`);
      s.circleW(ix, iy, 4.5, { fill: p.bad, stroke: p.panel, 'stroke-width': 1.3 }, 'front');

      /* Labels: what was built, and what is working.  The leaders are aimed
         away from the shaded disc so that nothing is written over it. */
      s.leader(rg * 0.707, -rg * 0.707, 26, 22,
        ['earthing system, ' + m(rg) + ' radius',
         'all of it works at 50 Hz'], { fill: p.ink2 });
      const away = edge ? -1 : 1;               // point the labels off-centre
      sorted.forEach((mo, i) => {
        if (i > 1) return;                      // two labels is enough
        const ang = i === 0 ? Math.PI * 0.75 * away : Math.PI * 1.25 * away;
        s.leader(ix + mo.r * Math.cos(ang), iy + mo.r * Math.sin(ang),
          Math.cos(ang) < 0 ? -46 : 46, Math.sin(ang) > 0 ? -22 : 22,
          [mo.name + ' — r_eff ' + m(mo.r),
           num(100 * mo.fraction, 0) + ' % of the area works'],
          { fill: p.zoneEdge });
      });

      s.legend([
        { label: 'earthing system', stroke: p.ink2, dash: '7 5', fill: 'none' },
        { label: 'effective area', fill: p.zoneFill, stroke: p.zoneEdge },
        { label: 'other estimates', stroke: p.zoneEdge, dash: '4 4', fill: 'none' },
        { label: 'stroke injected here', fill: p.bad }
      ], { x: 760 - 58, y: 42 });
      s.note(ar
        ? `Shaded: the smallest of three published estimates, which disagree by a factor `
          + `of ${num(ar.spread, 1)}. Take it as the design case.`
        : `Without a conductor spacing only the effective length is available: the front `
          + `reaches ${m(imp.linear.L_eff)} along a buried conductor here.`);
      s.scalebar();
    });
  }

  return {
    fourPin, soil, electrode, gridSection, bemSection,
    rollingSphere, protectiveAngle, zonePlan, meshPlan, impulsePlan
  };
})();
