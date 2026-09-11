"""
foundry.publish -- package a tool and hand it to itch.io via butler.

The pipeline's last two steps:

  package   zip the tool into build/<slug>/ and write COPY.md
            (title, tagline, description, tags -- ready to paste)

  push      run `butler push` for you. Works from the Windows terminal.

  page      print the 90-second manual checkpoint: exactly what to click
            on itch.io and exactly what text to paste.

WHY THERE IS A MANUAL STEP
butler can only push files to a project page that already exists; it cannot
create the page. itch.io has no public API for page creation. The checkpoint
below is therefore part of the design, not a gap. It is also your quality
gate -- itch.io's rules prohibit automated mass page creation and we obey
them, because that is what keeps the account alive.

Usage:
    python -m foundry.publish package dungeon-map-generator
    python -m foundry.publish page    dungeon-map-generator
    python -m foundry.publish push    dungeon-map-generator [--channel html5]
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / "build"
CONFIG = ROOT / "config.json"
LOCAL_BUTLER = ROOT / "bin" / "butler.exe"


def load_config() -> dict:
    with CONFIG.open(encoding="utf-8") as f:
        return json.load(f)


def get_tool(cfg: dict, slug: str) -> dict:
    for t in cfg["tools"]:
        if t["slug"] == slug:
            return t
    sys.exit(f"No tool named '{slug}' in config.json")


def butler_path() -> str | None:
    if LOCAL_BUTLER.exists():
        return str(LOCAL_BUTLER)
    return shutil.which("butler")


# ---------------------------------------------------------------------------
# package
# ---------------------------------------------------------------------------

DESCRIPTION_TEMPLATE = """{tagline}

**Delve** builds a complete dungeon from a seed in about a millisecond, entirely in
your browser. Nothing is downloaded, nothing phones home, there are no assets and
no dependencies -- the whole tool is one HTML file you can keep forever.

## What it does

- **Deterministic seeds.** Type a seed, get a dungeon. Share the seed, get the
  *same* dungeon. Every layout is reproducible exactly, which matters when you
  want to discuss or reuse a specific map.
- **Real dungeon structure.** Rooms placed by rejection sampling, connected by a
  minimum spanning tree so every room is reachable, plus optional loop corridors
  so the map is not a boring tree. Doorways are placed on room perimeters.
- **Tuned everything.** Grid size, room count, room size and variance, corridor
  width, loop density.
- **Four palettes** -- ink-on-parchment, blueprint, slate, and a mono
  tile-ready style.
- **Exports that are actually useful:**
  - PNG at 1x and 2x
  - **Tiles JSON** -- a W x H integer grid plus room/door/stair coordinates
  - **Tiles CSV** -- the same grid, dead simple to parse

## Tile legend

`0` void - `1` floor - `2` wall - `3` corridor - `4` door - `5` stairs - `6` prop

## Built for reuse

The generator is plain, readable JavaScript with a seeded PRNG (mulberry32 over
a cyrb128 hash). No `Math.random` anywhere in generation. Read it, fork it,
steal the algorithm -- it is deliberately simple.

## Honest notes

- Runs offline. Save the file, open it anywhere, forever.
- Keyboard: `space` regenerate, `r` random seed, `f` fit to screen.
- Everything is generated procedurally by a self-contained algorithm. No
  neural networks, no scraped data, no external assets.
"""


def package(cfg: dict, tool: dict) -> Path:
    src = ROOT / "tools" / tool["slug"]
    if not (src / "index.html").exists():
        sys.exit(f"{src} has no index.html")

    out = BUILD / tool["slug"]
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    # copy the tool's files
    for f in src.iterdir():
        if f.is_file():
            shutil.copy2(f, out / f.name)

    # zip it (this is what butler pushes)
    zpath = out / f"{tool['slug']}.zip"
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(src.rglob("*")):
            if f.is_file():
                z.write(f, f.relative_to(src).as_posix())

    # draft copy for the itch page
    desc = DESCRIPTION_TEMPLATE.format(tagline=tool["tagline"])
    tags = ", ".join(tool["tags"])
    copy = f"""# Paste-ready copy for the itch.io page

## Title
{tool['title']}

## Short description / tagline
{tool['tagline']}

## Classification
Kind of project: **Tool**
Runs in browser: **Yes** (tick "This file will be played in the browser")
Also downloadable: **Yes** (upload {tool['slug']}.zip too, marked "HTML")

## Tags (paste, comma separated)
{tags}

## Recommended price
${tool['price_usd'] or 0}{" + pay-what-you-want" if tool.get('pay_what_you_want') else ""}
{"**LAUNCH MODE: FREE.** Set pricing to 'No payments'. Leave 'Accept donations' OFF. While no adult operates the account's payout side, no money must be able to flow in -- not even a tip. itch's payment processors restrict receiving money to adults, so a free project with donations enabled would put the account out of compliance. Flip both on at 18, or the day an adult takes over payouts." if tool.get('launch_mode') == 'free' else "(Adjust after running `python -m foundry.scout --history`: match the median price of whatever niche scores highest.)"}

## Generative AI disclosure
Select: **No, this project does not contain generative AI content.**
Rationale, for your own records: all output comes from a self-contained
deterministic algorithm (seeded PRNG, rejection sampling, minimum spanning
tree). No neural networks, no external datasets. This is exactly the case
itch.io's guidelines describe as NOT requiring an AI tag.

## Description (markdown, paste as-is)
{desc}
"""
    (out / "COPY.md").write_text(copy, encoding="utf-8")

    print(f"packaged -> {out.relative_to(ROOT)}/")
    print(f"  index.html        ({(out/'index.html').stat().st_size:,} bytes)")
    print(f"  {tool['slug']}.zip  ({zpath.stat().st_size:,} bytes)")
    print(f"  COPY.md           (paste-ready page text)")
    return out


# ---------------------------------------------------------------------------
# page (the manual checkpoint)
# ---------------------------------------------------------------------------

def page_instructions(cfg: dict, tool: dict) -> None:
    uname = cfg["itch"].get("username") or "<your-itch-username>"
    print(f"""
==========================================================================
 CHECKPOINT -- create the itch.io page (~90 seconds, once per tool)
==========================================================================
 butler cannot create pages; only you can. Do this:

 1. https://itch.io/dashboard  ->  "Create new project"
 2. Title:            {tool['title']}
    Kind of project:  Tool
    Classification:   tick "This file will be played in the browser"
    Session:          Single player
 3. Paste the description from:  build/{tool['slug']}/COPY.md
 4. Tags: paste the tag line from COPY.md
 5. Uploads: add build/{tool['slug']}/{tool['slug']}.zip as kind "HTML",
    tick "This file will be played in the browser".
 6. Pricing: {"**No payments** (strictly free)" if tool.get('launch_mode') == 'free' else ("pay-what-you-want, minimum $0" if tool.get('pay_what_you_want') else f"${tool['price_usd']}")}
    {"Also leave 'Accept donations' OFF. No money may flow in until an adult operates payouts." if tool.get('launch_mode') == 'free' else ""}
 7. Generative AI disclosure: "No" (see COPY.md for the rationale)
 8. Visibility: Public. Save.
 9. Note the page URL. It should be:
        https://{uname}.itch.io/{tool['slug']}

 Then run:
        python -m foundry.publish push {tool['slug']}
==========================================================================
""")


# ---------------------------------------------------------------------------
# push
# ---------------------------------------------------------------------------

def push(cfg: dict, tool: dict, channel: str) -> int:
    butler = butler_path()
    if not butler:
        sys.exit(
            "butler not found.\n"
            "  Windows: run  powershell -ExecutionPolicy Bypass -File setup.ps1\n"
            "  or download from https://itch.io/docs/butler/ and put it on PATH."
        )
    uname = cfg["itch"].get("username")
    if not uname:
        sys.exit('Set your itch username in config.json:  "itch": {"username": "..."}')

    key_env = cfg["itch"].get("api_key_env", "BUTLER_API_KEY")
    if not os.environ.get(key_env):
        print(f"WARNING: {key_env} is not set. butler will open a browser to log in.",
              file=sys.stderr)
        print(f"  (Get a key at https://itch.io/user/settings/api-keys and run:",
              file=sys.stderr)
        print(f"   set {key_env}=********  in your terminal first.)", file=sys.stderr)

    src = ROOT / "tools" / tool["slug"]
    target = f"{uname}/{tool['slug']}:{channel}"
    cmd = [butler, "push", str(src), target, "--userversion", "0.1.0"]
    print("running:", " ".join(cmd))
    return subprocess.call(cmd)


# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("action", choices=["package", "page", "push"])
    ap.add_argument("slug")
    ap.add_argument("--channel", default="html5")
    args = ap.parse_args(argv)

    cfg = load_config()
    tool = get_tool(cfg, args.slug)

    if args.action == "package":
        package(cfg, tool)
    elif args.action == "page":
        page_instructions(cfg, tool)
    elif args.action == "push":
        package(cfg, tool)
        return push(cfg, tool, args.channel)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
