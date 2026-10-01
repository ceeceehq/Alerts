#!/usr/bin/env python3
"""Email me which UK fruit and vegetables are in season this fortnight.

Runs on the 1st and 15th. Each season is given in half-months: "5a" is early May
(1st-14th), "7b" is late July (15th-end). Seasons can wrap past New Year ("10a"
to "3a"). Dates are rough, for UK field-grown produce; a season that starts or
ends this half-month is called out as "just in" or "last chance".
--dry-run prints the email instead of sending it. --date YYYY-MM-DD pretends
it's that day.

Illustrations live in img/ (one <slug>.png per item, one header-<season>.jpg
per season) and are loaded from GitHub, so a new item needs its icon pushed.

Email settings come from env vars; see mailer.py.
"""
import html
import re
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

# How to pick a good one
TIPS = {
    "Forced rhubarb": "Look for slender, bright pink stalks that snap cleanly; skip any that are limp or bendy.",
    "Rhubarb": "Choose firm, glossy stalks with fresh-looking cut ends. Thinner stalks are more tender.",
    "Elderflower": "Pick creamy-white heads that smell sweet, on a dry sunny morning. Brown or musty ones are past it.",
    "Gooseberries": "Firm and green for cooking; slightly soft and blushed for eating raw.",
    "Strawberries": "Red right up to the stalk, glossy, with fresh green leaves. Smell them: good ones are fragrant.",
    "Cherries": "Plump, shiny and firm with green, flexible stems. Darker usually means sweeter.",
    "Raspberries": "Check the bottom of the punnet for juice stains or mould. Ripe berries are deep in colour and dry.",
    "Blackcurrants": "Go for glossy, plump berries still on their sprigs, with no shrivelling.",
    "Redcurrants": "Bright, translucent berries on intact strings; avoid split or dull ones.",
    "Blueberries": "Firm with a dusty silver bloom. A reddish tinge means they were picked early.",
    "Tomatoes": "Heavy for their size, evenly coloured, and smelling of tomato at the stalk end.",
    "Greengages": "A golden blush over the green and a slight give near the stem means they're ready.",
    "Plums": "A natural bloom on the skin and a little give when pressed gently at the stalk end.",
    "Blackberries": "Fully black and glossy; any red patches mean sour. They don't ripen once picked.",
    "Elderberries": "Only pick clusters where every berry is deep purple-black, and always cook them before eating.",
    "Apples": "Firm, no bruises, and a sweet smell. Early-season varieties don't keep, so eat those first.",
    "Damsons": "Deep blue-black with a dusty bloom and slightly soft; they're tart, so best cooked.",
    "Pears": "Press gently near the stalk: a little give means ripe. They ripen well on the windowsill.",
    "Quince": "Golden yellow and strongly fragrant; rub off the fuzz and always cook it.",
    "Purple sprouting broccoli": "Tight purple buds and stems that snap rather than bend. Skip any with yellow flowers.",
    "Spring greens": "Bright, crisp leaves with no yellowing; the loose heads should feel springy.",
    "Wild garlic": "Smell the leaves for garlic. Young leaves before flowering are the most tender.",
    "Spinach": "Dark green, crisp leaves with no slimy or yellow bits.",
    "Spring onions": "Firm white bulbs and bright, upright green tops.",
    "Watercress": "Deep green, perky leaves and a peppery smell; avoid any that are wilting.",
    "Asparagus": "Tight tips and firm stems that squeak when rubbed together. Fresher cut ends mean fresher spears.",
    "Radishes": "Firm and brightly coloured, with fresh leaves still attached.",
    "New potatoes": "Thin skin that rubs off with your thumb, and still a little earth on them.",
    "Lettuce and salad leaves": "Crisp and perky with no brown edges. Heads should feel heavy for their size.",
    "Broad beans": "Plump, bright green pods with a satiny feel. Smaller beans are sweeter.",
    "Peas": "Shiny, full pods that snap. Pop one open: the peas should be sweet and not starchy.",
    "Cucumbers": "Firm right to the ends, with no soft spots or yellowing.",
    "Chard": "Glossy, unwilted leaves and crisp, brightly coloured stems.",
    "Carrots": "Firm with smooth skin; bunches with fresh green tops are a good sign of freshness.",
    "Samphire": "Bright green, crisp stems that snap; avoid any that are slimy or woody.",
    "Globe artichokes": "Heavy for their size, with tight leaves that squeak when squeezed.",
    "Courgettes": "Small to medium, firm and glossy. Big ones get watery and seedy.",
    "Beetroot": "Firm and smooth, ideally with perky leaves attached (which you can cook too).",
    "French beans": "Bright and slim, and they should snap cleanly in half.",
    "Fennel": "White, firm bulbs with no brown patches and fresh, feathery fronds.",
    "Broccoli": "Tight, dark green florets; any yellow means it's getting old.",
    "Runner beans": "Young, flat pods that snap; avoid big lumpy ones, which are stringy.",
    "Sweetcorn": "Green, tight husks and moist silk; squeeze to feel plump kernels all the way up.",
    "Celery": "Tight, crisp stalks that snap, with fresh leaves.",
    "Wild mushrooms": "Firm, dry and fragrant. Only buy from a trusted seller; never eat ones you've foraged unless an expert has checked them.",
    "Squash and pumpkins": "Heavy for their size with a hard, matt skin and a dry, intact stalk.",
    "Red cabbage": "Heavy and tightly packed, with crisp, glossy outer leaves.",
    "Leeks": "Straight, firm and mostly white, with a crisp green top. Smaller ones are more tender.",
    "Celeriac": "Heavy for its size, without soft spots. Smaller roots are less woody.",
    "Cavolo nero": "Dark, crinkly, unwilted leaves; small ones are the most tender.",
    "Kale": "Deep green, crisp leaves with no yellowing; small leaves are less bitter.",
    "Savoy cabbage": "Heavy, with crinkly, bright leaves and no slimy outer layers.",
    "Swede": "Small to medium, heavy and firm; big ones can be woody.",
    "Parsnips": "Firm and medium-sized; they taste sweeter after the first frost.",
    "Brussels sprouts": "Small, tight, bright green sprouts. Buy them on the stalk if you can, as they keep longer.",
    "Jerusalem artichokes": "Firm, with as few knobbles as possible, so they're easier to peel.",
    "Chicory": "Tight, pale heads with yellow tips. Green tips mean extra bitterness.",
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


def pick_tips(sections, i, limit=6):
    """Everything just in, then a rotating handful of the rest, so tips vary each fortnight."""
    kinds = {kind: [n for _, parts in sections for k, items in parts if k == kind for n in items]
             for kind in KINDS}
    rest = kinds["In season"] + kinds["Last chance"]
    rest = rest[i % len(rest):] + rest[:i % len(rest)] if rest else []
    return [(name, TIPS[name]) for name in (kinds["Just in"] + rest)[:limit]]


def build_email(today):
    i = (today.month - 1) * 2 + (today.day >= 15)
    period = f"{'Early' if today.day < 15 else 'Late'} {today:%B}"
    sections = []
    for label, produce in (("Fruit", FRUIT), ("Veg", VEG)):
        new, now, ending = group(produce, i)
        sections.append((label, [("Just in", new), ("In season", now), ("Last chance", ending)]))
    tips = pick_tips(sections, i)
    season = SEASONS[today.month]

    next_update = (today.replace(day=15) if today.day < 15
                   else date(today.year + today.month // 12, today.month % 12 + 1, 1))
    subject = f"In season: {period}"
    text = "\n\n".join(
        f"{label.upper()}\n" + "\n".join(f"{kind}: {', '.join(items)}" for kind, items in parts if items)
        for label, parts in sections)
    text += "\n\nHOW TO PICK THE BEST\n" + "\n".join(f"{name}: {tip}" for name, tip in tips)
    text += f"\n\nNext update: {next_update:%-d %B}"
    return subject, text, render_html(period, season, sections, tips, next_update)


# Email clients ignore <style> blocks and most layout CSS, so everything is
# inline styles on tables. Images are served from the public GitHub repo.
FONT = "-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif"
IMG = "https://raw.githubusercontent.com/ceeceehq/Alerts/main/img"
SEASONS = {m: s for s, months in (("winter", (12, 1, 2)), ("spring", (3, 4, 5)),
                                  ("summer", (6, 7, 8)), ("autumn", (9, 10, 11))) for m in months}
ICONS = {"Fruit": "🍎", "Veg": "🥕"}
# kind -> (chip background, chip text, note next to the heading)
KINDS = {
    "Just in": ("#e3f1e4", "#1f5c2b", "new this fortnight"),
    "In season": ("#f1eee8", "#3d3a33", ""),
    "Last chance": ("#fbebd5", "#7a4a0c", "finishing this fortnight"),
}


def icon(name, size):
    slug = re.sub(r"[^a-z]+", "-", name.lower()).strip("-")
    return (f'<img src="{IMG}/{slug}.png" width="{size}" height="{size}" alt="" '
            f'style="display:inline-block;vertical-align:middle;border:0">')


def chips(kind, items):
    bg, fg, _ = KINDS[kind]
    return "".join(
        f'<span style="display:inline-block;margin:0 6px 8px 0;padding:3px 11px 3px 5px;border-radius:16px;'
        f'background:{bg};color:{fg};font-size:14px;line-height:24px;white-space:nowrap">'
        f'{icon(item, 24)}&nbsp;{html.escape(item)}</span>'
        for item in items)


def card(title, inner):
    return (f'<tr><td style="padding:0 0 16px"><table role="presentation" width="100%" cellpadding="0" '
            f'cellspacing="0" style="background:#ffffff;border:1px solid #e7e3da;border-radius:12px">'
            f'<tr><td style="padding:18px 20px 10px">'
            f'<h2 style="margin:0;font-size:18px;color:#26241f">{title}</h2>{inner}'
            f'</td></tr></table></td></tr>')


def produce_card(label, parts):
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
    return card(f"{ICONS[label]}&nbsp; {label}", rows)


def tips_card(tips):
    rows = "".join(
        f'<tr><td width="48" valign="top" style="padding:12px 12px 0 0">{icon(name, 44)}</td>'
        f'<td valign="top" style="padding:12px 0 0;font-size:14px;line-height:20px;color:#3d3a33">'
        f'<b style="color:#26241f">{html.escape(name)}</b><br>{html.escape(tip)}</td></tr>'
        for name, tip in tips)
    return card("🧺&nbsp; How to pick the best",
                f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
                f'style="margin:0 0 10px">{rows}</table>')


def render_html(period, season, sections, tips, next_update):
    return (f'<div style="margin:0;padding:24px 12px;background:#f7f5f0;font-family:{FONT}">'
            f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
            f'style="max-width:560px;margin:0 auto">'
            f'<tr><td style="padding:0 0 6px"><img src="{IMG}/header-{season}.jpg" width="560" alt="" '
            f'style="display:block;width:100%;max-width:560px;height:auto;border:0;border-radius:12px"></td></tr>'
            f'<tr><td style="padding:0 4px 18px">'
            f'<p style="margin:0;font-size:13px;color:#77736a">UK seasonal produce</p>'
            f'<h1 style="margin:2px 0 0;font-size:26px;color:#26241f">In season: {period}</h1></td></tr>'
            + "".join(produce_card(label, parts) for label, parts in sections)
            + tips_card(tips)
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
