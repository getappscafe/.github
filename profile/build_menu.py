#!/usr/bin/env python3
"""Regenerate the app grid in profile/README.md from the live getapps.cafe menu.

Scrapes the homepage, pulls every app icon (CDN PNG or inline SVG) into
profile/icons/, rebuilds the profile/menu.png hero wall, and rewrites the
section between the MENU markers.

    pip install pillow && brew install librsvg
    python3 profile/build_menu.py

Everything outside the MENU markers is left alone, including the
WEEKLY-REPORT block written by the release bot.
"""
import html
import json
import re
import subprocess
import urllib.request
from pathlib import Path

from PIL import Image

SITE = "https://getapps.cafe"
RAW = "https://raw.githubusercontent.com/getappscafe/.github/main/profile"
HERE = Path(__file__).parent
ICONS = HERE / "icons"
COLS = 6
EMOJI = {"house": "🎁", "espresso": "☕", "latte": "🥛", "mocha": "🍫",
         "americano": "🫘", "coldbrew": "🧊", "frappe": "🥤", "pourover": "💧"}

# ponytail: regex, not a parser. The markup is generated and stable; if it ever
# stops matching, the asserts below fail loudly instead of writing junk.
CARD = re.compile(r'<(?:a|div)\s[^>]*class="app-card[^"]*"[^>]*>')


def text(s):
    return html.unescape(re.sub(r"<[^>]+>", "", s)).strip()


def get(url):
    # ponytail: the asset CDN 403s the default urllib agent
    req = urllib.request.Request(url, headers={"User-Agent": "getappscafe-menu-build"})
    return urllib.request.urlopen(req, timeout=30).read()


def scrape():
    page = get(SITE).decode()
    secs = re.findall(r'<section class="category"[^>]*id="([^"]+)"[^>]*>(.*?)</section>',
                      page, re.S)
    free = re.search(r'<section[^>]*id="house".*?</section>', page, re.S)
    if free and "house" not in [s[0] for s in secs]:
        secs.insert(0, ("house", free.group(0)))
    cats = []
    for cid, body in secs:
        title = re.search(r'category-title">(.*?)</h2>', body, re.S)
        starts = [m.start() for m in CARD.finditer(body)] + [len(body)]
        apps = []
        for i in range(len(starts) - 1):
            chunk = body[starts[i]:starts[i + 1]]
            name = re.search(r'app-name">(.*?)</div>', chunk, re.S)
            if not name:
                continue
            tag = CARD.match(chunk).group(0)
            slug = re.search(r'href="/app/([^"]+)"', tag)
            icon = re.search(r'app-icon-img" src="([^"]+)"', chunk)
            nm = text(name.group(1))
            svg = None
            if not icon:
                a, b = chunk.find("<svg"), chunk.find("</svg>")
                svg = chunk[a:b + 6] if a >= 0 and b > a else None
            apps.append({"name": nm, "slug": slug.group(1) if slug else nm.lower().replace(" ", ""),
                         "icon": icon.group(1) if icon else None, "svg": svg,
                         "coming": "app-card-coming" in tag})
        assert apps, f"no apps parsed for {cid} — site markup changed"
        cats.append({"cid": cid, "title": text(title.group(1)) if title else cid, "apps": apps})
    assert cats, "no categories parsed — site markup changed"
    return cats


def fetch_icons(cats):
    ICONS.mkdir(exist_ok=True)
    seen = {}
    for app in (a for c in cats for a in c["apps"]):
        if app["slug"] in seen:
            continue
        out = ICONS / f"{app['slug']}.png"
        if app["icon"]:
            out.write_bytes(get(app["icon"]))
        elif app["svg"]:
            src = ICONS / f"{app['slug']}.svg.tmp"
            src.write_text(app["svg"])
            subprocess.run(["rsvg-convert", "-w", "128", "-h", "128", src, "-o", out], check=True)
            src.unlink()
        else:
            raise SystemExit(f"no icon for {app['name']}")
        im = Image.open(out).convert("RGBA")
        if im.size != (128, 128):
            im.resize((128, 128), Image.LANCZOS).save(out)
        seen[app["slug"]] = out
    # stale icons for apps pulled off the menu
    for f in ICONS.glob("*.png"):
        if f.stem not in seen:
            f.unlink()
    return list(seen)


def build_wall(slugs, size=116, pad=16):
    rows = -(-len(slugs) // 10)
    wall = Image.new("RGBA", (10 * (size + pad) - pad, rows * (size + pad) - pad), (0, 0, 0, 0))
    for i, slug in enumerate(slugs):
        ic = Image.open(ICONS / f"{slug}.png").convert("RGBA").resize((size, size), Image.LANCZOS)
        wall.paste(ic, ((i % 10) * (size + pad), (i // 10) * (size + pad)), ic)
    wall.save(HERE / "menu.png")


def render(cats):
    def cell(a):
        label = a["name"] + (" 🔜" if a["coming"] else "")
        img = (f'<img src="{RAW}/icons/{a["slug"]}.png" width="52" alt="{a["name"]}">'
               f"<br><sub><b>{label}</b></sub>")
        inner = img if a["coming"] else f'<a href="{SITE}/app/{a["slug"]}">{img}</a>'
        return f'<td align="center" width="105">{inner}</td>'

    out = []
    for c in cats:
        name, _, gloss = c["title"].partition("·")
        n = len(c["apps"])
        out.append(f"### {EMOJI.get(c['cid'], '•')} {name.strip()}\n\n"
                   f"<sub>{gloss.strip()} · {n} app{'s' * (n > 1)}</sub>\n\n<table>")
        for i in range(0, n, COLS):
            row = c["apps"][i:i + COLS]
            cells = "".join(cell(a) for a in row) + '<td width="105"></td>' * (COLS - len(row))
            out.append(f"<tr>{cells}</tr>")
        out.append("</table>\n")
    return "\n".join(out)


def main():
    cats = scrape()
    slugs = fetch_icons(cats)
    build_wall(slugs)
    readme = HERE / "README.md"
    body = readme.read_text()
    new, n = re.subn(r"(?<=<!-- MENU-START -->\n).*?(?=<!-- MENU-END -->)",
                     render(cats) + "\n", body, flags=re.S)
    assert n == 1, "MENU-START/END markers missing from README.md"
    readme.write_text(new)
    total = sum(len(c["apps"]) for c in cats)
    print(f"{len(cats)} collections · {total} slots · {len(slugs)} unique apps")


if __name__ == "__main__":
    main()
