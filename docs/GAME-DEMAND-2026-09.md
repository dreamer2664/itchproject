# Game demand sweep — 2026-09-12 (night build)

Question: the first FLAGSHIP GAME (not a tool). Which genre/complexity class
has real, measured demand AND is buildable as one self-contained HTML5 file
with purely procedural art?

## 1. Revenue by genre (Steam indie, 2026 data)
Median revenue for titles with 100+ reviews:
- **Factory/automation: $200k-$500k+ — the highest-median indie genre.**
  "Factorio and Satisfactory set the template, and the audience is dedicated
  and high-spending."
- **Colony sim / management: $150k-$400k.** "RimWorld, Dwarf Fortress and
  their successors proved this audience will pay premium prices."
- Survival crafting $100k-$350k; **city builders $75k-$250k** (consistent,
  loyal).
- Saturated/low: platformers, puzzle, walking sims, retro arcade.
https://www.steampageanalyzer.com/blog/indie-game-revenue-data
Macro: simulation & sandbox genres growing at **16.78% CAGR**, the fastest
climbing genre block; indies ≈ half of all Steam full-game revenue.
https://www.mordorintelligence.com/industry-reports/indie-game-market ,
https://www.accio.com/business/popular-indie-games-trend

## 2. The browser/itch shelf (where we actually publish, Phase 1 free)
- itch `Management` tag: **7,464 games**, of which **3,497 free simulation**;
  the new-and-popular feed is full of *browser-playable* management sims
  (Processor Tycoon, Hardware Tycoon, Metropolis, Immortality Factory,
  Industrial Knowledge...). The genre lives and breathes in-browser on itch.
  https://itch.io/games/tag-management ,
  https://itch.io/games/free/genre-simulation/tag-management
- itch HTML5 `Idle`: 5,574 results — incrementals are a browser staple, but
  the shelf is clicker-saturated; depth+polish is the differentiator.
  https://itch.io/games/html5/tag-idle
- Cozy building demand is real (Tiny Glade 600k first week) but the iconic
  titles are 3D dioramas; 2D cozy life-sim is a red ocean vs Stardew/Terraria.
  https://www.switchbladegaming.com/cozy-games/building/ ,
  https://www.accio.com/business/list_of_best_selling_indie_games

## 3. Feasibility filter (one HTML file, canvas 2D, zero assets, zero network)
- Factory/automation: grid + belts + machines + recipes = *the* most
  feasible deep genre in 2D canvas; physical logistics read beautifully
  top-down; no physics, no 3D, no art pipeline. Proven browser examples
  exist but few polished ones → quality gap we can fill.
- Colony sim layer (agents, needs, jobs): feasible as a LIGHT overlay
  (A* walkers + global food/beds) on top of the factory grid — captures the
  #2 genre without RimWorld-scale scope.
- 3D/"big": rejected — WebGL worlds need asset pipelines; our edge is
  systems depth with procedural art, matching both top revenue genres.

## 4. Decision
**GRIMFORGE — a goblin factory-automation tycoon with a light colony layer.**
- Genre #1 mechanics (belts, miners, smelters, assemblers, recipe chains,
  contracts/logistics) + genre #2 flavour (goblin crew: operators, food,
  beds, population growth).
- Dungeon-flavoured theme ties the game to our existing shelf (DELVE,
  TABLEFORGE) — portfolio cross-sell, "the tenth asset sells the first".
- Complete arc: seeded cave, timed delivery contracts, reputation tiers,
  endless sandbox after; save/load + seed sharing.
- Free-first Phase 1: a genuinely deep free browser game is exactly the
  kind of page that collects downloads, ratings and follows.

Sources fetched 2026-09-12 via web search index (itch pages through search
snippets to respect rate limits).
