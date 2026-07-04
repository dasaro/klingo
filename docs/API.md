# CLI / API Reference

## CLI Entry

```sh
./.venv/bin/python klingo [MODE] [OPTIONS] <file.lp> [file2.lp ...]
```

## Modes

- `--3nd-star` (default): depth-bounded 3ND* search
- `--3nd`: depth-bounded totality-backed classical-side branching
- `--bnm`: `--3nd` core branches + branch-local completion

## Core Options

- `-k, --depth <int>`: depth bound (must be `>= 0`)
- `-n, --models <int>`: max valuations (`0` = all)
- `--mode {all,brave,cautious}`: aggregation mode
- `-o, --clingo-output`: clingo-style output (default)
- `--no-clingo-output`: legacy k-lingo output
- `--color {auto,always,never}`: colorized output behavior
- `--version`: print version and exit

For ordinary use, the public CLI surface is just:
- mode selection (`--3nd-star`, `--3nd`, `--bnm`)
- `-k/--depth`
- `--mode`
- `-n/--models`
- output style flags

## Learning Options

- `--learn <path>` (requires `--bnm`): compute the depth flip gain, generalize it by
  resolution on bivalent literals, certify each schema classically against the
  totality-extended program, write certified lemmas to `<path>`, then exit.
- `--ilasp <path>` (requires `--bnm` and the ILASP binary on PATH): learn lemmas
  inductively. Each positional file is a training instance; flip gains become
  context-dependent examples; the hypothesis is refined by property-based CEGIS
  against the classical oracle, then written to `<path>` in the same ab-guarded
  register as `--learn`.
- `--use-lemmas <path>`: load a lemma file produced by `--learn` or `--ilasp`
  alongside the input files. Certified conclusions appear as `[b]` presumptions at
  depth 0, remain overridable by deeper derivation, and leave the classical limit
  unchanged.
- `--gate-lemmas` (requires `--use-lemmas`): apply the compiled bias only on
  syntactically familiar instances. Lemma files carry provenance
  Weisfeiler-Leman histograms; when the instance's name-blind structural
  distance to every provenance instance exceeds the stored threshold, the
  lemmas' `__ab` guards are asserted for the run (an Info line reports the
  distance and verdict either way).
- Convention: atoms named with a `__` prefix (lemma guards) are internal — they
  participate in solving but are never displayed.

## Inspection / Debugging Options

- `--restart-strategy <name[,name...]>`: restart policy cycle
- `--detect-max-depth`: print only the maximum reachable decision depth and exit
- `--debug`: verbose diagnostics
- `--dictionary`: print literal dictionary
- `--dump-preprocessed <path>`: dump static preprocessed program (mode injections only)
- `--print-config`: print resolved run configuration/trust-boundary settings

### `--detect-max-depth` Semantics

- `--3nd-star`: computes max depth on the original grounded program.
- `--3nd` and `--bnm`: computes max depth on the totality-backed core search.
- For `--bnm`, branch completion is intentionally excluded (detector measures core branching depth only).

## BNM-Specific Diagnostics

- `--emit-bnm-trace <outdir>`:
  - emits per-depth JSON trace payloads for core branches and completion metadata.
- `KLINGO_COMPLETION_DEBUG=<outdir>` (environment variable):
  - emits JSONL completion diagnostics for branch completion calls.

## Exit / Output

- Prints valuations or brave/cautious aggregates depending on `--mode`.
- Prints solver summary (`Calls`, `Models`, `Time`, `CPU Time`).
- Non-zero exit when input loading/grounding/solving fails.

## Python-Level Modules

- `klingo`:
  - thin CLI wrapper importing `main` from `klingo_engine.py`.
- `klingo_engine.py`:
  - argument parsing and top-level run orchestration.
  - propagator-based depth-bounded search.
  - restart policy selection, blocker construction, and model aggregation.
- `klingo_show.py`:
  - `#show` signature/term extraction and valuation filtering.
  - backward-compatible `parse_show_signatures(...)` helper.
- `klingo_totality.py`:
  - totality-universe construction from grounded and source-ground atoms.
  - rendered totality rules and backend totality injection helpers.
- `klingo_completion.py`:
  - assumption-based BNM branch completion.
  - completion diagnostics and completion-engine caching.
- `klingo_semantics.py`:
  - compatibility facade re-exporting helpers from the focused modules.
  - retained for older imports; new code should import the focused modules directly.
- `klingo_output.py`:
  - truth-value rendering and valuation formatting.
