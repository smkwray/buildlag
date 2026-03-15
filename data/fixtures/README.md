# Fixture data

The files in this folder are **development fixtures**.

They exist so the static site and score pipeline work immediately in a fresh checkout.

Rules:

- do not treat these files as factual outputs
- do not publish rankings generated from these fixtures
- keep fixture generation deterministic for tests
- replace them with real-source outputs in `data/processed/` for the first public release
