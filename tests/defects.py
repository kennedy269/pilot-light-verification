"""The defective behaviours the regression tests must catch.

Each one is labelled PRESERVED (the production code as it stood, copied without change),
ADAPTED (the production rule, rewritten only to fit this module's interfaces), or RECONSTRUCTED
(rebuilt from the failure log, because the original version was replaced the same day and not
kept). A test passes only when the current code behaves correctly AND the defective
version produces the historical wrong answer, which proves the test would have caught it.
"""
from pilot_light.normalize import addr_key
from pilot_light.verify import toks, MULTI_TENANT_THRESHOLD
from pilot_light import transitions


def accept_any_single_key(sig, *, building_count=1):
    """RECONSTRUCTED, before 2026-08-14: one agreeing field was enough. Name-token matching on
    this rule produced 261 matches, of which 18 survived address checks."""
    real = {s for s in sig if not s.startswith("_")}
    return (len(real) >= 1, "any")


def accept_address_counts(sig, *, building_count=1):
    """RECONSTRUCTED, before 2026-08-14: when names failed, an address fallback attributed the
    record anyway, which is how a corporate officer of a chain in the same building was
    attributed to an unrelated cafe."""
    real = {s for s in sig if not s.startswith("_")}
    return (len(real) >= 2 or "_ADDRESS" in sig, "address_fallback")


def accept_without_city_rule(sig, *, building_count=1):
    """ADAPTED, production until 2026-10-23: two name-derived signals passed with no check that
    the records were in the same city. Production had no _CITY diagnostic; it is ignored here."""
    real = sig - {"_ADDRESS", "_CITY"}
    if building_count >= MULTI_TENANT_THRESHOLD and "SUITE" not in real:
        return False, "multi_tenant_no_suite"
    return (len(real) >= 2, "two_keys")


def accept_without_suite_rule(sig, *, building_count=1):
    """RECONSTRUCTED, before 2026-08-14: no suite check in shared buildings, so an operator's
    second location in the same centre was attributed to the first."""
    real = {s for s in sig if not s.startswith("_")}
    return (len(real) >= 2, "two_keys")


def trade_overlap_with_generic(a, b):
    """RECONSTRUCTED: generic words like GRILL and CAFE counted as distinctive."""
    ta, tb = toks(a, drop_generic=False), toks(b, drop_generic=False)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / min(len(ta), len(tb))


def building_census_rows(rows, addr_of, city_of, tenant_of=None):
    """PRESERVED, production until 2026-10-23, apart from the unused tenant_of argument that the
    current signature needs: counted rows, so one tenant filed twice counted as two."""
    c = {}
    for r in rows:
        k = addr_key(addr_of(r), city_of(r))
        if k:
            c[k] = c.get(k, 0) + 1
    return c


def expect_rows_silent(n, label, minimum=1):
    """RECONSTRUCTED, before 2026-08-14: a zero-row pull returned quietly. A field name that did
    not exist and a double-encoded '%' each produced an empty result that looked like no data."""
    return n


def is_approval_any_issued(issued_row, submission_date):
    """RECONSTRUCTED, 2026-08-17: any issued licence with the matching id was an approval, so a
    licence issued in 2009 'approved' an application filed in 2026."""
    d = (issued_row.get("original_issue_date") or "")[:10]
    return (bool(d), d or None)


class SameDayTracker(transitions.LicenceTracker):
    """RECONSTRUCTED: decides on the day a licence leaves pending, ignoring the publishing lag."""

    def observe(self, day, pending, issued_rows):
        issued = {r["license_id"]: r for r in issued_rows}
        events = []
        for lic, submitted in pending.items():
            self.known.setdefault(lic, {"submitted": submitted, "awaiting_since": None})
        for lic, rec in self.known.items():
            if lic in self.resolved or lic in pending:
                continue
            row = issued.get(lic)
            ok, eff = transitions.is_approval(row, rec["submitted"]) if row else (False, None)
            event = ("application_approved", eff) if ok else ("left_pending_without_issued_match", day)
            self.resolved[lic] = event
            events.append((lic,) + event)
        return events


class NoResetTracker(transitions.LicenceTracker):
    """ADAPTED, production until 2026-10-23: the event spine's rule, rewritten into this tracker
    form. A parked licence that reappeared on the pending list kept its parked date and was later
    reported as having left."""

    def observe(self, day, pending, issued_rows):
        issued = {r["license_id"]: r for r in issued_rows}
        mark = transitions.watermark(issued_rows)
        events = []
        for lic, submitted in pending.items():
            self.known.setdefault(lic, {"submitted": submitted, "awaiting_since": None})
        for lic, rec in self.known.items():
            if lic in self.resolved:
                continue
            if lic not in pending and rec["awaiting_since"] is None:
                rec["awaiting_since"] = day
            if rec["awaiting_since"] is None:
                continue
            row = issued.get(lic)
            ok, eff = transitions.is_approval(row, rec["submitted"]) if row else (False, None)
            if ok:
                event = ("application_approved", eff)
            elif mark and mark >= rec["awaiting_since"]:
                event = ("left_pending_without_issued_match", rec["awaiting_since"])
            else:
                continue
            self.resolved[lic] = event
            events.append((lic,) + event)
        return events
