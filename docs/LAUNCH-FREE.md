# Launching DELVE free — click-by-click

**For: publishing with no adult on the account, no tax form, no payment
processor. Everything here is allowed by itch.io's terms for users 13+.**

The one rule that makes this legal: **no money may be able to flow in.**
Not sales, not pay-what-you-want, not donations. Receiving money is the act
that itch's payment processors restrict to adults. A free project with
payments disabled is just... a free project.

Estimated time: 10 minutes, once.

---

## Before you start (on your machine)

```powershell
cd foundry
python -m foundry.build dungeon-map-generator     # verify + package + copy
python -m foundry.assets  dungeon-map-generator   # cover + gallery art
```

You should now have, in `build/dungeon-map-generator/`:

| file | what it's for |
|---|---|
| `dungeon-map-generator.zip` | the upload (kind: HTML, plays in browser) |
| `COPY.md` | every piece of text you'll paste |
| `cover.gif` | animated page cover (or `cover.png` if you prefer still) |
| `gallery-ink.png` … `gallery-mono.png` | screenshots for the page |

---

## The itch.io part

1. **Account** — https://itch.io/user/register
   Email + password + username. No ID, no card, no phone.
   (Minimum age 13. If you're under 13, stop here and wait; everything else
   in this repo still works offline.)

2. **Dashboard → "Create new project"** — https://itch.io/dashboard

3. Fill in:

   | field | value |
   |---|---|
   | Title | `Delve — Procedural Dungeon Map Generator` (from COPY.md) |
   | Kind of project | **Tool** |
   | Classification | tick **"This file will be played in the browser"** |
   | Session | Single player |
   | Short description | the tagline line from COPY.md |
   | Description | paste the whole markdown description from COPY.md |

4. **Uploads section**
   - `Add file` → `build/dungeon-map-generator/dungeon-map-generator.zip`
   - Set its kind to **HTML**, tick *"This file will be played in the browser"*
   - Cover image: upload `cover.gif` (animated covers get more clicks;
     `cover.png` if the GIF is too big for your taste)
   - Screenshots: upload the four `gallery-*.png` files

5. **Tags** — paste the tag line from COPY.md:
   `dungeon-generator, map-generator, procedural-generation, roguelike, tools, level-design, ttrpg, dnd`

6. **Pricing — the important bit**
   - Choose **"No payments"**
   - **Leave "Accept donations" OFF / unticked**
   - There is no pay-what-you-want to set, because there is no price.
   This is deliberate. See the rule at the top of this document.

7. **Generative AI disclosure** — select **No** (this project contains no
   generative AI content; the rationale is written in COPY.md).

8. **Visibility: Public → Save.**

9. Copy your page URL. It will be
   `https://<your-username>.itch.io/dungeon-map-generator`

---

## Ship the build with butler

```powershell
$env:BUTLER_API_KEY="your-key-from-itch-io-user-settings-api-keys"
python -m foundry.publish push dungeon-map-generator
```

First push creates the `html5` channel and uploads. Every later update is the
same one line; butler only sends what changed.

Sanity check: open your page URL, press **Run game** (or whatever itch labels
the in-browser launch). It must load and generate with no console errors.
If it doesn't, `python -m foundry.verify` will tell you why.

---

## After launch: the weekly routine (~20 minutes)

1. **Analytics** — https://itch.io/dashboard/analytics
   Note views, downloads, and — most valuable — *which search terms* brought
   people. Those terms are tomorrow's keywords.
2. **Scout** — `python -m foundry.scout --limit 6` plus any terms you saw in
   analytics. `--history` shows the ranked table.
3. **Build the next tool** in the highest-scoring niche. Same pipeline:
   new folder under `tools/`, entry in `config.json`,
   `python -m foundry.build <slug>`, checkpoint, push.
4. **Jams** — https://itch.io/jams — free to enter, enormous visibility for
   free tools. One jam entry per month is the cheapest growth that exists.

Each live tool is an independent entry in itch's search index. The catalogue
compounds; the first sale you eventually enable lands on a shelf that already
has reviews and followers.

---

## Flip-day checklist (at 18, or when an adult takes over payouts)

Do these in order, on the day the adult setup is complete — not before:

1. Adult completes itch's payout setup + one-time tax interview (W-8BEN;
   it is a status certificate, not a tax return — see PARENT-BRIEFING.md in
   the project workspace docs).
2. Per project: Pricing → set a price or **pay-what-you-want, minimum $0**.
   Suggested starting price: the median of your niche from
   `python -m foundry.scout --history`.
3. Optionally tick **Accept donations**.
4. Create a **bundle** of your 4+ best tools at ~3× the single price.
   Bundles convert browsers into buyers better than anything else on itch.
5. Update each page description: remove nothing, add a line about the
   paid tier (offline batch export, commercial licence, presets...).
   Ship it with `butler push` as a new version.

Until flip day, this document's rule stands: **No payments. Donations off.**
