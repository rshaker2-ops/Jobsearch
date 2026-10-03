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
import hashlib
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
# Captures the LOW end of a stated range. "12-15+ years" is a twelve year
# floor, not fifteen, and reading it as fifteen wrongly rules out roles for the
# candidates whose gap to the bar is the whole question.
YEARS     = re.compile(
    r"(\d{1,2})(?:\s*[-\u2013to]+\s*\d{1,2})?\s*\+?\s*(?:or more\s*)?(?:years|yrs)", re.I
)
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


# What the posting itself says about where the work happens, as opposed to what
# the search flag claims. Added 3 October 2026 on Bob's instruction: keep
# trusting from_remote_search, but say out loud when a posting never addresses
# location, because that silence is where the bad ones hide.
#
# Every alternative below was copied from a posting that actually arrived in a
# sweep, not invented. The runbook's rule about patterns written against real
# text applies here more than anywhere, because a regex guessing at this would
# quietly mislabel a quarter of Jeff's list.
SAYS_REMOTE = re.compile(
    r"remote[- ]first"                     # Chainguard, Secureframe
    r"|remote[- ]flexible"                 # Blackbaud, in its benefits list
    r"|fully remote"                       # Paylocity
    r"|mix of remote"                      # Madison Logic
    r"|(?:is|as)\s+a\s+remote\s+(?:opportunity|position|role)"   # 1Password
    r"|remote\s+(?:opportunity|position|role)\s+within"           # 1Password
    r"|work\s+(?:remotely|from\s+home)"  # Chainguard, Paylocity
    r"|100%\s+remote"
    r"|no\s+in-?office\s+requirement",   # Paylocity
    re.I)
SAYS_PLACE = re.compile(
    r"fully\s+on-?site"                    # abbott
    r"|operate\s+fully\s+on-?site"        # GS2
    r"|working\s+in-?office"               # Rippling, Secureframe
    r"|in-?office\s+expectation"           # Docusign
    r"|\d+\s+days?\s+(?:a|per)\s+week"   # Docusign, PayPal
    r"|\d+\s+days?\s+in\s+the\s+office" # PayPal
    r"|hybrid\s+work\s+is\s+required"     # Madison Logic
    r"|position\s+is\s+hybrid"             # Illumia
    r"|hybrid\s+work\s+model"              # PayPal
    r"|100%\s+onsite",                      # Fidelity
    re.I)

# A sentence that mentions remote work only to say it is somebody else's.
# Fidelity's posting reads "This transition does not apply to fully remote
# roles", which is boilerplate about the rest of the company and not a claim
# about the advertised job. Without this the classifier called Fidelity a
# conflict and put a remote possibility in front of a reader who had none.
DISCLAIMS = re.compile(r"does not apply to|is not eligible|other than|except for", re.I)
SENTENCE = re.compile(r"[^.!?]+[.!?]|[^.!?]+$")


def location_evidence(desc):
    """One of "remote", "place", "conflict" or "silent".

    "place" rather than "onsite" because hybrid and a three-day week are the
    same answer to Jeff: the job has a location he cannot reach.

    "conflict" is real and not a parser artefact. Secureframe's advert says it
    highly values having employees working in-office and, four lines later,
    calls itself a remote first company. Madison Logic offers a mix of remote
    and hybrid working and then requires hybrid of anyone local. A classifier
    that picked a side would be inventing a decision the employer has not made.

    Read sentence by sentence so a remote phrase can be discounted when its own
    sentence disclaims it. The output is a prompt to go and read the posting,
    never a verdict to quote.
    """
    desc = desc or ""
    remote = place = False
    for sentence in SENTENCE.findall(desc):
        if SAYS_PLACE.search(sentence):
            place = True
        if SAYS_REMOTE.search(sentence) and not DISCLAIMS.search(sentence):
            remote = True
    if remote and place:
        return "conflict"
    if remote:
        return "remote"
    if place:
        return "place"
    return "silent"


def loc_ok(loc, p, ats, from_remote_search=False):
    loc = (loc or "").strip()

    # remote-only means exactly that. Jeff is in Humboldt County, which has no
    # technology employment market at this level, so an on-site role is not a
    # longer commute, it is impossible. Keeping them would fill his list with
    # roles he can never take.
    if "remote-only" in p["locations"]:
        if NON_US.search(loc) and not US_SIGNAL.search(loc):
            return False
        if from_remote_search:
            # The search was filtered to remote, so the city in the location
            # string is usually the employer's address rather than a commute.
            #
            # "Usually" is doing a lot of work and the flag is weaker evidence
            # than its old name (remote_confirmed) claimed. It records only that
            # the row came back from a search with f_WT set; it is not the
            # posting agreeing. On 3 October 2026, 69 of the 113 rows this flag
            # admitted to Jeff's list never used the word remote anywhere in
            # their text, and two postings it waved through said the opposite:
            # CommandLink listed the 24 states it hires in and California was
            # not among them, and Monstro reads as remote here while Bob knows
            # it is four days a week in New York.
            #
            # Still trusted, because dropping it costs Jeff most of his list
            # and LinkedIn's flag is right more often than not. But it is a
            # hint, so the document must read the posting's own words on
            # location for anything it recommends, and say when they are silent.
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


SEEN_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "seen")


def role_key(r):
    """Identity for the seen list.

    The same key the dedupe pass uses, company plus title, rather than the URL.
    Employers relist a job under a new req id often enough that a URL key would
    call the same role new every few days.
    """
    return f"{(r.get('company') or '').lower().strip()}|{r['title'].lower().strip()}"


def mark_seen(key, roles, today):
    """Stamp every role with the date it first appeared, and persist the list.

    The search window is 30 days, so a daily run returns yesterday's results
    shifted by one day: about 97 percent of any run is a repeat. Without this
    the daily document would be almost entirely content the reader has already
    been sent, and they would stop opening it. The flag is what lets the
    document lead with what actually changed.

    Marking happens at sweep time rather than at write-up time, so "new" means
    "not in the previous sweep" rather than "I chose to write about it". Those
    are different questions and only the first one is a fact.
    """
    path = os.path.join(SEEN_DIR, f"{key}.json")
    try:
        history = json.load(open(path))
    except (FileNotFoundError, ValueError):
        history = {}
    for r in roles:
        r["first_seen"] = history.setdefault(role_key(r), today)
        r["is_new"] = r["first_seen"] == today
    os.makedirs(SEEN_DIR, exist_ok=True)
    json.dump(dict(sorted(history.items())), open(path, "w"), indent=1)
    return sum(1 for r in roles if r["is_new"])


def sweep(key, outdir):
    p = PROFILES[key]
    os.makedirs(outdir, exist_ok=True)
    rows, stats = [], {}

    # The whole search phase is cached for the day, for the same reason the
    # descriptions are. It is several minutes of rate-limited calls and it
    # produces the same card list every time it runs on a given date, so a
    # killed sweep that restarts should not pay for it twice. On 30 September
    # that cost 3 to 4 minutes out of every 10 minute window, which is most of
    # the budget spent rediscovering what was already known.
    search_cache = os.path.join(outdir, f".search_{key}_{time.strftime('%Y-%m-%d')}.json")
    try:
        with open(search_cache, encoding="utf-8") as fh:
            rows = json.load(fh)
        print(f"  search phase: {len(rows)} cards from cache", file=sys.stderr, flush=True)
    except (FileNotFoundError, ValueError):
        rows = []

    if not rows:
        rows = _gather(p, key)
        with open(search_cache, "w", encoding="utf-8") as fh:
            json.dump(rows, fh)

    stats["raw"] = len(rows)
    return _score(key, p, rows, stats, outdir)


def _gather(p, key):
    """Every card both channels return, before any filtering."""
    rows = []
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
                # Named for what it is: this row came from a remote-filtered
                # search. Not a confirmation by the posting. See loc_ok.
                x["from_remote_search"] = is_remote_search
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
    return rows


def _score(key, p, rows, stats, outdir):
    """Everything after the two channels have been read: dedupe, filter, read
    each survivor, stamp the delta, write the scored file."""

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

    # ---- declined and excluded --------------------------------------------
    # Two different facts, both permanent, both belonging to the candidate
    # rather than to any one run:
    #
    #   company_block   an employer who has already said no, or who the
    #                   candidate will not work for. Re-presenting one is
    #                   worse than useless: it tells the reader the list was
    #                   not filtered by anyone paying attention.
    #   industry_block  a sector the candidate rules out on principle. Matched
    #                   against the posting's own text rather than the company
    #                   name, because the name rarely says it.
    #
    # Both remove the role rather than demote it, and both are counted so the
    # write-up can say what was dropped. A silent filter that eats a good role
    # is worse than no filter at all.
    blocked = {c.lower().strip() for c in p.get("company_block", [])}
    if blocked:
        before = len(rows)
        rows = [r for r in rows
                if (r.get("company") or "").lower().strip() not in blocked]
        stats["company_blocked"] = before - len(rows)

    # ---- location and seniority ------------------------------------------
    rows = [
        r for r in rows
        if loc_ok(r.get("loc"), p, r.get("ats"), r.get("from_remote_search", False))
    ]
    if p.get("drop_seniority"):
        rows = [r for r in rows if not SENIOR.search(r["title"])]
    stats["after_location"] = len(rows)

    # ---- read every survivor end to end ----------------------------------
    # Fetched descriptions are cached on disk by URL.
    #
    # Reading a posting is the slow part: roughly five a minute, rate limited on
    # purpose. Edan's list is around 300, so an hour of fetching. On 30 September
    # the background runner killed the sweep twice at about ten minutes, and
    # without a cache each restart began at role one and he could never have
    # finished at all.
    #
    # With it, a restart re-reads from disk and only fetches what is missing, so
    # every attempt makes progress instead of repeating the last one.
    cache_dir = os.path.join(outdir, ".desc_cache")
    os.makedirs(cache_dir, exist_ok=True)

    def cached_desc(url, is_workday):
        key = hashlib.sha1((url or "").encode("utf-8")).hexdigest()
        path = os.path.join(cache_dir, f"{key}.txt")
        try:
            with open(path, encoding="utf-8") as fh:
                return fh.read()
        except FileNotFoundError:
            pass
        if is_workday:
            try:
                import wd_detail
                desc = (wd_detail.get(url) or {}).get("desc", "")
            except Exception:
                desc = ""
        else:
            desc, _ = detail(url)
            desc = desc or ""
        # An empty read is not cached: it is usually a transient fetch failure,
        # and caching it would make the miss permanent for the next 30 days.
        if desc:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(desc)
        return desc

    HARD = re.compile(p["hard_gate"], re.I)
    FIT  = re.compile(p["fit_signal"], re.I)
    out = []
    for i, r in enumerate(rows, 1):
        desc = cached_desc(r["url"], r.get("ats") == "workday")
        yrs = [int(x) for x in YEARS.findall(desc) if int(x) <= 25]
        money = bands(desc)
        r.update(desc=desc[:14000], money=money,
                 min_years=min(yrs) if yrs else None,
                 band_low=money[0] if money else None,
                 band_high=money[-1] if money else None,
                 clears_floor=(money[-1] >= p["floor"]) if money else None,
                 hard_gate=bool(HARD.search(desc)),
                 location_evidence=location_evidence(desc),
                 fit=len({x.lower() for x in FIT.findall(desc)}))
        out.append(r)
        if i % 20 == 0:
            print(f"  read {i}/{len(rows)}", file=sys.stderr, flush=True)
    stats["read"] = len(out)

    if p.get("industry_block"):
        IND = re.compile(p["industry_block"], re.I)
        kept, dropped = [], []
        for r in out:
            (dropped if IND.search(r["desc"]) else kept).append(r)
        stats["industry_blocked"] = len(dropped)
        # Keep enough of each excluded role to write it up properly. Dropping
        # them to a name cost a link on 29 September: Bob's document listed
        # IDIQ and FanDuel as removed, and by then their URLs had been thrown
        # away, so he could not check the call. An exclusion he cannot verify
        # is one he cannot overrule.
        stats["industry_blocked_roles"] = [
            {"company": r.get("company"), "title": r["title"],
             "url": r.get("url"), "loc": r.get("loc"),
             "band_low": r.get("band_low"), "band_high": r.get("band_high")}
            for r in dropped]
        out = kept

    stats["new_today"] = mark_seen(key, out, time.strftime("%Y-%m-%d"))
    stats["publish_a_band"] = sum(1 for r in out if r["money"])
    stats["clear_floor"] = sum(1 for r in out if r["clears_floor"])
    stats["hard_gated"] = sum(1 for r in out if r["hard_gate"])

    # Location evidence, counted so the document has to account for it. The
    # silent bucket is the one Bob asked to have called out: a posting that
    # never addresses where the work happens has told you nothing, and the
    # search flag saying remote is not the posting agreeing.
    for bucket in ("remote", "place", "conflict", "silent"):
        stats[f"location_{bucket}"] = sum(
            1 for r in out if r["location_evidence"] == bucket)
    stats["location_silent_new"] = sum(
        1 for r in out if r["location_evidence"] == "silent" and r.get("is_new"))
    stats["location_silent_new_roles"] = [
        {"company": r.get("company"), "title": r["title"], "url": r.get("url"),
         "loc": r.get("loc"), "from_remote_search": r.get("from_remote_search")}
        for r in out if r["location_evidence"] == "silent" and r.get("is_new")]

    out.sort(key=lambda x: (0 if x["clears_floor"] else (1 if x["clears_floor"] is None else 2),
                            x["hard_gate"], -x["fit"], -(x["band_high"] or 0)))
    path = os.path.join(outdir, f"{key}_scored.json")
    json.dump({"profile": key, "generated": time.strftime("%Y-%m-%d"),
               "stats": stats, "roles": out}, open(path, "w"), indent=1)
    print(f"\n{key}: " + "  ".join(f"{k}={v}" for k, v in stats.items()), file=sys.stderr)
    print(path)


if __name__ == "__main__":
    sweep(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else ".")
