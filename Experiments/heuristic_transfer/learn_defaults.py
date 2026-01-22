#!/usr/bin/env python3
import argparse
import subprocess
import sys


def parse_atoms_from_bnm_output(text):
    lines = [line.rstrip() for line in text.splitlines()]
    atoms_line = None
    for i, line in enumerate(lines):
        if line.startswith("Answer:"):
            # atoms are printed on the next non-empty line
            for j in range(i + 1, len(lines)):
                if lines[j].strip() != "":
                    atoms_line = lines[j].strip()
                    break
    if atoms_line is None:
        return []
    return [tok for tok in atoms_line.split() if not tok.startswith("?")]


def to_default_rules(atoms):
    rules = []
    for atom in atoms:
        if atom.startswith("-"):
            base = atom[1:]
            rules.append(f"-{base} :- not {base}.")
        else:
            rules.append(f"{atom} :- not -{atom}.")
    return rules


def main():
    parser = argparse.ArgumentParser(description="Learn defeasible defaults from a deep k-lingo run.")
    parser.add_argument("--input", required=True, help="source .lp program")
    parser.add_argument("--k", type=int, required=True, help="depth to run")
    parser.add_argument("--output", required=True, help="path for learned defaults .lp")
    parser.add_argument("--klingo", default="./klingo", help="path to klingo executable")
    args = parser.parse_args()

    cmd = [
        args.klingo,
        "--bnm",
        "--mode",
        "brave",
        "--clingo-output",
        "-k",
        str(args.k),
        args.input,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        sys.stderr.write(proc.stderr)
        sys.exit(proc.returncode)

    atoms = parse_atoms_from_bnm_output(proc.stdout)
    rules = to_default_rules(atoms)

    header = [
        "% learned defaults from bnm brave consequences",
        f"% source: {args.input}",
        f"% depth: {args.k}",
    ]
    with open(args.output, "w", encoding="utf-8") as handle:
        for line in header:
            handle.write(line + "\n")
        for rule in rules:
            handle.write(rule + "\n")

    print(f"wrote {len(rules)} defaults to {args.output}")


if __name__ == "__main__":
    main()
