#!/usr/bin/env python3
"""Email me when anything changes on a specific TrustedHouseSitters listing.

For each listing ID in WATCH, fetches the listing page, takes a snapshot of its
open sits (dates, reviewing/confirmed status, application count), compares it
with watched.json and emails when a sit reopens, is confirmed, is added or
removed, or changes dates. A listing's first run
only records the snapshot. To stop watching, remove its ID from WATCH.
"""
import html
import json
import re
import sys
import urllib.request
from pathlib import Path

from ths_alert import BASE, UA, send_email

# listing id -> note for the email subject
WATCH = {
}
STATE_FILE = Path(__file__).with_name("watched.json")
STATE_RE = re.compile(r'<script id="__INITIAL_STATE__" type="application/json">(.*?)</script>', re.S)


def listing_page(listing_id):
    return f"{BASE}/house-and-pet-sitting-assignments/l/{listing_id}/"


def snapshot(listing_id):
    req = urllib.request.Request(listing_page(listing_id), headers={"User-Agent": UA, "Accept-Language": "en-GB"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = resp.read().decode("utf-8")
    m = STATE_RE.search(body)
    if not m:
        raise RuntimeError("no __INITIAL_STATE__ found (site layout changed or request blocked)")
    listing = json.loads(m.group(1)).get("search", {}).get("listing", {}).get(listing_id)
    if not listing:
        return {"available": False}
    return {
        "available": True,
        "title": listing.get("title"),
        "sits": {
            a["id"]: {
                "dates": f"{a['startDate']} → {a['endDate']}",
                "status": ("confirmed" if a.get("isConfirmed")
                           else "reviewing (not accepting)" if a.get("isReviewing")
                           else "open for applications"),
                "applications": a.get("applicationsCount"),
            }
            for a in listing.get("openAssignments", [])
        },
    }


def diff(old, new):
    if old["available"] != new["available"]:
        return ["Listing is back online" if new["available"] else "Listing is no longer available"]
    if not new["available"]:
        return []
    changes = []
    if old["title"] != new["title"]:
        changes.append(f"Title: {old['title']} → {new['title']}")
    for sid, sit in new["sits"].items():
        before = old["sits"].get(sid)
        if not before:
            changes.append(f"New sit: {sit['dates']} ({sit['status']})")
            continue
        # Application counts alone aren't worth an email: at 5 the sit gets
        # blocked, so what matters is the status flipping back to open
        if before["dates"] != sit["dates"]:
            changes.append(f"Dates changed: {before['dates']} → {sit['dates']}")
        if before["status"] != sit["status"]:
            changes.append(f"{sit['dates']}: {before['status']} → {sit['status']}"
                           f" ({sit['applications']} applications)")
    for sid, sit in old["sits"].items():
        if sid not in new["sits"]:
            changes.append(f"Sit {sit['dates']} removed (filled or cancelled)")
    return changes


def main():
    dry_run = "--dry-run" in sys.argv
    state = json.loads(STATE_FILE.read_text()) if STATE_FILE.exists() else {}
    failed = False
    for listing_id, note in WATCH.items():
        try:
            new = snapshot(listing_id)
        except Exception as e:  # keep checking the other listings
            print(f"[{listing_id}] failed: {e!r}", file=sys.stderr)
            failed = True
            continue
        old = state.get(listing_id)
        changes = diff(old, new) if old else []
        print(f"[{listing_id}] {len(changes)} changes{' (first run: recording snapshot)' if not old else ''}")
        if changes:
            url = listing_page(listing_id)
            subject = f"Listing changed ({note}): {changes[0]}"
            text = "\n".join(changes) + f"\n\n{url}"
            body = (f'<div style="font-family:sans-serif">'
                    + "".join(f"<p>{html.escape(c)}</p>" for c in changes)
                    + f'<p><a href="{html.escape(url)}">Open listing</a></p></div>')
            if dry_run:
                print(subject, text, sep="\n\n")
                continue
            send_email(subject, text, body)
            print(f"emailed: {subject}")
        if not dry_run:
            state[listing_id] = new
    if not dry_run:
        STATE_FILE.write_text(json.dumps(state, indent=1, ensure_ascii=False) + "\n")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
