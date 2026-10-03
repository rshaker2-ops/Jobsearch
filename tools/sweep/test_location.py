#!/usr/bin/env python3
"""
Tests for location_evidence() in run.py.

Bob's instruction on 3 October 2026 was to keep trusting the LinkedIn remote
flag and call out the postings that say nothing. That only works if the four
buckets are right, so every string below is lifted from a posting that really
arrived in a sweep. A regex guessing at this would mislabel a quarter of
Jeff's list, and the label decides whether he is told a role is reachable.

The classifier agreed with a hand reading of all 18 postings read in full on
3 October. These cases are those readings, kept so a later change has to
reproduce them.
"""

import unittest

from run import location_evidence as ev


class SaysRemote(unittest.TestCase):

    def test_chainguard_remote_first_culture(self):
        self.assertEqual(ev("A Few Of The Benefits We Offer - Flexible & "
                            "Remote-First Culture: Work remotely with team "
                            "meetup opportunities."), "remote")

    def test_blackbaud_remote_flexible_in_a_benefits_list(self):
        """Weaker than a culture statement and still the posting's own word.
        Finding this had moved Blackbaud out of the rule-outs."""
        self.assertEqual(ev("Benefits Include - Medical, dental, and vision "
                            "insurance - Remote-flexible workforce - Wellness "
                            "Programs."), "remote")

    def test_paylocity_fully_remote_no_office_requirement(self):
        self.assertEqual(ev("This is a fully remote position, allowing you to "
                            "work from home or location of record within the "
                            "U.S. with no in-office requirements."), "remote")

    def test_1password_a_remote_opportunity_within_the_us(self):
        self.assertEqual(ev("This is a remote opportunity within the US."),
                         "remote")


class SaysAPlace(unittest.TestCase):

    def test_abbott_fully_onsite(self):
        self.assertEqual(ev("This is a fully onsite role."), "place")

    def test_gs2_fully_on_site_in_houston(self):
        self.assertEqual(ev("Must be willing to operate fully on-site in the "
                            "Houston, TX office to centralize leadership."),
                         "place")

    def test_paypal_three_days_in_the_office(self):
        self.assertEqual(ev("PayPal's balanced hybrid work model offers 3 days "
                            "in the office for effective in-person "
                            "collaboration."), "place")

    def test_docusign_a_weekly_minimum(self):
        self.assertEqual(ev("(Frequency: Minimum 2 days per week; may vary by "
                            "team but will be weekly in-office expectation)"),
                         "place")

    def test_rippling_values_working_in_office(self):
        self.assertEqual(ev("Rippling highly values having employees working "
                            "in-office to foster a collaborative work "
                            "environment and company culture."), "place")

    def test_illumia_hybrid_if_local(self):
        self.assertEqual(ev("This position is hybrid if local to our office in "
                            "Alpharetta, GA or Scottsdale, AZ."), "place")


class SaysBoth(unittest.TestCase):
    """Real and not a parser artefact. A classifier that picked a side would be
    inventing a decision the employer has not made."""

    def test_secureframe_contradicts_itself(self):
        self.assertEqual(ev("Secureframe highly values having employees working "
                            "in-office to foster a collaborative work "
                            "environment. Collaboration, connection, and having "
                            "fun with colleagues is an important part of our "
                            "culture as a remote first company."), "conflict")

    def test_madison_logic_offers_a_mix_then_requires_hybrid_of_locals(self):
        self.assertEqual(ev("Work Environment We offer a mix of remote and "
                            "hybrid working. Remote work arrangements are not "
                            "available for all positions. Hybrid work is "
                            "required for employees local to our offices."),
                         "conflict")


class SaysNothing(unittest.TestCase):
    """The bucket Bob asked to have called out."""

    def test_a_posting_that_never_addresses_location(self):
        self.assertEqual(ev("The Senior Director of Product for Platform "
                            "Services will be responsible for standing up our "
                            "0-1 capabilities. Basic Qualifications: at least "
                            "7 years of Product Management experience."),
                         "silent")

    def test_a_city_in_the_location_field_is_not_in_the_text(self):
        """TechAviv names Dallas in its location field and never uses the word
        remote anywhere. The classifier reads the posting, not the field, so
        this is silent and the document has to say so."""
        self.assertEqual(ev("Customer Success Manager. 3 years of experience "
                            "in a customer facing role."), "silent")

    def test_empty_and_missing_descriptions_are_silent(self):
        self.assertEqual(ev(""), "silent")
        self.assertEqual(ev(None), "silent")


class Disclaimers(unittest.TestCase):

    def test_fidelity_remote_phrase_about_other_roles_does_not_count(self):
        """"This transition does not apply to fully remote roles" is boilerplate
        about the rest of the company. Counting it made Fidelity a conflict and
        put a remote possibility in front of a reader who had none."""
        self.assertEqual(ev("Currently, some roles and locations require 100% "
                            "onsite presence, while others require less. This "
                            "transition does not apply to fully remote roles."),
                         "place")

    def test_a_disclaimed_remote_phrase_alone_is_silent_not_remote(self):
        self.assertEqual(ev("This policy does not apply to fully remote roles."),
                         "silent")

    def test_an_ordinary_remote_sentence_still_counts(self):
        """The guard must not swallow a real statement that happens to sit near
        the word apply."""
        self.assertEqual(ev("Apply today. This is a fully remote position."),
                         "remote")


if __name__ == "__main__":
    unittest.main()
