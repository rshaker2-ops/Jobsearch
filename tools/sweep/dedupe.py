#!/usr/bin/env python3
"""
Collapse postings that are one job advertised twice.

    python3 tools/sweep/dedupe.py <sweep dir> [--floor-only]

The delta key in run.py is company plus title, which survives an employer
relisting under a fresh requisition id but not the company name changing. Two
cases have now cost a wrong count in a document:

  * a rename: Trinity Life Sciences came back as Trinity Partners on 1 October.
  * a parent and its subsidiary: TKO and On Location on 2 October, Dassault
    Systemes and Medidata on 3 October.

A third shape turned up on 3 October and is the most common of the three: an
agency posting a client's job beside the client's own listing. Clearbrook and
Argo carried byte-identical descriptions for the same Omaha role.

So the test is not the company name at all. Two rows are one job when they
share a title and a published band and their descriptions agree. The band
matters: titles like "Chief Technology Officer" with no band repeat sixteen
times across sixteen real employers in Bob's list, and merging those would be
worse than the problem. Text similarity settles the rest, because an agency
rewrites the posting and a subsidiary does not.

Why this is a script and not a habit: the runbook already said to check whether
two entries share a band and a title before reporting a number, and the next
day a document still reported Bob's qualifying set as 31 when 3 of those 31
were duplicates of each other and the honest figure was 28. A count that has
to be remembered is a count that will be wrong.

0.80 is deliberately high. Clearbrook and Argo score 1.00, Dassault and
Medidata 0.90, Thermo Fisher against its own second feed spelling 0.90. The
pairs that share a title and a round band but are genuinely different score
0.04 (Teikametrics against Intec Select) and 0.03 (East Daley against Input
Output), so nothing sits near the threshold and a small move either way
changes no decision.
"""

import argparse
import difflib
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PROFILES = REPO / "tools" / "sweep" / "profiles.json"
SIMILAR_ENOUGH = 0.80
WS = re.compile(r"\s+")


def floors():
    data = json.loads(PROFILES.read_text())
    return {k: v["floor"] for k, v in data.get("profiles", data).items()}


def body(row):
    return WS.sub(" ", row.get("desc") or "")


def same_job(a, b):
    """One job posted twice, rather than two jobs that look alike."""
    if a.get("title", "").strip().lower() != b.get("title", "").strip().lower():
        return False
    # An unpublished band is not evidence of anything: a bare title with no
    # band repeats across unrelated employers constantly.
    if a.get("band_low") is None and a.get("band_high") is None:
        return False
    if (a.get("band_low"), a.get("band_high")) != (b.get("band_low"), b.get("band_high")):
        return False
    return difflib.SequenceMatcher(None, body(a), body(b)).ratio() > SIMILAR_ENOUGH


def collapse(rows):
    """Return (distinct rows, [(kept, dropped), ...]) preserving input order."""
    kept, pairs = [], []
    for row in rows:
        match = next((k for k in kept if same_job(k, row)), None)
        if match is None:
            kept.append(row)
        else:
            pairs.append((match, row))
    return kept, pairs


def qualifying(rows, floor):
    """Not hard gated, and the top of the band reaches the floor."""
    return [r for r in rows
            if not r.get("hard_gate") and (r.get("band_high") or 0) >= floor]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("sweep_dir")
    ap.add_argument("--floor-only", action="store_true",
                    help="only the roles that clear the floor, which is what a "
                         "document quotes")
    args = ap.parse_args()

    f = floors()
    total = 0
    for key in sorted(f):
        path = Path(args.sweep_dir) / f"{key}_scored.json"
        if not path.exists():
            print(f"{key:8} no scored file")
            continue
        rows = json.loads(path.read_text())["roles"]
        if args.floor_only:
            rows = qualifying(rows, f[key])
        distinct, pairs = collapse(rows)
        total += len(pairs)
        label = "qualifying" if args.floor_only else "read"
        print(f"{key:8} {len(rows):4} {label}, {len(distinct):4} distinct, "
              f"{len(pairs)} duplicate(s)")
        for a, b in pairs:
            print(f"         {b['company'][:30]} is {a['company'][:30]} "
                  f"again: {a['title'][:44]}")
    print(f"\n{total} duplicate posting(s) in all. Quote the distinct figure.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
