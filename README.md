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
- `--classical` / `--sat`: enforce totality with strong negation for each grounded atom.
- `--3nd-star` / `--3nd*`: use 3ND* semantics (default). Note: `--3nd*` may need quoting in some shells.
- `--3nd`: use classical 3ND semantics (enables totality).
- `--bnm`: bounded non-monotonic completion on undecided atoms (paper logic). Implies `--3nd`.
- `--heuristics FILE`: learned defaults file for introspection and transfer; can be passed multiple times.
- `--learn-ilasp OUT`: generate an ILASP task and run ILASP to write a learned program to `OUT`.
- `--show-ilasp-task`: print the generated ILASP task and exit.
- `--ilasp-target name[/arity]`: target predicate for ILASP (repeatable; defaults to all unary `#show` predicates).
- `--per-target`: run ILASP separately for each target predicate.
- `--restart-strategy`: restart policy (luby, geometric, dynamic, fixed, none). Provide a comma-separated list to cycle.
- `--mode` / `--enum-mode`: output mode: all valuations, brave (true in some valuation), cautious (true in all valuations).
- `-n, --models`: stop after N valuations (0 = enumerate all).

k-lingo enumerates k-depth valuations by stopping at the first valuation found, restarting from depth 0, and applying blocking constraints to avoid repeats.

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

When `--clingo-output` is enabled (the default), model output follows clingo's format (`Answer: N`, atom line, and summary), except undefined atoms are prefixed with `?` and can be colorized (see `--color`).\nUse `--no-clingo-output` to print the legacy k-lingo format instead.\nIn brave/cautious mode, `-n` controls how many valuations contribute to consequences (mirroring clingo's `-n`).\nIf `#show pred/arity` directives are present, only those atoms are printed in clingo-style output.\nWith `--bnm`, undecided atoms may be completed to true or false if derivable under default negation. When color is enabled:\n- Blue marks standard non-monotonic completions from the core program.\n- Dark yellow marks completions due to the learned heuristics file.\n- Dark green marks confirmation: a learned default’s value is derived by the solver at this depth.\n- Teal marks disconfirmation: a learned default’s value is flipped by deeper reasoning.\nWhen color is disabled, atoms are prefixed with ASCII markers: `[b]`, `[h]`, `[c]`, `[d]` respectively.

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

- Added ILASP integration for learning heuristic rules (`--learn-ilasp`, `--show-ilasp-task`).
- Added multi-target ILASP support and per-target runs (`--per-target`).

**v1.0.1**:

- Added heuristic transfer experiments and rule-level prototype.
- Added Wason-like experimental runners and ILASP plan.

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
