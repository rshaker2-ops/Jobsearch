#!/usr/bin/env node
/**
 * Build one candidate's sweep document from a JSON spec.
 *
 *     node tools/build/sweep_doc.js <spec.json>
 *
 * The house format is tools/build/_example_doc.js, which this follows: the
 * finding first, tier one as cards with WHY / AGAINST and quoted requirements,
 * a tier two table, rule-outs each carrying the line that disqualifies them,
 * then the closing call.
 *
 * One addition since 28 September. If the spec names a narrative file, it is
 * rendered as the opening section, ahead of the market finding, because for
 * the people who have one that is the more urgent thing. Quoted paragraphs in
 * the narrative render as pull quotes: they are the words the person is
 * rehearsing for live interviews and they should be findable at a glance.
 */
const fs = require("fs");
const path = require("path");
const { Document, Packer, Paragraph, TextRun, PageBreak, BorderStyle, HeadingLevel } = require("docx");
const { make, pageProps, numbering, styles, SERIF, SANS, MONO } = require("./lib");

const F = { ink:"15171C", ink2:"4B4F59", ink3:"7F838D", accent:"1F4E63", warn:"8A6A16",
            good:"1D6144", bad:"8C2F2F", rule:"DBDDE2", ruleSoft:"E9EBEF", band:"F3F5F7" };
const k = make(F);
const { P, run, body, label, h1, quote, table, linkLine } = k;

const TONE = { strong: F.good, worth: F.accent, caveat: F.warn, stretch: F.warn };

function card({ n, title, org, band, loc, posted, verdict, tone, why, against, quotes, link }) {
  const colour = TONE[tone] || F.accent;
  const side = { left: { style: BorderStyle.SINGLE, size: 18, color: colour, space: 10 } };
  const out = [
    P({ heading: HeadingLevel.HEADING_2, spacing:{before:300,after:0}, border:side, indent:{left:120},
      children:[ run(`${n}.  `,{font:MONO,size:26,color:colour,bold:true}), run(title,{font:SERIF,size:26,color:F.ink}) ]}),
    P({ spacing:{before:40,after:40}, border:side, indent:{left:120}, children:[
      run(org,{font:MONO,size:16,color:F.ink3,caps:true,tracking:18}), run("     ",{font:MONO,size:16}),
      run(band,{font:MONO,size:17,color:F.ink,bold:true}), run("     ",{font:MONO,size:16}),
      run(String(verdict).toUpperCase(),{font:MONO,size:14,color:colour,bold:true,tracking:24}) ]}),
    P({ spacing:{before:0,after:100}, border:side, indent:{left:120},
      children:[ run(`${loc}${posted ? "   ·   " + posted : ""}`,{font:MONO,size:14,color:F.ink3}) ]}),
  ];
  if (link) out.push(linkLine([link],{indent:{left:120},border:side}));
  out.push(P({spacing:{before:60,after:100},border:side,indent:{left:120},children:[
    run("WHY  ",{font:MONO,size:13,color:F.good,caps:true,tracking:24}), run(why,{size:19,color:F.ink2}) ]}));
  if (against) out.push(P({spacing:{before:0,after:100},border:side,indent:{left:120},children:[
    run("AGAINST  ",{font:MONO,size:13,color:F.bad,caps:true,tracking:24}), run(against,{size:19,color:F.ink2}) ]}));
  (quotes||[]).forEach(q=>out.push(P({spacing:{before:0,after:60},indent:{left:320},
    children:[run("“"+q+"”",{size:18,color:F.ink3,italics:true})]})));
  return out;
}

function ruled({ title, org, band, reason, quotes }) {
  const side = { left:{style:BorderStyle.SINGLE,size:18,color:F.bad,space:10} };
  const out = [
    P({spacing:{before:240,after:0},border:side,indent:{left:120},children:[
      run(title,{font:SANS,size:21,color:F.ink,bold:true}),
      run(`     ${org}`,{font:MONO,size:15,color:F.ink3,caps:true,tracking:18}),
      run(`     ${band}`,{font:MONO,size:15,color:F.ink3}) ]}),
    P({spacing:{before:60,after:80},border:side,indent:{left:120},children:[
      run("RULED OUT  ",{font:MONO,size:13,color:F.bad,caps:true,tracking:24}), run(reason,{size:19,color:F.ink2}) ]}),
  ];
  (quotes||[]).forEach(q=>out.push(P({spacing:{before:0,after:60},indent:{left:320},
    children:[run("“"+q+"”",{size:18,color:F.ink3,italics:true})]})));
  return out;
}

/* Render a narrative markdown file. Deliberately a small subset: the files are
   written by hand for people to read, not generated, so anything fancier would
   be guessing at markdown nobody writes. */
function narrative(file) {
  const src = fs.readFileSync(file, "utf8");
  const out = [];
  const blocks = src.split(/\n\s*\n/);
  for (const raw of blocks) {
    const b = raw.trim();
    if (!b) continue;
    if (b.startsWith("# ")) { out.push(...h1(b.slice(2).trim(), "SAY THIS")); continue; }
    if (b.startsWith("## ")) { out.push(label(b.slice(3).trim())); continue; }
    const text = b.replace(/\n/g, " ").replace(/\s+/g, " ").trim();
    // A paragraph that opens with a quotation mark is speech: the actual words
    // to say. Those get pulled out so they can be found without reading prose.
    if (/^["“]/.test(text)) out.push(quote(text.replace(/^["“]|["”]$/g, "")));
    else out.push(body(text));
  }
  return out;
}

const spec = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
const kids = [];

// Masthead
kids.push(P({ spacing:{after:40}, children:[
  run(spec.kicker || "ROLE SWEEP", {font:MONO,size:15,color:F.accent,bold:true,caps:true,tracking:30}) ]}));
kids.push(P({ spacing:{after:40}, children:[ run(spec.name,{font:SERIF,size:44,color:F.ink}) ]}));
kids.push(P({ spacing:{after:260}, children:[ run(spec.subtitle,{font:MONO,size:16,color:F.ink3}) ]}));

if (spec.narrative) kids.push(...narrative(spec.narrative));

if (spec.finding && spec.finding.length) {
  kids.push(...h1(spec.findingTitle || "What this run found", "THE FINDING"));
  spec.finding.forEach(p => kids.push(body(p)));
}
if (spec.statsTable) kids.push(table(spec.statsTable.cols, spec.statsTable.head, spec.statsTable.rows));

if (spec.tier1 && spec.tier1.length) {
  kids.push(...h1(spec.tier1Title || "Worth your time", "TIER ONE"));
  spec.tier1.forEach((c,i) => kids.push(...card({ n:i+1, ...c })));
}
if (spec.tier2) {
  kids.push(...h1(spec.tier2.title || "Worth a look, with a caveat", "TIER TWO"));
  if (spec.tier2.intro) kids.push(body(spec.tier2.intro));
  kids.push(table(spec.tier2.cols, spec.tier2.head, spec.tier2.rows));
}
if (spec.ruledOut && spec.ruledOut.length) {
  kids.push(...h1(spec.ruledOutTitle || "Ruled out, and the line that did it", "RULE-OUTS"));
  if (spec.ruledOutIntro) kids.push(body(spec.ruledOutIntro));
  spec.ruledOut.forEach(r => kids.push(...ruled(r)));
}
if (spec.closing && spec.closing.length) {
  kids.push(...h1(spec.closingTitle || "What I would actually do with this", "THE CALL"));
  spec.closing.forEach((p,i) => kids.push(body(p, i === spec.closing.length-1 ? {after:60} : {})));
}

const doc = new Document({ numbering: numbering(F.accent), styles: styles(F),
                           sections:[{ properties: pageProps, children: kids }] });
Packer.toBuffer(doc).then(b => {
  fs.mkdirSync(path.dirname(spec.out), { recursive: true });
  fs.writeFileSync(spec.out, b);
  console.log(`${path.basename(spec.out)}  ${b.length.toLocaleString()} bytes`);
});
