"""
foundry.scout -- niche research for itch.io

Scans itch.io tag pages for a list of keywords and reports how crowded each
niche is, what things sell for, and where the gaps are.

POLITENESS RULES (do not remove):
  * /search is disallowed by itch.io's robots.txt -- we never touch it.
  * Tag and browse pages are allowed, and those are all we use.
  * One request every 8-15 seconds, with jitter. Never concurrent.
  * Everything is cached to disk for 24h so re-runs cost zero requests.
  * On HTTP 429 we stop immediately and wait, we do not retry hard.

This is designed to run on YOUR machine (residential IP). itch.io rate-limits
datacenter IPs aggressively, so it will not work from a cloud sandbox.

Usage:
    python -m foundry.scout                     # scan the default keyword list
    python -m foundry.scout dungeon tileset sfx # scan specific keywords
    python -m foundry.scout --category tools    # scan a different category
    python -m foundry.scout --no-cache          # force fresh requests
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

# A real browser UA. itch.io returns 429 for obvious bot agents.
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

MIN_DELAY = 8.0    # seconds between requests, minimum
MAX_DELAY = 15.0   # seconds between requests, maximum
CACHE_TTL = timedelta(hours=24)

ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = ROOT / "cache"
DB_PATH = ROOT / "data" / "foundry.db"

# Where to look. "game-assets" and "tools" are the two relevant itch categories.
CATEGORIES = ["game-assets", "tools", "games"]

# The default keyword list. These are seed ideas only -- scout tells us which
# ones are worth pursuing. Add freely; scanning is cheap because of the cache.
DEFAULT_KEYWORDS = [
    # gamedev / map generation
    "dungeon-generator", "map-generator", "tileset-generator",
    "texture-generator", "pixel-art-generator", "level-generator",
    "cave-generator", "city-generator", "terrain-generator",
    "heraldry", "flag-generator", "sprite-generator",
    # audio
    "sfx-generator", "sound-effect", "chiptune", "music-generator",
    "synthesizer", "8-bit-sound",
    # ttrpg
    "npc-generator", "name-generator", "random-table",
    "encounter-generator", "loot-generator", "tavern-generator",
    # utility
    "color-palette", "palette-generator", "font-generator",
    "sprite-sheet", "noise-generator",
]


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class Listing:
    """One product in an itch.io browse grid."""
    game_id: str
    title: str
    url: str
    author: str = ""
    short_text: str = ""
    price: str = ""          # raw string, e.g. "$9.99", "14.97EUR", "" for free
    price_usd: float | None = None
    on_sale: bool = False
    verified_author: bool = False
    playable_in_browser: bool = False


@dataclass
class NicheReport:
    """What we learned about one keyword."""
    keyword: str
    category: str
    url: str
    fetched_at: str
    total_results: int | None = None
    listings: list[Listing] = field(default_factory=list)
    error: str | None = None

    # --- derived metrics (filled in by score()) ---
    priced_count: int = 0
    free_count: int = 0
    median_price: float | None = None
    min_price: float | None = None
    max_price: float | None = None
    on_sale_count: int = 0
    verified_count: int = 0
    browser_playable_count: int = 0
    opportunity_score: float = 0.0
    verdict: str = ""

    @property
    def sampled(self) -> int:
        return len(self.listings)


# ---------------------------------------------------------------------------
# Fetching (polite)
# ---------------------------------------------------------------------------

class PoliteFetcher:
    """Rate-limited fetcher with on-disk caching."""

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
        """Return (html, error). html is None on failure."""
        cached = self._cache_get(url)
        if cached is not None:
            return cached, None

        # Rate limit: sleep until enough time has passed.
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
            if e.code == 429:
                # Rate limited. Back off hard and do NOT hammer.
                return None, "HTTP 429 rate-limited. Stop and try again in an hour."
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
    r"(?:\$|USD\s*)\s*(\d+(?:\.\d{1,2})?)"      # $9.99 / USD 9.99
    r"|(\d+(?:[.,]\d{1,2})?)\s*(?:€|EUR)"       # 14.97€ / 14,97 EUR
    r"|(?:£|GBP\s*)\s*(\d+(?:\.\d{1,2})?)"      # £5.00
)


def parse_price(raw: str) -> float | None:
    """Best-effort USD normalisation. Rough on purpose; good enough to rank."""
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
    """itch prints '(112,878 results)' in the page header."""
    m = re.search(r"\((\d[\d,]*)\s+results?\)", html)
    if not m:
        m = re.search(r"(\d[\d,]*)\s+results?\b", html)
    return int(m.group(1).replace(",", "")) if m else None


def parse_listings(html: str) -> list[Listing]:
    """Pull each product out of the browse grid."""
    out: list[Listing] = []
    # Split on cell boundaries so we only regex within one product at a time.
    chunks = re.split(r'(?=<div[^>]+data-game_id="\d+"[^>]+class="game_cell)', html)
    for chunk in chunks[1:]:
        gid = re.search(r'data-game_id="(\d+)"', chunk)
        title_m = re.search(
            r'class="title game_link"[^>]*>([^<]+)</a>', chunk
        ) or re.search(
            r'<a[^>]+class="title game_link"[^>]*>([^<]+)</a>', chunk
        )
        url_m = re.search(r'class="thumb_link game_link"[^>]*href="([^"]+)"', chunk) \
            or re.search(r'<a href="(https://[^"]+\.itch\.io/[^"]+)"', chunk)
        if not (gid and title_m):
            continue

        # The short description sits in <div title="..." class="game_text">
        short = re.search(r'<div title="([^"]*)" class="game_text"', chunk)
        author = re.search(r'class="game_author"[^>]*>.*?>([^<]+)</a>', chunk, re.S)
        price = re.search(r'class="price_value"[^>]*>([^<]*)<', chunk)
        sale = 'sale_tag' in chunk
        verified = 'icon_verified' in chunk or 'Verified Account' in chunk
        playable = 'icon-play' in chunk or 'web' in chunk.lower()

        price_raw = price.group(1).strip() if price else ""
        out.append(Listing(
            game_id=gid.group(1),
            title=_html.unescape(title_m.group(1)).strip(),
            url=(url_m.group(1) if url_m else ""),
            author=_html.unescape(author.group(1)).strip() if author else "",
            short_text=_html.unescape(short.group(1)).strip() if short else "",
            price=price_raw,
            price_usd=parse_price(price_raw),
            on_sale=sale,
            verified_author=verified,
            playable_in_browser=playable,
        ))
    return out


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def median(xs: list[float]) -> float | None:
    if not xs:
        return None
    xs = sorted(xs)
    n = len(xs)
    return xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2


def score(report: NicheReport) -> NicheReport:
    """
    Turn raw counts into an opportunity score.

    The heuristic: we want a niche with ENOUGH demand to prove people buy this
    kind of thing, but LOW enough competition that a new page can rank.

    Everything here is a guess until we have sales data. The point of the score
    is to rank 30 keywords against each other, not to be right in absolute
    terms. It gets recalibrated once real numbers come in.
    """
    L = report.listings
    report.sampled  # (property)
    report.priced_count = sum(1 for x in L if x.price_usd and x.price_usd > 0)
    report.free_count = len(L) - report.priced_count
    report.on_sale_count = sum(1 for x in L if x.on_sale)
    report.verified_count = sum(1 for x in L if x.verified_author)
    report.browser_playable_count = sum(1 for x in L if x.playable_in_browser)

    prices = [x.price_usd for x in L if x.price_usd and x.price_usd > 0]
    report.median_price = median(prices)
    report.min_price = min(prices) if prices else None
    report.max_price = max(prices) if prices else None

    total = report.total_results or 0
    sampled = len(L) or 1

    # Demand signal: are people charging money here at all?
    paid_ratio = report.priced_count / sampled

    # Competition signal: fewer total results = easier to rank.
    # Log scale because 112,000 vs 900 is the whole story.
    if total <= 0:
        competition = 0.0
    elif total < 50:
        competition = 1.0      # tiny -- easy to rank, but maybe no demand
    elif total < 200:
        competition = 0.85
    elif total < 600:
        competition = 0.65
    elif total < 2000:
        competition = 0.45
    elif total < 8000:
        competition = 0.25
    else:
        competition = 0.1      # saturated

    # Incumbent strength: lots of verified authors on page 1 = hard to displace.
    incumbent = 1.0 - (report.verified_count / sampled)

    # Price headroom: a healthy median means buyers spend here.
    mp = report.median_price or 0
    price_health = min(1.0, mp / 8.0)

    report.opportunity_score = round(
        100 * (
            0.40 * competition
            + 0.25 * paid_ratio
            + 0.20 * incumbent
            + 0.15 * price_health
        ), 1
    )

    s = report.opportunity_score
    if total < 25:
        report.verdict = "TOO SMALL -- maybe no demand at all"
    elif s >= 60:
        report.verdict = "PROMISING -- low competition, people pay here"
    elif s >= 45:
        report.verdict = "VIABLE -- worth a look"
    elif s >= 30:
        report.verdict = "CROWDED -- only enter with something clearly better"
    else:
        report.verdict = "SATURATED -- skip"

    return report


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------

def db() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(DB_PATH)
    c.executescript("""
    CREATE TABLE IF NOT EXISTS niches (
        keyword TEXT, category TEXT, url TEXT,
        fetched_at TEXT, total_results INTEGER,
        priced_count INTEGER, free_count INTEGER,
        median_price REAL, min_price REAL, max_price REAL,
        on_sale_count INTEGER, verified_count INTEGER,
        browser_playable_count INTEGER,
        opportunity_score REAL, verdict TEXT,
        raw_json TEXT,
        PRIMARY KEY (keyword, category)
    );
    """)
    return c


def save(report: NicheReport) -> None:
    with db() as c:
        c.execute("""
        INSERT OR REPLACE INTO niches VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            report.keyword, report.category, report.url, report.fetched_at,
            report.total_results, report.priced_count, report.free_count,
            report.median_price, report.min_price, report.max_price,
            report.on_sale_count, report.verified_count,
            report.browser_playable_count, report.opportunity_score,
            report.verdict,
            json.dumps([asdict(x) for x in report.listings]),
        ))


def load_history() -> list[dict]:
    with db() as c:
        c.row_factory = sqlite3.Row
        rows = c.execute(
            "SELECT * FROM niches ORDER BY opportunity_score DESC"
        ).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def scout_keyword(fetcher: PoliteFetcher, keyword: str, category: str) -> NicheReport:
    url = f"{BASE}/{category}/tag-{keyword}"
    report = NicheReport(
        keyword=keyword, category=category, url=url,
        fetched_at=datetime.now().isoformat(timespec="seconds"),
    )
    html, err = fetcher.get(url)
    if err:
        report.error = err
        return report
    report.total_results = parse_results_count(html)
    report.listings = parse_listings(html)
    if report.total_results is None and not report.listings:
        report.error = "parsed nothing -- page structure may have changed"
    return score(report)


def print_table(reports: list[NicheReport]) -> None:
    reports = [r for r in reports if not r.error]
    reports.sort(key=lambda r: r.opportunity_score, reverse=True)

    hdr = f"{'score':>6} {'results':>9} {'paid':>5} {'med$':>6}  {'verdict':<28} keyword"
    print("\n" + hdr)
    print("-" * len(hdr))
    for r in reports:
        med = f"{r.median_price:.2f}" if r.median_price else "-"
        print(f"{r.opportunity_score:>6.1f} {(r.total_results or 0):>9,} "
              f"{r.priced_count:>5} {med:>6}  {r.verdict:<28} {r.keyword}")

    errs = [r for r in reports if r.error]
    if errs:
        print("\nFailed:")
        for r in errs:
            print(f"  {r.keyword}: {r.error}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("keywords", nargs="*", help="keywords to scan (default: built-in list)")
    ap.add_argument("--category", default="game-assets", choices=CATEGORIES)
    ap.add_argument("--all-categories", action="store_true",
                    help="scan every category (3x the requests)")
    ap.add_argument("--no-cache", action="store_true")
    ap.add_argument("--limit", type=int, default=0, help="only scan first N keywords")
    ap.add_argument("--history", action="store_true", help="print stored results and exit")
    ap.add_argument("--json", action="store_true", help="also dump JSON to stdout")
    args = ap.parse_args(argv)

    if args.history:
        for row in load_history():
            print(f"{row['opportunity_score']:>6.1f}  {row['keyword']:<28} "
                  f"{row['verdict']}  ({row['total_results']:,} results, "
                  f"median ${row['median_price'] or 0:.2f})  [{row['fetched_at']}]")
        return 0

    keywords = args.keywords or DEFAULT_KEYWORDS
    if args.limit:
        keywords = keywords[:args.limit]
    cats = CATEGORIES if args.all_categories else [args.category]

    fetcher = PoliteFetcher(use_cache=not args.no_cache)
    reports: list[NicheReport] = []

    total = len(keywords) * len(cats)
    print(f"Scanning {total} niche(s) on itch.io. Cached pages cost no requests.\n")

    n = 0
    for cat in cats:
        for kw in keywords:
            n += 1
            print(f"[{n}/{total}] {cat}/tag-{kw}", file=sys.stderr)
            rep = scout_keyword(fetcher, kw, cat)
            reports.append(rep)
            save(rep)
            if rep.error and "429" in rep.error:
                print("\nRate limited. Stopping -- your cached results are saved.",
                      file=sys.stderr)
                print("Run again later; the cache means you won't re-fetch.",
                      file=sys.stderr)
                break

    print_table(reports)
    print(f"\nMade {fetcher.request_count} live request(s). Results saved to "
          f"{DB_PATH.relative_to(ROOT)}")

    if args.json:
        print(json.dumps([asdict(r) for r in reports], indent=2))

    top = [r for r in reports if not r.error]
    top.sort(key=lambda r: r.opportunity_score, reverse=True)
    if top:
        print(f"\nBest opportunity: {top[0].keyword} "
              f"(score {top[0].opportunity_score}) -- {top[0].verdict}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
