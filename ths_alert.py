#!/usr/bin/env python3
"""Email me when a new TrustedHouseSitters listing matches one of my saved searches.

For each search in SEARCHES, fetches the results, compares listing IDs against
seen.json, and emails any new ones via SMTP. A search's first run only records
what's already there. To add a search, paste the ?q=... value from its URL.
--test-email sends the newest listing as a sample alert without touching seen.json.

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

# name -> the q= value from the search URL on trustedhousesitters.com
SEARCHES = {
    "Europe, 29 Oct - 7 Nov": "eyJmaWx0ZXJzIjp7ImFjdGl2ZU1lbWJlcnNoaXAiOnRydWUsImFzc2lnbm1lbnRzIjp7ImRhdGVGcm9tIjoiMjAyNi0xMC0yOSIsImRhdGVUbyI6IjIwMjYtMTEtMDciLCJyZXZpZXdpbmciOmZhbHNlLCJjb25maXJtZWQiOmZhbHNlLCJkdXJhdGlvbkluRGF5cyI6eyJtaW5pbXVtIjozfX0sInNvcnRCeSI6WyJuZXdlc3QiXSwiZ2VvSGllcmFyY2h5Ijp7ImNvbnRpbmVudFNsdWciOiJldXJvcGUifX0sImZhY2V0cyI6W10sInNvcnQiOlt7InB1Ymxpc2hlZCI6ImRlc2MifV0sInBhZ2UiOjEsInJlc3VsdHNQZXJQYWdlIjoxMiwiZGVidWciOmZhbHNlLCJzdGF0cyI6W119",
    "London cats, March 2027": "eyJmaWx0ZXJzIjp7ImFjdGl2ZU1lbWJlcnNoaXAiOnRydWUsImFzc2lnbm1lbnRzIjp7ImRhdGVGcm9tIjoiMjAyNy0wMy0wNyIsImRhdGVUbyI6IjIwMjctMDMtMjkiLCJyZXZpZXdpbmciOmZhbHNlLCJjb25maXJtZWQiOmZhbHNlLCJkdXJhdGlvbkluRGF5cyI6eyJtaW5pbXVtIjo3fX0sInBldHMiOlt7InR5cGUiOiJkb2ciLCJleGNsdWRlIjp0cnVlfSx7InR5cGUiOiJjYXQiLCJleGNsdWRlIjpmYWxzZX0seyJ0eXBlIjoicmVwdGlsZSIsImV4Y2x1ZGUiOnRydWV9LHsidHlwZSI6ImhvcnNlIiwiZXhjbHVkZSI6dHJ1ZX0seyJ0eXBlIjoiZmlzaCIsImV4Y2x1ZGUiOnRydWV9LHsidHlwZSI6ImJpcmQiLCJleGNsdWRlIjp0cnVlfSx7InR5cGUiOiJwb3VsdHJ5IiwiZXhjbHVkZSI6dHJ1ZX0seyJ0eXBlIjoiZmFybSBhbmltYWwiLCJleGNsdWRlIjp0cnVlfSx7InR5cGUiOiJzbWFsbCBwZXQiLCJleGNsdWRlIjp0cnVlfV0sInNvcnRCeSI6WyJuZXdlc3QiXSwiZ2VvUG9pbnQiOnsibGF0aXR1ZGUiOjUxLjUwODUzLCJsb25naXR1ZGUiOi0wLjEyNTc0LCJkaXN0YW5jZSI6Ijcwa20ifX0sImZhY2V0cyI6W10sInNvcnQiOlt7InB1Ymxpc2hlZCI6ImRlc2MifV0sInBhZ2UiOjEsInJlc3VsdHNQZXJQYWdlIjoxMiwiZGVidWciOmZhbHNlLCJzdGF0cyI6W119",
}
BASE = "https://www.trustedhousesitters.com"
MAX_PAGES = 10
SEEN_FILE = Path(__file__).with_name("seen.json")
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0 Safari/537.36")
STATE_RE = re.compile(r'<script id="__INITIAL_STATE__" type="application/json">(.*?)</script>', re.S)


def search_url(q, page=1):
    if page != 1:
        search = json.loads(base64.b64decode(q))
        q = base64.b64encode(json.dumps({**search, "page": page}, separators=(",", ":")).encode()).decode()
    return f"{BASE}/house-and-pet-sitting-assignments/?q={q}"


def fetch_page(q, page):
    req = urllib.request.Request(search_url(q, page), headers={"User-Agent": UA, "Accept-Language": "en-GB"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = resp.read().decode("utf-8")
    m = STATE_RE.search(body)
    if not m:
        raise RuntimeError(f"page {page}: no __INITIAL_STATE__ found (site layout changed or request blocked)")
    state = json.loads(m.group(1))
    results = state["search"]["listings"]["search-listings-results"]
    return [state["search"]["listing"][i] for i in results["results"]], results["total"]


def fetch_all(q):
    listings, total = fetch_page(q, 1)
    page = 1
    while len(listings) < total and page < MAX_PAGES:
        page += 1
        time.sleep(2)
        more, _ = fetch_page(q, page)
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


def build_email(name, q, new):
    items = [describe(l) for l in new]
    subject = (f"New house sit ({name}): {items[0]['place']}" if len(items) == 1
               else f"{len(items)} new house sits ({name})")
    text = "\n\n".join(f"{i['title']}\n{i['place']}\nDates: {i['dates']}\nPets: {i['pets']}\n{i['url']}"
                       for i in items)
    text += f"\n\nFull search: {search_url(q)}"
    rows = "".join(
        f'<div style="margin:0 0 20px"><a href="{html.escape(i["url"])}" style="font-size:16px;font-weight:600">'
        f'{html.escape(i["title"])}</a><br>{html.escape(i["place"])}<br>'
        f'Dates: {html.escape(i["dates"])}<br>Pets: {html.escape(i["pets"])}</div>'
        for i in items)
    body = (f'<div style="font-family:sans-serif">{rows}'
            f'<p><a href="{html.escape(search_url(q))}">Open full search: {html.escape(name)}</a></p></div>')
    return subject, text, body


def send_email(subject, text, body):
    # Secrets pasted into GitHub often pick up stray spaces or newlines
    user = os.environ["SMTP_USER"].strip()
    password = re.sub(r"\s", "", os.environ["SMTP_PASSWORD"])
    if not user or not password:
        raise RuntimeError("SMTP_USER or SMTP_PASSWORD is empty")
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = user
    msg["To"] = (os.environ.get("ALERT_TO") or user).strip()
    msg.set_content(text)
    msg.add_alternative(body, subtype="html")
    host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    port = int(os.environ.get("SMTP_PORT", "465"))
    try:
        with smtplib.SMTP_SSL(host, port, timeout=30) as s:
            s.login(user, password)
            s.send_message(msg)
    except smtplib.SMTPServerDisconnected:
        print(f"{host}:{port} dropped the connection, retrying with STARTTLS on 587")
        with smtplib.SMTP(host, 587, timeout=30) as s:
            s.starttls()
            s.login(user, password)
            s.send_message(msg)


def load_seen():
    if not SEEN_FILE.exists():
        return {}
    seen = json.loads(SEEN_FILE.read_text())
    if isinstance(seen, list):  # older format: one list for the original search
        seen = {next(iter(SEARCHES)): seen}
    return {name: set(ids) for name, ids in seen.items()}


def save_seen(seen):
    SEEN_FILE.write_text(json.dumps({n: sorted(ids) for n, ids in seen.items()}, indent=1) + "\n")


def check(name, q, seen, dry_run):
    listings = fetch_all(q)
    first_run = name not in seen
    known = seen.get(name, set())
    new = [l for l in listings if l["id"] not in known]
    print(f"[{name}] {len(listings)} listings, {len(new)} new"
          f"{' (first run: recording baseline)' if first_run else ''}")

    if new and not first_run:
        subject, text, body = build_email(name, q, new)
        if dry_run:
            print(subject, text, sep="\n\n")
            return
        send_email(subject, text, body)
        print(f"emailed: {subject}")

    if not dry_run:
        seen[name] = known | {l["id"] for l in listings}
        save_seen(seen)


def main():
    dry_run = "--dry-run" in sys.argv

    if "--test-email" in sys.argv:
        for name, q in SEARCHES.items():
            listings = fetch_all(q)
            if listings:
                subject, text, body = build_email(name, q, listings[:1])
                send_email(f"[TEST] {subject}", text, body)
                print(f"sent test email: {subject}")
                return
        sys.exit("no listings in any search to send as a test")

    seen = load_seen()
    failed = False
    for name, q in SEARCHES.items():
        try:
            check(name, q, seen, dry_run)
        except Exception as e:  # keep checking the other searches
            print(f"[{name}] failed: {e!r}", file=sys.stderr)
            failed = True
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
