#!/usr/bin/env python3
import json
import subprocess
from pathlib import Path


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)


def clingo_truth(program, atoms):
    res = run(["clingo", program, "-n", "0", "--outf=2"])
    if res.returncode not in {0, 10, 20, 30}:
        raise RuntimeError(res.stderr or res.stdout)
    data = json.loads(res.stdout)
    models = data.get("Call", [])[0].get("Witnesses", [])
    truths = []
    for model in models:
        true_atoms = set(model.get("Value", []))
        truth = {atom: ("1" if atom in true_atoms else "0") for atom in atoms}
        truths.append(truth)
    return truths


def run_klingo(program, heuristics=None, k=0):
    cmd = ["./klingo", "--bnm", "--no-clingo-output", "--color", "never", "-n", "1", "-k", str(k), program]
    for h in heuristics or []:
        cmd.extend(["--heuristics", h])
    res = run(cmd)
    if res.returncode != 0:
        raise RuntimeError(res.stderr or res.stdout)
    vals = {}
    for line in res.stdout.splitlines():
        line = line.strip()
        if line.startswith("V(") and ") =" in line:
            atom = line[2:].split(") =", 1)[0].strip()
            for prefix in ("[b]", "[h]", "[c]", "[d]"):
                if atom.startswith(prefix):
                    atom = atom[len(prefix):]
                    break
            value = line.split("=", 1)[1].strip()
            vals[atom] = value
    return vals


def accuracy(values, truths, atoms):
    if not truths:
        return 0.0
    return max(
        sum(1 for a in atoms if values.get(a, "?") in {"0", "1"} and t.get(a) == values.get(a)) / len(atoms)
        for t in truths
    )


def main():
    learned = "Experiments/wason/rule_level/learned.lp"
    train = "Experiments/wason/rule_level/train.lp"
    res = run(["python3", "Experiments/wason/rule_level/learn_rules.py", "--train", train, "--out", learned])
    if res.returncode != 0:
        raise RuntimeError(res.stderr or res.stdout)

    for name in ["test_a", "test_b"]:
        program = f"Experiments/wason/rule_level/{name}.lp"
        if name == "test_a":
            base_atoms = ["flip(d1)", "flip(d2)", "flip(d3)", "flip(d4)"]
        else:
            base_atoms = ["flip(e1)", "flip(e2)", "flip(e3)", "flip(e4)"]
        atoms = base_atoms + [f"-{a}" for a in base_atoms]
        truths = clingo_truth(program, atoms)
        base_vals = run_klingo(program, k=0)
        heur_vals = run_klingo(program, heuristics=[learned], k=0)
        acc_base = accuracy(base_vals, truths, atoms)
        acc_heur = accuracy(heur_vals, truths, atoms)
        decided_base = sum(1 for a in atoms if base_vals.get(a, "?") in {"0", "1"})
        decided_heur = sum(1 for a in atoms if heur_vals.get(a, "?") in {"0", "1"})
        print(f"{name}:")
        print(f"  max acc k=0 (no heur): {acc_base:.2f}  decided={decided_base}/{len(atoms)}")
        print(f"  max acc k=0 (heur):    {acc_heur:.2f}  decided={decided_heur}/{len(atoms)}")


if __name__ == "__main__":
    main()
