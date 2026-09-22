const {
  Paragraph, TextRun, HeadingLevel, AlignmentType, ExternalHyperlink,
  Table, TableRow, TableCell, WidthType, BorderStyle, ShadingType, LevelFormat,
} = require("docx");

const SERIF = "Georgia";
const SANS  = "Calibri";
const MONO  = "Consolas";
const CONTENT = 10080;

const hair = (c) => ({ style: BorderStyle.SINGLE, size: 4, color: c });
const NO_BORDER = { style: BorderStyle.NONE, size: 0, color: "FFFFFF" };
const cellNone = { top: NO_BORDER, bottom: NO_BORDER, left: NO_BORDER, right: NO_BORDER };

const P = (o) => new Paragraph(o);

const run = (text, o = {}) => new TextRun({
  text, font: o.font || SANS, size: o.size || 20, color: o.color || "444444",
  bold: !!o.bold, italics: !!o.italics, allCaps: !!o.caps, characterSpacing: o.tracking || 0,
});

function make(C) {
  const body = (text, o = {}) => P({
    spacing: { before: o.before ?? 0, after: o.after ?? 120, line: 300 },
    indent: o.indent,
    children: Array.isArray(text) ? text : [run(text, { color: C.ink2, ...o })],
  });

  const label = (text) => P({
    spacing: { before: 60, after: 20 },
    children: [run(text, { font: MONO, size: 13, color: C.ink3, caps: true, tracking: 24 })],
  });

  const h1 = (text, kick) => [
    P({ spacing: { before: 360, after: 0 }, border: { bottom: { style: BorderStyle.SINGLE, size: 12, color: C.ink } }, children: [run("", { size: 2 })] }),
    ...(kick ? [P({ spacing: { before: 140, after: 40 }, children: [run(kick, { font: MONO, size: 15, color: C.accent, bold: true, caps: true, tracking: 30 })] })] : []),
    P({ heading: HeadingLevel.HEADING_1, spacing: { before: kick ? 0 : 140, after: 160 },
        children: [run(text, { font: SERIF, size: 34, color: C.ink })] }),
  ];

  const quote = (t) => P({
    spacing: { before: 200, after: 160 },
    border: { left: { style: BorderStyle.SINGLE, size: 10, color: C.rule, space: 14 } },
    indent: { left: 180 },
    children: [run(t, { font: SANS, size: 18, color: C.ink3, italics: true })],
  });

  /* link line: [[text, url], ...] */
  const linkLine = (links, o = {}) => {
    const kids = [run(o.prefix || "Apply   ", { font: MONO, size: 13, color: C.ink3, caps: true, tracking: 24 })];
    links.forEach(([t, u], i) => {
      if (i) kids.push(run("   ·   ", { font: MONO, size: 15, color: C.ink3 }));
      kids.push(new ExternalHyperlink({
        link: u,
        children: [new TextRun({ text: t, font: MONO, size: 16, color: C.accent, underline: {} })],
      }));
    });
    return P({ spacing: { before: 40, after: 140 }, indent: o.indent, border: o.border, children: kids });
  };

  function table(cols, headers, rows, opts = {}) {
    const headRow = new TableRow({
      tableHeader: true,
      children: headers.map((h, i) => new TableCell({
        width: { size: cols[i], type: WidthType.DXA },
        shading: { type: ShadingType.CLEAR, color: "auto", fill: C.accent },
        margins: { top: 90, bottom: 90, left: 130, right: 130 },
        borders: { top: hair(C.accent), bottom: hair(C.accent), left: hair(C.accent), right: hair(C.accent) },
        children: [P({ children: [run(h, { font: MONO, size: 14, color: "FFFFFF", bold: true, caps: true, tracking: 24 })] })],
      })),
    });
    const bodyRows = rows.map((r, ri) => new TableRow({
      children: r.map((cellText, i) => {
        const isNum = (opts.numeric || []).includes(i);
        const parts = Array.isArray(cellText) ? cellText : [cellText];
        return new TableCell({
          width: { size: cols[i], type: WidthType.DXA },
          shading: { type: ShadingType.CLEAR, color: "auto", fill: ri % 2 ? C.band : "FFFFFF" },
          margins: { top: 100, bottom: 100, left: 130, right: 130 },
          borders: { top: hair(C.ruleSoft), bottom: hair(C.ruleSoft), left: hair(C.ruleSoft), right: hair(C.ruleSoft) },
          children: parts.map((p) => P({
            spacing: { after: parts.length > 1 ? 60 : 0, line: 280 },
            alignment: isNum ? AlignmentType.RIGHT : AlignmentType.LEFT,
            children: [typeof p === "string"
              ? run(p, { font: isNum ? MONO : SANS, size: 19, color: i === 0 ? C.ink : C.ink2, bold: i === 0 && !isNum })
              : p],
          })),
        });
      }),
    }));
    return new Table({ columnWidths: cols, width: { size: cols.reduce((a, b) => a + b, 0), type: WidthType.DXA }, rows: [headRow, ...bodyRows] });
  }

  function facts(pairs) {
    const cols = [1650, 3390, 1650, 3390];
    const mk = (k, v, tone) => [
      new TableCell({ width: { size: cols[0], type: WidthType.DXA }, borders: cellNone,
        margins: { top: 40, bottom: 40, left: 0, right: 80 },
        children: [P({ children: [run(k, { font: MONO, size: 13, color: C.ink3, caps: true, tracking: 24 })] })] }),
      new TableCell({ width: { size: cols[1], type: WidthType.DXA }, borders: cellNone,
        margins: { top: 40, bottom: 40, left: 0, right: 160 },
        children: [P({ children: [run(v, { font: MONO, size: 17, color: tone || C.ink, bold: !!tone })] })] }),
    ];
    const rows = [];
    for (let i = 0; i < pairs.length; i += 2) {
      const a = pairs[i], b = pairs[i + 1];
      rows.push(new TableRow({ children: [...mk(a[0], a[1], a[2]), ...(b ? mk(b[0], b[1], b[2]) : [
        new TableCell({ width: { size: cols[2], type: WidthType.DXA }, borders: cellNone, children: [P({ children: [run("")] })] }),
        new TableCell({ width: { size: cols[3], type: WidthType.DXA }, borders: cellNone, children: [P({ children: [run("")] })] }),
      ])] }));
    }
    return new Table({ columnWidths: cols, width: { size: CONTENT, type: WidthType.DXA }, rows });
  }

  function role({ rank, score, title, org, sponsor, why, signals, gaps, meta, tier, links, comp }) {
    const stripe = tier === 1 ? C.accent : tier === 2 ? C.warn : C.ink3;
    const sideBorder = { left: { style: BorderStyle.SINGLE, size: 18, color: stripe, space: 10 } };
    const out = [
      P({
        heading: HeadingLevel.HEADING_2, spacing: { before: 300, after: 0 },
        border: sideBorder, indent: { left: 120 },
        children: [
          run(`${rank}.  `, { font: MONO, size: 26, color: stripe, bold: true }),
          run(title, { font: SERIF, size: 26, color: C.ink }),
          run(`   ${score}/100`, { font: MONO, size: 20, color: stripe, bold: true }),
        ],
      }),
      P({
        spacing: { before: 40, after: 0 },
        border: sideBorder, indent: { left: 120 },
        children: [
          run(org, { font: MONO, size: 16, color: C.ink3, caps: true, tracking: 18 }),
          run("   ", { font: MONO, size: 16 }),
          run(sponsor, { font: MONO, size: 16, color: C.accent, bold: true, caps: true, tracking: 18 }),
        ],
      }),
    ];
    if (links && links.length) out.push(linkLine(links, { indent: { left: 120 }, border: sideBorder }));
    else out.push(P({ spacing: { after: 140 }, children: [run("", { size: 2 })] }));
    if (comp) {
      out.push(P({
        spacing: { after: 120 },
        children: [
          run("$300k floor   ", { font: MONO, size: 13, color: C.ink3, caps: true, tracking: 24 }),
          run(comp[0], { font: MONO, size: 17, color: comp[1], bold: true }),
        ],
      }));
    }
    out.push(facts(meta));
    out.push(body(why, { before: 140, after: 100 }));
    out.push(P({ spacing: { after: 40 }, children: [
      run("Signals   ", { font: MONO, size: 14, color: C.good, bold: true, caps: true, tracking: 24 }),
      run(signals.join("  ·  "), { font: SANS, size: 18, color: C.ink2 }),
    ] }));
    out.push(P({ spacing: { after: 200 }, children: [
      run("Gaps   ", { font: MONO, size: 14, color: C.warn, bold: true, caps: true, tracking: 24 }),
      run(gaps.join("  ·  "), { font: SANS, size: 18, color: C.ink2 }),
    ] }));
    return out;
  }

  return { P, run, body, label, h1, quote, table, facts, role, linkLine, SERIF, SANS, MONO, CONTENT };
}

const pageProps = {
  page: {
    size: { width: 12240, height: 15840 },
    margin: { top: 1080, right: 1080, bottom: 1080, left: 1080, header: 640, footer: 640 },
  },
};

const numbering = (color) => ({
  config: [{
    reference: "steps",
    levels: [{
      level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.START,
      style: { paragraph: { indent: { left: 420, hanging: 300 } },
               run: { font: MONO, size: 19, color, bold: true } },
    }],
  }],
});

const styles = (C) => ({
  default: {
    document: { run: { font: SANS, size: 20, color: C.ink2 }, paragraph: { spacing: { line: 300 } } },
    heading1: { run: { font: SERIF, size: 34, color: C.ink, bold: false } },
    heading2: { run: { font: SERIF, size: 26, color: C.ink, bold: false } },
  },
});

module.exports = { make, pageProps, numbering, styles, SERIF, SANS, MONO, CONTENT, BorderStyle };
