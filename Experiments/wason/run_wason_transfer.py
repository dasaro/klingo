#!/usr/bin/env python3
import argparse
import json
import re
import subprocess
from pathlib import Path


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)


def learn_defaults(klingo, train_path, k, out_path):
    cmd = [klingo, "--bnm", "--mode", "brave", "--clingo-output", "-k", str(k), train_path]
    res = run(cmd)
    if res.returncode != 0:
        raise RuntimeError(res.stderr or res.stdout)
    atoms = []
    lines = [line.rstrip() for line in res.stdout.splitlines()]
    for i, line in enumerate(lines):
        if line.startswith("Answer:"):
            for j in range(i + 1, len(lines)):
                if lines[j].strip() != "":
                    atoms = [tok for tok in lines[j].split() if not tok.startswith("?")]
                    break
    rules = []
    for atom in atoms:
        if atom.startswith("-"):
            base = atom[1:]
            rules.append(f"-{base} :- not {base}.")
        else:
            rules.append(f"{atom} :- not -{atom}.")
    header = [
        "% learned defaults",
        f"% source: {train_path}",
        f"% depth: {k}",
    ]
    Path(out_path).write_text("\n".join(header + rules) + "\n")


def parse_cards(path):
    cards = []
    pattern = re.compile(r"^card\(([a-z0-9_]+),")
    for line in Path(path).read_text().splitlines():
        line = line.strip()
        match = pattern.match(line)
        if match:
            cards.append(match.group(1).strip())
    return cards


def parse_klingo_values(output):
    values = {}
    tags = {}
    for line in output.splitlines():
        line = line.strip()
        if line.startswith("V(") and ") =" in line:
            inner = line[2:].split(") =", 1)[0]
            atom = inner.strip()
            tag = None
            for prefix, name in (("[b]", "bnm"), ("[h]", "heur"), ("[c]", "confirm"), ("[d]", "disconfirm")):
                if atom.startswith(prefix):
                    atom = atom[len(prefix):]
                    tag = name
                    break
            value = line.split("=", 1)[1].strip()
            values[atom] = value
            if tag:
                tags[atom] = tag
    return values, tags


def run_klingo(klingo, program, heuristics, k):
    cmd = [klingo, "--bnm", "--no-clingo-output", "--color", "never", "-k", str(k), program]
    for h in heuristics:
        cmd.extend(["--heuristics", h])
    res = run(cmd)
    if res.returncode != 0:
        raise RuntimeError(res.stderr or res.stdout)
    return parse_klingo_values(res.stdout)


def run_clingo_truth(program, atoms, mode):
    cmd = ["clingo", program, "-n", "0", "--outf=2"]
    if mode in {"brave", "cautious"}:
        cmd.extend(["--enum-mode", mode])
    res = run(cmd)
    if res.returncode not in {0, 10, 20, 30}:
        raise RuntimeError(res.stderr or res.stdout)
    data = json.loads(res.stdout)
    models = data.get("Call", [])[0].get("Witnesses", [])
    if not models:
        return []
    if mode in {"brave", "cautious"}:
        true_atoms = set(models[0].get("Value", []))
        truth = {atom: ("1" if atom in true_atoms else "0") for atom in atoms}
        return [truth]
    truths = []
    for model in models:
        true_atoms = set(model.get("Value", []))
        truth = {atom: ("1" if atom in true_atoms else "0") for atom in atoms}
        truths.append(truth)
    return truths


def accuracy(values, truth, atoms):
    correct = 0
    for atom in atoms:
        val = values.get(atom, "?")
        if val in {"0", "1"} and truth.get(atom) == val:
            correct += 1
    return correct / max(1, len(atoms))


def main():
    parser = argparse.ArgumentParser(description="Run Wason heuristic transfer experiment.")
    parser.add_argument("--klingo", default="./klingo")
    parser.add_argument("--train", default="Experiments/wason/train.lp")
    parser.add_argument("--tests", nargs="+", default=[
        "Experiments/wason/test_same.lp",
        "Experiments/wason/test1.lp",
        "Experiments/wason/test2.lp",
        "Experiments/wason/test3.lp",
    ])
    parser.add_argument("--k-train", type=int, default=2)
    parser.add_argument("--k-test", type=int, default=0, help="single k for test runs")
    parser.add_argument("--k-tests", type=int, nargs="*", default=[0, 1, 2], help="list of k values to evaluate")
    parser.add_argument("--k-confirm", type=int, default=2)
    parser.add_argument("--out", default="Experiments/wason/learned.lp")
    args = parser.parse_args()

    learn_defaults(args.klingo, args.train, args.k_train, args.out)

    for test in args.tests:
        cards = parse_cards(test)
        atoms = [f"flip({c})" for c in cards] + ["ok_rule"]
        truths_brave = run_clingo_truth(test, atoms, "brave")
        truths_cautious = run_clingo_truth(test, atoms, "cautious")
        truths_all = run_clingo_truth(test, atoms, "all")

        results = []
        for k_val in args.k_tests:
            base_vals, _base_tags = run_klingo(args.klingo, test, [], k_val)
            learned_vals, _learned_tags = run_klingo(args.klingo, test, [args.out], k_val)

            acc_base_brave = accuracy(base_vals, truths_brave[0], atoms) if truths_brave else 0.0
            acc_learned_brave = accuracy(learned_vals, truths_brave[0], atoms) if truths_brave else 0.0
            acc_base_caut = accuracy(base_vals, truths_cautious[0], atoms) if truths_cautious else 0.0
            acc_learned_caut = accuracy(learned_vals, truths_cautious[0], atoms) if truths_cautious else 0.0

            acc_base_all = 0.0
            acc_learned_all = 0.0
            if truths_all:
                acc_base_all = max(accuracy(base_vals, t, atoms) for t in truths_all)
                acc_learned_all = max(accuracy(learned_vals, t, atoms) for t in truths_all)
            results.append((k_val, acc_base_brave, acc_learned_brave, acc_base_caut, acc_learned_caut, acc_base_all, acc_learned_all))

        confirm_vals, confirm_tags = run_klingo(args.klingo, test, [args.out], args.k_confirm)
        confirm = sum(1 for a in atoms if confirm_tags.get(a) == "confirm")
        disconfirm = sum(1 for a in atoms if confirm_tags.get(a) == "disconfirm")

        print(f"{Path(test).name}:")
        for k_val, acc_base_brave, acc_learned_brave, acc_base_caut, acc_learned_caut, acc_base_all, acc_learned_all in results:
            print(f"  brave acc k={k_val} (no heur): {acc_base_brave:.2f}")
            print(f"  brave acc k={k_val} (heur):    {acc_learned_brave:.2f}")
            print(f"  cautious acc k={k_val} (no heur): {acc_base_caut:.2f}")
            print(f"  cautious acc k={k_val} (heur):    {acc_learned_caut:.2f}")
            print(f"  -n 0 max acc k={k_val} (no heur): {acc_base_all:.2f}")
            print(f"  -n 0 max acc k={k_val} (heur):    {acc_learned_all:.2f}")
        print(f"  confirmed at k={args.k_confirm}: {confirm}/{len(atoms)}")
        print(f"  disconfirmed at k={args.k_confirm}: {disconfirm}/{len(atoms)}")


if __name__ == "__main__":
    main()
