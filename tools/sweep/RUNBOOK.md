# Twice-weekly role sweep

Runs Monday and Thursday, 07:00 Eastern. Fresh session, clean clone, no memory
of the last run. Everything needed is in this repo.

## What it produces

Four Word documents, one per candidate, emailed to all four recipients.

| Candidate | Folder | Email | Lane |
|---|---|---|---|
| Robert J. Shaker II (Bob) | `Bob/` | rshaker2@gmail.com | SVP+ product and engineering |
| Edan Mejias | `Edan/` | edanmejias@gmail.com | Senior / technical PM and PMM |
| Robert J. Shaker (Robbie) | `Robbie/` | robertshaker3@gmail.com | Information security and GRC analyst |
| Jeffrey G. Walton (Jeff) | `Jeff/` | jgordonwalton@gmail.com | Customer success, onboarding, enablement |

**Everyone receives every document.** Bob chose this deliberately
on 22 Sep 2026, knowing the analysis is frank and discusses each candidate's
gaps. Do not soften a finding because its subject is on the To: line. The
candor is the product. If a role is a bad fit, say so and quote the line that
makes it one.

## Step 1: sweep

```
python3 tools/sweep/run.py bob    /tmp/sweep
python3 tools/sweep/run.py edan   /tmp/sweep
python3 tools/sweep/run.py robbie /tmp/sweep
python3 tools/sweep/run.py jeff   /tmp/sweep
```

Roughly 8 to 12 minutes each; LinkedIn is rate limited and the script sleeps
1.6s between calls on purpose. Run them sequentially, not in parallel, or
LinkedIn starts returning 429.

Each writes `/tmp/sweep/<name>_scored.json`: `stats` plus a `roles` array
already filtered to title, location and seniority, each role carrying its full
posting text, its published band, and the lowest years-of-experience figure
stated anywhere in the posting.

Criteria live in `tools/sweep/profiles.json`. Change a floor or a search term
there, never in the scripts.

**Location rules, as of 22 Sep.** Bob, Edan and Robbie keep any United States
location, remote or on-site, so say where a role actually sits rather than
assuming remote. Boston and Rhode Island stay prioritised for Edan and Robbie.

Jeff is `remote-only` and that is a hard constraint, not a preference. He is in
McKinleyville, Humboldt County, which has no technology employment market at
this level, so an on-site role is not a longer commute, it is impossible.
Anything hybrid is a rule-out for him rather than a maybe, and his `hard_gate`
pattern flags the postings that say so.

Two traps the location code exists to avoid, both found in real data:

- LinkedIn writes most US roles as `Austin, TX`, not `Austin, Texas, United
  States`. Matching only the spelled-out country silently dropped 235 of 303
  US-located roles out of one sweep.
- LinkedIn carries remoteness in the `f_WT` search flag, not in the location
  string, so a fully remote role still reads `Austin, TX`. A remote-only
  profile that filters on the string alone throws away almost everything.

## Step 2: read the requirements

This is the part no script does, and the part that makes the document worth
opening. The scored JSON ranks by band and keyword fit. That ranking is a
starting point, **not** the answer.

For every role in the top ~15 of each list, read `desc` and decide:

- **Out** if it requires a named language at expert level, hands-on coding,
  distributed systems or architecture design, or SRE practice (Bob); if the
  stated experience floor is more than one year above the candidate (Edan,
  Robbie, Jeff); if it requires a clearance, a certification they do not hold
  as a hard requirement, or engineering and development work (Robbie, always);
  if it is hybrid or on-site in any form (Jeff, always).
- **In** if it requires org design, roadmap ownership, product strategy, P&L,
  hiring and developing people (Bob); platform, API, identity or security
  product ownership (Edan); vendor risk, third-party risk, questionnaires,
  SOC 2, ISO 27001, NIST, audit or policy work (Robbie); building a customer
  education, onboarding or enablement program from a blank page, MSP and
  channel motions, or a dual-track enterprise plus SMB model (Jeff).

Jeff's distinctive credential is worth stating plainly, because most of the
market will misread him as a generic customer success manager. He was on the
founding team of Malwarebytes Managed Security Services and built its global
onboarding from nothing, reaching 90% retention and 88% enablement. Postings
that ask for someone to build or significantly rebuild a program, rather than
run one that already exists, are the ones where that is rare rather than
ordinary. His security tenure is about five years, not the fifteen an older
version of his resume claimed, so treat a 5+ year bar as cleared and anything
above 8 as out.

Why this matters: on 19 Sep a Five9 engineering role was ranked first for Bob
on the strength of its title and its band. Reading the requirements would have
shown "Expert-level proficiency in Java" and "10+ years experience in
engineering management" in the first screen. Title and comp are not evidence.

Two facts to carry into the write-up every time:

1. **Bands come only from the posting's own text.** `run.py` enforces this.
   Never quote a number that is not inside `desc`. Most postings publish
   nothing; say "not published" rather than estimating.
2. **Quote the disqualifying line** on every rule-out. A rule-out without a
   quote is an opinion.

## Step 3: build the documents

`tools/build/lib.js` has the docx helpers; `tools/build/_example_doc.js` is the
22 Sep Bob document, which is the house format: finding first, then tier one as
cards with WHY / AGAINST / quotes, then a tier-two table, then rule-outs with
quoted requirements, then a short "what I would actually do with this".

```
node tools/build/<script>.js
```

Write to `<Folder>/<Name>_Channel_Sweep_<DDMon>.docx`, e.g.
`Bob/Shaker_Channel_Sweep_29Sep.docx`. Keep previous runs; they are the record
of what the market looked like that week.

## Step 4: commit, then queue the email

Commit the three documents to a `claude/` branch, push, open a draft PR.

Delivery is a separate step and it does NOT happen here. Do not try to send
mail. A GitHub Actions job does that at 13:00 UTC, an hour after this run.
What this step owes it is a queued email:

1. Write `outbox/<YYYY-MM-DD>.html` using today's date in America/New_York.
   Self-contained HTML: inline styles, a max-width table wrapper, no external
   CSS and no external images. Three or four short paragraphs, one per person,
   naming the single highest-value move for them this week and why. Not a
   summary of the documents. The documents are the summary.
2. Copy all four .docx into `outbox/<YYYY-MM-DD>.files/`, named so a stranger
   can tell them apart in an inbox, for example
   `Bob_Shaker_Role_Sweep_25Sep.docx`. Everything in that directory gets
   attached.
3. Push those two paths directly to `main`, not to the claude/ branch.
   Scheduled Actions runs always check out the default branch, so a queued
   email on a feature branch is invisible to the sender and nobody gets mail.
   The .docx still go through the PR for review; the queued copies are
   delivery artifacts.
4. Verify with `python3 tools/mail/send.py --dry-run`. It must exit 0, name
   the HTML file, and list four attachments. Exit 2 means the date or the
   filename is wrong. Fix it before finishing.

## When a run finds nothing new

Say so in one line and send anyway. A week with no new roles is information,
and skipping the email makes the reader wonder whether the job ran.

## Known limits

- The Workday channel covers 14 enterprise tenants
  (`tools/sweep/workday_tenants.txt`). Across 3,028 postings on 22 Sep it
  produced exactly one usable role. It is cheap to run and rarely pays.
  `tools/sweep/wd_probe.py` discovers more tenants if that changes.
- The LinkedIn guest endpoint returns 10 cards per call and caps out around 40
  per query. Widening coverage means more query terms, not more pages.
- The schedule is pinned to UTC. After the 1 Nov 2026 DST change it fires at
  06:00 Eastern until the cron is shifted to `0 12 * * 1,4`.
