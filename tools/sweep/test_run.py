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
import sys
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


if __name__ == "__main__":
    unittest.main(verbosity=2)
