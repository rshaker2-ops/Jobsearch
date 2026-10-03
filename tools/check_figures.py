#!/usr/bin/env python3
"""
Trace every dollar figure in a built document or email body back to a source.

    python3 tools/check_figures.py --scored DIR [--doc PATH ...] [--html PATH ...]

Exists because of 2 October. Jeff's document said the base at Doppel "could be
anywhere from $95,000 to $115,000 with the rest variable", off a posting that
published only "$120,000-140,000 OTE". Neither number is anywhere in the
posting. I made them up from a plausible OTE split, and the document build, the
link guard and the em dash gate all passed it, because none of them reads
meaning. The only thing that catches an invented number is checking where every
number came from.

Three outcomes per figure, not two, because a hard pass/fail got this wrong in
both directions on its first run.

  traced   it is in the text of a posting this document links to, is a band
           endpoint of one, is the candidate's floor, or is the absolute
           difference between any two of those. That last case is how a
           document says "$126,000 above your floor" without that number being
           published anywhere. Silent.

  review   it traces only to the candidate's wider scored data: a band on a
           role this document does not link to, or a difference involving one.
           Printed, not failed. Robbie's document quotes three roles he has not
           been sent and a median computed across all 125, all true and none of
           it visible from the linked postings alone.

  untraced it matches nothing at all. Failed.

What this does not do, stated plainly so nobody trusts it further than it goes:
it does not reliably fail the error that prompted it. Run against the original
faulty document, the invented $95,000 and $115,000 land in review rather than
untraced, because three other roles in Jeff's own list have a $95,000 band
endpoint and one has $115,000. Round salary numbers inside a candidate's range
nearly always coincide with something. The untraced tier catches a figure pulled
out of nowhere; the review tier is where an invented round number actually
surfaces, and only if somebody reads it.

So: run it after the build and before queueing, and read the review lines
instead of skipping to the exit code. Exit zero means no figure was baseless,
not that every figure is right. The review tier is also where a figure quoted
at the wrong role shows up, which is the reason for scoping to linked postings
at all.

Two kinds of true figure legitimately land in review, and both are worth the
noise. A statistic computed over the candidate's whole list, like the $43,000
between two medians in Robbie's document, traces only if the document prints
the two medians it came from; his email stated the gap in words without them
and failed, which is the check earning its keep rather than misfiring. And a
band belonging to a role the document mentions but does not link, like the three
two-year roles quoted at Robbie, is true and invisible from the linked postings.

One thing the script cannot judge at all: a round number offered as advice
rather than as fact. Jeff's document said "if the base is $100,000 or better",
a threshold nothing in the data set and not a claim about any posting. Read as
review, which is the best this can do. The honest version tied it to his floor.
"""

import argparse
import json
import re
import sys
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PROFILES = REPO / "tools" / "sweep" / "profiles.json"

# Four digits or more, so a "3+ years" or a "$5" never enters the check. Every
# figure the documents quote is a salary, and salaries are four digits up.
FIGURE = re.compile(r"\$([\d,]{4,})")
TAG = re.compile(r"<[^>]+>")
LINK_IN_RELS = re.compile(r'Target="(https?://[^"]+)"')
LINK_IN_HTML = re.compile(r'href="(https?://[^"]+)"')


def floors():
    data = json.loads(PROFILES.read_text())
    data = data.get("profiles", data)
    return {k: v["floor"] for k, v in data.items()}


def scored(directory, key):
    """Rows for one profile, keyed by URL, from <dir>/<key>_scored.json."""
    path = Path(directory) / f"{key}_scored.json"
    if not path.exists():
        sys.exit(f"no scored data at {path}")
    return {r["url"]: r for r in json.loads(path.read_text())["roles"]}


def docx_text_and_links(path):
    """A .docx keeps external hyperlinks in document.xml.rels, not in the body,
    so both parts have to be read. Learned the hard way on 1 October, when a
    link count taken from document.xml alone came back zero and looked like a
    build failure."""
    with zipfile.ZipFile(path) as z:
        body = z.read("word/document.xml").decode()
        rels = z.read("word/_rels/document.xml.rels").decode()
    return TAG.sub(" ", body), LINK_IN_RELS.findall(rels)


def html_text_and_links(path):
    raw = Path(path).read_text()
    return TAG.sub(" ", raw), LINK_IN_HTML.findall(raw)


def check(text, links, rows, floor):
    """Split the figures into traced, review and untraced.

    Deltas are computed over the posting's own text figures as well as its
    parsed band, because the two disagree more often than you would like. Chime
    published "will begin at $326,000" while the band field held $309,000, and
    the document's "$17,000 above what the band field captured" is arithmetic on
    one of each. A delta set built from parsed bands alone called it invented.
    """
    linked = [u for u in links if u in rows]
    if not linked:
        # No resolved posting means no sources, so nothing can trace. Returning
        # review here instead would let a document whose links all broke pass
        # having verified nothing. main() prints the specific reason; this keeps
        # check() honest for any other caller.
        return [], [], [], sorted({int(m.replace(",", ""))
                                   for m in FIGURE.findall(text)})

    def figures_in(blob):
        return {int(m.replace(",", "")) for m in FIGURE.findall(blob)}

    near_text = " ".join((rows[u].get("desc") or "") for u in linked)
    near = figures_in(near_text) | {
        int(v)
        for u in linked
        for v in (rows[u].get("band_low"), rows[u].get("band_high"))
        if v
    } | {floor}

    wide = {
        int(v)
        for r in rows.values()
        for v in (r.get("band_low"), r.get("band_high"))
        if v
    } | near

    def midpoints(rows_in_scope):
        """The middle of one posting's own band, and nothing else.

        "The middle of this range is $96,500" about a band of $85,000 to
        $108,000 is a figure a document legitimately computes, and the delta
        rule had no room for it. But allowing the midpoint of any two allowed
        figures is far too generous: the invented $115,000 from the Doppel
        error is exactly halfway between a $90,000 floor and a $140,000 band
        top, so a first version of this rule waved through the error the whole
        script exists to catch. A midpoint only counts when both halves are
        the two ends of a single published band.

        Halves are rounded the way a document writes them, so an odd span
        yields both neighbours rather than neither.
        """
        out = set()
        for r in rows_in_scope:
            lo, hi = r.get("band_low"), r.get("band_high")
            if lo and hi and lo != hi:
                out.add((int(lo) + int(hi)) // 2)
                out.add(-(-(int(lo) + int(hi)) // 2))
        return out

    near_deltas = ({abs(a - b) for a in near for b in near}
                   | midpoints([rows[u] for u in linked]))

    # Deltas over the wide set are restricted to operands that appear in this
    # document, and the restriction is load bearing. Unrestricted, the pairwise
    # differences across a hundred-odd band endpoints form a set dense enough to
    # excuse almost any round number: the invented $95,000 from the Doppel error
    # is exactly $185,000 minus a $90,000 floor, and a first version of this
    # check waved it through on that coincidence. A real cross-dataset delta is
    # written with its operands on the page, because that is the only way it
    # means anything to the reader: "$102,000 vs $145,000" and then "the
    # $43,000". An invented figure has no operands anywhere near it.
    on_page = figures_in(text)
    wide_operands = (wide & on_page) | {floor}
    wide_deltas = ({abs(a - b) for a in wide_operands for b in wide_operands}
                   | midpoints(rows.values()))

    traced, review, untraced = [], [], []
    for raw in sorted(figures_in(text)):
        if raw in near or raw in near_deltas:
            traced.append(raw)
        elif raw in wide or raw in wide_deltas:
            review.append(raw)
        else:
            untraced.append(raw)
    return linked, traced, review, untraced


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scored", required=True,
                    help="directory holding <key>_scored.json per profile")
    ap.add_argument("--doc", action="append", default=[], metavar="KEY=PATH",
                    help="a built .docx, as profile key and path")
    ap.add_argument("--html", action="append", default=[], metavar="KEY=PATH",
                    help="an email body, as profile key and path")
    args = ap.parse_args()

    f = floors()
    failed = False
    for spec, reader, kind in ((args.doc, docx_text_and_links, "docx"),
                              (args.html, html_text_and_links, "html")):
        for item in spec:
            if "=" not in item:
                sys.exit(f"expected KEY=PATH, got {item!r}")
            key, path = item.split("=", 1)
            if key not in f:
                sys.exit(f"{key} is not a profile in {PROFILES}")
            text, links = reader(path)
            rows = scored(args.scored, key)
            linked, traced, review, bad = check(text, links, rows, f[key])
            total = len(traced) + len(review) + len(bad)
            # A document with figures but no resolved link has nothing to check
            # against, so every figure falls to the review tier and the run
            # passes having verified nothing. That is the 30 September link
            # failure wearing this script's clothes, so it fails here instead.
            if total and not linked:
                failed = True
                print(f"FAIL {kind} {key} {Path(path).name}: {total} figure(s) "
                      f"but not one of its {len(links)} link(s) resolved against "
                      f"{key}'s scored data, so nothing was verified")
                continue
            if bad:
                failed = True
                print(f"FAIL {kind} {key} {Path(path).name}: "
                      f"{len(bad)} figure(s) trace to nothing")
                for v in bad:
                    print(f"       ${v:,}")
            else:
                print(f"ok   {kind} {key} {Path(path).name}: "
                      f"{total} figure(s), {len(linked)} linked posting(s), "
                      f"{len(traced)} traced, {len(review)} for review")
            for v in review:
                print(f"     review ${v:,}  not in a linked posting; "
                      f"check it is quoted at the right role")

    if failed:
        print("\nA figure that traces to nothing is either invented or a typo. "
              "Find where it came from before sending.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
