#!/usr/bin/env python3
"""
Two-channel role sweep: LinkedIn guest endpoint + Workday CXS API.

  python3 tools/sweep/run.py <profile> [outdir]

Emits <outdir>/<profile>_scored.json -- every survivor with its full posting
text, its published band (if any) and a stated experience floor. Ranking and
prose are NOT done here: a human or an agent reads the requirements. See
tools/sweep/RUNBOOK.md.

Two defects this pipeline exists to avoid, both found the hard way:

  1. Bands are read ONLY from the posting's own text. Scanning the whole
     LinkedIn page pulls figures out of the "more jobs like this" sidebar
     and staples other postings' numbers onto roles that publish none.
  2. Nothing is ranked on title plus band. A "Chief Technology Officer"
     paying $400k that turns out to require writing Python daily is a rule
     out, not a lead. The requirements decide.
"""
import json, os, re, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from li_sweep import search, detail
import wd_sweep

HERE = os.path.dirname(os.path.abspath(__file__))
PROFILES = json.load(open(os.path.join(HERE, "profiles.json")))

# A location counts as United States if it names the country, a state, or says
# nationwide. Written against the strings the two channels actually produce:
# LinkedIn gives "Austin, TX" far more often than "Austin, Texas, United
# States", and Workday gives "Remote Kentucky", "USA - Remote - Missouri" and
# "United States of America : Remote" alongside "United Kingdom - Remote".
STATES = (
    "alabama|alaska|arizona|arkansas|california|colorado|connecticut|delaware|"
    "florida|georgia|hawaii|idaho|illinois|indiana|iowa|kansas|kentucky|"
    "louisiana|maine|maryland|massachusetts|michigan|minnesota|mississippi|"
    "missouri|montana|nebraska|nevada|new hampshire|new jersey|new mexico|"
    "new york|north carolina|north dakota|ohio|oklahoma|oregon|pennsylvania|"
    "rhode island|south carolina|south dakota|tennessee|texas|utah|vermont|"
    "virginia|washington|west virginia|wisconsin|wyoming"
)
US_SIGNAL = re.compile(
    r"united states|\bu\.?s\.?a\.?\b|\bnationwide\b|\b(" + STATES + r")\b"
    r"|,\s*(A[LKZR]|C[AOT]|D[EC]|FL|GA|HI|I[DLNA]|K[SY]|LA|M[EDAINSOT]|"
    r"N[EVHJMYCD]|O[HKR]|PA|RI|S[CD]|T[NX]|UT|V[TA]|W[AVIY])\s*$",
    re.I,
)
# Only consulted when there is no US signal, so "Washington" or "Georgia" as a
# US state still wins over the country of the same name.
NON_US = re.compile(
    r"united kingdom|\bu\.?k\.?\b|canada|mexico|australia|philippines|india|"
    r"saudi|ireland|germany|france|spain|netherlands|poland|singapore|japan|"
    r"china|brazil|argentina|colombia|south africa|israel|sweden|norway|"
    r"denmark|finland|switzerland|austria|belgium|portugal|italy|romania|"
    r"czech|hungary|greece|turkey|egypt|kenya|nigeria|pakistan|bangladesh|"
    r"vietnam|thailand|malaysia|indonesia|korea|taiwan|hong kong|new zealand|"
    r"costa rica|chile|peru|uruguay|emirates|qatar|kuwait|bahrain|jordan|"
    r"lithuania|latvia|estonia|bulgaria|croatia|serbia|ukraine|slovakia",
    re.I,
)
REMOTEISH = re.compile(r"\bremote\b|\banywhere\b|work from home", re.I)
MA     = re.compile(r"\b(boston|cambridge|massachusetts|\bma\b|waltham|burlington|somerville|"
                    r"newton|quincy|providence|rhode island|\bri\b|medford|lexington|needham)\b", re.I)
SENIOR    = re.compile(r"\b(senior|sr\.?|lead|ii|iii|iv|principal|staff)\b", re.I)
YEARS     = re.compile(r"(\d{1,2})\s*\+?\s*(?:or more\s*)?(?:years|yrs)", re.I)
MONEY     = re.compile(r"\$\s?(\d{2,3}(?:,\d{3})|\d{2,3}(?:\.\d)?\s?[kK])\b")


def bands(text):
    """Salary figures stated inside the posting text. Never from page chrome."""
    out = []
    for m in MONEY.finditer(text or ""):
        s = m.group(1).replace(",", "").strip()
        v = float(s[:-1].strip()) * 1000 if s[-1] in "kK" else float(s)
        if 40000 <= v <= 1500000:
            out.append(int(v))
    return sorted(set(out))


def loc_ok(loc, p, ats, remote_confirmed=False):
    loc = (loc or "").strip()

    # remote-only means exactly that. Jeff is in Humboldt County, which has no
    # technology employment market at this level, so an on-site role is not a
    # longer commute, it is impossible. Keeping them would fill his list with
    # roles he can never take.
    if "remote-only" in p["locations"]:
        if NON_US.search(loc) and not US_SIGNAL.search(loc):
            return False
        if remote_confirmed:
            # The search itself was filtered to remote, so the city in the
            # location string is the employer's address, not a commute.
            return bool(US_SIGNAL.search(loc)) or not loc
        return bool(REMOTEISH.search(loc))

    # Everyone else keeps any US location, remote or on-site. Bob's call, 22 Sep.
    if US_SIGNAL.search(loc):
        return True
    if NON_US.search(loc):
        return False
    if "ma-ri" in p["locations"] and MA.search(loc):
        return True
    return bool(REMOTEISH.search(loc))


def sweep(key, outdir):
    p = PROFILES[key]
    os.makedirs(outdir, exist_ok=True)
    rows, stats = [], {}

    # ---- channel A: LinkedIn guest endpoint -------------------------------
    locs = ["United States"] + (["Boston, Massachusetts, United States"]
                                if "ma-ri" in p["locations"] else [])
    for q in p["linkedin_queries"]:
        for loc in locs:
            is_remote_search = loc == "United States"
            r = search(q, loc, tpr="r2592000", remote=is_remote_search, pages=4)
            for x in r:
                x["ats"] = "linkedin"
                # LinkedIn carries remoteness in the f_WT search flag, not in the
                # location string: a remote role still reads "Austin, TX". Without
                # recording the flag, a remote-only profile throws away everything
                # LinkedIn already confirmed was remote.
                x["remote_confirmed"] = is_remote_search
            rows += r
            print(f"  li [{q[:38]:38s}] {loc[:22]:22s} -> {len(r):3d}", file=sys.stderr, flush=True)

    # ---- channel C: Workday CXS across known enterprise tenants ----------
    tenants = [l.strip().split("|") for l in
               open(os.path.join(HERE, "workday_tenants.txt")) if l.strip()]
    for t in tenants:
        for q in p["workday_queries"]:
            try:
                rows += wd_sweep.search(t[0], t[1], t[2], q)
            except Exception as e:
                print(f"  wd {t[0]}/{q}: {e}", file=sys.stderr)
    stats["raw"] = len(rows)

    # Two passes. The URL catches the same posting returned by several queries;
    # company plus title catches an employer listing one job twice under
    # different req ids, which LinkedIn does often enough to matter.
    by_url = {}
    for r in rows:
        by_url.setdefault(r.get("url") or (r["company"], r["title"]), r)
    by_job = {}
    for r in by_url.values():
        by_job.setdefault(
            ((r.get("company") or "").lower().strip(), r["title"].lower().strip()), r
        )
    rows = list(by_job.values())
    stats["unique"] = len(rows)

    # ---- title filter -----------------------------------------------------
    K = re.compile(p["title_keep"], re.I)
    D = re.compile(p["title_drop"], re.I)
    S = re.compile(p["title_scope"], re.I) if p["title_scope"] else None
    rows = [r for r in rows if K.search(r["title"]) and not D.search(r["title"])
            and (not S or S.search(r["title"]))]
    stats["after_title"] = len(rows)

    # ---- location and seniority ------------------------------------------
    rows = [
        r for r in rows
        if loc_ok(r.get("loc"), p, r.get("ats"), r.get("remote_confirmed", False))
    ]
    if p.get("drop_seniority"):
        rows = [r for r in rows if not SENIOR.search(r["title"])]
    stats["after_location"] = len(rows)

    # ---- read every survivor end to end ----------------------------------
    HARD = re.compile(p["hard_gate"], re.I)
    FIT  = re.compile(p["fit_signal"], re.I)
    out = []
    for i, r in enumerate(rows, 1):
        if r.get("ats") == "workday":
            try:
                import wd_detail
                d = wd_detail.get(r["url"]) or {}
                desc = d.get("desc", "")
            except Exception:
                desc = ""
        else:
            desc, _ = detail(r["url"])
            desc = desc or ""
        yrs = [int(x) for x in YEARS.findall(desc) if int(x) <= 25]
        money = bands(desc)
        r.update(desc=desc[:14000], money=money,
                 min_years=min(yrs) if yrs else None,
                 band_low=money[0] if money else None,
                 band_high=money[-1] if money else None,
                 clears_floor=(money[-1] >= p["floor"]) if money else None,
                 hard_gate=bool(HARD.search(desc)),
                 fit=len({x.lower() for x in FIT.findall(desc)}))
        out.append(r)
        if i % 20 == 0:
            print(f"  read {i}/{len(rows)}", file=sys.stderr, flush=True)
    stats["read"] = len(out)
    stats["publish_a_band"] = sum(1 for r in out if r["money"])
    stats["clear_floor"] = sum(1 for r in out if r["clears_floor"])
    stats["hard_gated"] = sum(1 for r in out if r["hard_gate"])

    out.sort(key=lambda x: (0 if x["clears_floor"] else (1 if x["clears_floor"] is None else 2),
                            x["hard_gate"], -x["fit"], -(x["band_high"] or 0)))
    path = os.path.join(outdir, f"{key}_scored.json")
    json.dump({"profile": key, "generated": time.strftime("%Y-%m-%d"),
               "stats": stats, "roles": out}, open(path, "w"), indent=1)
    print(f"\n{key}: " + "  ".join(f"{k}={v}" for k, v in stats.items()), file=sys.stderr)
    print(path)


if __name__ == "__main__":
    sweep(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else ".")
