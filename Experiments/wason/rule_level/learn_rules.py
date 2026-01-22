#!/usr/bin/env python3
import argparse
import subprocess
from pathlib import Path


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)


def parse_atoms(output):
    atoms = set()
    for line in output.splitlines():
        line = line.strip()
        if line.startswith("Answer:"):
            continue
        if line and not line.startswith("SATISFIABLE") and not line.startswith("Models"):
            for tok in line.split():
                if not tok.startswith("?"):
                    atoms.add(tok)
    return atoms


def main():
    parser = argparse.ArgumentParser(description="Learn simple rule-level heuristic defaults.")
    parser.add_argument("--klingo", default="./klingo")
    parser.add_argument("--train", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    cmd = [args.klingo, "--bnm", "--mode", "brave", "--clingo-output", "-k", "5", args.train]
    res = run(cmd)
    if res.returncode != 0:
        raise RuntimeError(res.stderr or res.stdout)
    atoms = parse_atoms(res.stdout)

    reds = {a[4:-1] for a in atoms if a.startswith("red(") and a.endswith(")")}
    flips = {a[5:-1] for a in atoms if a.startswith("flip(") and a.endswith(")")}

    rules = []
    if reds and flips and reds.issubset(flips):
        rules.append("flip(C) :- red(C), not -flip(C).")

    header = ["% learned rules", f"% source: {args.train}"]
    Path(args.out).write_text("\n".join(header + rules) + "\n")

    print(f"wrote {len(rules)} rules to {args.out}")


if __name__ == "__main__":
    main()
