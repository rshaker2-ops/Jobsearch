#!/usr/bin/env python3
"""
Tests for tools/check_figures.py.

The runbook's rule is that a guard nobody has watched fail is not a guard, so
these drive the real check() with the real 2 October fault in it and assert it
comes back untraced. The three-tier split is also pinned, because the first
version of this script was a hard pass/fail and it was wrong in both directions
on its first run: it called Jonny's correct "$126,000 above your floor" invented,
and it would have failed Robbie's document for quoting medians computed across
his whole list.
"""

import unittest

from check_figures import check

FLOOR = 90000

# A posting shaped like Doppel's: OTE and a Salary Range carrying the same two
# figures, which is what made the base unanswerable from the text.
DOPPEL = {
    "url": "https://example.test/doppel",
    "desc": ("Why Join Doppel - $120,000-140,000 OTE - Meaningful equity. "
             "Salary Range: $120,000 USD - $140,000 USD"),
    "band_low": 120000,
    "band_high": 140000,
}
# A role in the candidate's list that this document does not link to.
ELSEWHERE = {
    "url": "https://example.test/elsewhere",
    "desc": "Compensation $160,000 to $185,000",
    "band_low": 160000,
    "band_high": 185000,
}
ROWS = {DOPPEL["url"]: DOPPEL, ELSEWHERE["url"]: ELSEWHERE}
LINKS = [DOPPEL["url"]]


def run(text, links=LINKS, rows=None, floor=FLOOR):
    return check(text, links, rows if rows is not None else ROWS, floor)


class FigureTracing(unittest.TestCase):

    def test_the_doppel_fault_is_untraced(self):
        """The actual 2 October error: a base range estimated off an OTE label."""
        _, _, _, bad = run("the base could be anywhere from $95,000 to $115,000")
        self.assertEqual(bad, [95000, 115000])

    def test_a_figure_quoted_from_the_posting_traces(self):
        _, traced, review, bad = run("published at $120,000 to $140,000 OTE")
        self.assertEqual((traced, review, bad), ([120000, 140000], [], []))

    def test_the_floor_traces(self):
        _, traced, _, bad = run("against your $90,000 floor")
        self.assertIn(FLOOR, traced)
        self.assertEqual(bad, [])

    def test_a_difference_against_the_floor_traces(self):
        """"$30,000 above your floor" is 120,000 minus 90,000 and is published
        nowhere, which is why deltas are allowed at all."""
        _, traced, _, bad = run("the floor is $30,000 above yours")
        self.assertIn(30000, traced)
        self.assertEqual(bad, [])

    def test_a_figure_in_the_posting_text_but_not_the_band_traces(self):
        """Chime's case. The posting said base begins at $326,000 while the band
        field held $309,000, and "$17,000 above what the band field captured" is
        arithmetic across one of each. A delta set built from parsed bands alone
        called that invented."""
        row = {"url": "https://example.test/chime",
               "desc": "base salary will begin at $326,000 and up to $383,000",
               "band_low": 309000, "band_high": 383000}
        _, traced, _, bad = run("which is $17,000 above what the band captured",
                                links=[row["url"]], rows={row["url"]: row})
        self.assertIn(17000, traced)
        self.assertEqual(bad, [])

    def test_a_band_from_an_unlinked_role_is_review_not_failure(self):
        """Robbie's document quotes three roles he has not been sent. True, and
        invisible from the linked postings, so it is for review rather than a
        failure."""
        _, traced, review, bad = run("elsewhere on your list, $185,000")
        self.assertEqual(review, [185000])
        self.assertEqual(bad, [])

    def test_review_and_failure_are_distinguished_in_one_pass(self):
        _, _, review, bad = run("$185,000 elsewhere, and I guessed $47,500")
        self.assertEqual(review, [185000])
        self.assertEqual(bad, [47500])

    def test_small_numbers_are_ignored(self):
        """"5+ years" and "$5" must not enter the check, or every document fails
        on its own requirement quotes."""
        _, traced, review, bad = run("asks 5+ years and 3 to 5 years of it")
        self.assertEqual((traced, review, bad), ([], [], []))

    def test_an_unlinked_document_fails_every_figure(self):
        """A document whose links did not resolve has no sources at all, so the
        check degrades to failing loudly rather than passing vacuously."""
        _, traced, review, bad = run("$120,000 to $140,000", links=[])
        self.assertEqual(traced, [])
        self.assertEqual(bad, [120000, 140000])


if __name__ == "__main__":
    unittest.main()


class StatedLimits(unittest.TestCase):
    """Pins what the check does NOT catch, so a later reader does not trust it
    further than it goes. These assert the weakness on purpose; if one starts
    failing because the check got stricter, delete it and say so."""

    def test_an_invented_round_number_matching_another_role_only_reviews(self):
        """The reason this check does not reliably fail the Doppel error. Three
        roles in Jeff's real list have a $95,000 band endpoint, so the invented
        "$95,000 to $115,000" matched one and dropped to review."""
        rows = dict(ROWS)
        coincidence = {"url": "https://example.test/other",
                       "desc": "Range $70,000 to $95,000",
                       "band_low": 70000, "band_high": 95000}
        rows[coincidence["url"]] = coincidence
        _, _, review, bad = run("the base could be anywhere from $95,000",
                                rows=rows)
        self.assertEqual(review, [95000])
        self.assertEqual(bad, [], "known weakness: documented, not fixed")

    def test_a_computed_statistic_needs_its_operands_on_the_page(self):
        """Robbie's $43,000 traces in the document, which prints the two medians,
        and failed in the email, which described them in words. Both correct."""
        rows = {r["url"]: r for r in [
            DOPPEL,
            {"url": "https://example.test/a", "desc": "", "band_low": 90000,
             "band_high": 102000},
            {"url": "https://example.test/b", "desc": "", "band_low": 120000,
             "band_high": 145000}]}
        with_operands = "median top $102,000 vs $145,000, so the $43,000 gap"
        _, _, review, bad = run(with_operands, rows=rows)
        # Review rather than traced, correctly: the two medians are endpoints of
        # roles this document does not link, so the gap is true but unverifiable
        # from the linked postings alone. What matters is that it does not fail.
        self.assertIn(43000, review)
        self.assertEqual(bad, [])

        _, _, _, bad = run("the $43,000 between the two medians", rows=rows)
        self.assertEqual(bad, [43000])
