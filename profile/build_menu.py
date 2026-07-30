#!/usr/bin/env python3
"""Regenerate the app grid and hero poster in profile/README.md from the live site.

Scrapes getapps.cafe, pulls every app icon (CDN PNG or inline SVG) into
profile/icons/, renders the isometric poster (light + dark), and rewrites the
section between the MENU markers.

    pip install pillow && brew install librsvg
    python3 profile/build_menu.py

Everything outside the MENU markers is left alone, including the
WEEKLY-REPORT block written by the release bot.
"""
import html
import io
import re
import subprocess
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

SITE = "https://getapps.cafe"
RAW = "https://raw.githubusercontent.com/getappscafe/.github/main/profile"
HERE = Path(__file__).parent
ICONS = HERE / "icons"
COLS = 6
EMOJI = {"house": "🎁", "espresso": "☕", "latte": "🥛", "mocha": "🍫",
         "americano": "🫘", "coldbrew": "🧊", "frappe": "🥤", "pourover": "💧"}
FONT = "/System/Library/Fonts/Avenir Next.ttc"      # Bold=0, DemiBold=2, Regular=7
SS = 2                                              # supersample, downscaled at the end
MAX_W = 1720                                        # final poster width in px
K = 1 / 3                                           # isometric shear: 1 down per 3 across
# Poster showcase, front panel first. Only some apps ship screenshots; these do.
SHOWCASE = ["doccafe", "lofilatte", "brewser", "nitronet", "stickyboard", "sheetcafe"]

# Straight from getapps.cafe/styles.css — :root and :root[data-theme="dark"].
# Keep these in sync with the site rather than inventing values.
THEMES = {
    "poster.png": dict(bg=(0xEE, 0xF1, 0xF5), ink=(0x1A, 0x22, 0x33), accent=(0x00, 0x7A, 0xFF),
                       muted=(0x8A, 0x93, 0xA3), line=(0xD8, 0xDD, 0xE5), shadow=(26, 34, 51, 46)),
    "poster-dark.png": dict(bg=(0x16, 0x18, 0x1D), ink=(0xF0, 0xF2, 0xF5), accent=(0x0A, 0x84, 0xFF),
                            muted=(0x82, 0x8B, 0x99), line=(0x30, 0x34, 0x3C), shadow=(0, 0, 0, 110)),
}

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


def font(px, index=0):
    try:
        return ImageFont.truetype(FONT, px, index=index)
    except OSError:                                  # non-macOS box
        return ImageFont.load_default(px)


def fetch_shots(names):
    """Grab one full-size UI screenshot per showcase app, straight off its /app page."""
    shots = []
    for slug in SHOWCASE:
        page = get(f"{SITE}/app/{slug}").decode()
        urls = [u for u in dict.fromkeys(re.findall(r"https://screenshot\.getapps\.cafe/[^\"]+\.png", page))
                if slug.replace("-", "") in u.replace("-", "")]
        for u in urls:
            im = Image.open(io.BytesIO(get(u)))
            if im.width > 600:                       # skip the 284px icon served from the same host
                shots.append((im, slug, names[slug]))
                break
        else:
            raise SystemExit(f"no screenshot found for {slug}")
    return shots


def iso_panel(im, w):
    """Shear an upright screenshot onto an isometric plane; verticals stay vertical."""
    im = im.convert("RGBA")
    im = im.crop(im.getbbox())                       # drop the transparent window-shadow margin
    h = int(w * im.height / im.width)
    im = im.resize((w, h), Image.LANCZOS)
    # forward: X=u, Y=v+K*u  ->  inverse: u=X, v=Y-K*X
    return im.transform((w, h + int(w * K)), Image.AFFINE,
                        (1, 0, 0, -K, 1, 0), resample=Image.BICUBIC)


def window_stack(shots, t, PW, frac=0.46):
    """Panels receding up-right along the depth axis, each labelled with its icon."""
    step = int(PW * frac)
    panels = [(iso_panel(im, PW), slug, name) for im, slug, name in shots]
    ph = panels[0][0].height
    M, LBL = 60 * SS, 46 * SS
    W = panels[-1][0].width + (len(panels) - 1) * step + 2 * M
    H = ph + int((len(panels) - 1) * step * K) + 2 * M + LBL
    art = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ds = ImageDraw.Draw(sh, "RGBA")
    top_y = int((len(panels) - 1) * step * K)         # back panel is highest
    place = [(M + i * step, M + LBL + top_y - int(i * step * K)) for i in range(len(panels))]

    for i in reversed(range(len(panels))):            # painter's order: back to front
        p = panels[i][0]
        ox, oy = place[i]
        pw, phh = p.size
        quad = [(ox, oy), (ox + pw, oy + int(pw * K)),
                (ox + pw, oy + phh), (ox, oy + phh - int(pw * K))]
        ds.polygon([(x + 10 * SS, y + 18 * SS) for x, y in quad], fill=t["shadow"])
        art.alpha_composite(p, (ox, oy))

    art = Image.alpha_composite(sh.filter(ImageFilter.GaussianBlur(14 * SS)), art)
    d = ImageDraw.Draw(art, "RGBA")                   # rebind: the composite above replaced `art`
    for (ox, oy), (_, slug, name) in zip(place, panels):
        ic = Image.open(ICONS / f"{slug}.png").convert("RGBA").resize((30 * SS, 30 * SS), Image.LANCZOS)
        art.alpha_composite(ic, (ox, oy - 38 * SS))
        d.text((ox + 38 * SS, oy - 23 * SS), name, font=font(26 * SS, 0),
               fill=t["ink"] + (255,), anchor="lm")
    return art.crop(art.getbbox())


def build_poster(shots, name, t):
    art = window_stack(shots, t, PW=760 * SS)
    PAD, HEAD = 70 * SS, 250 * SS
    W, H = art.width + PAD * 2, art.height + HEAD + PAD
    img = Image.new("RGBA", (W, H), t["bg"] + (255,))
    d = ImageDraw.Draw(img)
    x, xr = PAD + 10 * SS, W - PAD - 10 * SS
    d.text((x, 62 * SS), "getapps.cafe", font=font(76 * SS, 0), fill=t["ink"])
    d.text((x, 152 * SS), "apps · served fresh", font=font(40 * SS, 2), fill=t["accent"])
    d.text((xr, 168 * SS), "native apps for macOS & Windows · one subscription",
           font=font(32 * SS, 7), fill=t["muted"], anchor="rs")
    d.line([(x, 205 * SS), (xr, 205 * SS)], fill=t["line"], width=2 * SS)
    img.paste(art, (PAD, HEAD), art)
    by = H - PAD - 18 * SS                           # caption fills the wedge under the stack
    d.text((xr, by - 52 * SS), "Every app. Every update. Every device on your plan.",
           font=font(34 * SS, 2), fill=t["ink"], anchor="rs")
    d.text((xr, by), "getapps.cafe", font=font(34 * SS, 0), fill=t["accent"], anchor="rs")

    img = img.resize((W // SS, H // SS), Image.LANCZOS)
    if img.width > MAX_W:                            # README shows it at 860; 2x is plenty
        img = img.resize((MAX_W, round(img.height * MAX_W / img.width)), Image.LANCZOS)
    mask = Image.new("L", img.size, 0)               # rounded card corners
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, img.width - 1, img.height - 1], 20, fill=255)
    img.putalpha(mask)
    img.save(HERE / name, optimize=True)


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
    names = {a["slug"]: a["name"] for c in cats for a in c["apps"]}
    shots = fetch_shots(names)
    for name, theme in THEMES.items():
        build_poster(shots, name, theme)
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
