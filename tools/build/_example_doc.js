const fs = require("fs");
const { Document, Packer, Paragraph, TextRun, PageBreak, BorderStyle, HeadingLevel } = require("docx");
const { make, pageProps, numbering, styles, SERIF, SANS, MONO } = require("./lib");
const F = { ink:"15171C", ink2:"4B4F59", ink3:"7F838D", accent:"1F4E63", warn:"8A6A16", good:"1D6144", bad:"8C2F2F", rule:"DBDDE2", ruleSoft:"E9EBEF", band:"F3F5F7" };
const k = make(F);
const { P, run, body, label, h1, quote, table, linkLine } = k;

function card({ n, title, org, band, loc, posted, verdict, tone, why, against, quotes, link }) {
  const side = { left: { style: BorderStyle.SINGLE, size: 18, color: tone, space: 10 } };
  const out = [
    P({ heading: HeadingLevel.HEADING_2, spacing:{before:300,after:0}, border:side, indent:{left:120},
      children:[ run(`${n}.  `,{font:MONO,size:26,color:tone,bold:true}), run(title,{font:SERIF,size:26,color:F.ink}) ]}),
    P({ spacing:{before:40,after:40}, border:side, indent:{left:120}, children:[
      run(org,{font:MONO,size:16,color:F.ink3,caps:true,tracking:18}), run("     ",{font:MONO,size:16}),
      run(band,{font:MONO,size:17,color:F.ink,bold:true}), run("     ",{font:MONO,size:16}),
      run(verdict.toUpperCase(),{font:MONO,size:14,color:tone,bold:true,tracking:24}) ]}),
    P({ spacing:{before:0,after:100}, border:side, indent:{left:120},
      children:[ run(`${loc}   ·   posted ${posted}`,{font:MONO,size:14,color:F.ink3}) ]}),
  ];
  if (link) out.push(linkLine([link],{indent:{left:120},border:side}));
  out.push(P({spacing:{before:60,after:100},border:side,indent:{left:120},children:[
    run("WHY  ",{font:MONO,size:13,color:F.good,caps:true,tracking:24}), run(why,{size:19,color:F.ink2}) ]}));
  out.push(P({spacing:{before:0,after:100},border:side,indent:{left:120},children:[
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

const doc = new Document({ numbering: numbering(F.accent), styles: styles(F), sections:[{ properties: pageProps, children:[

  P({spacing:{after:40},children:[run("CHANNEL SWEEP  ·  LINKEDIN + WORKDAY  ·  22 SEP 2026",{font:MONO,size:15,color:F.accent,bold:true,caps:true,tracking:30})]}),
  P({heading:HeadingLevel.HEADING_1,spacing:{after:60},children:[run("Two channels the ATS boards cannot reach",{font:SERIF,size:40,color:F.ink})]}),
  P({spacing:{after:240},children:[run("Robert J. Shaker II  ·  SVP and above  ·  remote US  ·  $275k base floor",{size:20,color:F.ink3,italics:true})]}),

  ...h1("What ran","METHOD"),
  body("The September 19 sweep covered 364 company career sites through the Greenhouse, Ashby and Lever public APIs. Those APIs only return roles a company posts on its own board. Two categories never appear there: roles a retained search firm posts on a client’s behalf, and roles at large enterprises running Workday, whose job data sits behind a separate API that the board aggregators do not index. This run went after both."),
  table([2900,1450,5730],["Channel","Result","What it covers"],[
    ["LinkedIn guest endpoint","336 unique","Company posts plus retained search firms posting confidential client roles"],
    ["Workday CXS API","611 unique","14 enterprise tenants: Salesforce, Cisco, CrowdStrike, Abbott, Humana, Cigna, McKesson, Medtronic, Stryker, Thermo Fisher, Target, Chewy, Equifax, RingCentral"],
    ["Read end to end","53","Every remote-US survivor, full posting text, requirements before title"],
    ["Publishing a base band","22 of 53","The rest state no number anywhere in the posting"],
    ["Top of band at or above $275k","15","Before reading requirements"],
    ["Survive the requirements read","5","After reading requirements"],
  ]),

  body("One correction from earlier today. I told you all 53 came back with a published band. That was wrong, and it was my extractor’s fault, not the market’s: it was scraping every dollar figure on the page, including the “more jobs like this” sidebar, so unrelated postings’ numbers were being attached to roles that publish nothing. Every band in this document now comes from inside the posting’s own text, and 31 of the 53 publish no number at all.",{before:200}),

  ...h1("The Workday result","READ THIS"),
  body("14 enterprise tenants, 3,028 unique postings across all three searches I ran today, and for your band the entire channel produced one role. Six postings anywhere in the Workday pool carry an executive title with product, engineering or technology scope. Five of those six are on-site: Lake Forest, Alameda, Dallas, Kuala Lumpur. One is remote."),
  body("That is worth knowing because it closes a question rather than opening one. The large-enterprise Workday channel is not a hidden reservoir of SVP product roles. Those companies fill that level through search firms, and the search firms post on LinkedIn. Which is where the rest of this document comes from."),

  P({children:[new PageBreak()]}),
  ...h1("Apply this week","TIER ONE"),

  ...card({n:1,title:"SVP, Email Product Area",org:"Sinch",band:"$252,800 – $316,000",loc:"Remote, United States",posted:"11 Sep",
    verdict:"best structural fit in the sweep",tone:F.accent,
    why:"This is the only posting in 336 that asks for the exact combination you have rather than one half of it. It wants product leadership and engineering leadership and business leadership in one person, running an API-first developer platform. That is ActiveState, described by somebody else.",
    against:"Their requirement list names P&L ownership, pricing and packaging, and gross margin improvement. Those are the three things you told me your CPTO title did not actually include. Go in with an answer for that, not a hope that it will not come up.",
    quotes:["12-15+ years across product management, engineering leadership, and business leadership, with meaningful time in senior executive roles.",
            "Experience leading both product and engineering teams, with accountability for full product delivery from strategy through execution, operations, and product performance.",
            "A track record scaling SaaS, API-first, developer platform, or communications products across self-service, product-led growth, enterprise sales, and partner-led motions."],
    link:["linkedin.com/jobs/view/4464215264","https://www.linkedin.com/jobs/view/svp-email-product-area-at-sinch-4464215264"]}),

  ...card({n:2,title:"Senior Vice President of Product Management",org:"ClearCo",band:"$240,000 – $280,000",loc:"Remote, United States",posted:"11 Sep",
    verdict:"clean fit, band is tight",tone:F.accent,
    why:"They wrote down the distinction you had to correct me on this week. They want someone technical enough to be a peer to engineering and explicitly not someone who writes production code. Everything else on the list, platform and API products, third-party integrations, hiring and leveling PMs, scaling a product function through a rebuild, is your last two roles.",
    against:"Your floor is $275k and their band tops at $280k. You would be asking for the 96th percentile of their range on day one. Also HR tech, which you have not worked in, though they list it as a plus rather than a requirement.",
    quotes:["Technical credibility with the teams that build. You’re technical enough to be a genuine peer to engineering, data science, and QA, not to write the production code.",
            "People leadership. You’ve hired, leveled, and coached product managers, and built teams people want to work on.",
            "Experience scaling a product function through a period of significant change or rebuild."],
    link:["linkedin.com/jobs/view/4466394577","https://www.linkedin.com/jobs/view/senior-vice-president-of-product-management-at-clearco-4466394577"]}),

  ...card({n:3,title:"Chief Product and Technology Officer",org:"CareMessage",band:"$280,000 flat",loc:"Remote, United States",posted:"16 Sep",
    verdict:"the posting removes your two objections",tone:F.accent,
    why:"They rule out the hands-on-code requirement in writing and they rule out needing the title before. Then they name the one thing that is non-negotiable, and it happens to be a thing you can evidence: changing an engineering organization’s technical direction without authority over it. That is the Symantec security program review story.",
    against:"$280,000 is a single number, not a range, at a nonprofit serving safety-net healthcare. There is no negotiating headroom and the mission filter is real, they say outright it will not suit someone who treats low-income populations as a stage. Regular travel to frontline sites is a stated requirement.",
    quotes:["You do not need to be writing code, to have held this title before, or to know healthcare interoperability standards.",
            "You have changed an engineering organization’s technical direction without authority over it, and you can explain the argument well enough for an engineer to judge it. This one is not negotiable.",
            "This is a remote role within the United States."],
    link:["linkedin.com/jobs/view/4467942027","https://www.linkedin.com/jobs/view/chief-product-and-technology-officer-at-caremessage-4467942027"]}),

  ...card({n:4,title:"Chief Product Officer",org:"ASAPP",band:"$350,000 – $400,000",loc:"New York, remote-flagged",posted:"21 Sep",
    verdict:"highest band that survives the read",tone:F.accent,
    why:"Enterprise AI product leadership with a portfolio to run and an organization to build. The role partners with Research and Engineering rather than owning architecture, and the accountability is adoption, expansion and commercial value. Posted yesterday, so you are early.",
    against:"Listed as New York. It came through the remote-eligible filter but the location field says otherwise, so confirm before you invest in the application. The job is also judged on productizing one thing, GenerativeAgent, which makes it a narrower bet than the title suggests.",
    quotes:["Partner with Research, Engineering, Delivery, and Security to convert advances in AI into products that are intuitive, reliable, and commercially valuable.",
            "Lead products from incubation and early product-market fit through production deployment, adoption, expansion, and scale."],
    link:["linkedin.com/jobs/view/4468166158","https://www.linkedin.com/jobs/view/chief-product-officer-at-asapp-4468166158"]}),

  ...card({n:5,title:"Associate Vice President, Enterprise Digital Platforms",org:"Humana",band:"$203,400 – $279,800",loc:"Remote Nationwide",posted:"18 Sep",
    verdict:"the one Workday role",tone:F.warn,
    why:"The only remote-US executive product role the entire 14-tenant Workday sweep produced. It draws the product-versus-engineering line explicitly and puts you on the product side of it, with directors and senior product leaders reporting in and a regulated-industry operating model to run.",
    against:"Tops at $279,800, so your floor is again at the ceiling. The portfolio is Adobe Experience Platform, consent management and design systems, MarTech, not security or developer tooling. Adobe depth is preferred, not required, but you would be the candidate without it.",
    quotes:["Technology leaders remain accountable for architecture, engineering delivery, security, reliability, and technical operations.",
            "10 or more years of progressive leadership experience in product management, platform strategy, digital transformation... including leadership of enterprise-scale portfolios and teams.",
            "Lead and develop directors, senior product leaders, and persistent cross-functional platform teams."],
    link:["humana.wd5.myworkdayjobs.com · R-430680","https://humana.wd5.myworkdayjobs.com/Humana_External_Career_Site/job/Remote-Nationwide/Associate-Vice-President--Enterprise-Digital-Platforms_R-430680"]}),

  P({children:[new PageBreak()]}),
  ...h1("Worth a look, with a caveat each","TIER TWO"),
  table([3200,1900,6980],["Role","Band","The caveat"],[
    ["SVP, Product, Dassault Systèmes / Medidata","$252,750 – $337,000","Two hard gates. The qualification list names a Master’s or PhD in a scientific, medical or technical discipline, and the band is quoted for roles “physically based in New York.” Best band in the sweep, hardest entry."],
    ["Chief Product Officer, Viz.ai","not published","Leads PM, PMM and Design across US and Israel, revenue-connected prioritization, no hands-on requirement. Healthcare AI. No number published, so comp is an unknown."],
    ["Chief Product Officer, DigniFi","not published","Product and engineering under one seat, board reporting, KPI ownership for both functions. Auto-finance fintech. Partners with engineering leadership on architecture rather than owning it."],
    ["Head of Product Management, Sotheby’s","$275,000 – $320,000","Band clears your floor outright, which almost nothing else does. But it is a “Head of,” not an SVP, it is New York, and it is consumer luxury auction, which is the furthest thing in this document from your track record."],
  ]),

  ...h1("Ruled out, and why","THE REQUIREMENTS TEST"),
  body("Same test I should have applied before I put Five9 at the top of last week’s list. Title and band first, requirements second, is how that mistake happens. These six all carried a title and a band that would have made the list on those two signals alone."),

  ...ruled({title:"Chief Technology Officer",org:"Harrison Clarke",band:"$400,000",
    reason:"Writes code daily. Not a leadership role with technical depth, an individual contributor with a title.",
    quotes:["We’re looking for a hands-on AI agent builder, someone who writes code daily, ships production AI systems.","You’re writing Python/TypeScript daily, prototyping agent architectures, and pushing to production."]}),
  ...ruled({title:"Chief Product & Technology Officer",org:"Banyan Software",band:"$185,000 – $200,000",
    reason:"Fails on both axes. The band is $75k under your floor and the role is a legacy codebase consolidation with hands on the work.",
    quotes:["You will set product direction, own the technical foundation, shape culture, and drive transformation with your own hands on the work.","Drive consolidation of the multi-codebase legacy footprint toward a modern, maintainable SaaS architecture."]}),
  ...ruled({title:"Chief Technology Officer, FuzeRx",org:"Fuze Health",band:"$375,000 – $400,000",
    reason:"Named-technology requirement list. This is the Five9 pattern exactly.",
    quotes:["Hands-on experience with cloud platforms (AWS), containerization (Docker/Kubernetes), modern front-end frameworks (React and React Native), and API-first design principles."]}),
  ...ruled({title:"Chief Technology Officer",org:"Storm2 (search firm)",band:"$350,000",
    reason:"Explicitly hands-on, owns architecture and engineering decisions.",
    quotes:["This is a highly strategic and hands-on leadership position.","Leading architecture and engineering decisions, and building the systems, teams, and processes required to support continued growth."]}),
  ...ruled({title:"Senior Vice President of Engineering, Data Centers",org:"GS2",band:"$375,000 – $415,000",
    reason:"Not software. This is physical data center construction, structural and mechanical engineering across build campuses.",
    quotes:["Lead global engineering vision across all campuses, aligning architecture, structural, MEP, and OFCI equipment strategies into a unified framework."]}),
  ...ruled({title:"SVP, Engineering",org:"Riot Platforms",band:"$310,000 – $340,000",
    reason:"Engineering organization leadership at a bitcoin mining operator. Right level, right band, wrong function and wrong sector.",quotes:[]}),

  ...h1("What I would actually do with this","THE CALL"),
  body("Sinch first, and this week. It is the one posting in 336 written for the combination you have rather than for one half of it, and the band starts $22k under your floor and runs $41k over it, which is the only band in this document with real room in it. Everything else here either tops out at your floor or does not publish a number."),
  body("Then CareMessage and ClearCo together, because they cost you one hour each and they both removed the objection that has been costing you screens, that a product executive who came up through engineering-adjacent roles will be read as either too technical or not technical enough. Both postings say in writing which side of that line they want."),
  body("Humana is the one to apply to even though the band disappoints, because it is proof the channel works: a remote SVP-equivalent product role at a Fortune 50, found through an API that no job board indexes. If that one exists, others will appear. I can re-run the Workday sweep weekly against a wider tenant list, fourteen is what I could verify today, and there are several hundred.",{after:60}),
]}]});
Packer.toBuffer(doc).then(b=>{fs.writeFileSync("/home/user/Jobsearch/Bob/Shaker_Channel_Sweep_Sep22.docx",b);console.log("bob ok",b.length);});
