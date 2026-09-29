#!/usr/bin/env python3
"""Email me when a new TrustedHouseSitters listing matches my saved search.

Fetches the search results, compares listing IDs against seen.json, and emails
any new ones via SMTP. The first run only records what's already there.

Env vars:
  SMTP_USER      Gmail address that sends the email
  SMTP_PASSWORD  Gmail app password (https://myaccount.google.com/apppasswords)
  ALERT_TO       recipient (defaults to SMTP_USER)
  SMTP_HOST / SMTP_PORT  optional, default smtp.gmail.com:465
"""
import base64
import html
import json
import os
import re
import smtplib
import sys
import time
import urllib.request
from email.message import EmailMessage
from pathlib import Path

SEARCH = {
    "filters": {
        "activeMembership": True,
        "assignments": {
            "dateFrom": "2026-10-29",
            "dateTo": "2026-11-07",
            "reviewing": False,
            "confirmed": False,
            "durationInDays": {"minimum": 3},
        },
        "sortBy": ["newest"],
        "geoHierarchy": {"continentSlug": "europe"},
    },
    "facets": [],
    "sort": [{"published": "desc"}],
    "page": 1,
    "resultsPerPage": 12,  # the site caps this at 12
    "debug": False,
    "stats": [],
}
BASE = "https://www.trustedhousesitters.com"
MAX_PAGES = 10
SEEN_FILE = Path(__file__).with_name("seen.json")
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0 Safari/537.36")
STATE_RE = re.compile(r'<script id="__INITIAL_STATE__" type="application/json">(.*?)</script>', re.S)


def encode(search):
    return base64.b64encode(json.dumps(search, separators=(",", ":")).encode()).decode()


def search_url(page=1):
    return f"{BASE}/house-and-pet-sitting-assignments/?q={encode({**SEARCH, 'page': page})}"


def fetch_page(page):
    req = urllib.request.Request(search_url(page), headers={"User-Agent": UA, "Accept-Language": "en-GB"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = resp.read().decode("utf-8")
    m = STATE_RE.search(body)
    if not m:
        raise RuntimeError(f"page {page}: no __INITIAL_STATE__ found (site layout changed or request blocked)")
    state = json.loads(m.group(1))
    results = state["search"]["listings"]["search-listings-results"]
    return [state["search"]["listing"][i] for i in results["results"]], results["total"]


def fetch_all():
    listings, total = fetch_page(1)
    page = 1
    while len(listings) < total and page < MAX_PAGES:
        page += 1
        time.sleep(2)
        more, _ = fetch_page(page)
        if not more:
            break
        listings += more
    return listings


def listing_url(l):
    loc = l["location"]
    return (f"{BASE}/house-and-pet-sitting-assignments/{loc['countrySlug']}/"
            f"{loc['admin1Slug']}/{loc['slug']}/l/{l['id']}/")


def describe(l):
    loc = l["location"]
    dates = ", ".join(f"{a['startDate']} → {a['endDate']}" for a in l.get("openAssignments", []))
    pets = ", ".join(f"{a['count']} {a['name']}{'s' if a['count'] > 1 else ''}" for a in l.get("animals", []))
    return {
        "title": l["title"],
        "place": f"{loc['name']}, {loc['countryName']}",
        "dates": dates or "—",
        "pets": pets or "—",
        "url": listing_url(l),
    }


def build_email(new):
    items = [describe(l) for l in new]
    subject = (f"New house sit: {items[0]['place']}" if len(items) == 1
               else f"{len(items)} new house sits in Europe")
    text = "\n\n".join(f"{i['title']}\n{i['place']}\nDates: {i['dates']}\nPets: {i['pets']}\n{i['url']}"
                       for i in items)
    text += f"\n\nFull search: {search_url()}"
    rows = "".join(
        f'<div style="margin:0 0 20px"><a href="{html.escape(i["url"])}" style="font-size:16px;font-weight:600">'
        f'{html.escape(i["title"])}</a><br>{html.escape(i["place"])}<br>'
        f'Dates: {html.escape(i["dates"])}<br>Pets: {html.escape(i["pets"])}</div>'
        for i in items)
    body = (f'<div style="font-family:sans-serif">{rows}'
            f'<p><a href="{html.escape(search_url())}">Open full search</a></p></div>')
    return subject, text, body


def send_email(subject, text, body):
    user = os.environ["SMTP_USER"]
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = user
    msg["To"] = os.environ.get("ALERT_TO") or user
    msg.set_content(text)
    msg.add_alternative(body, subtype="html")
    host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    port = int(os.environ.get("SMTP_PORT", "465"))
    with smtplib.SMTP_SSL(host, port, timeout=30) as s:
        s.login(user, os.environ["SMTP_PASSWORD"])
        s.send_message(msg)


def main():
    dry_run = "--dry-run" in sys.argv
    listings = fetch_all()
    first_run = not SEEN_FILE.exists()
    seen = set() if first_run else set(json.loads(SEEN_FILE.read_text()))
    new = [l for l in listings if l["id"] not in seen]
    print(f"{len(listings)} listings, {len(new)} new{' (first run: recording baseline)' if first_run else ''}")

    if new and not first_run:
        subject, text, body = build_email(new)
        if dry_run:
            print(subject, text, sep="\n\n")
        else:
            send_email(subject, text, body)
            print(f"emailed: {subject}")

    if not dry_run:
        SEEN_FILE.write_text(json.dumps(sorted(seen | {l["id"] for l in listings}), indent=0) + "\n")


if __name__ == "__main__":
    main()
