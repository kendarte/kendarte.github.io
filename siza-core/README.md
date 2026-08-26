# Siza Shared Card Core

Shared card infrastructure used by the Card Generator and `siza-mobile-test`.

- `card-effects.js` defines and validates structured effect descriptors and owns generic effect-presence and amount-aggregation queries used by Arena.
- `card-schema.js` normalizes card data and preserves effect metadata across handoff, including `equipCost`; it also owns the runtime-equivalent Equipment classification and Equipment-cost queries used by Arena.
- `cards.js` is the official shared card catalog.
- `card-renderer.js` renders both standard Generator cards and the Mobile/Arena surface.
- `card-renderer.css` styles the standard Generator surface.
- `manifest-rules.js` owns the pure affinity, difficulty, natural-chance, Manafestation requirement, roll-deficit, and eligible manifest-bonus-source calculations. Arena keeps source application, artifact exhaustion, Mana Burn consumption, and presentation state local.
- `crystal-rules.js` owns printed-pip requirements, spell crystal cost, direct-payment planning, the pure Ofrenda/payment planner, crystal-pool refresh, and atomic crystal spending. Arena injects `cardById` into the planner so generated/test cards remain resolvable; turn sequencing, Ofrenda sacrifice, and other match-state decisions remain local to Arena.
- `entry-rules.js` owns the three experimental creature-entry modes plus pure preparation, attack eligibility, available-attacker, and legal-blocker calculations. Arena injects the active entry mode, `cardById`, and shared spell-cost calculation while battlefield mutation and combat resolution remain local.
- `creature-rules.js` owns creature counters, equipped-card lookup, descriptor-driven Equipment power bonuses, effective power/toughness, aligned battlefield add/remove mutations, pure `attack-declared` damage aggregation, the pure combat outcome plan, the pure player blocker reassignment plan, and the pure AI blocker assignment plan. Arena applies those plans to the existing match-state objects while life, graveyards, logs, win state, turn state, FX, toasts, and UI orchestration remain outside the shared core.

Arena now resolves the supported card behavior from structured card data for `resolve`, `enter`, `attack-declared`, `combat-damage`, `manifest-roll`, and `equipped` events. This covers the current stack/entry effects, Contrabandista Carmesí, Ignimite, Prisma de Enfoque, and Espada de Bajamar. Permanent regressions also exercise generated cards with unknown IDs to ensure these behaviors are driven by descriptors rather than catalog-specific conditionals.

The current Equipment runtime intentionally supports `Equipar {1}` only. The schema rejects larger `equipCost` values until multi-crystal Equipment payment has its own explicit runtime contract and tests.

The Arena monolith has also been canonicalized to zero duplicate named function declarations. Historical shadow declarations for combat, priority, battlefield removal, and rendering were removed only after old/new behavior checks; the surviving declarations are the functions that were already governing the runtime before cleanup.
