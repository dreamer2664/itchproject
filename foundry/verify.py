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
            const g = id => { const e = document.getElementById(id); return e ? e.textContent : ''; };
            return {w:cv.width,h:cv.height,distinct:seen.size,
                    statsLine:(document.getElementById('statsLine')||{}).textContent||'',
                    stats:{rooms:g('sRooms'),tiles:g('sTiles'),doors:g('sDoors'),ms:g('msTag')}};
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
        line = stats.get("statsLine") or ""
        if line.strip():
            ok(f"stats: {line.strip()[:90]}")
        elif any(stats.get("stats", {}).values()):
            st = stats["stats"]
            ok(f"stats: rooms={st.get('rooms')} tiles={st.get('tiles')} "
               f"doors={st.get('doors')} [{st.get('ms')}]")

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

        # 5. parameter extremes must not throw (generic: every slider and
        #    every select on the page, whatever the tool is)
        errors.clear()
        page.evaluate("""() => {
            document.querySelectorAll('input[type=range]').forEach(r => {
                r.value = r.min; r.dispatchEvent(new Event('input'));
            });
        }""")
        page.wait_for_timeout(300)
        page.evaluate("""() => {
            document.querySelectorAll('input[type=range]').forEach(r => {
                r.value = r.max; r.dispatchEvent(new Event('input'));
            });
        }""")
        page.wait_for_timeout(300)
        page.evaluate("""async () => {
            for (const s of document.querySelectorAll('select')) {
                for (let i = 0; i < s.options.length; i++) {
                    s.selectedIndex = i;
                    s.dispatchEvent(new Event('change'));
                    await new Promise(r => setTimeout(r, 120));
                }
            }
        }""")
        page.wait_for_timeout(300)
        if errors:
            fail(f"threw on extreme parameters: {errors[:3]}")
            passed = False
        else:
            ok("survived all sliders at min/max and every select option")

        # 6. every style renders
        errors.clear()
        for style in ["ink", "blueprint", "slate", "mono"]:
            page.evaluate("""(s) => {
                const w = document.getElementById('w');
                if (w) { w.value = 72; w.dispatchEvent(new Event('input', {bubbles:true})); }
                const sel = document.getElementById('style');
                sel.value = s;
                sel.dispatchEvent(new Event('change', {bubbles:true}));
                sel.dispatchEvent(new Event('input', {bubbles:true}));
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
        clicked = []
        for bid in ["randomize", "gen", "copySeed"]:
            if page.locator(f"#{bid}").count():
                page.click(f"#{bid}")
                page.wait_for_timeout(200)
                clicked.append(bid)
        if errors:
            fail(f"button errors: {errors[:3]}")
            passed = False
        else:
            ok(f"buttons work: {', '.join(clicked) if clicked else 'none present'}")

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
