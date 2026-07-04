# Implementation Trust Boundary

This note clarifies what affects semantics vs what affects presentation/debug output.

## Module Split After Refactor

- Semantics-critical implementation surface:
  - `klingo_engine.py`: depth-bounded solver loop, restarts, blockers, aggregation.
  - `klingo_totality.py`: tracked totality universe construction and totality injection.
  - `klingo_completion.py`: BNM branch completion under clingo assumptions.
- Output-only implementation surface:
  - `klingo_show.py`: `#show` parsing and valuation filtering.
  - `klingo_output.py`: rendering/formatting only.
- Compatibility surface:
  - `klingo_semantics.py`: re-export layer for older imports; not a distinct semantic engine.

## Semantics-Critical Inputs

- Solver mode: `--3nd-star`, `--3nd`, `--bnm`
- Depth bound: `-k/--depth`
- Enumeration cap: `-n/--models`
- Restart strategy: `--restart-strategy`
- Program files passed to `klingo`

### Mode injections

- `--3nd-star`: no totality injection.
- `--3nd`, `--bnm`: totality rules are injected over the tracked grounded atom set:
  runtime grounded atoms plus syntactically ground source atoms that may be simplified away before solving.
- `--bnm`: after the bounded core search, branch-local completion is computed separately via the completion engine under assumptions.

Use `--dump-preprocessed <path>` to inspect static preprocessing (before runtime blockers).

## Output-Only Controls

- `#show` directives are used only for output filtering in `all`, `brave`, and `cautious`.
- `--clingo-output`, `--no-clingo-output`, `--color` affect rendering only.

## Debug / Experimental Controls

- `--emit-bnm-trace <outdir>` writes branch/iteration trace artifacts.
- `KLINGO_COMPLETION_DEBUG=<outdir>` writes completion-engine diagnostics.
- `--print-config` prints resolved settings used in the current run.

These controls do not alter mode semantics.
