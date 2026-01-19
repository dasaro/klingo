# k-lingo 0.0.3

## Overview
k-lingo is a Python-based tool that runs a clingo propagator to compute k-depth 3ND*-valuations for logic programs.

## Requirements
- Python 3 (tested with 3.7.x and 3.9.x).
- A Python-enabled `clingo` installation (see https://potassco.org/clingo/).
- macOS users can use Anaconda or Homebrew Python; see `how_to_run_klingo.txt` for an example path.

## Installation
No packaging is required. Clone the repo and ensure the script is executable:

```sh
chmod +x klingo
```

## Usage
Run against a `.lp` program:

```sh
./klingo -k <depth> Examples/example1.lp
```

Common flags:
- `-k, --depth`: reasoning depth (default: 0).
- `-o, --clingo-output`: output only true/undefined atoms in clingo style.
- `--dictionary`: print the solver literal mapping.
- `--debug`: print debug information.

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
```

Notes:
- `example1.lp` is SAT at depth 0 with undefined atoms, and becomes total at depth 1.
- `mini_sudoku.lp` is SAT at depth 1 and returns a partial valuation with some bottoms.

## Output Format
The tool prints each atom with its truth value:
- `1` for true, `0` for false, `?` for undefined.
At the end, it prints satisfiability, atom counts, and elapsed time.

## Project Layout
- `klingo`: main executable script.
- `Examples/`: sample `.lp` programs for validation.

## CHANGELOG

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
