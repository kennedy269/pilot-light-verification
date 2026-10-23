"""Two venues, ten candidate records, and the decision on each.

Run from the repo root:  python3 examples/walkthrough.py
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from pilot_light.match import match  # noqa: E402

data = json.load(open(os.path.join(ROOT, "examples", "fixtures.json")))
for sc in data["scenarios"]:
    venue = sc["venue"]
    labels = {c["id"]: c["label"] for c in sc["candidates"]}
    print(f"{sc['title']}: {venue['trade_name']}, {venue['address']}, {venue['city']}")
    for cid, ok, reason, sig in match(venue, sc["candidates"]):
        verdict = "ACCEPT" if ok else "reject"
        print(f"  {cid}  {verdict:<7} {reason:<24} {labels[cid]}")
        print(f"      signals: {', '.join(sig) or 'none'}")
    print()
