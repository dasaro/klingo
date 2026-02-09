# k-lingo 1.2.2

## Overview
k-lingo is a Python-based tool that runs a clingo propagator to compute k-depth 3ND*-valuations for logic programs.

## Requirements
- Python 3 (tested with 3.7.x and 3.9.x).
- A Python-enabled `clingo` installation (see https://potassco.org/clingo/). The Python API currently reports 5.8.0 in this environment.
- macOS users can use Anaconda or Homebrew Python; see `how_to_run_klingo.txt` for an example path.

## Installation
No packaging is required. Clone the repo and ensure the script is executable:

```sh
chmod +x klingo
```

Optional: install as a standalone program (adds symlinks to `~/.local/bin`):

```sh
./scripts/install.sh
```

You can also add the repo to your PATH manually:

```sh
export PATH="$PATH:/path/to/repo"
```

## Usage
Run against one or more `.lp` programs:

```sh
./klingo -k <depth> Examples/kernel/asp_convergence.lp
./klingo -k <depth> Examples/kernel/asp_convergence.lp Examples/kernel/enum_modes.lp
```

Common flags:
- `-k, --depth`: reasoning depth (default: 0).
- `-o, --clingo-output`: output only true/undefined atoms in clingo style (default).
- `--no-clingo-output`: use the legacy k-lingo output format.
- `--dictionary`: print the solver literal mapping.
- `--debug`: print debug information.
- `--3nd-star`: original ASP approximation (default mode).
- `--3nd`: totality axioms only, no completion.
- `--bnm`: totality axioms plus bounded non-monotonic completion on undecided atoms.
- `--restart-strategy`: restart policy (luby, geometric, dynamic, fixed, none). Provide a comma-separated list to cycle.
- `--mode`: output mode: all valuations, brave (true in some valuation), cautious (true in all valuations).
- `-n, --models`: stop after N valuations (0 = enumerate all).

k-lingo enumerates k-depth valuations by stopping at the first valuation found, restarting from depth 0, and applying blocking constraints to avoid repeats.

Quick semantic entry points:

```sh
./klingo --3nd-star -k 1 Examples/kernel/asp_convergence.lp
./klingo --3nd -k 1 Examples/kernel/asp_convergence.lp
./klingo --bnm -k 1 Examples/kernel/bnm_totality.lp
```

Naive semi-orthogonal decomposition (intuition):
- Let `P` be a program and `k` the depth bound.
- Mode (i) `--3nd-star` computes `A_k(P)`: depth-bounded approximation of the non-monotonic semantics directly on `P`.
- Mode (ii.a) `--3nd` computes `T_k(P)`: depth-bounded search over the classicalized base (`3ND` totality only).
- Mode (ii.b) `--bnm` computes `C_k(P)`: `--3nd` plus bounded non-monotonic completion over the already decided core.
- Informally, you can view these as two axes:
  - ASP-side axis: `P -> A_k(P)` (`--3nd-star`)
  - Classical-side axis: `P -> classical(P) -> T_k(P) -> C_k(P)` (`--3nd` to `--bnm`)
- As `k` increases, both tracks are intended to stabilize, but they need not coincide at small `k`.

If `./klingo` is not on your PATH, use:

```sh
python3 klingo -k 0 Examples/kernel/enum_modes.lp
```

## Example Runs
Small sanity checks (run locally):

```sh
python3 klingo --3nd-star -k 0 Examples/kernel/asp_convergence.lp
python3 klingo --3nd-star -k 1 Examples/kernel/asp_convergence.lp
python3 klingo --3nd-star -k 2 --mode brave Examples/kernel/enum_modes.lp -n 0
python3 klingo --3nd-star -k 2 --mode cautious Examples/kernel/enum_modes.lp -n 0
python3 klingo --bnm -k 0 Examples/kernel/bnm_children_flip.lp --no-clingo-output -n 1
python3 klingo --bnm -k 2 Examples/kernel/bnm_totality.lp --mode brave -n 0
python3 klingo --3nd-star -k 0 Examples/kernel/unsat.lp
```

Notes:
- `asp_convergence.lp` is a minimal alternating-default benchmark for depth behavior.
- `bnm_totality.lp` is intended for direct comparison with `clingo` plus explicit totality axioms.

## Output Format
The tool prints each atom with its truth value:
- `1` for true, `0` for false, `?` for undefined.
At the end, it prints satisfiability, atom counts, and elapsed time.

When `--clingo-output` is enabled (the default), model output follows clingo's format (`Answer: N`, atom line, and summary), except undefined atoms are prefixed with `?` and can be colorized (see `--color`).
Use `--no-clingo-output` to print the legacy k-lingo format instead.
In brave/cautious mode, `-n` controls how many valuations contribute to consequences (mirroring clingo's `-n`).
If `#show pred/arity` directives are present, only those atoms are printed in clingo-style output.
With `--bnm`, undecided atoms may be completed from the already decided core (non-branching). This keeps depth-0 behavior conservative and avoids by-cases completion at depth 0. When color is enabled:
- Blue marks standard non-monotonic completions from the core program.
When color is disabled, atoms are prefixed with ASCII marker `[b]`.

## Computational Considerations
- Runtime can be highly non-monotonic in `k`; intermediate depths may be slower than both low and high depths.
- Large `k` values can be fast if the solver reaches a total valuation quickly, but enumeration may still be expensive when many partial valuations exist.
- `--restart-strategy` can influence time to the next valuation; consider cycling strategies for exploration.

## Project Layout
- `klingo`: main executable script.
- `Examples/kernel/`: focused kernel `.lp` programs for validation.
- `scripts/install.sh`: optional installation helper.

## Versioning
This repository uses `V.X(.Y)`:
- `V`: stable major generation.
- `X`: feature/minor release within the stable generation.
- `Y` (optional): patch/hotfix release.

Current release is in the `1.*` stable line. Bump guidance:
- Breaking semantic/CLI changes: bump `V`, reset `X`/`Y`.
- New backwards-compatible features or notable workflow changes: bump `X`.
- Bugfix-only or docs/test-only maintenance: bump `Y`.

## CHANGELOG

**1.2.2**:

- Colorized legend entries in color mode (legend now renders colored markers directly).

**1.2.1**:

- Fixed `#show` parsing for strong-negated signatures (e.g., `#show -blonde/1.`), so shown negative atoms are no longer dropped from clingo-style output filtering.

**1.2.0**:

- Reduced `Examples/` to a focused kernel set under `Examples/kernel/`.
- Added explicit convergence verification workflow:
  - `--3nd-star` vs plain `clingo`.
  - `--bnm` vs `clingo` on `(program + totality axioms)`.
- Removed overlapping/legacy examples and updated usage commands accordingly.

**1.1.0**:

- Stabilized the three-mode semantic interface: `--3nd-star`, `--3nd`, `--bnm`.
- Kept totality/completion as mode-internal semantics (not separately user-tunable).

**1.0.0**:

- Added brave/cautious modes, restart strategies, and valuation enumeration controls.
- Added helper scripts for installation and Sudoku pretty printing.

**0.0.3**:

- Klingo now outputs the number of atoms and bottoms in the 3ND\*-valuation.

**0.0.2**:

- README created
- Added options to control output format
- Output now clearly states when the input logic program is unsatisfisable
- Output now clearly states if the found 3ND\*-valuation is total

**0.0.1**:

- Git repository created.
- First alpha version uploaded.
