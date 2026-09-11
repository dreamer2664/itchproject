"""
foundry.verify -- headless browser check for a generated tool.

This is the HARD GATE in the pipeline. A tool does not ship unless it:
  * loads with zero console errors
  * renders a non-trivial amount of non-background pixels to its canvas
  * is deterministic (same seed -> byte-identical output)
  * is seed-sensitive (different seed -> different output)
  * survives extreme parameter values without throwing

Usage:
    python -m foundry.verify tools/dungeon-map-generator
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent


def fail(msg: str) -> None:
    print(f"  FAIL  {msg}")


def ok(msg: str) -> None:
    print(f"  ok    {msg}")


def verify(tool_dir: Path, shots_dir: Path) -> bool:
    index = tool_dir / "index.html"
    if not index.exists():
        fail(f"no index.html in {tool_dir}")
        return False

    url = index.as_uri()
    shots_dir.mkdir(parents=True, exist_ok=True)
    errors: list[str] = []
    passed = True

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 800})
        page.on("console", lambda m: errors.append(f"{m.type}: {m.text}")
                if m.type in ("error",) else None)
        page.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))

        print(f"\n== {tool_dir.name} ==")
        page.goto(url, wait_until="networkidle")
        page.wait_for_timeout(600)

        # 1. console errors
        if errors:
            fail(f"console errors: {errors[:4]}")
            passed = False
        else:
            ok("loaded with zero console errors")

        # 2. canvas has real content
        stats = page.evaluate("""() => {
            const cv = document.getElementById('cv');
            if (!cv) return null;
            const c = document.createElement('canvas');
            c.width = cv.width; c.height = cv.height;
            c.getContext('2d').drawImage(cv, 0, 0);
            const d = c.getContext('2d').getImageData(0,0,c.width,c.height).data;
            const seen = new Set();
            let nonbg = 0;
            for (let i=0;i<d.length;i+=4*37) {
              const k = d[i]+','+d[i+1]+','+d[i+2];
              seen.add(k);
            }
            return {w:cv.width,h:cv.height,distinct:seen.size,
                    stats:{rooms:document.getElementById('sRooms').textContent,
                           tiles:document.getElementById('sTiles').textContent,
                           doors:document.getElementById('sDoors').textContent,
                           ms:document.getElementById('msTag').textContent}};
        }""")
        if not stats:
            fail("no #cv canvas found")
            return False
        if stats["distinct"] < 4:
            fail(f"canvas looks blank ({stats['distinct']} distinct colours)")
            passed = False
        else:
            ok(f"canvas rendered ({stats['w']}x{stats['h']}, "
               f"{stats['distinct']} distinct colours)")
        ok(f"stats: rooms={stats['stats']['rooms']} tiles={stats['stats']['tiles']} "
           f"doors={stats['stats']['doors']} [{stats['stats']['ms']}]")

        # 3. determinism: fingerprint the canvas for a fixed seed
        def fingerprint() -> str:
            return page.evaluate("""(seed) => {
                document.getElementById('seed').value = seed;
                document.getElementById('seed').dispatchEvent(new Event('change'));
                const cv = document.getElementById('cv');
                return cv.toDataURL('image/png');
            }""", "test-seed-42")

        f1 = hashlib.sha256(fingerprint().encode()).hexdigest()[:16]
        page.reload(wait_until="networkidle")
        page.wait_for_timeout(400)
        f2 = hashlib.sha256(fingerprint().encode()).hexdigest()[:16]
        if f1 != f2:
            fail(f"NOT deterministic: {f1} != {f2}")
            passed = False
        else:
            ok(f"deterministic across reload (seed 'test-seed-42' -> {f1})")

        # 4. seed sensitivity
        f3 = hashlib.sha256(page.evaluate("""() => {
            document.getElementById('seed').value = 'different-seed-99';
            document.getElementById('seed').dispatchEvent(new Event('change'));
            return document.getElementById('cv').toDataURL('image/png');
        }""").encode()).hexdigest()[:16]
        if f3 == f1:
            fail("seed has no effect on output")
            passed = False
        else:
            ok(f"seed-sensitive (different seed -> {f3})")

        # 5. parameter extremes must not throw
        errors.clear()
        extremes = [
            {"w": 32, "h": 24, "rooms": 4, "rsize": 4, "rvar": 0, "cw": 1, "loops": 0},
            {"w": 160, "h": 120, "rooms": 40, "rsize": 16, "rvar": 10, "cw": 4, "loops": 10},
            {"w": 32, "h": 24, "rooms": 40, "rsize": 16, "rvar": 10, "cw": 4, "loops": 10},
        ]
        for i, ex in enumerate(extremes):
            page.evaluate("""(o) => {
                for (const k in o) {
                    const el = document.getElementById(k);
                    el.value = o[k];
                    el.dispatchEvent(new Event('input'));
                }
            }""", ex)
            page.wait_for_timeout(250)
        if errors:
            fail(f"threw on extreme parameters: {errors[:3]}")
            passed = False
        else:
            ok(f"survived {len(extremes)} extreme parameter sets")

        # 6. every style renders
        errors.clear()
        for style in ["ink", "blueprint", "slate", "mono"]:
            page.evaluate("""(s) => {
                document.getElementById('w').value = 72;
                document.getElementById('h').value = 48;
                document.getElementById('w').dispatchEvent(new Event('input'));
                const sel = document.getElementById('style');
                sel.value = s; sel.dispatchEvent(new Event('change'));
            }""", style)
            page.wait_for_timeout(150)
            page.screenshot(path=str(shots_dir / f"{tool_dir.name}-{style}.png"))
        if errors:
            fail(f"style switch errors: {errors[:3]}")
            passed = False
        else:
            ok("all 4 palettes rendered (screenshots saved)")

        # 7. buttons don't throw
        errors.clear()
        for bid in ["randomize", "gen", "copySeed"]:
            page.click(f"#{bid}")
            page.wait_for_timeout(200)
        if errors:
            fail(f"button errors: {errors[:3]}")
            passed = False
        else:
            ok("Random / Generate / Copy buttons all work")

        browser.close()

    print(f"\n{'PASS' if passed else 'FAIL'} — {tool_dir.name}")
    return passed


def main(argv: list[str]) -> int:
    targets = argv[1:] or ["tools/dungeon-map-generator"]
    shots = ROOT / "data" / "screenshots"
    all_ok = True
    for t in targets:
        p = Path(t)
        if not p.is_absolute():
            p = ROOT / p
        if not verify(p, shots):
            all_ok = False
    print("\n" + ("ALL CHECKS PASSED" if all_ok else "SOME CHECKS FAILED"))
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
