/* EarthSystem — scale engineering drawings in inline SVG.
 *
 * A small drawing library, not a chart library.  Everything is set out in
 * metres and projected onto the page, so a section drawn here can be measured
 * off the screen with the scale bar the same way a drawing on paper can.
 *
 * Why SVG and not Plotly: a section needs hatched strata, dimension lines with
 * extension lines and arrowheads, leaders, material textures and a scale bar.
 * Those are drawing primitives, not plot primitives.
 *
 * Colours are read from the interface CSS variables when the drawing is built,
 * and every scene is registered so that it can be rebuilt when the user
 * switches between the light and dark themes.
 *
 * Public surface
 * --------------
 *   DRAW.scene(hostId, opts, build)   build (or rebuild) a drawing
 *   DRAW.redrawAll()                  called on a theme change
 *   DRAW.toPNG(hostId, scale)         Promise<data URL> for the design report
 *   DRAW.clear(hostId)
 */
'use strict';

window.DRAW = (function () {

  const SCENES = {};          // hostId -> rebuild function
  let UID = 0;                // unique ids for pattern / marker defs

  /* ------------------------------------------------------------- palette */
  function cssv(name, fallback) {
    const s = getComputedStyle(document.body).getPropertyValue(name).trim();
    return s || fallback;
  }

  function palette() {
    const dark = document.body.dataset.theme === 'dark';
    return {
      dark,
      ink:      cssv('--ink', '#1a2027'),
      ink2:     cssv('--ink-2', '#5a6773'),
      ink3:     cssv('--ink-3', '#8b98a5'),
      line:     cssv('--line', '#d8e0e7'),
      accent:   cssv('--accent', '#0f6b8a'),
      ok:       cssv('--ok', '#0b7a45'),
      bad:      cssv('--bad', '#c0322b'),
      warn:     cssv('--warn', '#a8630a'),
      panel:    cssv('--panel', '#ffffff'),

      // drawing-specific colours, kept out of the interface variables
      sky:      dark ? '#151c23' : '#eff5fa',
      skyEdge:  dark ? '#1d2831' : '#dde8f1',
      soilA:    dark ? '#3b3125' : '#e9dcc4',   // upper stratum
      soilB:    dark ? '#2c313a' : '#d4dbe4',   // lower stratum
      soilC:    dark ? '#232a31' : '#c3ccd5',   // third stratum / bedrock
      gravel:   dark ? '#414952' : '#e2e7ec',   // surface layer
      concrete: dark ? '#353c44' : '#e7e9eb',
      water:    dark ? '#1e4a5c' : '#cfe6f2',
      copper:   dark ? '#cf8f4f' : '#a85a1a',
      steel:    dark ? '#a9b8c5' : '#5f6e7a',
      zinc:     dark ? '#9aa8b4' : '#8794a0',
      zoneFill: dark ? 'rgba(78,208,138,.15)' : 'rgba(11,122,69,.11)',
      zoneEdge: dark ? '#4ed08a' : '#0b7a45',
      riskFill: dark ? 'rgba(241,129,121,.16)' : 'rgba(192,50,43,.10)',
      riskEdge: dark ? '#f18179' : '#c0322b',
      sphere:   dark ? 'rgba(75,182,216,.10)' : 'rgba(15,107,138,.07)',
      sphereEdge: dark ? '#4bb6d8' : '#0f6b8a'
    };
  }

  const esc = s => String(s == null ? '' : s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;')
    .replace(/>/g, '&gt;').replace(/"/g, '&quot;');

  const attrs = o => Object.entries(o || {})
    .filter(([, v]) => v !== undefined && v !== null && v !== '')
    .map(([k, v]) => `${k}="${typeof v === 'number' ? round(v) : esc(v)}"`).join(' ');

  const round = n => Math.round(n * 100) / 100;

  /* Metric label with a sensible number of digits for a drawing. */
  function m(x, unit) {
    const a = Math.abs(x);
    let s;
    if (a >= 100) s = x.toFixed(0);
    else if (a >= 10) s = x.toFixed(1);
    else if (a >= 1) s = x.toFixed(2).replace(/0$/, '').replace(/\.$/, '');
    else s = x.toFixed(3).replace(/0+$/, '').replace(/\.$/, '');
    return unit === false ? s : s + ' ' + (unit || 'm');
  }

  /* ================================================================ Scene */
  function Scene(o) {
    o = o || {};
    this.p = palette();
    this.id = 'd' + (++UID);
    this.W = o.width || 920;
    this.H = o.height || 430;
    this.P = Object.assign({ l: 58, r: 58, t: 30, b: 66 }, o.pad || {});
    this.x0 = o.xmin; this.x1 = o.xmax;
    this.y0 = o.ymin; this.y1 = o.ymax;
    this.aw = this.W - this.P.l - this.P.r;
    this.ah = this.H - this.P.t - this.P.b;

    let sx = this.aw / (this.x1 - this.x0);
    let sy = this.ah / (this.y1 - this.y0);
    this.equal = o.equal !== false;
    if (this.equal) { const s = Math.min(sx, sy); sx = s; sy = s; }
    this.sx = sx; this.sy = sy;
    this.exag = sy / sx;

    this.ox = this.P.l + (this.aw - (this.x1 - this.x0) * sx) / 2;
    this.oy = this.P.t + (this.ah - (this.y1 - this.y0) * sy) / 2;

    this.back = [];     // strata and fills
    this.mid = [];      // the objects being drawn
    this.front = [];    // dimensions, leaders, labels
    this.defs = [];
    this.patterns = {};
    this.legendItems = [];
    this.notes = [];
    this.titleText = o.title || '';
  }

  Scene.prototype.X = function (x) { return this.ox + (x - this.x0) * this.sx; };
  Scene.prototype.Y = function (y) { return this.oy + (this.y1 - y) * this.sy; };
  Scene.prototype.dX = function (dx) { return dx * this.sx; };
  Scene.prototype.dY = function (dy) { return dy * this.sy; };
  /* inverse — used for hit boxes and for laying out labels in world units */
  Scene.prototype.iX = function (px) { return this.x0 + (px - this.ox) / this.sx; };
  Scene.prototype.iY = function (py) { return this.y1 - (py - this.oy) / this.sy; };

  Scene.prototype.push = function (layer, s) { this[layer].push(s); return this; };

  /* ------------------------------------------------------------ patterns */
  /* kind: soil | clay | sand | rock | gravel | concrete | water | fill */
  Scene.prototype.pattern = function (kind, colour) {
    const key = kind + '|' + colour;
    if (this.patterns[key]) return this.patterns[key];
    const pid = `${this.id}-p${Object.keys(this.patterns).length}`;
    const ink = this.p.ink3;
    let body = '';
    switch (kind) {
      case 'clay':      // close diagonal ruling
        body = `<path d="M0,8 L8,0 M-2,2 L2,-2 M6,10 L10,6" stroke="${ink}" stroke-width=".7" opacity=".55"/>`;
        break;
      case 'sand':      // stippling
        body = `<circle cx="2" cy="2" r=".8" fill="${ink}" opacity=".5"/>
                <circle cx="6" cy="5" r=".7" fill="${ink}" opacity=".45"/>
                <circle cx="4" cy="8" r=".6" fill="${ink}" opacity=".4"/>`;
        break;
      case 'rock':      // broken triangles, the usual bedrock symbol
        body = `<path d="M1,9 L4,3 L7,9 Z M8,5 L10,1 L12,5 Z" fill="none"
                 stroke="${ink}" stroke-width=".75" opacity=".55"/>`;
        break;
      case 'gravel':    // rounded aggregate
        body = `<circle cx="3" cy="3" r="1.7" fill="none" stroke="${ink}" stroke-width=".8" opacity=".6"/>
                <circle cx="8" cy="7" r="1.3" fill="none" stroke="${ink}" stroke-width=".8" opacity=".6"/>
                <circle cx="9" cy="2" r="1" fill="none" stroke="${ink}" stroke-width=".7" opacity=".5"/>
                <circle cx="2" cy="8" r="1.1" fill="none" stroke="${ink}" stroke-width=".7" opacity=".5"/>`;
        break;
      case 'concrete':  // stipple plus short dashes
        body = `<circle cx="2" cy="3" r=".7" fill="${ink}" opacity=".5"/>
                <circle cx="7" cy="7" r=".6" fill="${ink}" opacity=".45"/>
                <path d="M4,2 l3,1 M1,8 l2.5,-.8" stroke="${ink}" stroke-width=".7" opacity=".45"/>`;
        break;
      case 'water':
        body = `<path d="M0,5 q2.5,-2.5 5,0 t5,0" fill="none" stroke="${ink}" stroke-width=".7" opacity=".5"/>`;
        break;
      case 'fill':      // 45 degree section hatch
        body = `<path d="M-1,3 L3,-1 M0,8 L8,0 M5,9 L9,5" stroke="${ink}" stroke-width=".8" opacity=".5"/>`;
        break;
      default:          // topsoil — sparse ticks
        body = `<path d="M1,7 l1.4,-2 M5,4 l1.4,-2 M7,9 l1.2,-1.8" stroke="${ink}"
                 stroke-width=".8" opacity=".45"/>
                <circle cx="4" cy="7" r=".55" fill="${ink}" opacity=".4"/>`;
    }
    const size = kind === 'rock' ? 13 : 10;
    this.defs.push(`<pattern id="${pid}" width="${size}" height="${size}"
      patternUnits="userSpaceOnUse"><rect width="${size}" height="${size}" fill="${colour}"/>${body}</pattern>`);
    this.patterns[key] = `url(#${pid})`;
    return this.patterns[key];
  };

  Scene.prototype.arrowDefs = function () {
    if (this._arrows) return;
    this._arrows = true;
    const c = this.p.ink2;
    this.defs.push(
      `<marker id="${this.id}-ar" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7"
        markerHeight="7" orient="auto-start-reverse"><path d="M0,1 L10,5 L0,9 z" fill="${c}"/></marker>`,
      `<marker id="${this.id}-arS" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="5.5"
        markerHeight="5.5" orient="auto-start-reverse"><path d="M0,1.5 L10,5 L0,8.5 z" fill="${c}"/></marker>`,
      `<marker id="${this.id}-dot" viewBox="0 0 6 6" refX="3" refY="3" markerWidth="4"
        markerHeight="4"><circle cx="3" cy="3" r="2.4" fill="${c}"/></marker>`);
  };

  /* --------------------------------------------------------- primitives  */
  Scene.prototype.rectW = function (x, y, w, h, a, layer) {
    return this.push(layer || 'mid', `<rect ${attrs(Object.assign({
      x: this.X(x), y: this.Y(y + h), width: this.dX(w), height: this.dY(h)
    }, a))}/>`);
  };
  Scene.prototype.rectPx = function (x, y, w, h, a, layer) {
    return this.push(layer || 'mid',
      `<rect ${attrs(Object.assign({ x, y, width: w, height: h }, a))}/>`);
  };
  Scene.prototype.lineW = function (x1, y1, x2, y2, a, layer) {
    return this.push(layer || 'mid', `<line ${attrs(Object.assign({
      x1: this.X(x1), y1: this.Y(y1), x2: this.X(x2), y2: this.Y(y2)
    }, a))}/>`);
  };
  Scene.prototype.linePx = function (x1, y1, x2, y2, a, layer) {
    return this.push(layer || 'front', `<line ${attrs(Object.assign({ x1, y1, x2, y2 }, a))}/>`);
  };
  Scene.prototype.circleW = function (x, y, rPx, a, layer) {
    return this.push(layer || 'mid',
      `<circle ${attrs(Object.assign({ cx: this.X(x), cy: this.Y(y), r: rPx }, a))}/>`);
  };
  /* a circle whose radius is given in metres (a rolling sphere, a ring) */
  Scene.prototype.circleM = function (x, y, rM, a, layer) {
    return this.push(layer || 'mid', `<ellipse ${attrs(Object.assign({
      cx: this.X(x), cy: this.Y(y), rx: this.dX(rM), ry: this.dY(rM)
    }, a))}/>`);
  };
  Scene.prototype.polyW = function (pts, a, layer) {
    const d = pts.map(p => `${round(this.X(p[0]))},${round(this.Y(p[1]))}`).join(' ');
    return this.push(layer || 'mid', `<polygon ${attrs(Object.assign({ points: d }, a))}/>`);
  };
  Scene.prototype.pathW = function (cmds, a, layer) {
    /* cmds: array of ['M'|'L', x, y] or ['A', rx, ry, rot, large, sweep, x, y] */
    const d = cmds.map(c => {
      if (c[0] === 'A') return `A ${round(this.dX(c[1]))} ${round(this.dY(c[2]))} ${c[3]} ${c[4]} ${c[5]} ${round(this.X(c[6]))} ${round(this.Y(c[7]))}`;
      if (c[0] === 'Z') return 'Z';
      return `${c[0]} ${round(this.X(c[1]))} ${round(this.Y(c[2]))}`;
    }).join(' ');
    return this.push(layer || 'mid', `<path ${attrs(Object.assign({ d }, a))}/>`);
  };
  Scene.prototype.textPx = function (x, y, s, o) {
    o = o || {};
    const a = {
      x, y, 'text-anchor': o.anchor || 'start',
      'font-size': o.size || 11.5,
      'font-weight': o.weight || 400,
      fill: o.fill || this.p.ink2,
      'font-family': o.mono ? 'JetBrains Mono, Consolas, monospace' : 'Segoe UI, Inter, sans-serif',
      opacity: o.opacity
    };
    let inner = esc(s);
    if (o.halo) {
      /* a soft halo keeps a label readable over hatching */
      const h = `<text ${attrs(Object.assign({}, a, { stroke: this.p.panel, 'stroke-width': 3.2, 'stroke-linejoin': 'round', opacity: .85 }))}>${inner}</text>`;
      return this.push(o.layer || 'front', h + `<text ${attrs(a)}>${inner}</text>`);
    }
    return this.push(o.layer || 'front', `<text ${attrs(a)}>${inner}</text>`);
  };
  Scene.prototype.textW = function (x, y, s, o) {
    o = o || {};
    return this.textPx(this.X(x) + (o.dx || 0), this.Y(y) + (o.dy || 0), s, o);
  };

  /* ------------------------------------------------------------ ground   */
  /* The ground line: a heavy line with the usual short hatch below it. */
  Scene.prototype.groundLine = function (y, x0, x1, o) {
    o = o || {};
    const Y = this.Y(y);
    const A = x0 == null ? this.P.l : this.X(x0);
    const B = x1 == null ? this.W - this.P.r : this.X(x1);
    this.linePx(A, Y, B, Y, {
      stroke: o.colour || this.p.ink, 'stroke-width': o.width || 1.8
    }, 'mid');
    if (o.ticks !== false) {
      const step = 9, len = 6;
      let s = '';
      for (let x = A; x < B - 2; x += step) s += `M${round(x)},${round(Y)} l${-len * .7},${len}`;
      this.push('mid', `<path d="${s}" stroke="${this.p.ink3}" stroke-width=".9" opacity=".8" fill="none"/>`);
    }
    return this;
  };

  /* A band running the full width of the sheet between two levels.  Equal-scale
     sections rarely fill the frame exactly, and a stratum that stopped at the
     region of interest would look like a floating block rather than ground. */
  Scene.prototype.bandPx = function (yTop, yBot, a, layer) {
    const x = this.P.l, w = this.W - this.P.l - this.P.r;
    const y = this.Y(yTop), h = this.Y(yBot) - this.Y(yTop);
    return this.push(layer || 'back',
      `<rect ${attrs(Object.assign({ x, y, width: w, height: Math.max(0, h) }, a))}/>`);
  };

  /* A horizontal stratum between two depths, hatched and labelled. */
  Scene.prototype.stratum = function (yTop, yBot, o) {
    o = o || {};
    const fillCol = o.colour || this.p.soilA;
    const fill = o.pattern === false ? fillCol : this.pattern(o.pattern || 'soil', fillCol);
    this.bandPx(yTop, yBot, { fill, stroke: o.stroke || 'none' }, 'back');
    if (o.line !== false)
      this.linePx(this.P.l, this.Y(yTop), this.W - this.P.r, this.Y(yTop),
        { stroke: this.p.ink2, 'stroke-width': 1.1, 'stroke-dasharray': o.dash || '' }, 'back');
    if (o.label) {
      const bandPx = Math.abs(this.dY(yTop - yBot));
      const x = o.labelX != null ? o.labelX : this.x0 + (this.x1 - this.x0) * (o.at || 0.03);
      const anchor = o.anchor || 'start';
      /* A thin stratum has no room for a caption inside it, so the caption is
         floated just above the band — where a draughtsman would put it. */
      if (bandPx < 34) {
        const Y = this.Y(yTop) - 7;
        if (o.sub) {
          this.textPx(this.X(x), Y - 13, o.label,
            { anchor, size: 11.5, weight: 600, fill: this.p.ink, halo: true });
          this.textPx(this.X(x), Y, o.sub,
            { anchor, size: 10.5, fill: this.p.ink2, halo: true });
        } else {
          this.textPx(this.X(x), Y, o.label,
            { anchor, size: 11.5, weight: 600, fill: this.p.ink, halo: true });
        }
      } else {
        const yc = (yTop + yBot) / 2;
        this.textW(x, yc, o.label, {
          anchor, size: 12, weight: 600, fill: this.p.ink, halo: true, dy: 0
        });
        if (o.sub) this.textW(x, yc, o.sub, {
          anchor, size: 10.5, fill: this.p.ink2, halo: true, dy: 14
        });
      }
    }
    return this;
  };

  /* ---------------------------------------------------------- dimensions */
  /* Horizontal dimension between two world x at world y, offset in pixels. */
  Scene.prototype.dimH = function (xa, xb, y, label, o) {
    o = o || {};
    this.arrowDefs();
    const off = o.off == null ? -22 : o.off;          // negative = above
    const A = this.X(xa), B = this.X(xb), Y0 = this.Y(y), Y = Y0 + off;
    const c = this.p.ink2;
    const ext = o.ext === false ? 0 : 1;
    if (ext) {
      this.linePx(A, Y0, A, Y + (off < 0 ? -4 : 4), { stroke: c, 'stroke-width': .7, opacity: .75 });
      this.linePx(B, Y0, B, Y + (off < 0 ? -4 : 4), { stroke: c, 'stroke-width': .7, opacity: .75 });
    }
    const narrow = Math.abs(B - A) < 30;
    this.linePx(narrow ? A - 12 : A, Y, narrow ? B + 12 : B, Y, {
      stroke: c, 'stroke-width': .9,
      'marker-start': `url(#${this.id}-ar${narrow ? '' : ''})`,
      'marker-end': `url(#${this.id}-ar)`
    });
    if (label !== false)
      this.textPx((A + B) / 2, Y - 5, label == null ? m(Math.abs(xb - xa)) : label,
        { anchor: 'middle', size: 11, fill: this.p.ink, halo: true, weight: 500 });
    return this;
  };

  /* Vertical dimension between two world y at world x, offset in pixels. */
  Scene.prototype.dimV = function (ya, yb, x, label, o) {
    o = o || {};
    this.arrowDefs();
    const off = o.off == null ? -26 : o.off;          // negative = to the left
    const X0 = this.X(x), X = X0 + off, A = this.Y(ya), B = this.Y(yb);
    const c = this.p.ink2;
    if (o.ext !== false) {
      this.linePx(X0, A, X + (off < 0 ? -4 : 4), A, { stroke: c, 'stroke-width': .7, opacity: .75 });
      this.linePx(X0, B, X + (off < 0 ? -4 : 4), B, { stroke: c, 'stroke-width': .7, opacity: .75 });
    }
    this.linePx(X, A, X, B, {
      stroke: c, 'stroke-width': .9,
      'marker-start': `url(#${this.id}-ar)`, 'marker-end': `url(#${this.id}-ar)`
    });
    const txt = label == null ? m(Math.abs(yb - ya)) : label;
    if (label !== false) {
      const my = (A + B) / 2;
      this.push('front', `<g transform="translate(${round(X - 5)},${round(my)}) rotate(-90)">` +
        `<text text-anchor="middle" font-size="11" font-weight="500" font-family="Segoe UI,Inter,sans-serif"
          stroke="${this.p.panel}" stroke-width="3.2" stroke-linejoin="round" opacity=".85">${esc(txt)}</text>` +
        `<text text-anchor="middle" font-size="11" font-weight="500" font-family="Segoe UI,Inter,sans-serif"
          fill="${this.p.ink}">${esc(txt)}</text></g>`);
    }
    return this;
  };

  /* A leader: a short kinked line from a feature to a label. */
  Scene.prototype.leader = function (xw, yw, dxPx, dyPx, label, o) {
    o = o || {};
    this.arrowDefs();
    const X = this.X(xw), Y = this.Y(yw);
    const ex = X + dxPx, ey = Y + dyPx;
    const tail = dxPx >= 0 ? 13 : -13;
    const c = o.colour || this.p.ink2;
    this.push('front', `<path d="M${round(X)},${round(Y)} L${round(ex)},${round(ey)} l${tail},0"
      fill="none" stroke="${c}" stroke-width=".9" marker-start="url(#${this.id}-dot)"/>`);
    const lines = Array.isArray(label) ? label : [label];
    lines.forEach((L, i) => this.textPx(ex + tail + (dxPx >= 0 ? 4 : -4), ey + 4 + i * 13, L, {
      anchor: dxPx >= 0 ? 'start' : 'end', size: o.size || 11,
      fill: i ? this.p.ink2 : (o.fill || this.p.ink), weight: i ? 400 : 500, halo: true
    }));
    return this;
  };

  /* --------------------------------------------------------- furniture   */
  Scene.prototype.scalebar = function (o) {
    o = o || {};
    const span = this.x1 - this.x0;
    const nice = [.1, .2, .25, .5, 1, 2, 2.5, 5, 10, 20, 25, 50, 100, 200, 250, 500, 1000];
    let L = nice.reduce((b, v) => Math.abs(v - span / 5) < Math.abs(b - span / 5) ? v : b, 1);
    const px = this.dX(L);
    const x = o.x != null ? o.x : this.P.l;
    const y = o.y != null ? o.y : this.H - 16;
    const c = this.p.ink2;
    let s = `<g><line x1="${round(x)}" y1="${round(y)}" x2="${round(x + px)}" y2="${round(y)}" stroke="${c}" stroke-width="1.2"/>`;
    for (let i = 0; i <= 4; i++) {
      const xx = x + px * i / 4;
      s += `<line x1="${round(xx)}" y1="${round(y - 4)}" x2="${round(xx)}" y2="${round(y + 4)}" stroke="${c}" stroke-width="1"/>`;
      if (i % 2 === 0) s += `<rect x="${round(x + px * i / 4)}" y="${round(y - 3.5)}" width="${round(px / 4)}" height="3.5" fill="${c}" opacity=".55"/>`;
    }
    s += `<text x="${round(x + px + 7)}" y="${round(y + 4)}" font-size="10.5" fill="${c}"
      font-family="Segoe UI,Inter,sans-serif">${esc(m(L))}</text></g>`;
    this.push('front', s);
    if (!this.equal && isFinite(this.exag) && Math.abs(this.exag - 1) > 0.06) {
      this.textPx(x + px + 52, y + 4,
        `vertical exaggeration ${(this.exag).toFixed(1)} : 1`,
        { size: 10, fill: this.p.warn, weight: 600 });
    }
    return this;
  };

  Scene.prototype.legend = function (items, o) {
    o = o || {};
    this.legendItems = items.filter(Boolean);
    this.legendOpts = o;
    return this;
  };

  Scene.prototype.note = function (text) { this.notes.push(text); return this; };

  Scene.prototype.title = function (t, sub) { this.titleText = t; this.subText = sub; return this; };

  Scene.prototype._furniture = function () {
    if (this.titleText) {
      this.textPx(this.P.l, 16, this.titleText, { size: 12.5, weight: 700, fill: this.p.ink });
      if (this.subText)
        this.textPx(this.W - this.P.r, 16, this.subText, { size: 11, anchor: 'end', fill: this.p.ink2 });
    }
    if (this.legendItems.length) {
      const o = this.legendOpts || {};
      let x = o.x != null ? o.x : this.W - this.P.r;
      let y = o.y != null ? o.y : this.P.t + 6;
      const anchor = o.anchor || 'end';
      const box = [];
      this.legendItems.forEach((it, i) => {
        const yy = y + i * 16;
        const sx = anchor === 'end' ? x - 10 : x;
        box.push(`<rect x="${round(anchor === 'end' ? sx - 12 : sx)}" y="${round(yy - 7)}" width="11" height="9"
          rx="2" fill="${it.fill || 'none'}" stroke="${it.stroke || it.fill || this.p.ink3}"
          stroke-width="${it.dash ? 1.4 : 1}" stroke-dasharray="${it.dash || ''}"/>`);
        box.push(`<text x="${round(anchor === 'end' ? sx - 18 : sx + 16)}" y="${round(yy + 1.5)}"
          text-anchor="${anchor === 'end' ? 'end' : 'start'}" font-size="10.8" fill="${this.p.ink2}"
          font-family="Segoe UI,Inter,sans-serif">${esc(it.label)}</text>`);
      });
      const wPx = Math.max.apply(null, this.legendItems.map(it => 9 + 5.7 * String(it.label).length));
      const plate = `<rect x="${round(anchor === 'end' ? x - 22 - wPx : x - 4)}" y="${round(y - 13)}"
        width="${round(wPx + 26)}" height="${round(this.legendItems.length * 16 + 8)}" rx="5"
        fill="${this.p.panel}" opacity=".82"/>`;
      this.push('front', `<g>${plate}${box.join('')}</g>`);
    }
    /* Notes are laid out from the bottom up, wrapped to the frame width, so a
       long sentence never runs off the sheet. */
    const perLine = Math.max(40, Math.floor((this.W - this.P.l - 20) / 5.05));
    const lines = [];
    this.notes.forEach(n => {
      let cur = '';
      String(n).split(/\s+/).forEach(w => {
        if ((cur + ' ' + w).trim().length > perLine) { lines.push(cur.trim()); cur = w; }
        else cur = (cur + ' ' + w).trim();
      });
      if (cur) lines.push(cur);
    });
    lines.forEach((L, i) =>
      this.textPx(this.P.l, this.H - 30 - (lines.length - 1 - i) * 12.5, L,
        { size: 10.3, fill: this.p.ink3 }));
    return this;
  };

  /* A clip path covering the drawing area — for spheres and circles that run
     off the frame, which is normal on an elevation and should not spill. */
  Scene.prototype.clip = function () {
    if (this._clip) return this._clip;
    const id = `${this.id}-clip`;
    this.defs.push(`<clipPath id="${id}"><rect x="${this.P.l - 6}" y="${this.P.t - 6}"
      width="${this.W - this.P.l - this.P.r + 12}" height="${this.H - this.P.t - this.P.b + 12}"/></clipPath>`);
    this._clip = `url(#${id})`;
    return this._clip;
  };

  Scene.prototype.svg = function () {
    this._furniture();
    return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${this.W} ${this.H}"
      width="100%" preserveAspectRatio="xMidYMid meet" role="img"
      style="display:block;max-height:${this.H}px">
      <defs>${this.defs.join('')}</defs>
      <rect width="${this.W}" height="${this.H}" fill="none"/>
      ${this.back.join('')}${this.mid.join('')}${this.front.join('')}</svg>`;
  };

  /* ============================================================== public */
  function scene(hostId, opts, build) {
    const fn = () => {
      const host = document.getElementById(hostId);
      if (!host) return;
      const s = new Scene(typeof opts === 'function' ? opts() : opts);
      try { build(s); } catch (e) { console.error('drawing failed:', hostId, e); }
      host.innerHTML = s.svg();
      host.dataset.drawn = '1';
    };
    SCENES[hostId] = fn;
    fn();
  }

  function redrawAll() { Object.values(SCENES).forEach(f => { try { f(); } catch (e) { } }); }

  function clear(hostId) {
    delete SCENES[hostId];
    const h = document.getElementById(hostId);
    if (h) { h.innerHTML = ''; delete h.dataset.drawn; }
  }

  function has(hostId) {
    const h = document.getElementById(hostId);
    return !!(h && h.dataset.drawn && h.querySelector('svg'));
  }

  /* Rasterise a drawing for the design report.  The SVG is self-contained, so
     it can be handed straight to an <img> and painted onto a canvas. */
  function toPNG(hostId, scale) {
    return new Promise((resolve, reject) => {
      const host = document.getElementById(hostId);
      const svg = host && host.querySelector('svg');
      if (!svg) return reject(new Error('no drawing'));
      const k = scale || 2;
      const vb = svg.viewBox.baseVal;
      const w = vb.width, h = vb.height;
      const clone = svg.cloneNode(true);
      clone.setAttribute('width', w);
      clone.setAttribute('height', h);
      /* the report page is white, so give the raster an opaque ground */
      const bg = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
      bg.setAttribute('width', w); bg.setAttribute('height', h);
      bg.setAttribute('fill', palette().panel);
      clone.insertBefore(bg, clone.firstChild);
      const src = 'data:image/svg+xml;charset=utf-8,' +
        encodeURIComponent(new XMLSerializer().serializeToString(clone));
      const img = new Image();
      img.onload = () => {
        const c = document.createElement('canvas');
        c.width = w * k; c.height = h * k;
        const ctx = c.getContext('2d');
        ctx.fillStyle = palette().panel;
        ctx.fillRect(0, 0, c.width, c.height);
        ctx.drawImage(img, 0, 0, c.width, c.height);
        try { resolve(c.toDataURL('image/png')); } catch (e) { reject(e); }
      };
      img.onerror = () => reject(new Error('raster failed'));
      img.src = src;
    });
  }

  return { scene, redrawAll, clear, has, toPNG, palette, Scene, m, esc };
})();
