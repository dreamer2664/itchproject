"""
foundry.launch -- the closest thing to end-to-end that itch.io allows.

One command takes a tool from source to a live page:

    python -m foundry.launch <slug>

It runs, in order:
  1. VERIFY     the headless gate (always; a broken tool never reaches a page)
  2. PACKAGE    zip + COPY.md + copy.json
  3. ASSETS     cover / screenshots rendered by the tool itself
  4. BROWSER    opens a headed Chromium with a persistent profile so you log
                in to itch.io ONCE and stay logged in
  5. FILL       fills every field from copy.json and uploads cover,
                screenshots and the zip
  6. PUBLISH    stops and lets YOU click Save (default), or clicks it for you
                if config.json has launch.auto_publish = true

WHY THE HUMAN CLICK IS THE DEFAULT
itch.io has no public API for creating pages (the OAuth API is read-only),
and its quality guidelines forbid automated systems mass-producing product
pages. One page per genuinely distinct tool, auto-filled but human-published,
sits comfortably on the right side of that rule. Full autopublish exists but
is opt-in, capped at 2 per day, and logged. Your account is the asset; the
click is the quality gate that keeps a bad generation from going public
unreviewed.

FIRST RUN = CALIBRATION
I cannot see itch's editor from outside, so the first run dumps the form's
field inventory to data/editor_capture/editor_fields.json and exits without
touching anything. Send that file (it is small and contains no secrets) and
an editor_selectors.json gets written from it; from then on, filling works.

Usage:
    python -m foundry.launch <slug>            # assisted: fills, you click Save
    python -m foundry.launch <slug> --capture  # force a fresh form inventory
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import date, datetime
from pathlib import Path

from playwright.sync_api import sync_playwright

from . import assets, publish
from .verify import verify

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
PROFILE = DATA / "browser-profile"
CAPTURE_DIR = DATA / "editor_capture"
SELECTORS = ROOT / "editor_selectors.json"
DB = DATA / "foundry.db"
NEW_URL = "https://itch.io/game/new"

CAPTURE_JS = """
() => {
  const labelFor = (el) => {
    try {
      if (el.labels && el.labels.length) return el.labels[0].innerText.trim();
      if (el.id) {
        const l = document.querySelector('label[for="' + el.id + '"]');
        if (l) return l.innerText.trim();
      }
      const wr = el.closest('label');
      if (wr) return wr.innerText.trim();
      let p = el.parentElement, hops = 0;
      while (p && hops < 3) {
        const l = p.querySelector('label, .label, h4, h3');
        if (l && !l.contains(el)) return l.innerText.trim();
        p = p.parentElement; hops++;
      }
    } catch (e) {}
    return "";
  };
  const out = [];
  document.querySelectorAll('input, select, textarea, button').forEach((el, i) => {
    out.push({
      i, tag: el.tagName.toLowerCase(), type: el.type || "",
      id: el.id || "", name: el.name || "",
      placeholder: el.placeholder || "", accept: el.accept || "",
      label: labelFor(el).replace(/\\s+/g, " ").slice(0, 90),
      text: (el.innerText || "").replace(/\\s+/g, " ").slice(0, 60),
      visible: !!(el.offsetWidth || el.offsetHeight),
    });
  });
  return out;
}
"""


# ---------------------------------------------------------------------------
# guardrails
# ---------------------------------------------------------------------------

def _db() -> sqlite3.Connection:
    DATA.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(DB)
    c.execute("""CREATE TABLE IF NOT EXISTS launches(
        ts TEXT, slug TEXT, mode TEXT)""")
    return c


def auto_publish_allowed(cap: int) -> bool:
    today = date.today().isoformat()
    with _db() as c:
        n = c.execute(
            "SELECT COUNT(*) FROM launches WHERE mode='auto_publish' AND ts LIKE ?",
            (today + "%",),
        ).fetchone()[0]
    return n < cap


def record(slug: str, mode: str) -> None:
    with _db() as c:
        c.execute("INSERT INTO launches VALUES (?,?,?)",
                  (datetime.now().isoformat(timespec="seconds"), slug, mode))


# ---------------------------------------------------------------------------
# selector resolution
# ---------------------------------------------------------------------------

def resolve(page, spec):
    """spec = {"by": "id|name|css|label|placeholder|text", "value": ..., "nth": 0}"""
    by, val = spec["by"], spec["value"]
    nth = spec.get("nth", 0)
    if by == "id":
        loc = page.locator(f"#{val}")
    elif by == "name":
        loc = page.locator(f'[name="{val}"]')
    elif by == "css":
        loc = page.locator(val)
    elif by == "placeholder":
        loc = page.get_by_placeholder(val)
    elif by == "text":
        loc = page.get_by_text(val, exact=False)
    elif by == "label":
        loc = page.get_by_label(val, exact=False)
    else:
        raise ValueError(f"unknown selector kind {by}")
    return loc.nth(nth) if nth else loc.first


def fill_page(page, sel: dict, copy: dict, files: dict) -> list[str]:
    """Fill what we can. Returns list of warnings for skipped fields."""
    warn: list[str] = []

    def try_fill(key: str, value: str, how: str = "fill") -> None:
        if key not in sel:
            warn.append(f"no selector for '{key}' -- fill it by hand")
            return
        loc = resolve(page, sel[key])
        if how == "fill":
            loc.fill(value)
        elif how == "check":
            loc.check(force=True)
        elif how == "click":
            loc.click()

    try_fill("title", copy["title"])
    try_fill("short_description", copy["tagline"])
    try_fill("description", copy["description"])
    try_fill("tags", ", ".join(copy["tags"]))
    for key in ("kind_tool", "in_browser", "pricing_none"):
        if key in sel:
            try_fill(key, "", how="check" if key != "pricing_none" else "click")

    for key, path_key in (("cover", "cover_gif"), ("screenshots", "screenshots"),
                          ("zip", "zip")):
        if key not in sel:
            warn.append(f"no selector for '{key}' upload -- attach by hand")
            continue
        p = files.get(path_key)
        if not p or not p.exists():
            warn.append(f"missing file for '{key}': {p}")
            continue
        if path_key == "screenshots":
            resolve(page, sel[key]).set_input_files(files["screenshots_list"])
        else:
            resolve(page, sel[key]).set_input_files(str(p))
    return warn


# ---------------------------------------------------------------------------
# capture
# ---------------------------------------------------------------------------

def capture(page) -> Path:
    CAPTURE_DIR.mkdir(parents=True, exist_ok=True)
    fields = page.evaluate(CAPTURE_JS)
    out = CAPTURE_DIR / "editor_fields.json"
    out.write_text(json.dumps(fields, indent=1), encoding="utf-8")
    (CAPTURE_DIR / "editor_page.html").write_text(page.content(), encoding="utf-8")
    return out


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("slug")
    ap.add_argument("--capture", action="store_true",
                    help="dump the editor form inventory and exit")
    args = ap.parse_args(argv)

    cfg = publish.load_config()
    tool = publish.get_tool(cfg, args.slug)
    launch_cfg = cfg.get("launch", {})
    cap = int(launch_cfg.get("max_auto_publish_per_day", 2))
    want_auto = bool(launch_cfg.get("auto_publish", False))

    print("== 1/5 VERIFY ==")
    if not verify(ROOT / "tools" / args.slug, DATA / "screenshots"):
        print("\nGATE FAILED -- nothing will be published.")
        return 1

    print("\n== 2/5 PACKAGE ==")
    out_dir = publish.package(cfg, tool)

    print("\n== 3/5 ASSETS ==")
    assets.main([args.slug])

    copy = json.loads((out_dir / "copy.json").read_text(encoding="utf-8"))
    files = {
        "zip": out_dir / copy["files"]["zip"],
        "cover_gif": out_dir / copy["files"]["cover_gif"],
        "cover_png": out_dir / copy["files"]["cover_png"],
        "screenshots_list": [str(out_dir / s) for s in copy["files"]["screenshots"]],
    }

    sel = None
    if SELECTORS.exists() and not args.capture:
        sel = json.loads(SELECTORS.read_text(encoding="utf-8"))

    print("\n== 4/5 BROWSER ==")
    PROFILE.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        ctx = pw.chromium.launch_persistent_context(
            str(PROFILE), headless=False,
            viewport={"width": 1280, "height": 900},
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto(NEW_URL, wait_until="domcontentloaded")
        page.wait_for_timeout(1500)

        if "login" in page.url:
            print("  Not logged in. Log in in the opened browser window.")
            print("  (This profile is persistent: you won't be asked again.)")
            try:
                page.wait_for_url("**/game/new*", timeout=300_000)
            except Exception:
                print("  Timed out waiting for login. Re-run when ready.")
                ctx.close()
                return 1
            page.wait_for_timeout(1500)

        if args.capture or sel is None:
            print("== CALIBRATION: dumping editor form inventory ==")
            out = capture(page)
            print(f"  wrote {out.relative_to(ROOT)}")
            print(f"  and  { (CAPTURE_DIR / 'editor_page.html').relative_to(ROOT) }")
            print("\n  Nothing was filled or submitted.")
            print("  Send editor_fields.json back (paste it or push it) and an")
            print("  editor_selectors.json will be produced from it. Re-run after.")
            ctx.close()
            return 0

        print("\n== 5/5 FILL ==")
        warns = fill_page(page, sel, copy, files)
        for w in warns:
            print("  !", w)
        print("  Filled: title, tagline, description, tags, kind, uploads.")

        mode = "assisted"
        if want_auto:
            if auto_publish_allowed(cap):
                if "save" in sel:
                    resolve(page, sel["save"]).click()
                    mode = "auto_publish"
                    record(args.slug, mode)
                    page.wait_for_timeout(2500)
                    print(f"  Published automatically: {page.url}")
                else:
                    print("  ! no selector for 'save' -- click Save yourself")
            else:
                print(f"  Auto-publish cap reached ({cap}/day). Click Save yourself.")
        if mode == "assisted":
            record(args.slug, mode)
            print("\n  REVIEW THE PAGE IN THE BROWSER WINDOW.")
            print("  If everything looks right, click Save/publish yourself.")
            print("  (This click is the quality gate. Keep it until you trust")
            print("   the pipeline completely; see launch.auto_publish.)")
            print("  The browser stays open for 5 minutes so you can finish.")
            page.wait_for_timeout(300_000)
        ctx.close()

    print("\nDone. Updates from here on are one command:")
    print(f"    python -m foundry.publish push {args.slug}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
