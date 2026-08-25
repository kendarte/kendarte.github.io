# Siza Shared Card Core

Shared card infrastructure used by the Card Generator and `siza-mobile-test`.

- `card-effects.js` defines and validates structured effect descriptors.
- `card-schema.js` normalizes card data and preserves effect metadata across handoff, including `equipCost`.
- `cards.js` is the official shared card catalog.
- `card-renderer.js` renders both standard Generator cards and the Mobile/Arena surface.
- `card-renderer.css` styles the standard Generator surface.

Arena now resolves the supported card behavior from structured card data for `resolve`, `enter`, `attack-declared`, `combat-damage`, `manifest-roll`, and `equipped` events. This covers the current stack/entry effects, Contrabandista Carmesí, Ignimite, Prisma de Enfoque, and Espada de Bajamar. Permanent regressions also exercise generated cards with unknown IDs to ensure these behaviors are driven by descriptors rather than catalog-specific conditionals.

The current Equipment runtime intentionally supports `Equipar {1}` only. The schema rejects larger `equipCost` values until multi-crystal Equipment payment has its own explicit runtime contract and tests.

The Arena monolith has also been canonicalized to zero duplicate named function declarations. Historical shadow declarations for combat, priority, battlefield removal, and rendering were removed only after old/new behavior checks; the surviving declarations are the functions that were already governing the runtime before cleanup.
