# .github

Organization-level defaults for **getapps.cafe**.

| Path | What it is |
| --- | --- |
| [`profile/README.md`](profile/README.md) | The public org profile at [github.com/getappscafe](https://github.com/getappscafe) |
| [`profile/build_menu.py`](profile/build_menu.py) | Regenerates the app grid from the live site |
| [`profile/icons/`](profile/icons/) | 57 app icons, 128×128 — pulled from getapps.cafe |
| [`profile/menu.png`](profile/menu.png) | Hero wall of every app icon |
| [`profile/avatar.svg`](profile/avatar.svg) | Org avatar, source — traced from the getapps.cafe app icon |
| [`profile/avatar.png`](profile/avatar.png) | Org avatar, 512×512 — upload at Settings → Profile picture |

Brand: `#007AFF` on `#FAF6EF`.

## Updating the menu

When apps are added, renamed, or ship out of "coming soon", rerun:

```sh
pip install pillow && brew install librsvg
python3 profile/build_menu.py
```

It rewrites only the block between the `MENU-START` / `MENU-END` markers, so the
release bot's `WEEKLY-REPORT` section and everything else stay untouched.
Prices, plan details, and copy are **not** generated — edit those by hand.

Regenerate the avatar PNG after editing the SVG:

```sh
rsvg-convert -w 512 -h 512 profile/avatar.svg -o profile/avatar.png
```
