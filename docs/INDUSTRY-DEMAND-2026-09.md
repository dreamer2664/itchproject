# Industry demand sweep — 2026-09-11

Purpose: pick the next product verticals with evidence, after the itch captcha
retired browser-automated publishing (see DECISIONS.md, same date).
Method: marketplace revenue reports, itch.io tag census, engine-community
install data, and our own scout v2 gap measurements (residential run).

---

## 1. Where the money flows (premium marketplaces)

Unity Asset Store (revenue guides, 2025-2026):
- **Editor tools & extensions = highest-earning category** ($15-80+, highest
  margins) — "directly save developers hours of work".
  https://generalistprogrammer.com/tutorials/unity-asset-store-selling-guide-revenue
- 3D models/environments = highest volume ($5-50 singles, $50-200+ packs).
- **Audio packs = steady, predictable income**, engine-agnostic (same WAV works
  everywhere), long sales tails, moderate competition.
- 2D art/sprites/tilesets = competitive but high demand ($5-30).
- Shaders/VFX = premium pricing ($10-60), specialised knowledge.
- Publisher economics: $50-200 sweet spot; portfolios of 10+ assets earn 3.7x
  those with <5; **specialisation creates 10x pricing power**; complete
  solutions command 5x component prices.
  https://mktclarity.com/blogs/news/top-unity-stores
- **Procedural Worlds (terrain / world-generation tools) ≈ $1M+/year** —
  procedural generation tooling is a proven million-dollar niche, not a hobby
  corner. (same source)

Unreal / Fab: materials & textures $10-80, VFX $25-150, environment packs
$50-300. https://generalistprogrammer.com/tutorials/game-asset-stores-complete-marketplace-guide-2025

Game UI: GraphicRiver maintains a *weekly-updated best-seller list* of game UI
templates ($6-27 typical) = recurring, evergreen sales.
https://graphicriver.net/popular_item/by_category?category=game-assets/user-interfaces

## 2. Where the traffic flows (itch.io — our Phase 1 shelf)

Tag census (itch top-tags pages, captured via search index Dec 2025):
- Top game-asset tags, in order: **Pixel Art, 2D, Sprites, Asset Pack**,
  Animation. https://itch.io/tags/assets
- Engine/community activity (projects, new per week):
  - **Godot 50.6k (+506/wk) — now out-adds Unity 135k (+430/wk)**
  - Unreal 22k (+80/wk), Blender 5.9k (+139/wk)
  - **Tabletop 18.3k (+135/wk)** — second-most active content community
  - **User Interface 5.8k (+113/wk)**, Ren'Py 10k (+59/wk), RPG Maker MZ 3.7k (+47/wk)
  https://itch.io/tags/tools
- **Tool supply is thin**: game-assets tagged `tools` = 333 results; `tools`
  tag = 241; tools tagged `game-assets` = **9**. Compare 135k+430/wk Unity and
  50.6k+506/wk Godot projects whose authors all need tools.
  https://itch.io/game-assets/tag-tool , https://itch.io/tools/tag-game-assets
- Free-pack traffic proof: a free pixel-art platformer pack passed
  **200,000+ downloads** on itch. https://www.relebook.com/articles/best-free-paid-game-asset-download-sites-2024
- itch UI top sellers: $4.99 - $31.99 per pack, GIFs animating = active market.
  https://itch.io/game-assets/top-sellers/tag-user-interface
- Tabletop/VTT: battlemaps & tokens are staple goods; Roll20 marketplace is a
  paid ecosystem; **Arkenforge is a paid map-BUILDER tool** — willingness to
  pay for map-making tooling is proven. https://itch.io/game-assets/free/tag-roll20

## 3. What developers actually install (engine communities)

Godot Asset Library top addons by stars: **terrain tools** (Terrain3D 2.2k★,
Heightmap Terrain 1.8k★), cameras, **dialogue systems (Dialogic)**,
**procedural generation (Gaea 1.1k★)**, debug consoles, importers.
https://www.reddit.com/r/godot/comments/1gvr4bu/most_popular_godot_4_asset_library_addons/ ,
https://garciamarquez.dev/posts/godot-popular-assets/
Unity's honoured list is editor tools: Odin Inspector, PlayMaker, A* Pathfinding,
Amplify Shader Editor. https://howik.com/best-unity-asset-store-assets
=> workflow/terrain/procedural tooling is what devs reach for first.

## 4. The audio gap

- "Audio is the most neglected discipline in indie game development… the skill
  set is specialized, the tools are expensive." (2026 pipeline article)
- Current AI SFX tools = **subscription, cloud, murky commercial licences**
  (ElevenLabs/Stable Audio/OptimizerAI). UE5's MetaSignals/MetaSounds push
  procedural audio mainstream.
  https://www.strayspark.studio/blog/procedural-audio-ai-music-ue5 ,
  https://www.strayspark.studio/blog/ai-sound-design-indie-games-pipeline
- Gap: an **offline, deterministic, licence-clean, one-price** SFX laboratory
  that exports plain WAV. The old jsfxr-family web toys are the only free
  competition and show their age.

## 5. Our own scout v2 gap table (residential run, 2026-09-11)

| keyword  | score | demand | supply | paid | median $ | verdict   |
|----------|-------|--------|--------|------|----------|-----------|
| texture  | 87.4  | 2,369  | 0      | 14   | 12.52    | PROMISING |
| dungeon  | 72.5  |   607  | 3      | 0    | -        | PROMISING |
| tileset  | 63.5  | 8,016  | 0      | 0    | -        | VIABLE    |
| pixel-art|  n/a  |   429* | -      | -    | -        | incomplete (*rate-limited) |

## 6. Candidate verticals, ranked for OUR constraints

Constraints: self-contained single-file HTML5, purely procedural (no scraped or
neural content), buildable in one cycle, minor-legal, free-first on itch.

| # | Vertical | Demand evidence | Competition | Our product | Build risk |
|---|----------|-----------------|-------------|-------------|------------|
| A | Textures / PBR materials | scout 87.4 (supply 0!); Unreal $10-80; Poly Haven proves mass appetite | itch generators ~0; free libs at high end | **Weave — BUILT & verified** | done |
| B | Tabletop / GM tools (battlemaps, tokens, VTT export) | tabletop 18.3k +135/wk; Arkenforge paid-tool proof | many map PACKS, few generators | DELVE line extension: caves/towns/sci-fi, grid+token export | low (code reuse) |
| C | Procedural SFX / audio lab | Unity "steady income" category; neglected discipline; AI tools = subscription cloud | jsfxr-era toys | WebAudio offline render -> WAV packs, seeded | medium |
| D | 2D tileset / sprite factory | pixel art = #1 itch asset tag; 200k-download packs; scout 63.5 | many packs, some generators | autotile rulesets, animated sprites, sheet export | medium-high |
| E | UI / HUD kit builder | UI 5.8k +113/wk; top sellers $4.99-31.99; GraphicRiver weekly bestsellers | many handmade packs, ~0 generators | 9-slice frames, buttons, icons, themes -> PNG kit | medium-high |
| F | Terrain heightmap -> mesh exporter | Procedural Worlds ~$1M/yr; Godot terrain addons top-10 | few web exporters | Weave heightmaps -> OBJ/STL export (3D-print crossover) | medium |

**Recommendation:** ship A now (zero build cost, 6-minute manual page birth).
Build B or C next: B reuses DELVE's engine and rides itch's second-biggest
community; C opens an engine-agnostic line with the weakest head-to-head
competition and the "steady income" economics.
