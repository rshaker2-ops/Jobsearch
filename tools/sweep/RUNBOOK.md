# Daily role sweep

Runs every day at 09:47 UTC, which is early morning Eastern and shifts by an
hour when daylight saving ends, because cron is always UTC. Fresh session,
clean clone, no memory of the last run. Everything needed is in this repo.

It ran Monday and Thursday until 29 September 2026, when Bob moved it to daily.

## Daily only works because of the delta

The search window is 30 days (`tpr="r2592000"` in `li_sweep.py`). A daily run
therefore returns yesterday's results shifted by one day: about 97 percent of
any run is a repeat. Twice weekly, 3 of 30 days turned over. Daily, 1 does.

So `run.py` keeps a per-candidate history in `tools/sweep/seen/<key>.json` and
stamps every role with `first_seen` and `is_new`. `stats["new_today"]` counts
them. A role is keyed on company plus title rather than its URL, because
employers relist the same job under a fresh req id often enough that a URL key
would present the same role as a new find every few days.

**Lead the document with what is new.** Roles already reported belong in a
compact "still open" list or left out, never re-presented as a fresh find. A
document that repeats 97 percent of yesterday's is one people stop opening,
and then the whole pipeline is theatre.

`first_seen` is also worth using directly: a role that has been open for
eleven days and still has not been filled is a different proposition from one
posted this morning, and saying so is useful.

**The delta detects what left, not just what arrived.** A role in yesterday's
history that is absent from today's results is worth reporting, and on
30 September one was: a Workday seat with a $408,000 ceiling that was in
Jonny's document on the 29th and gone on the 30th. Report it as an absence,
never as a closure. The guest endpoint drops postings it still holds, so one
missing sweep is not proof of anything, and the honest sentence is that it was
there yesterday and is not today, so apply now or accept it may be gone.

The obvious alternative, narrowing the window to 24 hours, was rejected. The
LinkedIn guest endpoint surfaces postings inconsistently and indexes some of
them late, so a 24 hour window silently drops real roles. The 30 day window
with a seen list gives both completeness and novelty.

**`tools/sweep/seen/` must be pushed to `main`, with the outbox, not to the
`claude/` branch.** Every run starts from a fresh clone of the default branch.
A history sitting on a feature branch is a history the next run cannot see, so
tomorrow would call all 99 roles new and the delta would quietly do nothing
while appearing to work. This is the same trap as queueing the email on a
feature branch.

## What it produces

Five Word documents, one per candidate. Each candidate is emailed their own
document and nobody else's, under the subject "Your personalized job
market analysis from Bob".

| Candidate | Folder | Email | Lane |
|---|---|---|---|
| Robert J. Shaker II (Bob) | `Bob/` | rshaker2@gmail.com | SVP+ product and engineering |
| Edan Mejias | `Edan/` | edanmejias@gmail.com | Senior / technical PM and PMM |
| Robert J. Shaker (Robbie) | `Robbie/` | robertshaker3@gmail.com | Information security and GRC analyst |
| Jeffrey G. Walton (Jeff) | `Jeff/` | jgordonwalton@gmail.com | Customer success, onboarding, enablement |
| Jonathan Rivera (Jonny) | `Jonny/` | jonnydb86@gmail.com | Director to VP Product, platform transformation |

**One document per person, to that person only.** On 24 Sep 2026 a single
broadcast put all four addresses on one To: line and attached all four
documents, so every candidate received the others' comp floors, experience
gaps and verdicts. That must not happen again. The sender now supports a
per-recipient layout and Step 4 uses it.

The analysis stays frank. Each reader sees only their own, so do not soften a
finding to spare them. The candor is the product. If a role is a bad fit, say
so and quote the line that makes it one. What changes is distribution, not
tone.

## Step 1: sweep

```
python3 tools/sweep/run.py bob    /tmp/sweep
python3 tools/sweep/run.py edan   /tmp/sweep
python3 tools/sweep/run.py robbie /tmp/sweep
python3 tools/sweep/run.py jeff   /tmp/sweep
python3 tools/sweep/run.py jonny  /tmp/sweep
```

Roughly 8 to 12 minutes each; LinkedIn is rate limited and the script sleeps
1.6s between calls on purpose. Run them sequentially, not in parallel, or
LinkedIn starts returning 429.

**Drive them with a script that skips finished profiles.** The whole chain is
45 to 75 minutes and a background runner can kill it partway: on 30 September
it was stopped about ten minutes in, having finished Bob and lost Edan mid
search. The day before, the same chain ran 57 minutes untouched, so the limit
is not a number you can plan around.

    for who in bob edan robbie jeff jonny; do
      [ -s "$SW/${who}_scored.json" ] && continue
      python3 tools/sweep/run.py "$who" "$SW"
    done

Checking for the scored file first makes a restart cost only the profile that
was in flight rather than everything after it. Without it, a kill at minute ten
means starting all five again, and the second attempt is no more likely to
survive than the first.

**Commit `tools/sweep/seen/` as profiles finish, not only at the end.** The
sweep stamps its history as it goes. If the container dies before that reaches
git, those roles look new again tomorrow, which is precisely the repetition the
delta exists to stop. Committing partway is cheap; the final state still goes to
main with the outbox at Step 4.

Each writes `/tmp/sweep/<name>_scored.json`: `stats` plus a `roles` array
already filtered to title, location and seniority, each role carrying its full
posting text, its published band, and the lowest years-of-experience figure
stated anywhere in the posting.

Criteria live in `tools/sweep/profiles.json`. Change a floor or a search term
there, never in the scripts.

### Rejections and sectors a candidate rules out

Two optional profile fields, both permanent facts about the person rather than
about any one run:

- `company_block`, a list of employer names. Someone who has already said no,
  or who the candidate will not work for. Matched on the company name, case
  and padding insensitive.
- `industry_block`, a regex matched against the posting's own text rather than
  the company name, because the name almost never says it.

Both remove the role rather than demote it, and both are counted into `stats`
as `company_blocked` and `industry_blocked`, with `industry_blocked_names`
listing what went. **Say in the document what was dropped and why.** A silent
filter that eats a good role is worse than no filter, and the only way the
candidate can correct a bad rule is to see it fire.

As of 29 September 2026 only Bob carries either: IDIQ turned him down that day,
and he does not work for gambling companies. The industry pattern is written
against the terms that actually appeared in a real posting (sportsbook,
sports betting, iGaming, casino, wagering, responsible gaming) rather than
guessed, and it is tested against ordinary postings so that a line like "we are
betting on a new architecture" does not trip it.

**Location rules, as of 22 Sep.** Bob, Edan and Robbie keep any United States
location, remote or on-site, so say where a role actually sits rather than
assuming remote. Boston and Rhode Island stay prioritised for Edan and Robbie.

**Robbie is rewriting his own resume, as of 29 September.** Do not offer to do
it for him; the 29 September document did, and he has taken it on. The problem
it fixes is real and worth restating once he has: his resume carried a single
dated line, ActiveState 2025 to Present, so a reader subtracted to eighteen
months and never reached the 95 vendor assessments or the eight consecutive
months at 100% compliance behind it. Bob confirmed ActiveState had him doing a
much more senior person's job.

Two things follow. When he sends a new version, read it and say whether the fix
actually landed. A self-edit can correctly date the role and still bury the
volume in paragraph four, which leaves the reader doing the same subtraction.
Offering to review the new version is useful; offering to write it again is not.
And his targeting needs the correction below, which is the more important of
the two.

**His targeting, corrected 1 October. There is no squeeze.** The 30 September
and 1 October documents both told him the roles that would take his tenure
price below his floor while the roles above it want years he lacks, and the
1 October one said that squeeze had "broken". Both were wrong. Counted across
125 roles in his own data:

| Stated years | Roles | Clear the $94,500 floor | Median band top |
|---|---|---|---|
| 0 to 2 | 41 | 17 of the 25 publishing | $102,000 |
| 3 | 35 | 12 of 14 | $108,000 |
| 4 to 5 | 12 | 7 of 8 | $145,000 |
| 6+ | 6 | 4 of 4 | $120,000 |

The 0 to 2 band is the largest in his list and most of it clears his floor.
Chime at $105,000 to $145,000 asking two years, Quantum Space at $115,000 to
$145,000 asking two, M&T Bank topping at $143,000 asking two. The same 17 roles
were in the 30 September data when the opposite was written.

That claim came from two roles that happened to be in front of me, Broadridge
under his floor and Crawford Thomas at six years, generalised without counting
the other 126. Two well-chosen examples will make any pattern. Count before
describing a market.

So the targeting is not about clearing the floor, which he already does at two
years. It is about the $43,000 between the 0 to 2 median top and the 4 to 5
median top. Apply at 0 to 2 for volume and speed, and go after 4 and 5
deliberately for the money, leading with throughput rather than dates: 95
vendor assessments, 30 customer questionnaires and eight consecutive months at
100% compliance is what a four-year analyst has on paper, and he did it in
eighteen months. Bob's point, made 1 October, is that the work was what a much
more senior person would have been expected to do, and that is the argument
that wins the stretch rather than a plea about the gap.

Stop saying a one-year gap is arguable and a two-year gap is not. It framed the
whole thing as a concession to negotiate instead of an upside to go and take.

Jonny is in Tampa and open to remote anywhere in the United States, so he keeps
any US location like the others. His distinctive credential is platform
transformation: taking companies off legacy products onto new ones, which he has
done at three of four employers, plus a gross revenue retention turnaround from
roughly 65 to 87 percent across a $50M to $150M ARR portfolio. His blocking
problem, found in the 11 September resume audit, is that nine of sixteen target
roles gate on years spent managing product people.

**His floor and level are settled, as of 29 September.** $200,000 base, Director
through VP Product. Bob confirmed both. Stop asking him to check them: the
documents did on 28 and 29 September and the question is now answered. Treat the
figures in `profiles.json` as decided, like every other floor.

**The headcount is settled, as of 28 September.** At Malwarebytes he had three
direct reports and led a fifteen-person cross-functional team. Bob confirmed it.
The resume currently says only "cross-functional team of 15", which is the worst
of both readings: a generous recruiter infers fifteen reports, a careful one
infers none.

Two different things follow from that, and the distinction decides how a role is
scored:

- **A people-management minimum is answerable.** "4+ years in a people management
  role" or "experience managing product managers" is a yes. He has managed people
  and can say so with a number. Do not rule these out.
- **A scale requirement is not.** "Lead and scale teams of product managers",
  "grow a product organisation", or any posting implying a double-digit direct
  team, reads three reports as small. That is a caveat to name and quote, not a
  silent rule-out, and not something to paper over either.

The fifteen is real leadership and worth stating, but it is influence across
functions rather than reporting lines, and a recruiter screening on headcount
reads those differently. Say which one a posting is asking for.

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

### A guard that checks a key exists has not checked anything

`sweep_doc.js` refuses to build a document with a missing posting link, added on
30 September after five documents went out with none. On 1 October five more
nearly went out with every rule-out link broken, and the guard passed.

The specs passed bare URL strings where `card()` and `ruled()` want a
`[label, url]` pair. `linkLine` rendered its prefix with nothing behind it, so
each rule-out printed CHECK ME and led nowhere. The guard tested
`"link" in r`, the key was present, so it said nothing. The same specs wrote
`why` where `ruled()` reads `reason`, so every rule-out also rendered with no
stated reason, which is an opinion with the evidence stripped out.

Neither fault was visible in the prose and neither failed the build. What found
them was counting hyperlinks in the finished `.docx` and comparing against the
number the spec should have produced. Bob's had three where seven were due.

The guard now validates the shape the renderer actually consumes: a two-element
array, a non-empty label, a URL that starts with http. It requires `reason` on
every rule-out, and when it finds `why` instead it says so by name. It was
checked by running it against the broken specs and watching it reject all eight
faults before any fix was applied.

The general rule: a guard should assert the thing the consumer needs, not the
thing the producer happened to write. And count the output. Prose reads fine
with a dead link in it.

### The delta key is company plus title, so a company rename reads as new

`role_key()` is company plus title rather than URL, because employers relist the
same job under a fresh requisition id every few days and a URL key would call
each relist a new find. It does not survive the company changing its name. On
1 October a Trinity Life Sciences role first seen 29 September came back as
Trinity Partners, same band, same text, and counted as new. Bob's four new roles
were really three.

It does not survive a parent and a subsidiary posting the same job either. On
2 October a Head of Product at $225,000 to $300,000 in New York arrived twice,
once as TKO and once as On Location, with identical bands, identical locations
and identical requirement text, because On Location is TKO's events and
hospitality business. Bob's six new roles were really five. That is the second
rename in two days.

Not worth fixing by fuzzy-matching company names, which would start merging
genuinely different employers. Worth knowing when a count looks surprising:
check whether two entries share a band and a title before reporting a number.
Two rows with the same band and the same title are one job until proven
otherwise, whatever the company field says.

### A guard nobody has watched fail is not a guard

The send workflow's exit-code policy, the thing that stops a late cron going
red when the day is already delivered, was written on 28 September, reviewed,
merged, and never executed once. GitHub runs a `run:` block as `bash -e {0}`,
so errexit is on before the first line, and the script's `set -uo pipefail`
does not clear it: `set` turns named options on or off and says nothing about
the rest. send.py exited 2, bash killed the script on that line, and every
line below it, the entire policy, was unreachable. Three crons went red for
the one reason that is not a problem, and the `::error::` branch never printed
either, so the red X came with no explanation at all.

Two things to take from it. A conditional that has never been observed running
is not tested, it is hoped for, and CI passing says nothing because CI was not
exercising it. And when a fix does not appear to work, check whether it ran at
all before assuming it ran and was wrong.

`tools/mail/test_workflow_gate.py` now lifts the Send step's script out of the
YAML and runs it under `bash -e` with a stubbed send.py, so the policy is
executed on every pull request rather than read. Five of its eight tests fail
if the `set +e` is removed, which is the only reason to trust the other three.

### Every superlative has to be computed, not felt

"The highest band I have seen for you", "the best fit in two days", "the only
role that does X" are claims about the whole dataset, and the only honest way
to make one is to sort the data and look. On 30 September Edan's document said
Legora's $230,000 to $300,000 was the highest band I had seen for him in two
days of sweeping. Eight roles carried over from yesterday beat it at the
ceiling, none of them gated out on years, and the error survived the document
build, the link check and the em dash check because none of those reads meaning.
It was caught by sorting his 299 rows by `band_high` and reading the top of the
list, which takes one line of Python.

Superlatives are worth making, because they are what turns a list into advice.
Just compute them. And when a superlative is true only of a subset, say which
subset: "the best band of today's eight" is a different and much weaker claim
than "the best band in your list", and the reader is entitled to know which one
they are being given.

The same discipline applies to requirements. Broadridge's posting says
"Minimum of 1-3 years"; the document said "one year asked, which you clear
outright", which quietly turned a range Robbie sits inside into a bar he had
cleared. Quote the posting's own words for anything load bearing.

It applies hardest to claims about the shape of a market, which are superlatives
wearing a different hat. On 30 September Robbie's document described a squeeze:
roles that take his tenure price below his floor, roles above his floor want
years he lacks. It came from two roles that happened to be open on the page in
front of me and it was wrong about the other 126. Counting took one query and
showed the largest band in his list sitting at nought to two years with most of
it clearing his floor. Bob caught it eleven days later by asking why so many of
the roles wanted three to five years.

A market claim needs a count, a cross-tabulation, or both. Two well-chosen
examples will make any pattern you like, which is exactly why they are not
evidence of one.

### Count jobs, not postings

`tools/sweep/dedupe.py`, run as `python3 tools/sweep/dedupe.py <sweep dir>
--floor-only`. Quote the distinct figure it prints and nothing else.

On 3 October Bob's document would have said 34 roles clear his floor. Three
pairs in those 34 were one job advertised twice, so the honest figure was 31.
The day before, the same three pairs were in his list and the document said 31
when the truth was 28, and two of those three pairs were already written down
in the section above as known. Knowing about a duplicate does not subtract it
from a count.

Three shapes, all now seen in real data:

| Shape | Example |
|---|---|
| a rename | Trinity Life Sciences became Trinity Partners |
| a parent and its subsidiary | TKO and On Location; Dassault Systemes and Medidata |
| an agency beside its client | Clearbrook posting Argo's Omaha role, byte-identical |

The third is the most common and the easiest to miss, because the two company
names have no visible relationship at all.

The test is not the company name. Two rows are one job when they share a title
**and** a published band **and** their descriptions agree above 0.80. The band
requirement is load bearing: "Chief Technology Officer" with no band appears
across sixteen real employers in Bob's list, and merging those would be a worse
error than the miscount. Nothing sits near the threshold, so it is not a tuned
number: the true pairs score 1.00, 0.90 and 0.90, and the pairs that share a
title and a round band while being genuinely different score 0.04 and 0.03.

When the evidence is short of proof, say so rather than merging quietly.
Purple Squirrel and Impruvon carried the same title, the same band to the
dollar and the same location, and Purple Squirrel's own text says applications
sent directly to its client are redirected back to it. Almost certainly one
job, not provably so, so Jonny's document said exactly that and the count left
them separate.

### Read bands from the resolved table, never from memory

Resolve every role once into a table keyed by URL, carrying its URL, its
formatted band and its location, then build the document and the email from
that table. On 3 October five bands typed straight into the specs were wrong,
including Monstro at $336,000 to $399,000 and Squarespace at $108,000, both
written as "not published". Squarespace was Robbie's first recommendation and
its published figure is $13,500 above his floor, so "not published" was not a
cosmetic slip. The previous day's documents had all five right, which is the
tell: the error arrives when a second document is written from memory of the
first instead of from the data.

A flat band needs collapsing in the formatter, or a role paying one figure
renders as "$130,000 - $130,000". And when a correction changes a band, reread
the prose around it: fixing the Monstro cell left a sentence saying "No band,
so same first question as Harris Allied" two lines below the band.

### Never estimate a band, and never trust the parsed one

The rule has always been to quote only what the posting says and to write "not
published" rather than guess. On 2 October I broke it in a way the rule did not
obviously cover. Doppel published "$120,000-140,000 OTE", and Jeff's document
said the base "could be anywhere from $95,000 to $115,000 with the rest
variable". Those two numbers appear nowhere in the posting. I made them up from
a plausible OTE split and the hedging made it worse rather than better, because
a number in a document gets remembered and the hedge does not.

So the rule, stated so it covers this: a dollar figure may appear in a document
only if it is in the posting's text, in the scored band for that posting, is the
candidate's floor, or is arithmetic on those. Nothing else. If the posting's
comp is ambiguous, say what the ambiguity is. Doppel in fact publishes the same
two figures twice, once labelled OTE and once labelled "Salary Range", which
makes the base genuinely unanswerable from the text. That is more useful to Jeff
than any estimate, and it is true.

The parsed band is not the posting either. Three of 2 October's bands were wrong
in `*_scored.json`:

| Posting | Parsed | What the posting says |
|---|---|---|
| Zocks | $130,000 flat | "$130,000-150,000K base salary", the top dropped over the stray K |
| Chime | $309,000 low | "base salary ... will begin at $326,000", $17,000 higher |
| Seneca Gaming | $58,883 flat band | "Salary Starting Rate $58,883.30", negotiable, no top published |

A flat band where low equals high usually means the parser found one number, not
that the employer published one. Read the comp sentence before describing it.

So the check, `tools/check_figures.py`: extract every dollar figure from every
built document and every email body, and trace each one to posting text, a
parsed band, the candidate's floor, or an arithmetic difference between those.

    python3 tools/check_figures.py --scored <sweep dir> \
      --doc bob=Bob/....docx --html bob=<outbox>/rshaker2@gmail.com.html ...

Three outcomes, not two, and the middle one is the point. **traced** to a linked
posting, silent. **review**, traceable only to the candidate's wider list,
printed but not failed. **untraced**, failed.

Be clear about what it earns, because the first version of this entry claimed
more. It does not reliably fail the error that prompted it. Run against the
original faulty document, the invented $95,000 and $115,000 land in *review*,
not untraced, because three other roles in Jeff's own list have a $95,000 band
endpoint and one has $115,000. Round salary numbers inside a candidate's range
nearly always coincide with something. The untraced tier catches a figure pulled
from nowhere; an invented round number surfaces in review, and only if somebody
reads it.

So read the review lines instead of skipping to the exit code. Exit zero means
no figure was baseless, not that every figure is right.

Two true things land in review and both are worth the noise. A statistic
computed across the whole list traces only if the document prints its operands:
Robbie's $43,000 traced in the document, which shows "$102,000 vs $145,000", and
failed in the email, which described the two medians in words without them. That
failure was the check working. **Write the operands next to a derived figure, in
the email as well as the document**, or the reader is asked to take it on trust.
The other is a band belonging to a role the document names but does not link,
like the three two-year roles quoted at Robbie.

An earlier version of the check was worse than useless on exactly this: it
allowed the difference between *any* two band endpoints in the candidate's list,
and across a hundred-odd bands those differences form a set dense enough to
excuse almost any round number. The invented $95,000 is $185,000 minus a $90,000
floor. Deltas are now restricted to operands that appear on the page.

Midpoints count, but only of one posting's own band. "The middle of this range
is $96,500" about a published $85,000 to $108,000 is arithmetic a document
legitimately does, and the delta rule had no room for it. The first attempt
allowed the midpoint of any two permitted figures and that quietly defeated the
whole check: the invented $115,000 from the Doppel error is exactly halfway
between a $90,000 floor and a $140,000 band top. A test now pins that
coincidence so the rule cannot drift back.

Second-order arithmetic is where to stop extending the script and fix the
sentence instead. Robbie's email said a band midpoint was "$2,000 clear"
without his floor on the page; rather than teach the check about differences of
midpoints, the sentence now gives both numbers. If a figure is hard to trace
mechanically, it is usually hard for the reader to check too, which is the
better reason to rewrite it.

Run it every day, after the build and before the queue, against the documents
**and** the email bodies. `tools/test_check_figures.py` pins the behaviour,
including the weaknesses above, so the limits are executable rather than
remembered.

### Bob's figures, canonical, confirmed 1 October

Five documents in this repo disagreed about Bob's career numbers, and a figure
being in a document he wrote is not the same as it being sourced. On 1 October he
walked through each one. These are the confirmed facts; take numbers from here
rather than from any resume, dossier or CV.

| Arc | Figure | Where |
|---|---|---|
| Build | zero to $100M | managed detection and response, Symantec |
| Build | zero to $10M | incident response, Symantec |
| Build | zero to $10M | cyber insurance center, Symantec |
| Build | zero to $10M, to profitability | MDR, Malwarebytes |
| Growth | $150M to $250M | managed network forensics, Symantec |
| Portfolio outcome | reached $500M | the overall Symantec business, as a result |
| Launches | 12 across his career, 5 of them at Symantec | both true, different scopes |

Bob added the Symantec managed detection and response build, zero to $100M, on
1 October after the first version of this table was written. It is the largest
single build on his record and it also makes the $500M total add up, which the
earlier figures did not quite do. The highlights bullet had said "built three
businesses from zero to $10M", which capped him at $10M while the experience
section below showed the $100M build, so the summary contradicted the detail and
understated him by $90M. Fixed the same day.

His degree year was also removed. He went back to school after working for many
years, so a 2004 date sat on the same page as a claim of 30+ years and invited
arithmetic it did not answer. Nobody hiring at this level needs the year.
| Employers | four PE-backed businesses | Trellix, Malwarebytes, Symantec, ActiveState |

Symantec counts as PE-backed because Silver Lake invested $500M while it was
public and led from inside the board. Worth knowing because a cybersecurity
reader will remember Symantec as NASDAQ-listed and may ask. Also worth keeping
Silver Lake's $500M well away from the $500M business figure on any one page,
since they are different things that happen to share a number.

**What went wrong, so it does not repeat.** The old CV said "Scaled 4 PE-backed
businesses from $10M to $500M+", which welded an employer count onto a revenue
range and used $10M as a starting point when it is the endpoint of the builds.
No business went from $10M to $500M. On 30 September that line was partly
rewritten to "$0M to $100M+ and from $100M to $250M+", which was also wrong in
both halves: the builds reached $10M, not $100M, and the growth arc starts at
$150M, not $100M. That error was propagated from his resume into a note drafted
for a recruiter before he caught it.

The lesson is narrow and worth holding. When a figure is load bearing, source it
to the engagement that produced it, not to another document that may also be
wrong. Asking "is this the same businesses or separate ones" was the right
question about the $250M and the wrong question to stop at, because it took the
$100M on either side as given.

`Bob/superseded/` and `Bob/Shaker_Executive_Product_Search_Dossier.docx` still
carry the old $10M to $500M range. They are left as they are, because an archive
should record what was actually written. Do not quote them.

### Published posts live in the candidate's folder, not in narratives/

`tools/sweep/narratives/` is interview preparation and the builder renders it
into the opening section of the person's document. Anything a candidate has
actually published goes in their own folder instead, dated, with a note on what
was deliberately left out. `Robbie/LinkedIn_Open_To_Work_01Oct.md` is the first.
The CI check also requires every filename in `narratives/` to be a profile key,
so a second file for one person cannot go there regardless.

Read a candidate's published post before writing anything public for them again.
The reasons something was omitted are recorded with it, and a later draft that
helpfully restores an omission can contradict what is already live.

### The ActiveState narrative goes first, for the people who have one

`tools/sweep/narratives/` holds one file per candidate who was in the
28 September reduction: `jonny.md`, `edan.md`, `robbie.md`. ActiveState
restructured around AI that day and cut about half the company, roughly twenty
people across every function. Bob sent each of those three their own narrative
by email the same evening.

If a file exists for the profile you are building, render it as the opening
section of that person's document, ahead of the market finding. Use the
headings as written and keep the quoted narrative text exact. Those are the
words they are rehearsing for live interviews, so a paraphrase is worse than
useless.

No file means no section, and the list of who gets one is not hard-coded
anywhere. Bob has no narrative because he is still at ActiveState, and Jeff was
never there. Deleting a file is how the section stops appearing once someone
has landed.

The one-document-per-person rule applies here with no exceptions. Each file
carries its owner's own record and their own reference framing, so no part of
one person's narrative belongs in anyone else's document.

## Step 4: commit, then queue the email

Commit the three documents to a `claude/` branch, push, open a draft PR.

**Never type a job URL into an email body.** Resolve every link by looking it
up in that candidate's scored data, keyed on a company and title fragment, and
fail the build if the lookup does not return exactly one row. On 30 September
six of fifteen links in the five drafted emails were req ids I had typed from
memory, and every one of them was for a role new that day, so no amount of
re-reading the prose would have caught it. `sweep_doc.js` already refuses to
build a document with a missing link; the email step is hand-written HTML and
had no such guard, which is exactly why it failed. The rule is mechanical:
if a URL is not in the data, it does not go in the email.

Delivery is a separate step and it does NOT happen here. Do not try to send
mail. A GitHub Actions job does that at 13:00 UTC, an hour after this run.
What this step owes it is a queued email:

1. Make a directory `outbox/<YYYY-MM-DD>/` using today's date in
   America/New_York. The directory, not a single `.html` file, is what tells
   the sender to write to each person separately.
2. Inside it write one `<address>.html` per candidate, named after the exact
   address in `tools/sweep/profiles.json`:

   ```
   outbox/2026-09-28/
     rshaker2@gmail.com.html
     rshaker2@gmail.com.files/Bob_Shaker_Role_Sweep_28Sep.docx
     edanmejias@gmail.com.html
     edanmejias@gmail.com.files/Edan_Mejias_Role_Sweep_28Sep.docx
     robertshaker3@gmail.com.html
     robertshaker3@gmail.com.files/Robbie_Shaker_Role_Sweep_28Sep.docx
     jgordonwalton@gmail.com.html
     jgordonwalton@gmail.com.files/Jeff_Walton_Role_Sweep_28Sep.docx
   ```

   Each body is self-contained HTML: inline styles, a max-width table wrapper,
   no external CSS and no external images. Two or three short paragraphs about
   that one person, naming the single highest-value move for them this week and
   why. Not a summary of the document. The document is the summary.

   **Write each body as if the reader is the only person receiving it,**
   because they are. No "here is everyone's sweep", no comparisons to the other
   candidates, no mention of who else is on the list. A candidate should not be
   able to tell from their email that anybody else got one.
3. Put that person's .docx, and only that person's, in their `.files/`
   directory. A name a stranger could tell apart in an inbox, for example
   `Bob_Shaker_Role_Sweep_28Sep.docx`.
4. Push `outbox/<YYYY-MM-DD>/` directly to `main`, not to the claude/ branch.
   Scheduled Actions runs always check out the default branch, so a queued
   email on a feature branch is invisible to the sender and nobody gets mail.
   The .docx still go through the PR for review; the queued copies are
   delivery artifacts.
5. Verify with `python3 tools/mail/send.py --dry-run`. It must exit 0, report
   `mode  per recipient, 5 message(s)`, one per profile,
   and show exactly one attachment under each address. If it reports
   `broadcast`, the directory is named wrong and everybody is about to get
   everybody else's mail. Exit 2 means the date or a filename is wrong, or a
   file in the directory is not named after an email address. Fix it before
   finishing.
6. **Dispatch the send workflow yourself. Do not wait for 13:00 UTC.** Once the
   queue is on `main` and the dry run is clean, trigger
   `send-scheduled-email.yml` against `main`. Then confirm it succeeded and
   that a `Sent <date>` commit landed on `main`.

`send_config.yaml` is not consulted in this mode. The filenames in the
directory decide who is written to, so an address that is missing a `.html`
simply does not get mail.

### Why the run dispatches its own send

GitHub's `schedule` cron has never once fired this workflow on time. On 24
September it produced nothing at 13:00 and fired at 17:36, four and a half
hours late, by which point the day had been sent by hand. On 28 September it
produced no scheduled run at all. Both sends happened only because somebody
was awake and pressed the button.

Dispatching from this run removes that dependency. The cron line stays in the
workflow as a backstop, and a late firing is harmless: the sender refuses a
date that already exists in `sent/`, which is exactly what happened on 24
September. The failure mode being designed out is silence, where nobody
receives anything and nobody finds out until someone asks.

## When a run finds nothing new

Say so in one line and send anyway. A day with no new roles is information,
and skipping the email makes the reader wonder whether the job ran.

This matters far more now that it runs daily. `stats["new_today"]` will be
zero or close to it on plenty of days, and that is the honest answer rather
than a reason to pad the document. A short email saying two roles moved and
nothing else did is worth more than a long one that recycles last week.

Never manufacture volume by re-presenting roles the person has already been
sent. It is the single fastest way to make this stop being read.

## Known limits

- The Workday channel covers 14 enterprise tenants
  (`tools/sweep/workday_tenants.txt`). Across 3,028 postings on 22 Sep it
  produced exactly one usable role. It is cheap to run and rarely pays.
  `tools/sweep/wd_probe.py` discovers more tenants if that changes.
- The LinkedIn guest endpoint returns 10 cards per call and caps out around 40
  per query. Widening coverage means more query terms, not more pages.
- The schedule is pinned to UTC. After the 1 Nov 2026 DST change it fires at
  06:00 Eastern until the cron is shifted to `0 12 * * 1,4`.
