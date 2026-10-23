"""Regression tests for licence resolution. All records are synthetic."""
import unittest

from pilot_light.transitions import LicenceTracker, is_approval
from tests import defects


def issued(lic, date):
    return {"license_id": lic, "original_issue_date": date}


class LicenceAlreadyOnTheWall(unittest.TestCase):
    """2026-08-17: six of the first seven backfilled approvals were licences issued years before
    the application was filed."""

    def test_older_licence_is_not_an_approval(self):
        self.assertFalse(is_approval(issued("L1", "2009-03-02"), "2026-07-30")[0])
        self.assertTrue(defects.is_approval_any_issued(issued("L1", "2009-03-02"), "2026-07-30")[0])

    def test_licence_issued_after_filing_is_an_approval(self):
        self.assertEqual(is_approval(issued("L1", "2026-08-12"), "2026-07-30"), (True, "2026-08-12"))


class PublishingLag(unittest.TestCase):
    """The issued file runs one to two business days behind. Deciding on the day was wrong for
    16 of the first 34 licences."""

    def run_days(self, tracker):
        out = []
        out += tracker.observe("2026-08-17", {"L7": "2026-07-20"}, [issued("X", "2026-08-14")])
        # L7 leaves pending on the 18th; the issued file has only published through the 14th.
        out += tracker.observe("2026-08-18", {}, [issued("X", "2026-08-14")])
        # On the 20th the issued file catches up and shows L7 issued on the 18th.
        out += tracker.observe("2026-08-20", {}, [issued("X", "2026-08-14"), issued("L7", "2026-08-18")])
        return out

    def test_approval_is_found_after_the_lag(self):
        self.assertEqual(self.run_days(LicenceTracker()), [("L7", "application_approved", "2026-08-18")])

    def test_deciding_on_the_day_reports_a_withdrawal(self):
        self.assertEqual(self.run_days(defects.SameDayTracker())[0][1], "left_pending_without_issued_match")

    def test_absence_becomes_a_finding_once_the_file_covers_that_day(self):
        t = LicenceTracker()
        t.observe("2026-08-17", {"L8": "2026-07-20"}, [issued("X", "2026-08-14")])
        self.assertEqual(t.observe("2026-08-18", {}, [issued("X", "2026-08-14")]), [])
        out = t.observe("2026-08-21", {}, [issued("X", "2026-08-19")])
        self.assertEqual(out, [("L8", "left_pending_without_issued_match", "2026-08-18")])


class NoIssuedFileUpdate(unittest.TestCase):
    """If the issued file stops advancing, a parked licence is still resolved after 21 days."""

    def test_parked_licence_resolves_after_21_days(self):
        t = LicenceTracker()
        stuck = [issued("X", "2026-08-14")]
        t.observe("2026-08-17", {"L5": "2026-07-20"}, stuck)
        t.observe("2026-08-18", {}, stuck)
        self.assertEqual(t.observe("2026-09-07", {}, stuck), [])
        self.assertEqual(t.observe("2026-09-08", {}, stuck),
                         [("L5", "left_pending_without_issued_match", "2026-08-18")])


class LicenceReappears(unittest.TestCase):
    """Found 2026-10-23 in publication review: a licence that dropped off the pending list for a
    day and came back was later reported as having left."""

    def run_days(self, tracker):
        out = []
        out += tracker.observe("2026-08-17", {"L9": "2026-07-20"}, [issued("X", "2026-08-14")])
        out += tracker.observe("2026-08-18", {}, [issued("X", "2026-08-14")])
        out += tracker.observe("2026-08-19", {"L9": "2026-07-20"}, [issued("X", "2026-08-15")])
        out += tracker.observe("2026-08-22", {"L9": "2026-07-20"}, [issued("X", "2026-08-20")])
        return out

    def test_reappearing_licence_produces_no_event(self):
        self.assertEqual(self.run_days(LicenceTracker()), [])

    def test_old_logic_reports_it_as_gone(self):
        out = self.run_days(defects.NoResetTracker())
        self.assertEqual([e[1] for e in out], ["left_pending_without_issued_match"])


if __name__ == "__main__":
    unittest.main()
