# Manual page birth — the shipping protocol (post-captcha)

`foundry.launch` (browser automation) is **retired**: itch's captcha defeats
automated browsers even with a human solving it. A *normal* browser window has
no such problem, so page creation is a 6-minute human task. Everything else
stays automated. See docs/DECISIONS.md (2026-09-11).

## Once per machine
- Log in to itch.io in your everyday browser (Chrome/Edge/Firefox). Stay logged in.

## Once per product (≈6 minutes)
1. Generate the kit (from the repo root):
       python -m foundry.build <slug>
       python -m foundry.assets <slug>
   This writes `build/<slug>/`: `COPY.md` (all the page text), `copy.json`,
   `<slug>.zip` (the playable build), `cover.png`, `cover.gif`, `gallery-*.png`.
2. itch.io → your dashboard → **Upload new project** (button top-right of
   https://itch.io/dashboard).
3. Fill from `COPY.md`, in this order:
   - **Title** = copy title. **Kind of project** = *HTML*.
   - **Description** = paste the description block (rich text editor: paste as
     plain text, then bold the header line if you like).
   - **Cover image** = upload `cover.gif` (animated, catches eyes in browse
     views) or `cover.png`.
   - **Screenshots** = upload the four `gallery-*.png`.
   - **Uploads** → *Upload files* = `<slug>.zip`, and tick
     **"This file will be played in the browser"**.
   - **Tags**: type every tag listed in COPY.md, Enter after each.
     Include `free` positioning tags exactly as listed.
   - **Pricing** = **No payments** (Phase 1 rule: nothing monetary, donations
     OFF, until an adult operates payouts or you turn 18).
4. Eyeball the preview pane. Click **Save & view page**.
5. Play it once in the browser player on your live page. If it runs, done —
   the page is live and free.

## Updates forever after (no browser)
    $env:BUTLER_API_KEY = "<your itch API key>"   # once per shell
    python -m foundry.publish push <slug>
Butler uploads new builds to the existing page; the page itself (text, art,
price) stays as you set it in the browser.

## Guardrails that stay true
- One product per build cycle; human eyes on every page before Save.
- Free-first Phase 1: no PWYW, no donations, no paid tiers.
- Max ~2 page births per week while the account is young — quality shelf,
  never mass pages (itch quality guidelines).
