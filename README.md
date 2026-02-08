# k-lingo 2.0.0

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
./klingo -k <depth> Examples/example1.lp
./klingo -k <depth> Examples/example1.lp Examples/example2.lp
```

Common flags:
- `-k, --depth`: reasoning depth (default: 0).
- `-o, --clingo-output`: output only true/undefined atoms in clingo style (default).
- `--no-clingo-output`: use the legacy k-lingo output format.
- `--dictionary`: print the solver literal mapping.
- `--debug`: print debug information.
- `--classical`: enforce totality with strong negation for each grounded atom.
- `--3nd-star`: use 3ND* semantics (default).
- `--3nd`: use classical 3ND semantics (enables totality).
- `--bnm`: bounded non-monotonic completion on undecided atoms (paper-inspired, non-branching core completion). Implies `--3nd`.
- `--asp-approx`: shorthand for mode (i), approximation of a non-monotonic logic (same as `--3nd-star`).
- `--classical-approx`: shorthand for mode (ii), non-monotonic approximation of a classical logic (same as `--bnm`).
- `--restart-strategy`: restart policy (luby, geometric, dynamic, fixed, none). Provide a comma-separated list to cycle.
- `--mode`: output mode: all valuations, brave (true in some valuation), cautious (true in all valuations).
- `-n, --models`: stop after N valuations (0 = enumerate all).

k-lingo enumerates k-depth valuations by stopping at the first valuation found, restarting from depth 0, and applying blocking constraints to avoid repeats.

Quick semantic entry points:

```sh
./klingo --asp-approx -k 1 Examples/example1.lp
./klingo --classical-approx -k 1 Examples/example1.lp
```

Naive semi-orthogonal decomposition (intuition):
- Let `P` be a program and `k` the depth bound.
- Mode (i) `--asp-approx` computes `A_k(P)`: depth-bounded approximation of the non-monotonic semantics directly on `P` (3ND* track).
- Mode (ii) `--classical-approx` computes `C_k(P)`: first force a classicalized base (`3ND` totality), then apply bounded non-monotonic completion (BNM track) over the already decided core, without extra completion branching.
- Informally, you can view these as two axes:
  - ASP-side axis: `P -> A_k(P)`
  - Classical-side axis: `P -> classical(P) -> C_k(P)`
- As `k` increases, both tracks are intended to stabilize, but they need not coincide at small `k`.

If `./klingo` is not on your PATH, use:

```sh
python3 klingo -k 0 Examples/example2.lp
```

## Example Runs
Small sanity checks (run locally):

```sh
python3 klingo -k 0 Examples/example1.lp
python3 klingo -k 1 Examples/example1.lp
python3 klingo -k 1 Examples/mini_sudoku.lp
python3 klingo -k 1 --restart-strategy luby,geometric Examples/example1.lp
python3 klingo -k 1 --mode brave Examples/example1.lp
python3 klingo -k 1 --mode cautious Examples/example1.lp
python3 klingo -k 1 --mode brave Examples/aba_example.lp
python3 klingo -k 1 --mode cautious Examples/aba_example.lp
```

Notes:
- `example1.lp` is SAT at depth 0 with undefined atoms, and becomes total at depth 1.
- `mini_sudoku.lp` is SAT at depth 1 and returns a partial valuation with some bottoms.

## Pretty-Printed Sudoku
To render Sudoku grids without embedding formatting in `klingo`, pipe its output to the helper formatter:

```sh
python3 klingo -k 6 --clingo-output Examples/sudoku.lp | \\
  python3 scripts/pretty_sudoku_from_klingo.py
python3 klingo -k 6 --mode cautious --clingo-output Examples/sudoku.lp | \\
  python3 scripts/pretty_sudoku_from_klingo.py
```

The formatter reads from stdin and formats `sudoku/3` atoms into a 9x9 grid with 3x3 boxes.

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
- `Examples/`: sample `.lp` programs for validation.
- `scripts/pretty_sudoku_from_klingo.py`: stdin formatter for Sudoku grids.
- `scripts/install.sh`: optional installation helper.

## CHANGELOG

**v2.0.0**:

- Added shorthand semantic modes (`--asp-approx`, `--classical-approx`) and stabilized non-branching BNM completion.

**v1.0.0**:

- Added brave/cautious modes, restart strategies, and valuation enumeration controls.
- Added helper scripts for installation and Sudoku pretty printing.

**v0.0.3**:

- Klingo now outputs the number of atoms and bottoms in the 3ND\*-valuation.

**v0.0.2**:

- README created
- Added options to control output format
- Output now clearly states when the input logic program is unsatisfisable
- Output now clearly states if the found 3ND\*-valuation is total

**v0.0.1**:

- Git repository created.
- First alpha version uploaded.
