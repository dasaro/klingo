# Installation Guide

## Requirements

- Python 3.10+ recommended
- `clingo` Python package (`>=5.8,<5.9`)

Install dependencies:

```sh
pip install -r requirements.txt
```

Optional: `matplotlib` is needed only for `scripts/regress_semantics.py --perf` plot
generation (use `--skip-perf-plots` to collect perf metrics without it).

## Recommended Local Setup

```sh
./scripts/setup_venv.sh
source .venv/bin/activate
chmod +x klingo
```

Run:

```sh
./.venv/bin/python klingo --3nd-star -k 1 Examples/kernel/asp_convergence.lp
```

## Optional CLI Install

System-wide install (default target: `/usr/local/bin`):

```sh
./scripts/install.sh
```

User-local install:

```sh
./scripts/install.sh --user
```

Custom directory:

```sh
./scripts/install.sh --bin-dir /custom/bin
```

If needed (for user-local scope):

```sh
export PATH="$HOME/.local/bin:$PATH"
```

## Troubleshooting

- `ModuleNotFoundError: clingo`:
  - activate `.venv` and reinstall `requirements.txt`.
- `klingo: command not found`:
  - use `./.venv/bin/python klingo ...` or run `scripts/install.sh`.
