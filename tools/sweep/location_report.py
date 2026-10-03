#!/usr/bin/env python3
"""
What the postings themselves say about where the work happens.

    python3 tools/sweep/location_report.py <sweep dir> [--profile jeff]

Bob's instruction, 3 October 2026: keep trusting the LinkedIn remote flag,
but call out the postings that never address location. This prints what to
call out.

Why it is a report and not a filter. `from_remote_search` records only that a
row came back from a search with `f_WT` set, and `loc_ok()` uses it to admit
roles that would otherwise fail a remote-only location filter. Measured on
3 October, of Jeff's 117 postings:

    say remote in their own text     14
    say a place (on-site or hybrid)   9   <- admitted by the flag anyway
    say both, and mean it             3
    never address location           91

Dropping the flag would have cost most of his list, so it stays. But those 9
are the CommandLink shape: flagged remote, and the posting names a city or a
number of days. They are the ones worth reading first, and the 91 silent ones
are where the next CommandLink is hiding.

The four buckets come from `location_evidence()` in run.py. Its output is a
prompt to go and read the posting, never a verdict to quote in a document.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from run import PROFILES, location_evidence  # noqa: E402

BUCKETS = ("remote", "place", "conflict", "silent")


def classify(rows):
    out = {b: [] for b in BUCKETS}
    for r in rows:
        out[location_evidence(r.get("desc") or "")].append(r)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("sweep_dir")
    ap.add_argument("--profile", action="append", default=[],
                    help="limit to these profile keys (default: all)")
    ap.add_argument("--new-only", action="store_true",
                    help="only roles new since the last run, which is what a "
                         "document leads on")
    args = ap.parse_args()

    keys = args.profile or sorted(PROFILES)
    print(f"{'':8} {'remote':>7} {'place':>7} {'conflict':>9} {'silent':>7}"
          f"   flagged remote but says a place")
    worth_reading = []
    for key in keys:
        path = Path(args.sweep_dir) / f"{key}_scored.json"
        if not path.exists():
            print(f"{key:8} no scored file")
            continue
        rows = json.loads(path.read_text())["roles"]
        if args.new_only:
            rows = [r for r in rows if r.get("is_new")]
        got = classify(rows)
        # The contradiction worth reading first: the search called it remote
        # and the posting names a place.
        contradicted = [r for r in got["place"] if r.get("from_remote_search")]
        print(f"{key:8} {len(got['remote']):7} {len(got['place']):7} "
              f"{len(got['conflict']):9} {len(got['silent']):7}   "
              f"{len(contradicted)}")
        for r in contradicted:
            worth_reading.append((key, r))
        for r in got["conflict"]:
            worth_reading.append((key, r))

    if worth_reading:
        print("\nRead these before ranking anything. The search said remote and "
              "the posting says otherwise, or says both:")
        for key, r in worth_reading:
            print(f"  {key:8} {(r.get('company') or '')[:26]:26} "
                  f"{r['title'][:38]:38} {r.get('loc')}")
    else:
        print("\nNo posting contradicts the remote flag today.")

    print("\nSay in the document how many of the new roles never address "
          "location. Silence is not a maybe.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
