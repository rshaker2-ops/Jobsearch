#!/usr/bin/env python3
"""
Tests for the sweep pipeline.

    python3 tools/sweep/test_run.py

Standard library only, no network. Every case here is derived from a bug that
actually shipped or from the real location strings the two channels produce,
so a failure means something that once broke is broken again.
"""

import json
import os
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import run  # noqa: E402  (imports li_sweep and wd_sweep, neither opens a socket on import)

REQUIRED_KEYS = {
    "name", "folder", "email", "headline", "floor", "locations",
    "linkedin_queries", "workday_queries",
    "title_keep", "title_scope", "title_drop",
    "hard_gate", "fit_signal", "drop_seniority",
}


class ProfilesTestCase(unittest.TestCase):
    """profiles.json is the whole configuration surface, so it gets checked hard."""

    def test_every_profile_has_every_key(self):
        for key, profile in run.PROFILES.items():
            missing = REQUIRED_KEYS - set(profile)
            self.assertFalse(missing, f"{key} is missing {sorted(missing)}")

    def test_every_regex_compiles(self):
        for key, profile in run.PROFILES.items():
            for field in ("title_keep", "title_drop", "hard_gate", "fit_signal", "title_scope"):
                pattern = profile[field]
                if not pattern:
                    continue
                try:
                    re.compile(pattern, re.I)
                except re.error as exc:
                    self.fail(f"{key}.{field} does not compile: {exc}")

    def test_floors_are_sane(self):
        for key, profile in run.PROFILES.items():
            floor = profile["floor"]
            self.assertIsInstance(floor, int, f"{key} floor is not an integer")
            self.assertGreater(floor, 10000, f"{key} floor looks like thousands, not dollars")
            self.assertLess(floor, 2000000, f"{key} floor is implausible")

    def test_emails_look_like_addresses(self):
        pattern = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
        for key, profile in run.PROFILES.items():
            self.assertRegex(profile["email"], pattern, f"{key} has a bad email")

    def test_locations_use_known_modes(self):
        known = {"us-any", "ma-ri", "remote-only"}
        for key, profile in run.PROFILES.items():
            unknown = set(profile["locations"]) - known
            self.assertFalse(unknown, f"{key} uses unknown location mode {sorted(unknown)}")

    def test_queries_are_present(self):
        for key, profile in run.PROFILES.items():
            self.assertTrue(profile["linkedin_queries"], f"{key} has no LinkedIn queries")
            self.assertTrue(profile["workday_queries"], f"{key} has no Workday queries")

    def test_folders_exist(self):
        repo = HERE.parents[1]
        for key, profile in run.PROFILES.items():
            self.assertTrue(
                (repo / profile["folder"]).is_dir(),
                f"{key} points at {profile['folder']}, which is not a directory",
            )

    def test_every_profile_resolves(self):
        """
        The crash that would have happened on 24 Sep if the Jeff profile had not
        been merged before the routine ran `run.py jeff`.
        """
        for key in ("bob", "edan", "robbie", "jeff"):
            self.assertIn(key, run.PROFILES, f"{key} is missing from profiles.json")


class LocationTestCase(unittest.TestCase):
    """
    Two bugs live here. Both shipped, both were silent, both are covered.

      1. LinkedIn writes "Austin, TX", not "Austin, Texas, United States".
         Matching only the spelled-out country dropped 235 of 303 US roles.
      2. LinkedIn carries remoteness in the f_WT search flag, not the location
         string, so a remote role still reads "Austin, TX". A remote-only
         profile filtering on the string alone kept 6 of 191.
    """

    def p(self, key):
        return run.PROFILES[key]

    # -- the country, however it is spelled --------------------------------

    def test_us_strings_from_both_channels_are_kept(self):
        for loc in [
            "United States", "New York, United States", "Remote, United States",
            "United States of America : Remote", "USA - Remote", "Remote, USA",
            "USA - Remote - Missouri", "USA - Georgia - Atlanta - Remote",
            "Remote Nationwide", "Remote Kentucky", "Remote Michigan",
            "United States - California - Alameda",
        ]:
            self.assertTrue(run.loc_ok(loc, self.p("bob"), "workday"), loc)

    def test_bare_city_and_state_is_kept(self):
        """The 235 dropped roles."""
        for loc in ["Austin, TX", "San Francisco, CA", "Boston, MA",
                    "Quincy, MA", "Medford, MA", "Addison, TX", "Alpharetta, GA"]:
            self.assertTrue(run.loc_ok(loc, self.p("bob"), "linkedin"), loc)

    def test_foreign_locations_are_rejected(self):
        for loc in ["United Kingdom - Remote", "Remote, Mexico", "Remote Australia",
                    "Canada - Quebec - Remote", "Philippines - Remote",
                    "Saudi Arabia - Remote", "Bengaluru, India",
                    "London, United Kingdom", "Toronto, ON", "Remote, South Africa"]:
            self.assertFalse(run.loc_ok(loc, self.p("bob"), "linkedin"), loc)

    def test_a_us_state_beats_a_country_of_the_same_name(self):
        """Washington and Georgia are both states and countries-ish. States win."""
        for loc in ["Seattle, WA", "Remote Washington", "Atlanta, GA", "Remote Georgia"]:
            self.assertTrue(run.loc_ok(loc, self.p("bob"), "linkedin"), loc)

    # -- remote-only --------------------------------------------------------

    def test_remote_only_honours_the_search_flag(self):
        """The 6-of-191 bug. A remote-flagged search means the city is an address."""
        self.assertTrue(run.loc_ok("Austin, TX", self.p("jeff"), "linkedin", True))
        self.assertTrue(run.loc_ok("San Francisco, CA", self.p("jeff"), "linkedin", True))

    def test_remote_only_rejects_onsite_when_the_flag_is_absent(self):
        self.assertFalse(run.loc_ok("Austin, TX", self.p("jeff"), "linkedin", False))
        self.assertFalse(run.loc_ok("United States", self.p("jeff"), "workday", False))

    def test_remote_only_keeps_explicitly_remote_without_the_flag(self):
        for loc in ["Remote Nationwide", "USA - Remote", "Remote (Pacific Time)"]:
            self.assertTrue(run.loc_ok(loc, self.p("jeff"), "workday", False), loc)

    def test_remote_only_rejects_foreign_even_with_the_flag(self):
        self.assertFalse(run.loc_ok("London, United Kingdom", self.p("jeff"), "linkedin", True))
        self.assertFalse(run.loc_ok("Remote, Mexico", self.p("jeff"), "workday", False))

    # -- the regional preference -------------------------------------------

    def test_ma_ri_profiles_keep_new_england(self):
        for loc in ["Boston, MA", "Providence, RI", "Waltham, MA", "Cambridge, MA"]:
            self.assertTrue(run.loc_ok(loc, self.p("robbie"), "linkedin"), loc)

    def test_empty_location_is_not_an_accident(self):
        self.assertFalse(run.loc_ok("", self.p("bob"), "linkedin"))
        self.assertFalse(run.loc_ok(None, self.p("bob"), "linkedin"))


class BandsTestCase(unittest.TestCase):
    """
    Bands come only from the posting's own text. Reading the whole LinkedIn page
    pulled figures out of the "more jobs like this" sidebar and stapled other
    postings' numbers onto roles that publish none.
    """

    def test_reads_comma_and_k_notation(self):
        self.assertEqual(run.bands("The range is $252,800 - $316,000 a year"), [252800, 316000])
        self.assertEqual(run.bands("Compensation Range: $170K - $210K"), [170000, 210000])

    def test_ignores_figures_outside_a_salary_range(self):
        self.assertEqual(run.bands("a $12 lunch stipend and $5,000,000 in funding"), [])

    def test_no_band_means_empty_not_a_guess(self):
        self.assertEqual(run.bands("Competitive compensation and equity."), [])
        self.assertEqual(run.bands(""), [])
        self.assertEqual(run.bands(None), [])

    def test_values_are_sorted_and_deduplicated(self):
        self.assertEqual(run.bands("$150,000 then $90,000 then $150,000"), [90000, 150000])


class YearsTestCase(unittest.TestCase):
    """
    A stated range means its LOW end is the floor. Reading the high end
    overstates the requirement, and that only changes a verdict when the
    candidate sits between the two, which is where these candidates live.

    Measured against the descriptions already fetched, the old regex
    overstated 47 floors and flipped 14 verdicts:

        bob     41 roles read,  3 overstated,  0 flipped (25 years clears all)
        edan   110 roles read,  7 overstated,  3 flipped
        robbie  33 roles read,  9 overstated,  2 flipped
        jeff   131 roles read, 28 overstated,  9 flipped

    The cases below are the real strings behind those flips.
    """

    def test_a_range_floor_is_its_low_end(self):
        for text, expected, who in [
            # Rapid7, Sonos, OPSWAT. Edan has 4, so a 5 excluded him and a 3 does not.
            ("Bring 3-5+ years of dedicated experience in vulnerability management", 3, "edan"),
            # InComm Vendor Risk Analyst I. Robbie has 1.
            ("Minimum 3 years in financial services, with 1-2 years specifically in risk", 1, "robbie"),
            # Drata and the enablement postings. Jeff has 5.
            ("5 to 8 years in enablement, including building or rebuilding a program", 5, "jeff"),
            ("2 to 4 years of experience in customer success", 2, "jeff"),
        ]:
            found = [int(x) for x in run.YEARS.findall(text) if int(x) <= 25]
            self.assertEqual(min(found), expected, f"{who}: {text}")

    def test_reads_the_stated_floor(self):
        for text, expected in [
            ("5+ years of product management experience", "5"),
            ("12-15+ years across product management", "12"),
            ("3-5+ years of dedicated experience", "3"),
            ("10 or more years of progressive leadership", "10"),
        ]:
            found = [int(x) for x in run.YEARS.findall(text) if int(x) <= 25]
            self.assertEqual(str(min(found)), expected, text)

    def test_company_age_is_not_an_experience_requirement(self):
        """"profitable for over 15 years" was read as a 15-year floor once."""
        text = "We have been profitable for over 15 years. Bring 3+ years of GRC."
        found = sorted(int(x) for x in run.YEARS.findall(text) if int(x) <= 25)
        self.assertEqual(min(found), 3)


class SeenTestCase(unittest.TestCase):
    """The delta that makes a daily cadence readable.

    The search window is 30 days, so a daily run is 97 percent yesterday's
    results. If is_new is wrong, every document repeats itself and the whole
    thing stops being worth opening.
    """

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.saved = run.SEEN_DIR
        run.SEEN_DIR = self.tmp

    def tearDown(self):
        run.SEEN_DIR = self.saved
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_everything_is_new_on_a_first_run(self):
        roles = [{"company": "Acme", "title": "Director, Product"}]
        self.assertEqual(run.mark_seen("bob", roles, "2026-10-01"), 1)
        self.assertTrue(roles[0]["is_new"])
        self.assertEqual(roles[0]["first_seen"], "2026-10-01")

    def test_the_same_role_is_not_new_the_next_day(self):
        first = [{"company": "Acme", "title": "Director, Product"}]
        run.mark_seen("bob", first, "2026-10-01")
        second = [{"company": "Acme", "title": "Director, Product"}]
        self.assertEqual(run.mark_seen("bob", second, "2026-10-02"), 0)
        self.assertFalse(second[0]["is_new"])
        # The date it first appeared survives, so the write-up can say how long
        # a role has been sitting open.
        self.assertEqual(second[0]["first_seen"], "2026-10-01")

    def test_only_the_genuinely_new_role_counts(self):
        day_one = [{"company": "Acme", "title": "Director, Product"}]
        run.mark_seen("bob", day_one, "2026-10-01")
        day_two = [
            {"company": "Acme", "title": "Director, Product"},
            {"company": "Globex", "title": "VP Product"},
        ]
        self.assertEqual(run.mark_seen("bob", day_two, "2026-10-02"), 1)
        self.assertFalse(day_two[0]["is_new"])
        self.assertTrue(day_two[1]["is_new"])

    def test_a_relist_under_a_new_url_is_not_new(self):
        # LinkedIn hands the same job a fresh req id regularly. Keying on the
        # URL would call it new every few days and the reader would see the
        # same role presented as a fresh find.
        run.mark_seen("bob", [{"company": "Acme", "title": "Director, Product",
                               "url": "https://www.linkedin.com/jobs/view/111"}],
                      "2026-10-01")
        relisted = [{"company": "Acme", "title": "Director, Product",
                     "url": "https://www.linkedin.com/jobs/view/999"}]
        self.assertEqual(run.mark_seen("bob", relisted, "2026-10-02"), 0)

    def test_casing_and_whitespace_do_not_make_a_role_new(self):
        run.mark_seen("bob", [{"company": "Acme", "title": "Director, Product"}],
                      "2026-10-01")
        noisy = [{"company": "  ACME ", "title": "  director, PRODUCT  "}]
        self.assertEqual(run.mark_seen("bob", noisy, "2026-10-02"), 0)

    def test_each_candidate_keeps_their_own_history(self):
        # Robbie seeing a role does not mean Edan has seen it. Sharing one file
        # would silently suppress a role for everyone after the first person.
        run.mark_seen("robbie", [{"company": "Acme", "title": "GRC Analyst"}],
                      "2026-10-01")
        edan = [{"company": "Acme", "title": "GRC Analyst"}]
        self.assertEqual(run.mark_seen("edan", edan, "2026-10-02"), 1)

    def test_a_corrupt_history_does_not_kill_the_run(self):
        # Losing a day of delta is a bad document. Crashing is no document.
        open(os.path.join(self.tmp, "bob.json"), "w").write("{not json")
        roles = [{"company": "Acme", "title": "Director, Product"}]
        self.assertEqual(run.mark_seen("bob", roles, "2026-10-01"), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
