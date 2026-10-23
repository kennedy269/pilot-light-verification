"""Two-key verification. Every cross-source join runs through this module.

The rules exist because of specific failures measured on 2026-08-14, when single-key joins were
still allowed:
  * name-token matching produced 261 "matches", of which 18 survived address checks (93 percent
    false positive);
  * an address fallback attributed a large coffee chain's corporate officer to an unrelated
    Dallas cafe in the same building;
  * same-building tenants inflated construction-record coverage from 6.8 to 16.5 percent;
  * three source pulls returned zero rows silently instead of failing.

RULES
  1. A join is accepted only when TWO independent signals agree.
  2. Building-level address agreement is never a signal. It is a candidate filter only.
  3. Buildings with MULTI_TENANT_THRESHOLD or more distinct tenants need a matching suite.
  4. Name-derived signals alone (entity, trade name, person) also need the same city, since
     two names agreeing is not independent evidence that two records describe one place.
  5. A zero result from a source is a suspected bug until proven otherwise.

Rules 3 and 4 were tightened during the 2026-10-23 publication review. See PROVENANCE.md.
"""
import re

from .normalize import addr_key, unit_key, norm_ent, ent_match, norm_city

MULTI_TENANT_THRESHOLD = 3
NAME_SIGNALS = {"ENTITY", "TRADE", "PERSON"}

STOP = re.compile(r"\b(LLC|L L C|INC|CORP|CORPORATION|COMPANY|CO|LTD|LP|LLP|PLLC|THE|AND|OF|"
                  r"A|AT|TX|TEXAS|NEW|CONSTRUCTION|REMODEL|INTERIOR|FINISH|OUT|SUITE|STE|"
                  r"BLDG|BUILDING|TENANT|DBA)\b")
GENERIC = {"RESTAURANT", "BAR", "GRILL", "CAFE", "KITCHEN", "LOUNGE", "CANTINA", "TAVERN",
           "PUB", "BISTRO", "EATERY", "FOOD", "PIZZA", "TACO", "TACOS", "BBQ", "CUISINE",
           "MEXICAN", "ITALIAN", "CHINESE", "INDIAN", "THAI", "SPORTS", "HOUSE"}


def toks(s, drop_generic=True):
    s = re.sub(r"[^A-Z0-9 ]", " ", str(s or "").upper())
    s = STOP.sub(" ", s)
    out = {t for t in s.split() if len(t) > 2}
    return out - GENERIC if drop_generic else out


def trade_overlap(a, b):
    """Distinctive-token overlap. Generic restaurant words never count as agreement:
    two unrelated places both called something-GRILL is the bug class."""
    ta, tb = toks(a), toks(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / min(len(ta), len(tb))


def person_eq(a, b):
    """Same human across two sources: order-insensitive, at least two shared name tokens."""
    ta = {t for t in re.sub(r"[^A-Z ]", " ", str(a or "").upper()).split() if len(t) > 1}
    tb = {t for t in re.sub(r"[^A-Z ]", " ", str(b or "").upper()).split() if len(t) > 1}
    return len(ta & tb) >= 2


def building_census(rows, addr_of, city_of, tenant_of):
    """Distinct tenants per building key. The same tenant filed twice counts once."""
    seen = {}
    for r in rows:
        k = addr_key(addr_of(r), city_of(r))
        if k:
            seen.setdefault(k, set()).add(norm_ent(tenant_of(r)) or id(r))
    return {k: len(v) for k, v in seen.items()}


def signals(venue, *, cand_entity=None, cand_trade=None, cand_taxid=None, venue_taxid=None,
            cand_addr=None, cand_city=None, cand_person=None, venue_people=None):
    """The set of signals on which venue and candidate agree.

    Names starting with an underscore are diagnostics. They inform `accept` but never count
    toward the two-signal rule.
    """
    got = set()
    if cand_entity and ent_match(norm_ent(venue.get("legal_entity")), norm_ent(cand_entity)):
        got.add("ENTITY")
    if cand_taxid and venue_taxid and str(cand_taxid).strip() == str(venue_taxid).strip():
        got.add("TAXID")
    if cand_trade and trade_overlap(venue.get("trade_name"), cand_trade) >= 0.5:
        got.add("TRADE")
    if cand_person and venue_people and any(person_eq(cand_person, p) for p in venue_people):
        got.add("PERSON")
    if cand_city and norm_city(cand_city) == norm_city(venue.get("city")):
        got.add("_CITY")
    if cand_addr:
        city = cand_city or venue.get("city")
        vk, ck = unit_key(venue.get("address"), venue.get("city")), unit_key(cand_addr, city)
        if vk and ck and vk == ck and "#" in vk:
            got.add("SUITE")
        bk = addr_key(venue.get("address"), venue.get("city"))
        if bk and bk == addr_key(cand_addr, city):
            got.add("_ADDRESS")
    return got


def accept(sig, *, building_count=1):
    """Return (accepted, reason)."""
    real = {s for s in sig if not s.startswith("_")}
    if building_count >= MULTI_TENANT_THRESHOLD and "SUITE" not in real:
        return False, "multi_tenant_no_suite"
    if len(real) >= 2 and real <= NAME_SIGNALS and "_CITY" not in sig:
        return False, "names_only_no_city"
    if len(real) >= 2:
        return True, "+".join(sorted(real))
    if len(real) == 1:
        return False, "single_key:" + next(iter(real))
    return False, "address_only" if "_ADDRESS" in sig else "no_signal"


class SourceHealthError(RuntimeError):
    pass


def expect_rows(n, label, minimum=1):
    if n < minimum:
        raise SourceHealthError(
            f"{label}: {n} rows, expected >= {minimum}. Zero results are bugs until proven "
            "otherwise (bad field name, double-encoding, pagination cap, blocked endpoint).")
    return n


def advance_by(rows_returned, requested, label, log=None):
    """Cursor advance for paginated pulls. One state API silently caps pages at 100 while
    accepting a request for 1,000, so advancing by the requested size skipped 90 percent of it."""
    if rows_returned == 0:
        raise SourceHealthError(f"{label}: page returned 0 rows mid-pagination.")
    if rows_returned < requested and log:
        log(f"{label}: server capped page at {rows_returned} (requested {requested}).")
    return rows_returned
