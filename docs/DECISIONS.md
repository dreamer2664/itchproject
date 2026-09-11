# Decisions — why this platform, why these rules

*Condensed from the research phase (September 2026). Links to primary sources
are included so any claim here can be re-checked.*

## The constraint that shaped everything

Revenue = traffic × conversion × price. Conversion and price can be automated.
Traffic cannot be created — it must be borrowed from a platform where buyers
already search. With a $0 budget and no audience, that means: **a marketplace
with built-in search, free listing, and a payout rail that doesn't demand a
separate payment-processor account.**

## Platform comparison (verified Sept 2026)

| platform | listing fee | cut | payout min | traffic | verdict |
|---|---|---|---|---|---|
| **itch.io** | $0 | you choose (0-100%) | **$5** | yes, browse+search+jams | **chosen** |
| Gumroad | $0 | 10% + $0.50 (30% Discover) | $100 unverified (raised Mar 2026) | some | rejected |
| Whop | $0 | 3% | low | yes (Discover ~4M/mo, no extra cut since mid-2025) | fallback once first reviews exist |
| Ko-fi / Payhip | $0 | 0% / 5% | via your Stripe/PayPal | **none** | rejected (no traffic, needs your own processor) |
| Redbubble / TeePublic | $0 | margin | monthly | yes | rejected (Apprentice tier hides new sellers in search; mass/AI uploads = top ban cause) |
| Telegram Stars | $0 | ~0% creator-side | 1000 Stars + 21-day hold | some | rejected (cash-out needs crypto exchange KYC) |

Sources:
- itch payouts & $5 minimum, revenue share: https://itch.io/docs/creators/payments
- Gumroad $100 unverified threshold: https://roo.beehiiv.com/p/gumroad-fees-2026
- Whop Discover commission removed: https://www.creatorstackclub.com/software/whop
- TeePublic Apprentice invisibility: https://autokeyworder.com/blog/teepublic-vs-redbubble/

## Why procedural tools specifically

itch.io's quality guidelines state that *"projects using self-contained
algorithms without external large datasets don't require the use of
generative AI tags. For example... procedural level generation... dynamic
music... are not considered generative AI."*
(https://itch.io/docs/creators/quality-guidelines)

So a generator written as plain code, running locally, is **not AI content on
itch.io**: no AI tag, no filtering, and the indie-dev audience — which is
hostile to AI-generated art — actively likes procedural tools.

The same guidelines prohibit the obvious alternative: *"do not use automated
systems to mass produce product pages. We will consider this spam."* The math
agrees with the rule: 200 cheap spam pages nets ~$0.13/day; 15-20 good tools
at $4-6 reaches $2-3/day. Quality wins and is also the only thing allowed.

## Why there is a manual checkpoint

`butler` cannot create project pages (confirmed in itch's own docs and forum:
"Butler does not create a new project page for you"). itch has no public API
for page creation. Browser-automating internal web forms would be fragile and
would edge toward the mass-page rule. The 90-second human checkpoint is
therefore load-bearing: it satisfies the platform, and it is the quality gate.

## Why the verifier is a gate, not a suggestion

A broken public tool costs reviews you cannot delete. The gate checks the
failure modes that actually happen: console errors, blank canvas,
non-determinism (leaked `Math.random`), crashes on extreme parameters, broken
exports. It runs in headless Chromium so it costs nothing and catches almost
everything.

## Minors (read if applicable)

itch.io Terms of Service: publishers must be 18+ *or possess legal parental
or guardian consent*. Founder statement: *"You can have your own account if
you are under 18, but if you plan on selling please make sure you have an
adult manage the payments on your account."*
(https://itch.io/t/2726510, https://itch.io/t/1202220)

Publishing **free** projects requires only age 13+, no adult, no tax form,
no payment processor. Free projects accumulate downloads, reviews, followers
and search ranking exactly like paid ones. Strategy for a minor: build and
ship free now; enable payments at 18 or when an adult agrees to handle
payouts. Nothing is wasted either way.

**The strict-free rule.** While no adult operates the payout side, a project
must be set to **"No payments"** with **donations OFF**. Pay-what-you-want and
tip jars can receive money, and receiving money is the act the processors
restrict to adults -- so a "free" page with a tip jar enabled is out of
compliance just as much as a priced one. This repo encodes the rule in
`config.json` (`launch_mode: free`) and prints it in every packaging run.

There is no legitimate path anywhere for a minor to receive fiat payouts
without an adult: every processor (Stripe, PayPal, Square) and every
marketplace requires 18+ or a guardian, because receiving money is a contract
and minors cannot be held to contracts. Crypto is not an exception:
reputable exchanges are 18+, and non-KYC services are scams or illegal.

## What we will not do

- Falsify age or identity anywhere, ever. Consequences include permanent
  bans and funds held 180 days, and can extend to family at the same address.
- Mass-produce pages, reskin products, or misrepresent content.
- Scrape `/search` (disallowed by robots.txt) or exceed polite rate limits.
- Put generative-AI output into products (breaks the platform's trust and
  the community's).
