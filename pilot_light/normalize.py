"""Address and entity normalisation for Texas public-record joins.

Extracted from the Pilot Light build stage. Building keys and tenant keys are kept apart on
purpose: shopping centres, food halls and airports put many businesses behind one street
address, so a building key alone never identifies a tenant.
"""
import re

SUFFIX = {"STREET": "ST", "AVENUE": "AVE", "ROAD": "RD", "DRIVE": "DR", "BOULEVARD": "BLVD",
          "HIGHWAY": "HWY", "PARKWAY": "PKWY", "LANE": "LN", "COURT": "CT", "CIRCLE": "CIR",
          "TRAIL": "TRL", "PLACE": "PL", "EXPRESSWAY": "EXPY", "FREEWAY": "FWY",
          "SUITE": "", "STE": ""}
SUITE_RE = re.compile(r"(?:\b(?:STE|SUITE|UNIT|APT|BLDG|BUILDING)\b|#)\s*\.?\s*([A-Z0-9][A-Z0-9\-]*)\b")


def suite(a):
    m = SUITE_RE.search(str(a or "").upper())
    return m.group(1) if m else ""


def norm_addr(a):
    a = str(a or "").upper()
    a = re.sub(r"[.,]", " ", a)
    a = SUITE_RE.sub(" ", a)
    a = re.sub(r"[^A-Z0-9 ]", " ", a)
    toks = [SUFFIX.get(t, t) for t in a.split()]
    return re.sub(r"\s+", " ", " ".join(t for t in toks if t)).strip()


def addr_key(a, city):
    """BUILDING-level key: house number, two street tokens, city."""
    n = norm_addr(a)
    m = re.match(r"^(\d+)\s+(.*)$", n)
    if not m:
        return None
    num, rest = m.group(1), m.group(2).split()
    if not rest:
        return None
    return f"{num}|{' '.join(rest[:2])}|{str(city or '').upper().strip()}"


def unit_key(a, city):
    """TENANT-level key: the building key plus the suite, when the address has one."""
    b = addr_key(a, city)
    if not b:
        return None
    s = suite(a)
    return f"{b}|#{s}" if s else b


def norm_ent(n):
    n = re.sub(r"[^A-Z0-9 ]", " ", str(n or "").upper())
    n = re.sub(r"\b(LLC|L L C|INC|LP|LLP|LTD|CO|CORP|CORPORATION|COMPANY|INCORPORATED|THE)\b", " ", n)
    return re.sub(r"\s+", " ", n).strip()


def ent_match(a, b):
    """Same legal entity: exact, or one contained in the other when both are long enough."""
    if not a or not b:
        return False
    if a == b:
        return True
    return len(a) >= 8 and len(b) >= 8 and (a in b or b in a)


def norm_city(c):
    return str(c or "").upper().strip()
