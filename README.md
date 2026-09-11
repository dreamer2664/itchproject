# Foundry

**A self-contained pipeline that researches a niche, builds a procedural web
tool for it, verifies it in a headless browser, packages it, and ships it to
itch.io -- from your Windows terminal.**

Cost to run: $0. Dependencies: Python and the official `butler` CLI. No APIs,
no keys you pay for, no cloud services.

---

## Read this first: honest expectations

- Revenue is **not** immediate. On a cold itch.io account expect **weeks** of
  $0 while the search index warms up. The realistic path to $1/day is 8-16
  weeks with a catalogue of 10-15 good tools live. Anyone promising faster is
  selling something.
- Each tool is an independent lottery ticket in itch's search. The system's
  real power is that it makes producing *good* tickets cheap.
- itch.io's rules prohibit automated mass page creation. This project obeys
  that on purpose: one human checkpoint per page (~90 seconds), everything
  else automated. See "Compliance" below.

---

## Requirements

- Windows 10/11
- Python 3.10+ from https://www.python.org/downloads/
  (**tick "Add python.exe to PATH"** during install)
- An itch.io account (free; email + password, no ID check to create)
- Optional: Playwright + Chromium, for the verification gate (strongly
  recommended; the installer has a `-WithVerifier` switch)

---

## Part 1 -- one-time account setup (~10 minutes)

1. Create an itch.io account. Pick a username you're happy with; it becomes
   your storefront URL.
2. Get an API key: **https://itch.io/user/settings/api-keys**
   Treat it like a password. It lives in an environment variable, never in a
   file and never in git.
3. Put your username in `config.json`:
   ```json
   "itch": { "username": "your-username-here", ... }
   ```
4. **About money.** itch.io can pay out via PayPal with a **$5 minimum** --
   the lowest of any platform. Before your *first payout* (not before
   selling) itch requires a one-time tax interview.

   If you are **under 18**, itch.io's terms permit you to publish with
   parental consent and require an adult to operate the financial side of
   the account. That is the compliant structure; see `docs/DECISIONS.md`.
   Publishing **free** tools needs no adult and no tax form at all, and free
   projects build exactly the audience and reviews you'll want later.

   **If you publish with no adult on the account:** pricing must be
   **"No payments"** and **donations must stay OFF**. Even pay-what-you-want
   or a tip jar can receive money, and receiving money is precisely what
   requires an adult. `config.json` encodes this as `"launch_mode": "free"`,
   and `docs/LAUNCH-FREE.md` walks the whole launch click-by-click,
   including the flip-day checklist for when payments switch on.

---

## Part 2 -- install on Windows

```powershell
# anywhere you like:
git clone <your-repo-url> foundry
cd foundry

# one-time setup: checks Python, downloads official butler into .\bin
powershell -ExecutionPolicy Bypass -File setup.ps1

# add the verifier (recommended, ~120 MB download):
powershell -ExecutionPolicy Bypass -File setup.ps1 -WithVerifier

# every session you want to publish:
$env:BUTLER_API_KEY="paste-your-api-key-here"
```

No `pip install` needed for the core. Everything except the verifier uses
only the Python standard library.

---

## Part 3 -- research: find a niche worth entering

```powershell
python -m foundry.scout --limit 8          # scan 8 niches (first run is slow, ~1 min each)
python -m foundry.scout --history          # everything you've learned, ranked
python -m foundry.scout dungeon sfx npc    # scan specific keywords
```

`scout` fetches itch **tag pages** (allowed by robots.txt -- it never touches
`/search`), counts results, samples the first page of products, and scores
each niche:

| factor | weight | why |
|---|---|---|
| low total results | 40% | fewer competitors = a new page can rank |
| fraction of page-1 items that are paid | 25% | proves buyers spend here |
| few verified incumbents | 20% | entrenched authors are hard to displace |
| healthy median price | 15% | price headroom |

**Politeness is enforced in code:** one request every 8-15 s, 24 h disk cache,
and on HTTP 429 it stops immediately instead of retrying. Run it once a day
at most. The cache means re-runs cost zero requests.

Interpretation: score ≥ 60 = promising, ≥ 45 = viable, < 30 = skip. The score
is a *relative* ranking of your own scans; it gets smarter as sales data
comes in.

---

## Part 4 -- build, verify, package

```powershell
python -m foundry.build dungeon-map-generator
```

This runs:

1. **VERIFY** (the hard gate) -- a headless Chromium loads the tool and
   checks: zero console errors; canvas actually renders; same seed =
   byte-identical output; different seed = different output; extreme slider
   values don't throw; all palettes render; buttons work. **A failing gate
   packages nothing.**
2. **PACKAGE** -- zips the tool into `build/<slug>/` and writes
   `build/<slug>/COPY.md`: paste-ready title, tagline, description, tags,
   pricing recommendation and AI-disclosure answer.
3. **CHECKPOINT** -- prints the manual step.

Try the tool yourself first, any time, by opening
`tools/dungeon-map-generator/index.html` in a browser. It works offline.

---

## Part 5 -- the 90-second checkpoint, then ship

`butler` can push files but **cannot create a project page**, and itch has no
public API for page creation. So, once per tool:

1. itch.io dashboard → *Create new project*
2. Fill in title / kind = Tool / "will be played in the browser"
3. Paste description + tags from `build/<slug>/COPY.md`
4. Upload `build/<slug>/<slug>.zip` as kind **HTML**, playable in browser
5. Pricing per COPY.md (start free or pay-what-you-want)
6. AI disclosure: **No** (see COPY.md for why that's accurate here)
7. Save, publish

Then, from the terminal:

```powershell
python -m foundry.publish push dungeon-map-generator
```

That's `butler push` with your API key. Every future update is just
re-running this line -- versions and patches are handled by butler.

---

## Part 5b -- one-command launch (optional, after calibration)

`python -m foundry.launch <slug>` chains verify -> package -> assets ->
browser: it opens a headed Chromium with a persistent profile (you log in to
itch.io **once**, ever), fills every field of the new-project form from
`copy.json`, uploads cover, screenshots and the zip -- then **stops and lets
you click Save**.

First run is calibration: itch's editor is behind login and has no public
API, so the script dumps the form's field inventory to
`data/editor_capture/editor_fields.json` and submits nothing. That file gets
turned into `editor_selectors.json` (committed to the repo), and from then on
filling works.

Fully unattended publishing exists but is **opt-in**: set
`launch.auto_publish` to `true` in `config.json`. It is hard-capped at
`max_auto_publish_per_day` (default 2) and every launch is logged in
`data/foundry.db`. Rationale: itch.io's guidelines forbid automated systems
mass-producing product pages, and the human click is the quality gate that
stops a bad generation from going public under your name. Default stays
assisted; flip it only once you've reviewed several assisted launches.

---

## Part 6 -- watch and iterate

- Sales and views: https://itch.io/dashboard/analytics
- Once sales exist, run `python -m foundry.scout --history` and let the
  numbers argue with your gut. Raise prices toward the niche median; build
  the next tool in whichever niche scored highest.
- itch runs periodic **Creator Days** and themed **jams**. Free entries are
  the cheapest visibility you will ever get.

---

## Adding a new tool

1. Copy `tools/dungeon-map-generator/` to `tools/<new-slug>/`.
2. Edit `index.html`. Keep the contract `foundry/verify.py` expects:
   an `#cv` canvas, a `#seed` input, `#sRooms`/`#sTiles`/`#sDoors` stats, and
   a `generate()` function that is fully seeded (no `Math.random`).
3. Add an entry to `config.json` under `tools` (title, tagline, tags, price).
4. `python -m foundry.build <new-slug>`

The verifier will catch the common mistakes for you.

---

## Compliance -- read once, obey always

These are the rules that keep the account alive. They are enforced in code
where possible and in culture where not.

1. **No generative AI in products.** Every output must come from a
   self-contained deterministic algorithm. This is what itch.io's guidelines
   explicitly exempt from AI tagging, and it is what the community trusts.
2. **One page, one human checkpoint.** Never automate page creation. itch's
   quality guidelines call automated mass page production spam and will
   delist you for it.
3. **No reskins.** "Many project pages for minor changes" is banned. Each
   tool must be genuinely distinct.
4. **Accurate everything.** Titles, tags, screenshots and descriptions must
   describe the real product. No borrowed imagery.
5. **One account.** No multi-accounting.
6. **Polite scraping.** The rate limits in `scout.py` are not tunables; they
   are the deal you make with the platform that hosts your income.
7. **Withdraw early.** Don't let earnings accumulate on any platform longer
   than necessary.

---

## Repository map

```
foundry/
├── config.json               your itch username + tool registry (no secrets!)
├── setup.ps1                 Windows one-time setup (downloads butler)
├── foundry/
│   ├── scout.py              niche research (rate-limited, cached, robots-aware)
│   ├── verify.py             headless-browser gate (playwright)
│   ├── publish.py            package + COPY.md + butler push + checkpoint text
│   ├── assets.py             cover/screenshot art rendered by the tool itself
│   └── build.py              orchestrates verify -> package -> checkpoint
├── tools/
│   └── dungeon-map-generator/
│       └── index.html        DELVE: single-file, offline, deterministic
├── cache/                    scraped pages (24 h TTL, gitignored)
├── data/                     SQLite niche history + screenshots (gitignored)
├── build/                    packaged zips + COPY.md (gitignored)
└── docs/
    ├── DECISIONS.md          why this platform, why these rules (read it)
    ├── LAUNCH-FREE.md        click-by-click free launch + flip-day checklist
    └── PARENT-BRIEFING.md    plain-language brief if an adult ever gets involved
```

---

## Putting this on GitHub

You do not need to give any tool or AI your GitHub token. From your machine:

```powershell
# on github.com: create an empty private repo, copy its URL, then:
cd foundry
git init
git add -A
git commit -m "Foundry v0.1: scout, verify, package, publish + DELVE"
git branch -M main
git remote add origin https://github.com/<you>/<repo>.git
git push -u origin main
```

If you ever must hand a token to a tool or service: use a **fine-grained
personal access token**, scoped to that one repository, Contents: Read and
write only, short expiry, revoked when done. Never a classic token.

---

## Troubleshooting

| symptom | fix |
|---|---|
| `butler` not found | run `setup.ps1` (uses the current host `broth.itch.zone`; reuses the itch app's butler if installed). Or skip butler: manual web upload is in `docs/LAUNCH-FREE.md` |
| 429 while scouting | you're rate-limited; cached pages are kept, re-run tomorrow |
| verify says "canvas looks blank" | your tool must render into `#cv` |
| verify says "NOT deterministic" | remove every `Math.random` from generation |
| push fails `bad user` | username in `config.json` ≠ your itch URL slug |
| push fails auth | `$env:BUTLER_API_KEY=...` not set in *this* terminal |
| page 404 after push | the checkpoint wasn't done; butler needs an existing page |
