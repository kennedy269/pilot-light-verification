"""The calling path: raw records in, accept or reject decisions out.

In production the same steps run inside the lead build, once per source (sales-tax permits,
franchise-tax officers, construction records). This is the single-source version.
"""
from .normalize import addr_key
from .verify import building_census, signals, accept


def tenant_name(r):
    return r.get("entity") or r.get("trade")


def match(venue, candidates):
    """Decide each candidate record against one venue. Returns a list of
    (candidate_id, accepted, reason, signals)."""
    census = building_census(candidates, lambda r: r.get("address"), lambda r: r.get("city"),
                             tenant_name)
    bk = addr_key(venue.get("address"), venue.get("city"))
    bcount = census.get(bk, 1) if bk else 1
    out = []
    for c in candidates:
        sig = signals(venue, cand_entity=c.get("entity"), cand_trade=c.get("trade"),
                      cand_taxid=c.get("taxid"), venue_taxid=venue.get("taxid"),
                      cand_addr=c.get("address"), cand_city=c.get("city"),
                      cand_person=c.get("person"), venue_people=venue.get("people"))
        ok, reason = accept(sig, building_count=bcount)
        out.append((c["id"], ok, reason, sorted(sig)))
    return out
