# .github

Organization-level defaults for **getapps.cafe**.

| Path | What it is |
| --- | --- |
| [`profile/README.md`](profile/README.md) | The public org profile at [github.com/getappscafe](https://github.com/getappscafe) |
| [`profile/build_menu.py`](profile/build_menu.py) | Regenerates the poster and app grid from the live site |
| [`profile/icons/`](profile/icons/) | 57 app icons, 128×128 — pulled from getapps.cafe |
| [`profile/poster.png`](profile/poster.png) | Isometric hero poster — real app UI as sheared 3D panels |
| [`profile/poster-dark.png`](profile/poster-dark.png) | Same poster in the site's dark theme; README picks via `<picture>` |
| [`profile/avatar.svg`](profile/avatar.svg) | Org avatar, source — traced from the getapps.cafe app icon |
| [`profile/avatar.png`](profile/avatar.png) | Org avatar, 512×512 — upload at Settings → Profile picture |

Poster colours come from `getapps.cafe/styles.css` (`:root` and
`:root[data-theme="dark"]`) — see `THEMES` in the build script. Keep them in sync
with the site rather than inventing values.

The poster showcases the apps listed in `SHOWCASE`. Only some apps publish UI
screenshots, so that list can only be drawn from those — the script fails loudly
if a chosen app has none.

`FREE_EXTRA` lists apps we serve free that the site still files as paid. They get
added to **On the House** and marked 🆓 while staying in their own category — the
same "derived row" convention the site uses. Remove an entry once the site itself
moves the app, or the override becomes a silent no-op.

## Updating the menu

When apps are added, renamed, or ship out of "coming soon", rerun:

```sh
pip install pillow && brew install librsvg
python3 profile/build_menu.py
```

It refreshes `icons/`, re-renders `poster.png`, and rewrites only the block between
the `MENU-START` / `MENU-END` markers — the release bot's `WEEKLY-REPORT` section and
everything else stay untouched. Prices, plan details, and copy are **not** generated
— edit those by hand.

The poster needs the Avenir Next system font (macOS); elsewhere it falls back to
PIL's default face and the headline will look off.

Regenerate the avatar PNG after editing the SVG:

```sh
rsvg-convert -w 512 -h 512 profile/avatar.svg -o profile/avatar.png
```
