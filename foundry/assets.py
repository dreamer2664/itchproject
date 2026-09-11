"""
foundry.assets -- generate store-page art FROM the tool itself.

No design software, no stock imagery, no AI image generation: the cover art
is the product rendering itself. That also keeps every screenshot honest --
itch.io's rules prohibit misleading imagery, and these are literal frames of
the tool running.

Produces, in build/<slug>/:
    cover.png      630x500  (itch's recommended cover size)
    cover.gif      animated cover: the same dungeon family across seeds
    gallery-*.png  full-page shots, one per palette

Usage:
    python -m foundry.assets dungeon-map-generator
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent

COVER_W, COVER_H = 630, 500

# Seeds chosen to look good on a store page. Deterministic, so this art is
# reproducible forever.
COVER_SEED = "hollow-catacomb-4271"
GIF_SEEDS = [
    "hollow-catacomb-4271",
    "gilded-undercroft-2214",
    "sunken-reliquary-8830",
    "brazen-ossuary-1407",
    "whispering-barrow-5562",
    "obsidian-sanctum-3391",
]
PALETTES = ["ink", "blueprint", "slate", "mono"]


def _set_state(page, seed: str, style: str | None = None, labels: bool = True) -> None:
    page.evaluate(
        """([seed, style, labels]) => {
            const s = document.getElementById('seed');
            s.value = seed; s.dispatchEvent(new Event('change'));
            if (style) {
                const st = document.getElementById('style');
                st.value = style; st.dispatchEvent(new Event('change'));
            }
            const l = document.getElementById('optLabels');
            if (l && l.checked !== labels) { l.checked = labels; l.dispatchEvent(new Event('change')); }
        }""",
        [seed, style, labels],
    )
    page.wait_for_timeout(150)
    page.evaluate("fit()")
    page.wait_for_timeout(120)


def _crop_to(path: Path, w: int, h: int) -> None:
    im = Image.open(path)
    if im.size != (w, h):
        im = im.resize((w, h), Image.LANCZOS)
        im.save(path)


def main(argv: list[str] | None = None) -> int:
    slug = (argv or sys.argv[1:])[0] if (argv or sys.argv[1:]) else "dungeon-map-generator"
    tool = ROOT / "tools" / slug
    out = ROOT / "build" / slug
    out.mkdir(parents=True, exist_ok=True)
    url = (tool / "index.html").resolve().as_uri()

    with sync_playwright() as pw:
        browser = pw.chromium.launch()

        # ---- cover: stage sized exactly 630x500 ----
        page = browser.new_page(viewport={"width": 264 + COVER_W, "height": 46 + COVER_H})
        page.goto(url, wait_until="networkidle")
        page.wait_for_timeout(400)
        _set_state(page, COVER_SEED, style="ink")
        page.locator("#stage").screenshot(path=str(out / "cover.png"))
        _crop_to(out / "cover.png", COVER_W, COVER_H)
        print(f"  cover.png   {COVER_W}x{COVER_H}")

        # ---- animated cover ----
        frames = []
        for i, seed in enumerate(GIF_SEEDS):
            _set_state(page, seed)
            tmp = out / f"_frame{i}.png"
            page.locator("#stage").screenshot(path=str(tmp))
            _crop_to(tmp, COVER_W, COVER_H)
            frames.append(Image.open(tmp).convert("P", palette=Image.ADAPTIVE, colors=128))
        frames[0].save(
            out / "cover.gif",
            save_all=True,
            append_images=frames[1:],
            duration=750,
            loop=0,
            optimize=True,
        )
        for i in range(len(GIF_SEEDS)):
            (out / f"_frame{i}.png").unlink(missing_ok=True)
        print(f"  cover.gif   {len(frames)} frames, "
              f"{(out / 'cover.gif').stat().st_size:,} bytes")

        # ---- gallery: full-page, one per palette ----
        page.close()
        page = browser.new_page(viewport={"width": 1280, "height": 800})
        page.goto(url, wait_until="networkidle")
        page.wait_for_timeout(400)
        for style in PALETTES:
            _set_state(page, COVER_SEED, style=style)
            page.screenshot(path=str(out / f"gallery-{style}.png"))
            print(f"  gallery-{style}.png")

        browser.close()

    print(f"\nArt written to {out.relative_to(ROOT)}/ -- upload cover.png (or cover.gif)")
    print("as the page cover and the gallery-*.png files as screenshots.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
