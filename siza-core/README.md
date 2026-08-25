# Siza Shared Card Core

Shared card infrastructure used by the Card Generator and `siza-mobile-test`.

- `card-effects.js` defines and validates structured effect descriptors.
- `card-schema.js` normalizes card data and preserves effect metadata across handoff.
- `cards.js` is the official shared card catalog.
- `card-renderer.js` renders both standard Generator cards and the Mobile/Arena surface.
- `card-renderer.css` styles the standard Generator surface.

Arena resolves supported `resolve`, `enter`, `attack-declared`, and `combat-damage` behavior from structured card data. This currently covers the stack/entry effects plus Contrabandista Carmesí and Ignimite combat triggers. Activated Manafestation abilities and continuous Equipment modifiers are migrated separately so each behavior retains its existing regression coverage.
