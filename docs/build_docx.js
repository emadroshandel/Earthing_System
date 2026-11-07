/*
 * Build the Earthing System theory document as a Word file from docs/THEORY.md.
 *
 *     node docs/build_docx.js
 *
 * The markdown file is the single source of truth: the same text is rendered on
 * GitHub, inside the application's Theory page, and here.
 */
'use strict';

const fs = require('fs');
const path = require('path');
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType, TabStopType,
  Table, TableRow, TableCell, WidthType, ShadingType, BorderStyle, ImageRun,
  PageBreak, Header, Footer, PageNumber, LevelFormat, LineRuleType,
  TabStopPosition, LeaderType,
  convertInchesToTwip, ExternalHyperlink, VerticalAlign,
} = require('docx');

const ROOT = path.dirname(__dirname);
const MD = path.join(ROOT, 'docs', 'THEORY.md');
const OUT = path.join(ROOT, 'docs', 'THEORY.docx');

const INK = '1A2027', NAVY = '0F2F4F', ACC = '0F6B8A', GREY = '5A6773';
const PANEL = 'F5F8FA', LINE = 'D8E0E7';
const CONTENT_PX = 610;               // usable width at 96 dpi, A4 with 2 cm margins

/* ------------------------------------------------------------ PNG size --- */
function pngSize(file) {
  const b = fs.readFileSync(file);
  return { w: b.readUInt32BE(16), h: b.readUInt32BE(20) };
}

/* --------------------------------------------------------- inline runs --- */
function inline(text, base = {}) {
  // Recursive so that `code`, *italics* and links nest correctly inside **bold**.
  const runs = [];
  const re = /(`[^`]+`)|(\*\*[^*]+?\*\*)|(\*[^*\n]+?\*)|(\[[^\]]+\]\([^)]+\))/g;
  let last = 0, m;
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) {
      runs.push(new TextRun({ text: text.slice(last, m.index), ...base }));
    }
    const tok = m[0];
    if (tok.startsWith('`')) {
      runs.push(new TextRun({ text: tok.slice(1, -1), ...base,
                              font: 'Consolas', size: base.size ? base.size - 3 : 18,
                              color: ACC }));
    } else if (tok.startsWith('**')) {
      runs.push(...inline(tok.slice(2, -2), { ...base, bold: true }));
    } else if (tok.startsWith('[')) {
      const mm = tok.match(/\[([^\]]+)\]\(([^)]+)\)/);
      runs.push(new ExternalHyperlink({
        link: mm[2],
        children: [new TextRun({ text: mm[1], ...base, color: ACC, underline: {} })],
      }));
    } else {
      runs.push(...inline(tok.slice(1, -1), { ...base, italics: true }));
    }
    last = m.index + tok.length;
  }
  if (last < text.length) {
    runs.push(new TextRun({ text: text.slice(last), ...base }));
  }
  return runs.length ? runs : [new TextRun({ text: '', ...base })];
}

/* ------------------------------------------------------------- blocks ---- */
function codeBlock(lines) {
  return lines.map((ln, i) => new Paragraph({
    children: [new TextRun({ text: ln || ' ', font: 'Consolas', size: 17, color: INK })],
    shading: { type: ShadingType.CLEAR, fill: PANEL },
    border: {
      left: { style: BorderStyle.SINGLE, size: 18, color: ACC, space: 8 },
      top: i === 0 ? { style: BorderStyle.SINGLE, size: 2, color: PANEL, space: 4 } : undefined,
      bottom: i === lines.length - 1
        ? { style: BorderStyle.SINGLE, size: 2, color: PANEL, space: 4 } : undefined,
    },
    spacing: { before: i === 0 ? 140 : 0, after: i === lines.length - 1 ? 160 : 0, line: 250 },
    indent: { left: 120 },
    keepLines: true,
  }));
}

function quoteBlock(lines) {
  return [new Paragraph({
    children: inline(lines.join(' '), { size: 19, color: INK }),
    shading: { type: ShadingType.CLEAR, fill: 'FDF6E7' },
    border: { left: { style: BorderStyle.SINGLE, size: 18, color: 'A8630A', space: 10 } },
    spacing: { before: 160, after: 180, line: 300 },
    indent: { left: 160, right: 120 },
  })];
}

function tableBlock(rows) {
  const ncol = rows[0].length;
  const total = 9200;
  const w = Math.floor(total / ncol);
  const widths = Array(ncol).fill(w);
  widths[ncol - 1] = total - w * (ncol - 1);
  const mkCell = (txt, head, i) => new TableCell({
    width: { size: widths[i], type: WidthType.DXA },
    shading: head ? { type: ShadingType.CLEAR, fill: 'EEF4F7' } : undefined,
    margins: { top: 70, bottom: 70, left: 110, right: 110 },
    verticalAlign: VerticalAlign.CENTER,
    children: [new Paragraph({
      children: inline(txt, { size: 18, bold: head, color: head ? NAVY : INK }),
      spacing: { before: 0, after: 0, line: 250 },
    })],
  });
  return [new Table({
    columnWidths: widths,
    width: { size: total, type: WidthType.DXA },
    borders: {
      top: { style: BorderStyle.SINGLE, size: 4, color: LINE },
      bottom: { style: BorderStyle.SINGLE, size: 4, color: LINE },
      left: { style: BorderStyle.SINGLE, size: 4, color: LINE },
      right: { style: BorderStyle.SINGLE, size: 4, color: LINE },
      insideHorizontal: { style: BorderStyle.SINGLE, size: 2, color: LINE },
      insideVertical: { style: BorderStyle.SINGLE, size: 2, color: LINE },
    },
    rows: rows.map((r, ri) => new TableRow({
      tableHeader: ri === 0,
      children: r.map((c, ci) => mkCell(c, ri === 0, ci)),
    })),
  }),
  new Paragraph({ text: '', spacing: { after: 160 } })];
}

function imageBlock(file) {
  const abs = path.join(ROOT, 'docs', file);
  if (!fs.existsSync(abs)) return [];
  const { w, h } = pngSize(abs);
  const width = Math.min(CONTENT_PX, w);
  const height = Math.round(h * width / w);
  return [new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { before: 200, after: 60, line: 240, lineRule: LineRuleType.AUTO },
    keepNext: true,
    children: [new ImageRun({ type: 'png', data: fs.readFileSync(abs),
                              transformation: { width, height } })],
  })];
}

/* -------------------------------------------------------------- parse ---- */
const HEADINGS = [];
let olInstance = 0;      // a fresh numbering instance per ordered list

function convert(md) {
  const lines = md.split('\n');
  const out = [];
  let i = 0;
  let inContents = false;

  while (i < lines.length) {
    const L = lines[i];

    // ---- skip the markdown contents list; a real TOC field replaces it ----
    if (/^##\s+Contents\s*$/.test(L)) { inContents = true; i++; continue; }
    if (inContents) {
      if (/^---\s*$/.test(L)) { inContents = false; }
      i++; continue;
    }

    // ---- fenced code ----
    if (/^```/.test(L)) {
      const buf = [];
      i++;
      while (i < lines.length && !/^```/.test(lines[i])) buf.push(lines[i++]);
      i++;
      out.push(...codeBlock(buf));
      continue;
    }

    // ---- table ----
    if (/^\s*\|/.test(L) && /^\s*\|[\s:|-]+\|\s*$/.test(lines[i + 1] || '')) {
      const cells = r => r.trim().replace(/^\||\|$/g, '').split('|').map(c => c.trim());
      const rows = [cells(L)];
      i += 2;
      while (i < lines.length && /^\s*\|/.test(lines[i])) rows.push(cells(lines[i++]));
      out.push(...tableBlock(rows));
      continue;
    }

    // ---- image + caption ----
    let m = L.match(/^!\[[^\]]*\]\(([^)]+)\)\s*$/);
    if (m) { out.push(...imageBlock(m[1])); i++; continue; }
    m = L.match(/^\*(Figure \d+ —.*)\*\s*$/);
    if (m) {
      out.push(new Paragraph({
        alignment: AlignmentType.CENTER,
        spacing: { before: 0, after: 240 },
        children: inline(m[1], { size: 17, italics: true, color: GREY }),
      }));
      i++; continue;
    }

    // ---- headings ----
    m = L.match(/^(#{1,4})\s+(.*)$/);
    if (m) {
      const lvl = m[1].length, txt = m[2];
      if (lvl === 1) { i++; continue; }        // title handled by the title page
      const heading = lvl === 2 ? HeadingLevel.HEADING_1
        : lvl === 3 ? HeadingLevel.HEADING_2 : HeadingLevel.HEADING_3;
      if (lvl <= 3) HEADINGS.push({ level: lvl, text: txt.replace(/[*`]/g, '') });
      out.push(new Paragraph({
        heading, children: inline(txt),
        pageBreakBefore: lvl === 2 && /^\d+\./.test(txt),
      }));
      i++; continue;
    }

    // ---- blockquote ----
    if (/^>\s?/.test(L)) {
      const buf = [];
      while (i < lines.length && /^>\s?/.test(lines[i])) buf.push(lines[i++].replace(/^>\s?/, ''));
      out.push(...quoteBlock(buf));
      continue;
    }

    // ---- lists ----
    if (/^\s*[-*]\s+/.test(L)) {
      while (i < lines.length && /^\s*[-*]\s+/.test(lines[i])) {
        let t = lines[i].replace(/^\s*[-*]\s+/, '');
        while (i + 1 < lines.length && /^\s{2,}\S/.test(lines[i + 1]) &&
               !/^\s*[-*]\s+/.test(lines[i + 1])) t += ' ' + lines[++i].trim();
        out.push(new Paragraph({
          children: inline(t), numbering: { reference: 'bullets', level: 0 },
          spacing: { before: 40, after: 40, line: 290 },
        }));
        i++;
      }
      continue;
    }
    if (/^\s*\d+\.\s+/.test(L)) {
      olInstance += 1;
      while (i < lines.length && /^\s*\d+\.\s+/.test(lines[i])) {
        let t = lines[i].replace(/^\s*\d+\.\s+/, '');
        while (i + 1 < lines.length && /^\s{3,}\S/.test(lines[i + 1]) &&
               !/^\s*\d+\.\s+/.test(lines[i + 1])) t += ' ' + lines[++i].trim();
        out.push(new Paragraph({
          children: inline(t),
          numbering: { reference: 'numbers', level: 0, instance: olInstance },
          spacing: { before: 40, after: 40, line: 290 },
        }));
        i++;
      }
      continue;
    }

    // ---- horizontal rule ----
    if (/^\s*---+\s*$/.test(L)) {
      out.push(new Paragraph({
        text: '', spacing: { before: 60, after: 160 },
        border: { bottom: { style: BorderStyle.SINGLE, size: 4, color: LINE, space: 2 } },
      }));
      i++; continue;
    }

    if (L.trim() === '') { i++; continue; }

    // ---- paragraph ----
    const buf = [L];
    while (i + 1 < lines.length && lines[i + 1].trim() !== '' &&
           !/^(#{1,4}\s|>|```|!\[|\s*[-*]\s|\s*\d+\.\s|\s*\||\s*---+\s*$)/
             .test(lines[i + 1])) {
      buf.push(lines[++i]);
    }
    out.push(new Paragraph({
      children: inline(buf.join(' ')),
      spacing: { before: 80, after: 120, line: 300 },
      alignment: AlignmentType.LEFT,
    }));
    i++;
  }
  return out;
}

/* --------------------------------------------------------- title page ---- */
function titlePage() {
  const hero = path.join(ROOT, 'docs', 'figures', 'fig10_surface_potential.png');
  const kids = [
    new Paragraph({ text: '', spacing: { after: 900 } }),
    new Paragraph({
      alignment: AlignmentType.CENTER, spacing: { after: 60 },
      children: [new TextRun({ text: 'EARTHSYSTEM', size: 30, bold: true,
                               color: ACC, characterSpacing: 90 })],
    }),
    new Paragraph({
      alignment: AlignmentType.CENTER, spacing: { after: 140 },
      children: [new TextRun({
        text: 'Earthing System Design', size: 56, bold: true, color: NAVY })],
    }),
    new Paragraph({
      alignment: AlignmentType.CENTER, spacing: { after: 40 },
      border: { top: { style: BorderStyle.SINGLE, size: 8, color: ACC, space: 14 } },
      children: [new TextRun({
        text: 'The Physics and Mathematics Behind Every Calculation',
        size: 28, color: GREY })],
    }),
    new Paragraph({
      alignment: AlignmentType.CENTER, spacing: { before: 60, after: 420 },
      children: [new TextRun({
        text: 'A teaching companion to the Earthing System software',
        size: 21, italics: true, color: GREY })],
    }),
  ];
  if (fs.existsSync(hero)) {
    const { w, h } = pngSize(hero);
    const width = 430, height = Math.round(h * width / w);
    kids.push(new Paragraph({
      alignment: AlignmentType.CENTER,
      spacing: { after: 420, line: 240, lineRule: LineRuleType.AUTO },
      children: [new ImageRun({ type: 'png', data: fs.readFileSync(hero),
                                transformation: { width, height } })],
    }));
  }
  kids.push(
    new Paragraph({
      alignment: AlignmentType.CENTER, spacing: { after: 40 },
      children: [new TextRun({ text: 'Dr. Emad Roshandel', size: 26, bold: true,
                               color: INK })],
    }),
    new Paragraph({
      alignment: AlignmentType.CENTER, spacing: { after: 300 },
      children: [new TextRun({
        text: 'Mehrad Pars Technology Development · Shiraz, Iran',
        size: 19, color: GREY })],
    }),
    new Paragraph({
      alignment: AlignmentType.CENTER, spacing: { after: 30 },
      children: [new TextRun({
        text: 'IEEE Std 80-2013  ·  IEEE Std 81-2012  ·  IEEE Std 142  ·  '
            + 'IEC 60364  ·  IEC 60909  ·  IEC 62305',
        size: 17, color: ACC })],
    }),
    new Paragraph({
      alignment: AlignmentType.CENTER,
      children: [new TextRun({
        text: `Version 1.1 · ${new Date().toISOString().slice(0, 10)}`,
        size: 17, color: GREY })],
    }),
    new Paragraph({ children: [new PageBreak()] }),
  );
  return kids;
}

/* The page numbers come from a first rendering pass (docs/.tocmap.json).  The
   entries are laid out identically in both passes, so pagination does not move
   between them. */
function tocPage() {
  let map = {};
  const mf = path.join(ROOT, 'docs', '.tocmap.json');
  if (fs.existsSync(mf)) { try { map = JSON.parse(fs.readFileSync(mf, 'utf8')); } catch (e) {} }

  const kids = [new Paragraph({
    spacing: { after: 260 },
    children: [new TextRun({ text: 'Contents', size: 36, bold: true, color: NAVY })],
    border: { bottom: { style: BorderStyle.SINGLE, size: 8, color: ACC, space: 8 } },
  })];

  for (const h of HEADINGS) {
    const top = h.level === 2;
    const page = map[h.text] !== undefined ? String(map[h.text]) : '00';
    kids.push(new Paragraph({
      spacing: { before: top ? 130 : 12, after: 12, line: 240,
                 lineRule: LineRuleType.AUTO },
      indent: { left: top ? 0 : 340 },
      tabStops: [{ type: TabStopType.RIGHT, position: 9200,
                   leader: LeaderType.DOT }],
      children: [
        new TextRun({ text: h.text, size: top ? 21 : 19,
                      bold: top, color: top ? NAVY : INK }),
        new TextRun({ text: '\t' + page, size: top ? 21 : 19,
                      bold: top, color: top ? NAVY : GREY }),
      ],
    }));
  }
  kids.push(new Paragraph({ children: [new PageBreak()] }));
  return kids;
}

/* ------------------------------------------------------------- build ----- */
function build() {
  const md = fs.readFileSync(MD, 'utf8');
  const body = convert(md);

  const doc = new Document({
    creator: 'Dr. Emad Roshandel',
    title: 'Earthing System — earthing (grounding) system design: The Physics and Mathematics',
    description: 'Teaching companion to the Earthing System earthing design software.',
    styles: {
      default: {
        document: { run: { font: 'Calibri', size: 21, color: INK },
                    paragraph: { spacing: { line: 300, lineRule: LineRuleType.AUTO } } },
        heading1: {
          run: { font: 'Calibri Light', size: 34, bold: true, color: NAVY },
          paragraph: { spacing: { before: 360, after: 180 },
                       border: { bottom: { style: BorderStyle.SINGLE, size: 8,
                                           color: ACC, space: 6 } } },
        },
        heading2: {
          run: { font: 'Calibri Light', size: 26, bold: true, color: ACC },
          paragraph: { spacing: { before: 300, after: 120 } },
        },
        heading3: {
          run: { font: 'Calibri', size: 22, bold: true, color: NAVY },
          paragraph: { spacing: { before: 220, after: 100 } },
        },
      },
    },
    numbering: {
      config: [
        { reference: 'bullets', levels: [
          { level: 0, format: LevelFormat.BULLET, text: '•',
            alignment: AlignmentType.LEFT,
            style: { paragraph: { indent: { left: 460, hanging: 240 } } } }] },
        { reference: 'numbers', levels: [
          { level: 0, format: LevelFormat.DECIMAL, text: '%1.',
            alignment: AlignmentType.LEFT,
            style: { paragraph: { indent: { left: 460, hanging: 240 } } } }] },
      ],
    },
    sections: [{
      properties: {
        page: {
          size: { width: convertInchesToTwip(8.27), height: convertInchesToTwip(11.69) },
          margin: {
            top: convertInchesToTwip(0.95), bottom: convertInchesToTwip(0.9),
            left: convertInchesToTwip(1.0), right: convertInchesToTwip(1.0),
          },
        },
      },
      headers: {
        default: new Header({
          children: [new Paragraph({
            tabStops: [{ type: TabStopType.RIGHT, position: 9200 }],
            border: { bottom: { style: BorderStyle.SINGLE, size: 4, color: LINE, space: 6 } },
            children: [new TextRun({ text: 'Earthing System — earthing (grounding) system design',
                                     size: 16, color: GREY }),
                       new TextRun({ text: '\tThe physics and mathematics',
                                     size: 16, color: GREY, italics: true })],
          })],
        }),
      },
      footers: {
        default: new Footer({
          children: [new Paragraph({
            alignment: AlignmentType.CENTER,
            children: [new TextRun({ children: ['Page ', PageNumber.CURRENT, ' of ',
                                                PageNumber.TOTAL_PAGES],
                                     size: 16, color: GREY })],
          })],
        }),
      },
      children: [...titlePage(), ...tocPage(), ...body],
    }],
  });

  Packer.toBuffer(doc).then(buf => {
    fs.writeFileSync(OUT, buf);
    fs.writeFileSync(path.join(ROOT, 'docs', '.headings.json'),
                     JSON.stringify(HEADINGS, null, 1));
    console.log('wrote', OUT, (buf.length / 1024 / 1024).toFixed(2), 'MB',
                '|', HEADINGS.length, 'headings');
  });
}

build();
