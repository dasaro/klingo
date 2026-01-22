#!/usr/bin/env python3
import json
import subprocess
from pathlib import Path


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)


def run_clingo_all_models(program, atoms):
    cmd = ["clingo", program, "-n", "0", "--outf=2"]
    res = run(cmd)
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


def run_klingo(klingo, program, k, heuristics=None):
    cmd = [klingo, "--bnm", "--no-clingo-output", "--color", "never", "--restart-strategy", "none", "-n", "1", "-k", str(k), program]
    for h in heuristics or []:
        cmd.extend(["--heuristics", h])
    res = run(cmd)
    if res.returncode != 0:
        raise RuntimeError(res.stderr or res.stdout)
    values = {}
    for line in res.stdout.splitlines():
        line = line.strip()
        if line.startswith("V(") and ") =" in line:
            atom = line[2:].split(") =", 1)[0].strip()
            for prefix in ("[b]", "[h]", "[c]", "[d]"):
                if atom.startswith(prefix):
                    atom = atom[len(prefix):]
                    break
            value = line.split("=", 1)[1].strip()
            values[atom] = value
    return values


def accuracy(values, truth, atoms):
    correct = 0
    for atom in atoms:
        val = values.get(atom, "?")
        if val in {"0", "1"} and truth.get(atom) == val:
            correct += 1
    return correct / max(1, len(atoms))


def learn_defaults(klingo, program, out_path):
    learn_cmd = [klingo, "--bnm", "--mode", "all", "-n", "1", "--no-clingo-output", "--color", "never", "-k", "15", program]
    res = run(learn_cmd)
    if res.returncode != 0:
        raise RuntimeError(res.stderr or res.stdout)
    learned_atoms = []
    for line in res.stdout.splitlines():
        line = line.strip()
        if line.startswith("V(") and ") =" in line:
            atom = line[2:].split(") =", 1)[0].strip()
            for prefix in ("[b]", "[h]", "[c]", "[d]"):
                if atom.startswith(prefix):
                    atom = atom[len(prefix):]
                    break
            value = line.split("=", 1)[1].strip()
            if value == "1":
                learned_atoms.append(atom)
    rules = []
    for atom in learned_atoms:
        if atom.startswith("-"):
            base = atom[1:]
            rules.append(f"-{base} :- not {base}.")
        else:
            rules.append(f"{atom} :- not -{atom}.")
    header = [
        "% learned defaults",
        f"% source: {program}",
        "% depth: 15",
    ]
    Path(out_path).write_text("\n".join(header + rules) + "\n")


def run_case(label, program, heuristics):
    atoms = [f"t({i})" for i in range(1, 13)]
    truths = run_clingo_all_models(program, atoms)
    k_values = [0, 1, 2, 5, 10, 15]
    print(f"{label}:")
    for k in k_values:
        vals = run_klingo("./klingo", program, k)
        vals_heur = run_klingo("./klingo", program, k, heuristics)
        max_acc = max(accuracy(vals, t, atoms) for t in truths) if truths else 0.0
        max_acc_heur = max(accuracy(vals_heur, t, atoms) for t in truths) if truths else 0.0
        decided = sum(1 for a in atoms if vals.get(a, "?") in {"0", "1"})
        decided_heur = sum(1 for a in atoms if vals_heur.get(a, "?") in {"0", "1"})
        print(f"  k={k:2d}  max_acc={max_acc:.2f}  max_acc_heur={max_acc_heur:.2f}  decided={decided}/{len(atoms)}  decided_heur={decided_heur}/{len(atoms)}")


def main():
    train = "Experiments/wason/depth_curve/train.lp"
    learned = "Experiments/wason/depth_curve/learned.lp"
    learn_defaults("./klingo", train, learned)

    run_case("test_a (same mapping)", "Experiments/wason/depth_curve/test_a.lp", [learned])
    run_case("test_b (exclusive mapping)", "Experiments/wason/depth_curve/test_b.lp", [learned])
    run_case("test_c (missing mapping)", "Experiments/wason/depth_curve/test_c.lp", [learned])


if __name__ == "__main__":
    main()
