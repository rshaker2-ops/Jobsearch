#!/usr/bin/env python3
"""
Tests for tools/sweep/dedupe.py.

Driven by the three real shapes that cost a wrong count in a document, and by
the two pairs that look like duplicates and are not. The near misses matter as
much as the hits: a dedupe that merges sixteen unrelated Chief Technology
Officer postings would be worse than the miscount it was built to stop.
"""

import unittest

from dedupe import collapse, qualifying, same_job


def row(company, title, low=None, high=None, desc="", gate=False):
    return {"company": company, "title": title, "band_low": low,
            "band_high": high, "desc": desc, "hard_gate": gate,
            "url": f"https://example.test/{company}".replace(" ", "")}


BODY = "Own the platform roadmap. " * 40
OTHER = "Deliver utility scale solar projects. " * 40


class RealShapes(unittest.TestCase):

    def test_agency_posting_a_clients_job(self):
        """Clearbrook and Argo, 3 October: byte-identical descriptions."""
        a = row("Argo", "Risk Analyst", 65000, 102000, BODY)
        b = row("Clearbrook", "Risk Analyst", 65000, 102000, BODY)
        self.assertTrue(same_job(a, b))

    def test_parent_and_subsidiary(self):
        """Dassault Systemes and Medidata, and TKO and On Location: the
        subsidiary runs the parent's copy with a little of its own."""
        a = row("Dassault Systemes", "SVP, Product", 252750, 337000, BODY)
        b = row("Medidata Solutions", "SVP, Product", 252750, 337000,
                BODY[:int(len(BODY) * 0.88)] + "Medidata is part of the group.")
        self.assertTrue(same_job(a, b))

    def test_same_company_two_feed_spellings(self):
        """Thermo Fisher Scientific against thermofisher."""
        a = row("Thermo Fisher Scientific", "Director, Software Product Management",
                192100, 256100, BODY)
        b = row("thermofisher", "Director, Software Product Management",
                192100, 256100, BODY)
        self.assertTrue(same_job(a, b))


class NearMisses(unittest.TestCase):

    def test_same_title_and_round_band_but_different_jobs(self):
        """Teikametrics and Intec Select both posted a Chief Technology Officer
        at $200,000 to $250,000 and scored 0.04 on text. Different jobs."""
        a = row("Teikametrics", "Chief Technology Officer", 200000, 250000, BODY)
        b = row("Intec Select", "Chief Technology Officer", 200000, 250000, OTHER)
        self.assertFalse(same_job(a, b))

    def test_a_bare_title_with_no_band_is_not_evidence(self):
        """Sixteen real employers advertise Chief Technology Officer with no
        band in Bob's list. Merging those would be the worse error."""
        a = row("Foodsmart", "Chief Technology Officer", None, None, BODY)
        b = row("Hot Topic", "Chief Technology Officer", None, None, BODY)
        self.assertFalse(same_job(a, b))

    def test_a_different_band_is_a_different_job(self):
        a = row("A", "VP Product", 200000, 250000, BODY)
        b = row("B", "VP Product", 200000, 260000, BODY)
        self.assertFalse(same_job(a, b))

    def test_a_different_title_is_a_different_job(self):
        a = row("A", "VP Product", 200000, 250000, BODY)
        b = row("A", "VP Engineering", 200000, 250000, BODY)
        self.assertFalse(same_job(a, b))


class Collapsing(unittest.TestCase):

    def test_the_first_row_is_kept_and_order_survives(self):
        rows = [row("Argo", "Risk Analyst", 65000, 102000, BODY),
                row("Clearbrook", "Risk Analyst", 65000, 102000, BODY),
                row("Other", "GRC Analyst", 80000, 100000, OTHER)]
        distinct, pairs = collapse(rows)
        self.assertEqual([r["company"] for r in distinct], ["Argo", "Other"])
        self.assertEqual([(a["company"], b["company"]) for a, b in pairs],
                         [("Argo", "Clearbrook")])

    def test_three_copies_of_one_job_collapse_to_one(self):
        rows = [row(c, "Head of Product", 225000, 300000, BODY)
                for c in ("TKO", "On Location", "TKO Events")]
        distinct, pairs = collapse(rows)
        self.assertEqual(len(distinct), 1)
        self.assertEqual(len(pairs), 2)

    def test_nothing_to_collapse_returns_the_input(self):
        rows = [row("A", "VP Product", 200000, 250000, BODY),
                row("B", "VP Product", 300000, 350000, OTHER)]
        distinct, pairs = collapse(rows)
        self.assertEqual(len(distinct), 2)
        self.assertEqual(pairs, [])


class Qualifying(unittest.TestCase):

    def test_the_band_top_must_reach_the_floor(self):
        rows = [row("Under", "A", 57300, 82000), row("Over", "B", 85000, 108000)]
        self.assertEqual([r["company"] for r in qualifying(rows, 94500)], ["Over"])

    def test_a_hard_gated_role_never_qualifies(self):
        rows = [row("Gated", "A", 300000, 400000, gate=True)]
        self.assertEqual(qualifying(rows, 94500), [])

    def test_no_published_band_never_qualifies(self):
        """Deliberate: a document cannot say an unpublished band clears a floor,
        so the count of roles clearing the floor must not include it."""
        rows = [row("Unpublished", "A", None, None)]
        self.assertEqual(qualifying(rows, 94500), [])


if __name__ == "__main__":
    unittest.main()
