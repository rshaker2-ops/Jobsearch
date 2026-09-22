# Twice-weekly role sweep

Runs Monday and Thursday, 07:00 Eastern. Fresh session, clean clone, no memory
of the last run. Everything needed is in this repo.

## What it produces

Three Word documents, one per candidate, emailed to all three recipients.

| Candidate | Folder | Email |
|---|---|---|
| Robert J. Shaker II (Bob) | `Bob/` | rshaker2@gmail.com |
| Edan Mejias | `Edan/` | edanmejias@gmail.com |
| Robert J. Shaker (Robbie) | `Robbie/` | robertshaker3@gmail.com |

**All three people receive all three documents.** Bob chose this deliberately
on 22 Sep 2026, knowing the analysis is frank and discusses each candidate's
gaps. Do not soften a finding because its subject is on the To: line. The
candor is the product. If a role is a bad fit, say so and quote the line that
makes it one.

## Step 1 — sweep

```
python3 tools/sweep/run.py bob    /tmp/sweep
python3 tools/sweep/run.py edan   /tmp/sweep
python3 tools/sweep/run.py robbie /tmp/sweep
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

## Step 2 — read the requirements

This is the part no script does, and the part that makes the document worth
opening. The scored JSON ranks by band and keyword fit. That ranking is a
starting point, **not** the answer.

For every role in the top ~15 of each list, read `desc` and decide:

- **Out** if it requires a named language at expert level, hands-on coding,
  distributed systems or architecture design, or SRE practice (Bob); if the
  stated experience floor is more than one year above the candidate (Edan,
  Robbie); if it requires a clearance, a certification they do not hold as a
  hard requirement, or engineering and development work (Robbie, always).
- **In** if it requires org design, roadmap ownership, product strategy, P&L,
  hiring and developing people (Bob); platform, API, identity or security
  product ownership (Edan); vendor risk, third-party risk, questionnaires,
  SOC 2, ISO 27001, NIST, audit or policy work (Robbie).

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

## Step 3 — build the documents

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

## Step 4 — commit and email

Commit to a `claude/` branch, push, open a draft PR.

Then one email per recipient via `mcp__Gmail__send_message`, all three
documents attached as base64, subject `Role sweep — <date>`. Body: three or
four lines naming the single highest-value move for each person this week. Not
a summary of the document. The document is the summary.

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
