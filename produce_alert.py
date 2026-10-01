#!/usr/bin/env python3
"""Email me which UK fruit and vegetables are in season this fortnight.

Runs on the 1st and 15th. Each season is given in half-months: "5a" is early May
(1st-14th), "7b" is late July (15th-end). Seasons can wrap past New Year ("10a"
to "3a"). Dates are rough, for UK field-grown produce; a season that starts or
ends this half-month is called out as "just in" or "last chance".
--dry-run prints the email instead of sending it. --date YYYY-MM-DD pretends
it's that day.

Email settings come from env vars; see mailer.py.
"""
import html
import sys
from datetime import date

from mailer import send_email

FRUIT = {
    "Forced rhubarb": ("1a", "3b"),
    "Rhubarb": ("4a", "6b"),
    "Elderflower": ("5b", "6b"),
    "Gooseberries": ("6a", "7b"),
    "Strawberries": ("6a", "8b"),
    "Cherries": ("6b", "8a"),
    "Raspberries": ("6b", "10a"),
    "Blackcurrants": ("7a", "8a"),
    "Redcurrants": ("7a", "8a"),
    "Blueberries": ("7a", "9a"),
    "Tomatoes": ("7a", "10a"),
    "Greengages": ("8a", "8b"),
    "Plums": ("8a", "9b"),
    "Blackberries": ("8a", "10a"),
    "Elderberries": ("8b", "9b"),
    "Apples": ("8b", "2b"),
    "Damsons": ("9a", "10a"),
    "Pears": ("9a", "1b"),
    "Quince": ("10a", "11b"),
}

VEG = {
    "Purple sprouting broccoli": ("1b", "4b"),
    "Spring greens": ("2b", "5b"),
    "Wild garlic": ("3a", "5a"),
    "Spinach": ("4a", "10a"),
    "Spring onions": ("4a", "9a"),
    "Watercress": ("4a", "9a"),
    "Asparagus": ("4b", "6b"),
    "Radishes": ("4b", "9b"),
    "New potatoes": ("5a", "7b"),
    "Lettuce and salad leaves": ("5a", "9b"),
    "Broad beans": ("6a", "8b"),
    "Peas": ("6a", "9a"),
    "Cucumbers": ("6a", "9a"),
    "Chard": ("6a", "11a"),
    "Carrots": ("6a", "12b"),
    "Samphire": ("6b", "8b"),
    "Globe artichokes": ("6b", "9a"),
    "Courgettes": ("6b", "9b"),
    "Beetroot": ("6b", "1b"),
    "French beans": ("7a", "9b"),
    "Fennel": ("7a", "9b"),
    "Broccoli": ("7a", "10b"),
    "Runner beans": ("7b", "10a"),
    "Sweetcorn": ("8a", "9b"),
    "Celery": ("8a", "11a"),
    "Wild mushrooms": ("9a", "11a"),
    "Squash and pumpkins": ("9a", "12b"),
    "Red cabbage": ("9a", "2b"),
    "Leeks": ("9a", "4a"),
    "Celeriac": ("9b", "3a"),
    "Cavolo nero": ("9b", "2b"),
    "Kale": ("10a", "3b"),
    "Savoy cabbage": ("10a", "2b"),
    "Swede": ("10a", "2b"),
    "Parsnips": ("10a", "3a"),
    "Brussels sprouts": ("10b", "2b"),
    "Jerusalem artichokes": ("11a", "2b"),
    "Chicory": ("11a", "3a"),
}


def half_index(code):
    """'5a' -> 8, '5b' -> 9: half-months counted from early January = 0."""
    return (int(code[:-1]) - 1) * 2 + (code[-1] == "b")


def in_season(start, end, i):
    s, e = half_index(start), half_index(end)
    return s <= i <= e if s <= e else i >= s or i <= e


def group(produce, i):
    now, new, ending = [], [], []
    for name, (start, end) in produce.items():
        if not in_season(start, end, i):
            continue
        if half_index(start) == i:
            new.append(name)
        elif half_index(end) == i:
            ending.append(name)
        else:
            now.append(name)
    return sorted(new), sorted(now), sorted(ending)


def build_email(today):
    i = (today.month - 1) * 2 + (today.day >= 15)
    period = f"{'Early' if today.day < 15 else 'Late'} {today:%B}"
    sections = []
    for label, produce in (("Fruit", FRUIT), ("Veg", VEG)):
        new, now, ending = group(produce, i)
        sections.append((label, [("Just in", new), ("In season", now), ("Last chance", ending)]))

    next_update = (today.replace(day=15) if today.day < 15
                   else date(today.year + today.month // 12, today.month % 12 + 1, 1))
    subject = f"In season: {period}"
    text = "\n\n".join(
        f"{label.upper()}\n" + "\n".join(f"{kind}: {', '.join(items)}" for kind, items in parts if items)
        for label, parts in sections)
    text += f"\n\nNext update: {next_update:%-d %B}"
    return subject, text, render_html(period, sections, next_update)


# Email clients ignore <style> blocks and most layout CSS, so everything is
# inline styles on tables
FONT = "-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif"
ICONS = {"Fruit": "🍎", "Veg": "🥕"}
# kind -> (chip background, chip text, note next to the heading)
KINDS = {
    "Just in": ("#e3f1e4", "#1f5c2b", "new this fortnight"),
    "In season": ("#f1eee8", "#3d3a33", ""),
    "Last chance": ("#fbebd5", "#7a4a0c", "finishing this fortnight"),
}


def chips(kind, items):
    bg, fg, _ = KINDS[kind]
    return "".join(
        f'<span style="display:inline-block;margin:0 6px 8px 0;padding:5px 11px;border-radius:14px;'
        f'background:{bg};color:{fg};font-size:14px;line-height:18px">{html.escape(item)}</span>'
        for item in items)


def card(label, parts):
    rows = ""
    for kind, items in parts:
        if not items:
            continue
        note = KINDS[kind][2]
        rows += (f'<p style="margin:14px 0 8px;font-size:12px;letter-spacing:.06em;text-transform:uppercase;'
                 f'color:#77736a;font-weight:600">{kind}'
                 + (f'<span style="text-transform:none;letter-spacing:0;font-weight:400"> · {note}</span>'
                    if note else "")
                 + f'</p><div>{chips(kind, items)}</div>')
    return (f'<tr><td style="padding:0 0 16px"><table role="presentation" width="100%" cellpadding="0" '
            f'cellspacing="0" style="background:#ffffff;border:1px solid #e7e3da;border-radius:12px">'
            f'<tr><td style="padding:18px 20px 10px">'
            f'<h2 style="margin:0;font-size:18px;color:#26241f">{ICONS[label]}&nbsp; {label}</h2>{rows}'
            f'</td></tr></table></td></tr>')


def render_html(period, sections, next_update):
    return (f'<div style="margin:0;padding:24px 12px;background:#f7f5f0;font-family:{FONT}">'
            f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
            f'style="max-width:560px;margin:0 auto">'
            f'<tr><td style="padding:0 4px 18px">'
            f'<p style="margin:0;font-size:13px;color:#77736a">UK seasonal produce</p>'
            f'<h1 style="margin:2px 0 0;font-size:26px;color:#26241f">In season: {period}</h1></td></tr>'
            + "".join(card(label, parts) for label, parts in sections)
            + f'<tr><td style="padding:4px 4px 0;font-size:12px;color:#8f8a80">'
            f'Rough dates for UK field-grown produce. Next update: {next_update:%-d %B}.</td></tr>'
            f'</table></div>')


def main():
    today = date.today()
    if "--date" in sys.argv:
        today = date.fromisoformat(sys.argv[sys.argv.index("--date") + 1])
    subject, text, body = build_email(today)
    if "--dry-run" in sys.argv:
        print(subject, text, sep="\n\n")
        return
    send_email(subject, text, body)
    print(f"emailed: {subject}")


if __name__ == "__main__":
    main()
