# Provenance

What in this repo came from the private Pilot Light pipeline, and what was written for
publication on 2026-10-23.

| File | Origin | Changes |
|---|---|---|
| `pilot_light/normalize.py` | Extracted from the build stage | Functions unchanged. `norm_city` added. `_suite` renamed `suite`. |
| `pilot_light/verify.py` | Extracted from the verification layer | `building_census` counts distinct tenants and takes a `tenant_of` argument. `signals` adds a `_CITY` diagnostic. `accept` rejects name-only pairs without a city match and treats every underscore signal as a diagnostic. Docstrings rewritten without business or personal names. |
| `pilot_light/transitions.py` | New, written for publication | An in-memory rewrite of the spine's resolution step. `is_approval` and `watermark` are extracted unchanged. The reset for a licence that returns to the pending list is new. |
| `pilot_light/match.py` | New | A single-source version of the calling path in the lead build. |
| `examples/` | New | Synthetic fixtures and the walkthrough. |
| `tests/` | New | Regression tests. `defects.py` labels each defective function PRESERVED, ADAPTED or RECONSTRUCTED. |

Not published: source fetchers, the classification and lead build, the event store and its
export, the site generator, pricing, and all data.
