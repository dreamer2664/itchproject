"""
foundry.scout -- niche research for itch.io (v2: demand vs supply)

A tag page measures SUPPLY: how many sellers use that tag. It says nothing
about DEMAND: how many buyers browse the category. v2 therefore fetches two
pages per keyword:

    demand  = game-assets/tag-<category>        e.g. tag-dungeon, tag-tileset
    supply  = game-assets/tag-<category>-generator   e.g. tag-dungeon-generator

The opportunity is the gold-rush gap: a category with healthy buyer traffic
and almost no generator tools selling into it. A "-generator" tag with zero
results usually just means the slug doesn't exist -- v2 detects that instead
of misreading it as a dead niche.

POLITENESS RULES (do not remove):
  * /search is disallowed by itch.io's robots.txt -- we never touch it.
  * Tag/browse pages are allowed, and those are all we use.
  * One request every 15-25 s, jittered. Never concurrent.
  * 24 h disk cache: re-runs cost zero requests.
  * On HTTP 429 we stop immediately. Run a few keywords per session,
    a couple of sessions per day; the cache accumulates the picture.

Runs on YOUR machine (residential IP). itch rate-limits datacenter IPs hard.

Usage:
    python -m foundry.scout                      # 4 keywords (8 requests)
    python -m foundry.scout dungeon sfx npc      # specific keywords
    python -m foundry.scout --limit 2            # fewer requests today
    python -m foundry.scout --history            # everything learned, ranked
"""

from __future__ import annotations

import argparse
import html as _html
import json
import random
import re
import sqlite3
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from pathlib import Path

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

BASE = "https://itch.io"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

MIN_DELAY = 15.0   # seconds between requests, minimum
MAX_DELAY = 25.0   # seconds between requests, maximum
CACHE_TTL = timedelta(hours=24)
DEFAULT_LIMIT = 4  # keywords per run -> 2 requests each

ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = ROOT / "cache"
DB_PATH = ROOT / "data" / "foundry.db"

# keyword -> (supply tag, demand tag). Supply is "<key>-generator" unless the
# demand tag differs from the key (itch slugs: textures, not texture).
DEFAULT_KEYWORDS: dict[str, str] = {
    "dungeon": "dungeon",
    "tileset": "tileset",
    "texture": "textures",
    "pixel-art": "pixel-art",
    "map": "map",
    "sfx": "sfx",
    "chiptune": "chiptune",
    "npc": "npc",
    "palette": "palette",
    "font": "font",
    "heraldry": "heraldry",
    "dungeon-crawl": "dungeon-crawl",
}


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class Listing:
    game_id: str
    title: str
    url: str
    author: str = ""
    short_text: str = ""
    price: str = ""
    price_usd: float | None = None
    on_sale: bool = False
    verified_author: bool = False
    playable_in_browser: bool = False


@dataclass
class Side:
    """One fetched tag page (either the demand or the supply side)."""
    tag: str
    url: str
    total: int | None = None
    missing: bool = False
    listings: list[Listing] = field(default_factory=list)
    error: str | None = None

    @property
    def priced(self) -> int:
        return sum(1 for x in self.listings if x.price_usd and x.price_usd > 0)

    @property
    def paid_ratio(self) -> float:
        return self.priced / len(self.listings) if self.listings else 0.0

    @property
    def median_price(self) -> float | None:
        ps = sorted(x.price_usd for x in self.listings if x.price_usd and x.price_usd > 0)
        if not ps:
            return None
        n = len(ps)
        return ps[n // 2] if n % 2 else (ps[n // 2 - 1] + ps[n // 2]) / 2

    @property
    def verified(self) -> int:
        return sum(1 for x in self.listings if x.verified_author)


@dataclass
class NicheReport:
    keyword: str
    fetched_at: str
    demand: Side
    supply: Side
    # derived
    score: float = 0.0
    verdict: str = ""
    notes: str = ""


# ---------------------------------------------------------------------------
# Fetching (polite)
# ---------------------------------------------------------------------------

class PoliteFetcher:
    def __init__(self, use_cache: bool = True):
        self.use_cache = use_cache
        self.last_request = 0.0
        self.request_count = 0
        CACHE_DIR.mkdir(parents=True, exist_ok=True)

    def _cache_path(self, url: str) -> Path:
        return CACHE_DIR / (re.sub(r"\W+", "_", url)[-120:] + ".html")

    def _cache_get(self, url: str) -> str | None:
        if not self.use_cache:
            return None
        p = self._cache_path(url)
        if not p.exists():
            return None
        if datetime.now() - datetime.fromtimestamp(p.stat().st_mtime) > CACHE_TTL:
            return None
        return p.read_text(encoding="utf-8", errors="replace")

    def get(self, url: str) -> tuple[str | None, str | None]:
        cached = self._cache_get(url)
        if cached is not None:
            return cached, None

        wait = (self.last_request + random.uniform(MIN_DELAY, MAX_DELAY)) - time.time()
        if wait > 0 and self.last_request:
            print(f"    ...waiting {wait:.1f}s (politeness)", file=sys.stderr)
            time.sleep(wait)

        req = urllib.request.Request(url, headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "en-US,en;q=0.9",
        })
        self.last_request = time.time()
        self.request_count += 1
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                html = r.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None, "404"
            if e.code == 429:
                return None, "HTTP 429 rate-limited. Stop; re-run later. Cache is kept."
            return None, f"HTTP {e.code}"
        except Exception as e:  # noqa: BLE001
            return None, f"{type(e).__name__}: {e}"

        if self.use_cache:
            self._cache_path(url).write_text(html, encoding="utf-8")
        return html, None


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

PRICE_RE = re.compile(
    r"(?:\$|USD\s*)\s*(\d+(?:\.\d{1,2})?)"
    r"|(\d+(?:[.,]\d{1,2})?)\s*(?:€|EUR)"
    r"|(?:£|GBP\s*)\s*(\d+(?:\.\d{1,2})?)"
)


def parse_price(raw: str) -> float | None:
    raw = raw.strip()
    if not raw:
        return None
    m = PRICE_RE.search(raw)
    if not m:
        return None
    usd, eur, gbp = m.group(1), m.group(2), m.group(3)
    if usd:
        return float(usd)
    if eur:
        return float(eur.replace(",", ".")) * 1.09
    if gbp:
        return float(gbp) * 1.27
    return None


def parse_results_count(html: str) -> int | None:
    m = re.search(r"\((\d[\d,]*)\s+results?\)", html) or re.search(
        r"(\d[\d,]*)\s+results?\b", html)
    return int(m.group(1).replace(",", "")) if m else None


def parse_listings(html: str) -> list[Listing]:
    out: list[Listing] = []
    chunks = re.split(r'(?=<div[^>]+data-game_id="\d+"[^>]+class="game_cell)', html)
    for chunk in chunks[1:]:
        gid = re.search(r'data-game_id="(\d+)"', chunk)
        title_m = re.search(r'class="title game_link"[^>]*>([^<]+)</a>', chunk)
        url_m = re.search(r'class="thumb_link game_link"[^>]*href="([^"]+)"', chunk)
        if not (gid and title_m):
            continue
        short = re.search(r'<div title="([^"]*)" class="game_text"', chunk)
        author = re.search(r'class="game_author"[^>]*>.*?>([^<]+)</a>', chunk, re.S)
        price = re.search(r'class="price_value"[^>]*>([^<]*)<', chunk)
        price_raw = price.group(1).strip() if price else ""
        out.append(Listing(
            game_id=gid.group(1),
            title=_html.unescape(title_m.group(1)).strip(),
            url=(url_m.group(1) if url_m else ""),
            author=_html.unescape(author.group(1)).strip() if author else "",
            short_text=_html.unescape(short.group(1)).strip() if short else "",
            price=price_raw,
            price_usd=parse_price(price_raw),
            on_sale='sale_tag' in chunk,
            verified_author=('icon_verified' in chunk or 'Verified Account' in chunk),
            playable_in_browser=('icon-play' in chunk),
        ))
    return out


def fetch_side(fetcher: PoliteFetcher, tag: str, category: str = "game-assets") -> Side:
    url = f"{BASE}/{category}/tag-{tag}"
    side = Side(tag=tag, url=url)
    html, err = fetcher.get(url)
    if err:
        if err == "404":
            side.missing = True          # tag slug doesn't exist: not a dead
            side.total = 0               # niche, just an unused label
        else:
            side.error = err
        return side
    side.total = parse_results_count(html)
    side.listings = parse_listings(html)
    if side.total is None and not side.listings:
        side.total = 0
        side.missing = True
    return side


# ---------------------------------------------------------------------------
# Scoring: the gold-rush gap
# ---------------------------------------------------------------------------

def score(rep: NicheReport) -> NicheReport:
    D = rep.demand.total or 0
    S = rep.supply.total or 0
    notes: list[str] = []

    if rep.demand.error or rep.supply.error:
        rep.verdict = f"INCOMPLETE ({rep.demand.error or rep.supply.error})"
        return rep

    if rep.demand.missing:
        rep.verdict = "BAD DEMAND TAG -- pick a real category tag"
        return rep
    if rep.supply.missing:
        notes.append("supply tag unused (treat competition as ~0)")

    # demand health: enough buyers browsing, without being a ocean
    if D < 50:
        demand_health, dv = 0.15, "tiny category"
    elif D < 200:
        demand_health, dv = 0.6, "small category"
    elif D <= 5000:
        demand_health, dv = 1.0, "healthy category"
    elif D <= 20000:
        demand_health, dv = 0.7, "big category"
    else:
        demand_health, dv = 0.45, "ocean (differentiation must carry you)"

    # supply gap: how empty is the generator shelf in this category?
    if S <= 3:
        gap = 1.0
    elif S <= 10:
        gap = 0.8
    elif S <= 30:
        gap = 0.5
    elif S <= 100:
        gap = 0.25
    else:
        gap = 0.1

    # buyers here actually pay?
    paid = rep.demand.paid_ratio
    med = rep.demand.median_price
    price_health = min(1.0, (med or 0) / 8.0)

    # entrenched incumbents on the demand page make displacement harder
    incumbent = 1.0 - (rep.demand.verified / max(1, len(rep.demand.listings)))

    rep.score = round(100 * (
        0.35 * gap
        + 0.30 * demand_health
        + 0.20 * paid
        + 0.15 * (0.5 * price_health + 0.5 * incumbent)
    ), 1)
    rep.notes = "; ".join(notes + [dv])

    s = rep.score
    if D < 50:
        rep.verdict = "NO DEMAND SIGNAL"
    elif s >= 65:
        rep.verdict = "PROMISING -- buyers browse here, almost no tools sell"
    elif s >= 50:
        rep.verdict = "VIABLE -- worth a look"
    elif s >= 35:
        rep.verdict = "CROWDED -- enter only with something clearly better"
    else:
        rep.verdict = "SATURATED -- skip"
    return rep


# ---------------------------------------------------------------------------
# Storage (with migration for v1 databases)
# ---------------------------------------------------------------------------

NEW_COLS = ["demand_total", "supply_total", "demand_paid", "demand_median", "notes"]


def db() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(DB_PATH)
    c.executescript("""
    CREATE TABLE IF NOT EXISTS niches (
        keyword TEXT PRIMARY KEY,
        category TEXT, url TEXT,
        fetched_at TEXT, total_results INTEGER,
        priced_count INTEGER, free_count INTEGER,
        median_price REAL, min_price REAL, max_price REAL,
        on_sale_count INTEGER, verified_count INTEGER,
        browser_playable_count INTEGER,
        opportunity_score REAL, verdict TEXT,
        raw_json TEXT
    );
    CREATE TABLE IF NOT EXISTS launches (
        ts TEXT, slug TEXT, mode TEXT
    );
    """)
    have = {r[1] for r in c.execute("PRAGMA table_info(niches)")}
    for col in NEW_COLS:
        if col not in have:
            c.execute(f"ALTER TABLE niches ADD COLUMN {col} TEXT")
    return c


def save(rep: NicheReport) -> None:
    d, s = rep.demand, rep.supply
    prices = [x.price_usd for x in d.listings if x.price_usd and x.price_usd > 0]
    with db() as c:
        c.execute("""
        INSERT OR REPLACE INTO niches (
            keyword, category, url, fetched_at, total_results,
            priced_count, free_count, median_price, min_price, max_price,
            on_sale_count, verified_count, browser_playable_count,
            opportunity_score, verdict, raw_json,
            demand_total, supply_total, demand_paid, demand_median, notes
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            rep.keyword, "game-assets", d.url, rep.fetched_at,
            s.total, d.priced, len(d.listings) - d.priced,
            d.median_price, min(prices) if prices else None,
            max(prices) if prices else None,
            sum(1 for x in d.listings if x.on_sale), d.verified,
            sum(1 for x in d.listings if x.playable_in_browser),
            rep.score, rep.verdict,
            json.dumps({"demand": asdict(d), "supply": asdict(s)}),
            str(d.total), str(s.total), str(d.priced),
            str(d.median_price), rep.notes,
        ))


def load_history() -> list[dict]:
    with db() as c:
        c.row_factory = sqlite3.Row
        rows = c.execute(
            "SELECT * FROM niches ORDER BY opportunity_score DESC").fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def print_table(reports: list[NicheReport]) -> None:
    good = [r for r in reports if r.verdict and not r.verdict.startswith("INCOMPLETE")]
    good.sort(key=lambda r: r.score, reverse=True)
    hdr = (f"{'score':>6} {'demand':>8} {'supply':>7} {'paid':>5} "
           f"{'med$':>6}  {'verdict':<46} keyword")
    print("\n" + hdr)
    print("-" * len(hdr))
    for r in good:
        med = f"{r.demand.median_price:.2f}" if r.demand.median_price else "-"
        print(f"{r.score:>6.1f} {(r.demand.total or 0):>8,} {(r.supply.total or 0):>7,} "
              f"{r.demand.priced:>5} {med:>6}  {r.verdict:<46} {r.keyword}")
    bad = [r for r in reports if r not in good]
    if bad:
        print("\nSkipped/failed:")
        for r in bad:
            print(f"  {r.keyword}: {r.verdict or r.demand.error or r.supply.error}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("keywords", nargs="*", help="keywords (default: built-in list)")
    ap.add_argument("--limit", type=int, default=DEFAULT_LIMIT,
                    help=f"keywords per run (default {DEFAULT_LIMIT}; 2 requests each)")
    ap.add_argument("--no-cache", action="store_true")
    ap.add_argument("--history", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    if args.history:
        for row in load_history():
            print(f"{float(row['opportunity_score'] or 0):>6.1f}  "
                  f"{row['keyword']:<16} demand={row['demand_total']:>6} "
                  f"supply={row['supply_total']:>5}  {row['verdict']}")
        return 0

    keys = args.keywords or list(DEFAULT_KEYWORDS.keys())
    keys = keys[:args.limit]

    fetcher = PoliteFetcher(use_cache=not args.no_cache)
    reports: list[NicheReport] = []

    print(f"Scanning {len(keys)} keyword(s): demand tag + supply tag each.")
    print("Cached pages cost no requests. A run makes at most "
          f"{2 * len(keys)} live requests.\n")

    for i, kw in enumerate(keys, 1):
        demand_tag = DEFAULT_KEYWORDS.get(kw, kw)
        print(f"[{i}/{len(keys)}] {kw}  (demand: tag-{demand_tag}, "
              f"supply: tag-{kw}-generator)", file=sys.stderr)
        rep = NicheReport(
            keyword=kw,
            fetched_at=datetime.now().isoformat(timespec="seconds"),
            demand=Side(tag=demand_tag, url=f"{BASE}/game-assets/tag-{demand_tag}"),
            supply=Side(tag=f"{kw}-generator",
                        url=f"{BASE}/game-assets/tag-{kw}-generator"),
        )
        stopped = False
        for side in (rep.demand, rep.supply):
            html, err = fetcher.get(side.url)
            if err:
                if err == "404":
                    side.missing, side.total = True, 0
                else:
                    side.error = err
                    if "429" in err:
                        stopped = True
                continue
            side.total = parse_results_count(html)
            side.listings = parse_listings(html)
            if side.total is None and not side.listings:
                side.total, side.missing = 0, True
        score(rep)
        save(rep)
        reports.append(rep)
        if stopped:
            print("\nRate limited. Stopping -- cached results are saved.",
                  file=sys.stderr)
            print("Re-run later; the cache means finished keywords cost nothing.",
                  file=sys.stderr)
            break

    print_table(reports)
    print(f"\nMade {fetcher.request_count} live request(s).")
    top = [r for r in reports if r.verdict.startswith(("PROMISING", "VIABLE"))]
    top.sort(key=lambda r: r.score, reverse=True)
    if top:
        print(f"\nBest bet: '{top[0].keyword}' -- demand {top[0].demand.total:,} "
              f"vs supply {top[0].supply.total}. {top[0].notes}")
    else:
        print("\nNothing conclusive yet. Run again later (--limit 4); "
              "the picture builds across sessions.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
