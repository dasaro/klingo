#!/usr/bin/env python3
import argparse
import json
import subprocess
from pathlib import Path


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)


def clingo_models(program):
    cmd = ["clingo", program, "-n", "0", "--outf=2"]
    res = run(cmd)
    if res.returncode not in {0, 10, 20, 30}:
        raise RuntimeError(res.stderr or res.stdout)
    data = json.loads(res.stdout)
    models = data.get("Call", [])[0].get("Witnesses", [])
    return [set(m.get("Value", [])) for m in models]


def cautious_and_negative(models, atoms):
    if not models:
        return set(), set()
    true_all = set.intersection(*models)
    false_all = set(atoms) - set.union(*models)
    return true_all, false_all


def extract_unary_constants(program, predicate):
    consts = set()
    prefix = f"{predicate}("
    for line in Path(program).read_text().splitlines():
        line = line.strip()
        if line.startswith("%"):
            continue
        # handle multiple facts on one line
        for segment in line.split("."):
            segment = segment.strip()
            if not segment or ":-" in segment:
                continue
            if segment.startswith(prefix) and segment.endswith(")"):
                body = segment[len(prefix) : -1]
                if body and body.replace("_", "").isalnum() and body[0].islower():
                    consts.add(body)
    return consts


def build_atom_universe(program, predicate):
    # Prefer card/1 domain if present.
    consts = extract_unary_constants(program, "card")
    if not consts:
        # fall back to any unary facts for colors
        for pred in ("red", "blue"):
            consts |= extract_unary_constants(program, pred)
    if not consts:
        return set()
    return {f"{predicate}({c})" for c in consts}


def extract_background_facts(program):
    facts = []
    for line in Path(program).read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("%") or line.startswith("#"):
            continue
        for segment in line.split("."):
            segment = segment.strip()
            if not segment or ":-" in segment:
                continue
            facts.append(segment + ".")
    return facts


def main():
    parser = argparse.ArgumentParser(description="Generate ILASP examples from k‑lingo high‑k consequences.")
    parser.add_argument("--program", required=True)
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--out", required=True)
    parser.add_argument("--klingo", default="./klingo")
    parser.add_argument("--predicate", default="flip")
    args = parser.parse_args()

    # Use clingo to enumerate full models as ground truth at high depth.
    models = clingo_models(args.program)

    # Build atom universe for the target predicate (use card domain if possible).
    atoms = build_atom_universe(args.program, args.predicate)
    if not atoms:
        # fall back to atoms observed in models
        atoms = {a for m in models for a in m if a.startswith(f"{args.predicate}(")}

    pos, neg = cautious_and_negative(models, atoms)
    pred_prefix = f"{args.predicate}("
    pos = {a for a in pos if a.startswith(pred_prefix)}
    neg = {a for a in neg if a.startswith(pred_prefix)}
    if not neg:
        neg = {f"-{a}" for a in pos}

    lines = [
        "#modeh(flip(var(c))).",
        "#modeb(red(var(c))).",
        "#modeb(blue(var(c))).",
        "#modeb(card(var(c))).",
        "#maxv(1).",
    ]
    lines.extend(extract_background_facts(args.program))
    idx = 1
    for atom in sorted(pos):
        lines.append(f"#pos(p{idx}, {{{atom}}}, {{}}).")
        idx += 1
    for atom in sorted(neg):
        lines.append(f"#neg(n{idx}, {{{atom}}}, {{}}).")
        idx += 1

    Path(args.out).write_text("\n".join(lines) + "\n")
    print(f"wrote {len(lines)} examples to {args.out}")


if __name__ == "__main__":
    main()
