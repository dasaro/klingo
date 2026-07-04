# k-lingo 2.6.0

k-lingo is a Python CLI wrapper around clingo for depth-bounded reasoning modes:
- `--3nd-star`: depth-bounded approximation of the stable-model semantics;
- `--3nd`: depth-bounded classical reasoning over the totality-extended program;
- `--bnm`: `--3nd` core branches plus supervaluational stable completion
  (undecided atoms are presumed true/false when every compatible stable model agrees).

## Quick Start

```sh
./scripts/setup_venv.sh
source .venv/bin/activate
chmod +x klingo
./.venv/bin/python klingo --3nd-star -k 2 --mode all -n 0 Examples/kernel/enum_modes.lp
```

## Install

- System-wide CLI install (default: `/usr/local/bin`):

```sh
./scripts/install.sh
```

- User-local install:

```sh
./scripts/install.sh --user
```

- Manual usage without PATH changes:

```sh
./.venv/bin/python klingo --bnm -k 1 Examples/kernel/bnm_children_flip.lp
```

Full installation notes: [docs/INSTALLATION.md](docs/INSTALLATION.md)

## Max-Depth Detector

Print only the maximum reachable decision depth for the selected mode and input:

```sh
./.venv/bin/python klingo --3nd-star --detect-max-depth Examples/kernel/enum_modes.lp
./.venv/bin/python klingo --3nd --detect-max-depth Examples/kernel/enum_modes.lp
./.venv/bin/python klingo --bnm --detect-max-depth Examples/kernel/enum_modes.lp
```

Mode semantics:
- `--3nd-star`: depth measured on the original grounded program.
- `--3nd` / `--bnm`: depth measured on the totality-backed core search (`--bnm` completion is not part of this detector).

## API / CLI Reference

Main entrypoint:
- `klingo` (thin wrapper)
- orchestration: `klingo_engine.py`
- focused helper modules: `klingo_totality.py`, `klingo_completion.py`, `klingo_show.py`, `klingo_output.py`
- compatibility facade for older imports: `klingo_semantics.py`

CLI/API reference: [docs/API.md](docs/API.md)
Trust boundary note: [docs/implementation_trust_boundary.md](docs/implementation_trust_boundary.md)

Normal use is intentionally small:
- pick one mode (`--3nd-star`, `--3nd`, `--bnm`);
- choose a depth with `-k`;
- optionally select `--mode brave` or `--mode cautious`.

Inspection flags such as `--detect-max-depth`, `--dump-preprocessed`, `--print-config`, and
`--emit-bnm-trace` are available, but they are not needed for ordinary runs.

## Learning

Compile depth-earned conclusions into depth-0 presumptions:

```sh
./.venv/bin/python klingo --bnm --learn lemmas.lp Examples/kernel/bnm_children_open.lp
./.venv/bin/python klingo --bnm -k 0 --use-lemmas lemmas.lp Examples/kernel/bnm_children_open.lp
```

`--learn` computes the depth flip gain (what deeper reasoning establishes that
depth 0 lacks), generalizes it by resolving the defining rules on bivalent
literals, classically certifies each candidate schema against the
totality-extended program, and writes the survivors as ab-guarded default
lemmas. `--ilasp lemmas.lp inst1.lp inst2.lp ...` learns inductively instead
(requires the [ILASP](https://ilasp.com) binary): each positional file is a
training instance, per-instance flip gains become context-dependent examples,
the mode bias is generated from the gained atom's dependency cone, and the
hypothesis is refined by property-based CEGIS against the classical oracle
until no sampled counterexample context remains. `--use-lemmas` loads such a file: certified conclusions then appear as
`[b]` presumptions at depth 0, remain overridable by deeper derivation, are
retractable by asserting the guard atom, and leave the classical limit
unchanged. Guard atoms (`__`-prefixed) participate in solving but are never
displayed.

`--gate-lemmas` (with `--use-lemmas`) restricts the compiled bias to a
syntactic trust region: lemma files carry Weisfeiler-Leman signatures of
their provenance instances, and when the current instance's name-blind
structural distance exceeds the provenance threshold, the lemmas' guard
atoms are asserted and the bias is disabled for that run.

## Examples

Maintained kernel programs live in `Examples/kernel/`.
See [Examples/README.md](Examples/README.md) for intent and commands.

## Regression

Run semantic regression checks:

```sh
./.venv/bin/python scripts/regress_semantics.py
```

This suite explicitly checks:
- `#show` behavior in `all`, `brave`, and `cautious` output modes;
- grounded-only totality construction for `--3nd` / `--bnm`;
- mode-aware max-depth detection;
- supervaluational `--bnm` completion (no unsound promotions, classical-limit parity);
- the flip-trajectory examples (cautious-status transitions across depths).

## Project Layout

- `klingo`: CLI entrypoint
- `klingo_engine.py`: CLI parsing, propagator-based depth search, restart/block loop, aggregate bookkeeping
- `klingo_show.py`: `#show` parsing and valuation filtering
- `klingo_totality.py`: totality-universe construction, rendered totality rules, backend totality injection
- `klingo_completion.py`: assumption-based BNM branch completion and completion diagnostics
- `klingo_semantics.py`: compatibility facade re-exporting helpers from the focused modules
- `klingo_output.py`: truth-value conversion and output formatting
- `Examples/kernel/`: maintained `.lp` examples
- `scripts/`: install/setup and utility scripts
- `tests/`: golden fixtures and generated perf outputs for the regression harness

## Changelog

Release notes: [CHANGELOG.md](CHANGELOG.md)
