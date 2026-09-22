# tools/

Machinery for the twice-weekly role sweep (Monday and Thursday, 07:00 Eastern).

- `sweep/RUNBOOK.md` — what the scheduled run does, step by step. Start here.
- `sweep/profiles.json` — the three candidates' criteria: floors, locations,
  search terms, title filters, disqualifiers. Change criteria here, never in
  the scripts.
- `sweep/run.py` — the pipeline. One profile per invocation; writes scored JSON.
- `sweep/li_sweep.py` — LinkedIn guest jobs endpoint (10 cards per call).
- `sweep/wd_sweep.py`, `wd_detail.py`, `wd_probe.py` — Workday CXS API.
- `sweep/workday_tenants.txt` — 14 verified enterprise tenants.
- `build/lib.js` — docx helpers.
- `build/_example_doc.js` — the 22 Sep document, kept as the house format.

Node deps for the builders: `npm i docx` in a scratch directory.
