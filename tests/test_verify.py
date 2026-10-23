"""Regression tests for the join rules. Each class is one historical failure.

Every test asserts two things: the current code gives the right answer, and the defective
version in defects.py gives the wrong answer it gave in production. The second assertion is
what shows the test would have caught the bug.
"""
import json
import os
import unittest
from unittest import mock

from pilot_light import verify, match as match_mod
from pilot_light.verify import signals, accept, trade_overlap, expect_rows, SourceHealthError
from tests import defects

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCENARIOS = {s["title"]: s for s in json.load(open(os.path.join(ROOT, "examples", "fixtures.json")))["scenarios"]}
STANDALONE = SCENARIOS["A restaurant in its own building"]
CENTRE = SCENARIOS["A restaurant in a shopping centre"]


def decisions(scenario, accept_fn=None, census_fn=None):
    """Run the real calling path, optionally with one function swapped for its defective form."""
    patches = []
    if accept_fn:
        patches.append(mock.patch.object(match_mod, "accept", accept_fn))
    if census_fn:
        patches.append(mock.patch.object(match_mod, "building_census", census_fn))
    for p in patches:
        p.start()
    try:
        return {cid: ok for cid, ok, _, _ in match_mod.match(scenario["venue"], scenario["candidates"])}
    finally:
        for p in patches:
            p.stop()


class SingleKeyJoins(unittest.TestCase):
    """2026-08-14: name-token matching alone was a 93 percent false positive."""

    def test_one_distinctive_word_is_not_a_match(self):
        self.assertFalse(decisions(STANDALONE)["a3"])
        self.assertTrue(decisions(STANDALONE, accept_fn=defects.accept_any_single_key)["a3"])


class AddressIsNeverASignal(unittest.TestCase):
    """2026-08-14: an address fallback attributed a chain's officer to a cafe in its building."""

    def test_previous_business_at_same_address_is_rejected(self):
        self.assertFalse(decisions(STANDALONE)["a4"])
        self.assertTrue(decisions(STANDALONE, accept_fn=defects.accept_address_counts)["a4"])


class MultiTenantBuildings(unittest.TestCase):
    """2026-08-14: same-building tenants inflated construction coverage from 6.8 to 16.5 percent."""

    def test_neighbours_in_a_shopping_centre_are_rejected(self):
        d = decisions(CENTRE)
        self.assertFalse(d["b2"])
        self.assertFalse(d["b4"])
        self.assertTrue(decisions(CENTRE, accept_fn=defects.accept_address_counts)["b2"])

    def test_same_owner_in_another_suite_is_rejected(self):
        # Entity and trade name both agree and the city matches, so only the suite rule stops it.
        self.assertFalse(decisions(CENTRE)["b6"])
        self.assertTrue(decisions(CENTRE, accept_fn=defects.accept_without_suite_rule)["b6"])

    def test_the_same_suite_is_accepted(self):
        self.assertTrue(decisions(CENTRE)["b1"])

    def test_known_cost_same_company_without_a_suite_is_rejected(self):
        # The rule's price, kept visible on purpose: a true match whose permit omits the suite
        # is lost. Production accepted this trade for precision.
        self.assertFalse(decisions(CENTRE)["b5"])


class GenericWords(unittest.TestCase):
    """Two unrelated places sharing only GRILL or CAFE were scored as the same trade name."""

    def test_generic_words_do_not_agree(self):
        self.assertEqual(trade_overlap("Quillfeather Grill", "Marrowbend Grill"), 0.0)
        self.assertGreater(defects.trade_overlap_with_generic("Quillfeather Grill", "Marrowbend Grill"), 0.0)


class NamesOnlyAcrossCities(unittest.TestCase):
    """Found 2026-10-23 in publication review: entity and trade name both come from names, so a
    same-named business in another city passed the two-signal rule."""

    def test_same_names_in_another_city_are_rejected(self):
        self.assertFalse(decisions(STANDALONE)["a2"])
        self.assertTrue(decisions(STANDALONE, accept_fn=defects.accept_without_city_rule)["a2"])

    def test_same_names_same_city_still_accepted(self):
        self.assertTrue(decisions(STANDALONE)["a1"])

    def test_tax_id_plus_entity_needs_no_city(self):
        sig = signals(STANDALONE["venue"], cand_entity="Juniper Smokehouse Holdings",
                      cand_taxid="32000000001", venue_taxid="32000000001", cand_city="El Paso")
        self.assertEqual(sig, {"ENTITY", "TAXID"})
        self.assertTrue(accept(sig)[0])

    def test_person_name_counts_as_a_name_signal(self):
        venue = STANDALONE["venue"]
        kw = dict(cand_entity="Juniper Smokehouse Holdings", cand_person="Sample, Alex",
                  venue_people=venue["people"])
        same_city = signals(venue, cand_city="Austin", **kw)
        other_city = signals(venue, cand_city="El Paso", **kw)
        self.assertIn("PERSON", same_city)
        self.assertTrue(accept(same_city)[0])
        self.assertEqual(accept(other_city), (False, "names_only_no_city"))


class DistinctTenantCensus(unittest.TestCase):
    """Found 2026-10-23 in publication review: the census counted rows, so one tenant filed twice
    made a two-tenant building look like a shopping centre and suppressed a true match."""

    def setUp(self):
        venue = dict(CENTRE["venue"])
        rows = [c for c in CENTRE["candidates"] if c["id"] in ("b1", "b2", "b3")]
        self.scenario = {"venue": venue, "candidates": rows}

    def test_duplicate_filing_counts_once(self):
        census = verify.building_census(self.scenario["candidates"], lambda r: r["address"],
                                        lambda r: r["city"], match_mod.tenant_name)
        self.assertEqual(list(census.values()), [2])

    def test_true_match_survives_in_a_two_tenant_building(self):
        b5 = dict(next(c for c in CENTRE["candidates"] if c["id"] == "b5"))
        self.scenario["candidates"].append(b5)
        self.assertTrue(decisions(self.scenario)["b5"])
        self.assertFalse(decisions(self.scenario, census_fn=defects.building_census_rows)["b5"])


class SilentZeroResults(unittest.TestCase):
    """2026-08-14: three pulls returned zero rows instead of failing."""

    def test_zero_rows_raise(self):
        with self.assertRaises(SourceHealthError):
            expect_rows(0, "permits")
        self.assertEqual(defects.expect_rows_silent(0, "permits"), 0)

    def test_zero_row_page_mid_pagination_raises(self):
        with self.assertRaises(SourceHealthError):
            verify.advance_by(0, 1000, "construction records")

    def test_capped_page_advances_by_rows_returned(self):
        log = []
        self.assertEqual(verify.advance_by(100, 1000, "construction records", log.append), 100)
        self.assertTrue(log)


if __name__ == "__main__":
    unittest.main()
