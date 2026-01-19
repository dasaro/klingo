#!/usr/bin/env python3

import argparse
import re
import subprocess
from collections import defaultdict

PAT = re.compile(r"sudoku\((\d+),(\d+),(\d+)\)")


def run_klingo(args):
    cmd = ["python3", "klingo", "-k", str(args.depth), "--clingo-output"]
    if args.mode:
        cmd += ["--mode", args.mode]
    if args.max_valuations is not None:
        cmd += ["--max-valuations", str(args.max_valuations)]
    cmd += [args.file]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return proc.stdout


def extract_atoms(output, mode):
    if mode in {"brave", "cautious"}:
        key = "Brave consequences" if mode == "brave" else "Cautious consequences"
        capture = False
        for line in output.splitlines():
            if line.startswith(key):
                capture = True
                continue
            if capture:
                line = line.strip()
                if not line:
                    continue
                if line == "(none)":
                    return []
                return line.split()
        return []

    lines = [line.strip() for line in output.splitlines() if line.strip()]
    for i, line in enumerate(lines):
        if line.startswith("Valuation "):
            if i + 1 < len(lines):
                return lines[i + 1].split()
    return []


def atoms_to_grid(atoms, size):
    grid = defaultdict(lambda: ".")
    for atom in atoms:
        if atom.startswith("?"):
            continue
        m = PAT.fullmatch(atom)
        if not m:
            continue
        r, c, n = map(int, m.groups())
        grid[(r, c)] = str(n)
    return grid


def print_grid(grid, size, box):
    horiz = "+" + "+".join(["-" * (box * 2 + 1)] * (size // box)) + "+"
    print(horiz)
    for r in range(1, size + 1):
        row_cells = []
        for c in range(1, size + 1):
            row_cells.append(grid[(r, c)])
        chunks = [" ".join(row_cells[i:i + box]) for i in range(0, size, box)]
        print("| " + " | ".join(chunks) + " |")
        if r % box == 0:
            print(horiz)


def main():
    parser = argparse.ArgumentParser(description="Pretty-print Sudoku valuations from klingo output.")
    parser.add_argument("file", help="path to sudoku .lp file")
    parser.add_argument("-k", "--depth", type=int, default=0, help="k-depth for klingo")
    parser.add_argument(
        "--mode",
        choices=["all", "brave", "cautious"],
        default="all",
        help="which result set to render",
    )
    parser.add_argument(
        "--max-valuations",
        type=int,
        default=1,
        help="limit valuations (ignored for brave/cautious)",
    )
    parser.add_argument("--size", type=int, default=9, help="grid size (default: 9)")
    parser.add_argument("--box", type=int, default=3, help="box size (default: 3)")
    args = parser.parse_args()

    output = run_klingo(args)
    atoms = extract_atoms(output, args.mode)
    grid = atoms_to_grid(atoms, args.size)
    print_grid(grid, args.size, args.box)


if __name__ == "__main__":
    main()
