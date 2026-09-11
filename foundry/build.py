"""
foundry.build -- the whole pipeline in one command.

    python -m foundry.build <tool-slug>

Runs, in order:
  1. VERIFY    headless-browser checks (the hard gate -- nothing ships on a fail)
  2. PACKAGE   zip + paste-ready page copy into build/<slug>/
  3. CHECKPOINT instructions for the one manual step (creating the itch page)

Step 1 is skipped with a warning if Playwright is not installed; that is
acceptable for a quick iteration but NEVER for a first publish. The gate
exists because a broken tool on a public page costs you reviews you cannot
get back.

Usage:
    python -m foundry.build dungeon-map-generator
    python -m foundry.build dungeon-map-generator --skip-verify
"""
from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

from . import publish

ROOT = Path(__file__).resolve().parent.parent


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("slug")
    ap.add_argument("--skip-verify", action="store_true")
    args = ap.parse_args(argv)

    cfg = publish.load_config()
    tool = publish.get_tool(cfg, args.slug)

    have_pw = importlib.util.find_spec("playwright") is not None

    if not args.skip_verify:
        if have_pw:
            from .verify import verify
            print("== STEP 1: VERIFY ==")
            if not verify(ROOT / "tools" / args.slug, ROOT / "data" / "screenshots"):
                print("\nGATE FAILED. Nothing was packaged. Fix the tool and re-run.")
                return 1
        else:
            print("== STEP 1: VERIFY SKIPPED (playwright not installed) ==")
            print("   pip install playwright && python -m playwright install chromium")
            print("   Do NOT publish a first version without running this gate.")
    else:
        print("== STEP 1: VERIFY SKIPPED (--skip-verify) ==")

    print("\n== STEP 2: PACKAGE ==")
    publish.package(cfg, tool)

    print("\n== STEP 3: CHECKPOINT ==")
    publish.page_instructions(cfg, tool)

    print("Done. When the page exists, ship it with:")
    print(f"    python -m foundry.publish push {args.slug}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
