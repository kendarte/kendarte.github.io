# Siza Shared Card Core

Shared card infrastructure used by the Card Generator and `siza-mobile-test`.

- `card-effects.js` defines and validates structured effect descriptors.
- `card-schema.js` normalizes card data and preserves effect metadata across handoff.
- `cards.js` is the official shared card catalog.
- `card-renderer.js` renders both standard Generator cards and the Mobile/Arena surface.
- `card-renderer.css` styles the standard Generator surface.

Arena currently resolves the supported `resolve` and `enter` effects from card data. Combat-triggered and continuous card abilities are migrated separately so each behavior can retain its existing regression coverage.
