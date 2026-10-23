"""What happened to a liquor-licence application after it left the pending list.

A compact, in-memory version of the production event spine's resolution step. The production
spine (SQLite event store, typed events, backfill and export) is not published here.

Two facts about the source make this harder than a diff:
  * The issued-licence file publishes one to two business days behind, so a licence that left
    the pending list today usually cannot be matched to its issuance yet. Across the first 34
    licences parked this way, 16 turned out to be approvals: deciding on the day would have been
    wrong 47 percent of the time. Unmatched licences are parked and resolved later, once the
    issued file has published through the day they left.
  * The pending row's licence id can point at a licence already hanging on the wall at an
    existing venue. Six of the first seven backfilled "approvals" were issued years before the
    application was filed. An approval cannot predate its own application.
"""
import datetime

AWAIT_MAX_DAYS = 21


def is_approval(issued_row, submission_date):
    """(approved, issue_date). Rejects an issued licence older than the application."""
    issued = (issued_row.get("original_issue_date") or "")[:10]
    sub = (submission_date or "")[:10]
    if not issued:
        return False, None
    if sub and issued < sub:
        return False, issued
    return True, issued


def watermark(issued_rows):
    """The newest issue date the issued file has actually published."""
    return max(((r.get("original_issue_date") or "")[:10] for r in issued_rows), default="")


def _days(a, b):
    return (datetime.date.fromisoformat(b) - datetime.date.fromisoformat(a)).days


class LicenceTracker:
    def __init__(self):
        self.known = {}       # licence_id -> {"submitted": date, "awaiting_since": date | None}
        self.resolved = {}    # licence_id -> (event, effective_date)

    def observe(self, day, pending, issued_rows):
        """One daily snapshot. `pending` maps licence_id -> submission date. Returns new events."""
        issued = {r["license_id"]: r for r in issued_rows}
        mark = watermark(issued_rows)
        events = []

        for lic, submitted in pending.items():
            if lic in self.resolved:
                continue
            rec = self.known.setdefault(lic, {"submitted": submitted, "awaiting_since": None})
            # Back on the pending list: whatever we parked it for did not happen. Without this
            # reset a licence that dropped off for a day and returned was later reported as
            # having left pending (found in the 2026-10-23 publication review).
            rec["awaiting_since"] = None

        for lic, rec in self.known.items():
            if lic in self.resolved or lic in pending:
                continue
            if rec["awaiting_since"] is None:
                rec["awaiting_since"] = day
            row = issued.get(lic)
            ok, eff = is_approval(row, rec["submitted"]) if row else (False, None)
            if ok:
                event = ("application_approved", eff)
            elif (mark and mark >= rec["awaiting_since"]) or _days(rec["awaiting_since"], day) >= AWAIT_MAX_DAYS:
                # The issued file now covers the day this licence vanished, so its absence is a
                # finding. Withdrawal, denial and a re-file under a new id look identical from
                # here, which is why the event name says only what was observed.
                event = ("left_pending_without_issued_match", rec["awaiting_since"])
            else:
                continue
            self.resolved[lic] = event
            events.append((lic,) + event)
        return events
