#!/usr/bin/env python3

import argparse
import re
import sys
from collections import defaultdict

PAT = re.compile(r"sudoku\((\d+),(\d+),(\d+)\)")


def extract_atoms(text):
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for key in ("Brave consequences", "Cautious consequences"):
        for i, line in enumerate(lines):
            if line.startswith(key) and i + 1 < len(lines):
                atoms_line = lines[i + 1].strip()
                if atoms_line == "(none)":
                    return []
                return atoms_line.split()

    for i, line in enumerate(lines):
        if (line.startswith("Answer:") or line.startswith("Valuation ")) and i + 1 < len(lines):
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
    parser = argparse.ArgumentParser(
        description="Pretty-print Sudoku valuations from klingo output on stdin."
    )
    parser.add_argument("--size", type=int, default=9, help="grid size (default: 9)")
    parser.add_argument("--box", type=int, default=3, help="box size (default: 3)")
    args = parser.parse_args()

    data = sys.stdin.read()
    atoms = extract_atoms(data)
    grid = atoms_to_grid(atoms, args.size)
    print_grid(grid, args.size, args.box)


if __name__ == "__main__":
    main()
