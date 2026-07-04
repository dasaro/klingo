# Regression Fixtures

This folder contains fixtures for `scripts/regress_semantics.py`.

- `golden/*.out`: normalized expected outputs for core semantic checks.
- `golden/totality_bnm_totality.lp`: helper fixture used for clingo totality oracle parity checks.
- `golden/totality_3nd_formal_resolution.lp`: helper fixture for the 3nd formal-resolution oracle check.

Regenerate golden outputs only when a behavior/output change is intentional:

```sh
./.venv/bin/python scripts/regress_semantics.py --update-golden --skip-oracle
```

Performance logs and plots can be generated with:

```sh
./.venv/bin/python scripts/regress_semantics.py --perf --perf-only
```

Outputs are written to `tests/perf/`.

## Testing Discipline

Run this sequence for regular development:

```sh
./.venv/bin/python scripts/regress_semantics.py
```

Rules to keep the tree organized:

- Keep semantic regressions bound to `tests/golden/` only.
- Keep kernel examples minimal and stable under `Examples/kernel/`.
- Keep exploratory outputs out of the repository and avoid committing ad-hoc logs.
- Treat `tests/perf/` as generated output, not source.
- If an exploratory script graduates to core workflow, document it in `README.md`; otherwise keep it out of the core harness.
