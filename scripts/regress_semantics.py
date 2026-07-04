#!/usr/bin/env python3

import argparse
import csv
import difflib
import hashlib
import re
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
KLINGO_ENTRYPOINT = ROOT / "klingo"
GOLDEN_DIR = ROOT / "tests" / "golden"
TOTALITY_FIXTURE = GOLDEN_DIR / "totality_bnm_totality.lp"
TOTALITY_FORMAL_3ND_FIXTURE = GOLDEN_DIR / "totality_3nd_formal_resolution.lp"
DEFAULT_PERF_DIR = ROOT / "tests" / "perf"
CORE_GUARD_PATHS = [
    ROOT / "klingo",
    ROOT / "klingo_engine.py",
    ROOT / "klingo_semantics.py",
    ROOT / "klingo_output.py",
]

CALLS_RE = re.compile(r"^Calls\s*:\s*(\d+)$", flags=re.M)
MODELS_RE = re.compile(r"^Models\s*:\s*(\d+)\+?$", flags=re.M)
TIME_RE = re.compile(r"^Time\s*:\s*([0-9.]+)s$", flags=re.M)
CPU_TIME_RE = re.compile(r"^CPU Time\s*:\s*([0-9.]+)s$", flags=re.M)
BNM_SHOWN_RE = re.compile(r"\[b\][^\s]+")
VALUATION_RE = re.compile(r"^Valuation\s+\d+\s+\(", flags=re.M)
BNM_DETAIL_RE = re.compile(r"^V\(\[b\]([^)]+)\)\s*=\s*([01?])$", flags=re.M)
UNDEF_RE = re.compile(r"^V\([^)]+\)\s*=\s*\?$", flags=re.M)


@dataclass(frozen=True)
class GoldenCase:
    name: str
    args: list[str]
    golden_path: Path


@dataclass(frozen=True)
class OracleCase:
    name: str
    klingo_args: list[str]
    clingo_args: list[str]


@dataclass(frozen=True)
class PerfCase:
    name: str
    solver_args: list[str]
    file: str
    k_values: list[int]
    timeout_s: float
    collect_bnm_details: bool = False


GOLDEN_CASES = [
    GoldenCase(
        name="3nd_star_enum_all_k2",
        args=["--3nd-star", "-k", "2", "--mode", "all", "-n", "0", "Examples/kernel/enum_modes.lp"],
        golden_path=GOLDEN_DIR / "3nd_star_enum_all_k2.out",
    ),
    GoldenCase(
        name="3nd_star_enum_brave_k2",
        args=["--3nd-star", "-k", "2", "--mode", "brave", "-n", "0", "Examples/kernel/enum_modes.lp"],
        golden_path=GOLDEN_DIR / "3nd_star_enum_brave_k2.out",
    ),
    GoldenCase(
        name="3nd_star_enum_cautious_k2",
        args=["--3nd-star", "-k", "2", "--mode", "cautious", "-n", "0", "Examples/kernel/enum_modes.lp"],
        golden_path=GOLDEN_DIR / "3nd_star_enum_cautious_k2.out",
    ),
    GoldenCase(
        name="3nd_star_unsat_k0",
        args=["--3nd-star", "-k", "0", "Examples/kernel/unsat.lp"],
        golden_path=GOLDEN_DIR / "3nd_star_unsat_k0.out",
    ),
    GoldenCase(
        name="3nd_brave_totality_k2",
        args=["--3nd", "-k", "2", "--mode", "brave", "-n", "0", "Examples/kernel/bnm_totality.lp"],
        golden_path=GOLDEN_DIR / "3nd_brave_totality_k2.out",
    ),
    GoldenCase(
        name="3nd_formal_resolution_cautious_k0",
        args=["--3nd", "-k", "0", "--mode", "cautious", "-n", "0", "Examples/kernel/3nd_formal_resolution.lp"],
        golden_path=GOLDEN_DIR / "3nd_formal_resolution_cautious_k0.out",
    ),
    GoldenCase(
        name="3nd_formal_resolution_cautious_k1",
        args=["--3nd", "-k", "1", "--mode", "cautious", "-n", "0", "Examples/kernel/3nd_formal_resolution.lp"],
        golden_path=GOLDEN_DIR / "3nd_formal_resolution_cautious_k1.out",
    ),
    GoldenCase(
        name="bnm_children_flip_k0",
        args=["--bnm", "-k", "0", "--mode", "all", "-n", "1", "Examples/kernel/bnm_children_flip.lp"],
        golden_path=GOLDEN_DIR / "bnm_children_flip_k0.out",
    ),
    GoldenCase(
        name="bnm_children_flip_k1",
        args=["--bnm", "-k", "1", "--mode", "all", "-n", "1", "Examples/kernel/bnm_children_flip.lp"],
        golden_path=GOLDEN_DIR / "bnm_children_flip_k1.out",
    ),
]


ORACLE_CASES = [
    OracleCase(
        name="3nd_star_vs_clingo_brave_convergence",
        klingo_args=["--3nd-star", "-k", "2", "--mode", "brave", "-n", "0", "Examples/kernel/asp_convergence.lp"],
        clingo_args=["Examples/kernel/asp_convergence.lp", "-n", "0", "--enum-mode=brave"],
    ),
    OracleCase(
        name="3nd_vs_clingo_totality_brave",
        klingo_args=["--3nd", "-k", "2", "--mode", "brave", "-n", "0", "Examples/kernel/bnm_totality.lp"],
        clingo_args=[
            "Examples/kernel/bnm_totality.lp",
            str(TOTALITY_FIXTURE.relative_to(ROOT)),
            "-n",
            "0",
            "--enum-mode=brave",
        ],
    ),
    OracleCase(
        name="3nd_vs_clingo_totality_cautious",
        klingo_args=["--3nd", "-k", "2", "--mode", "cautious", "-n", "0", "Examples/kernel/bnm_totality.lp"],
        clingo_args=[
            "Examples/kernel/bnm_totality.lp",
            str(TOTALITY_FIXTURE.relative_to(ROOT)),
            "-n",
            "0",
            "--enum-mode=cautious",
        ],
    ),
    OracleCase(
        name="3nd_vs_clingo_formal_resolution_cautious",
        klingo_args=["--3nd", "-k", "2", "--mode", "cautious", "-n", "0", "Examples/kernel/3nd_formal_resolution.lp"],
        clingo_args=[
            "Examples/kernel/3nd_formal_resolution.lp",
            str(TOTALITY_FORMAL_3ND_FIXTURE.relative_to(ROOT)),
            "-n",
            "0",
            "--enum-mode=cautious",
        ],
    ),
]


PERF_CASES = [
    PerfCase(
        name="3nd_star_enum_modes",
        solver_args=["--3nd-star", "--mode", "all", "-n", "0"],
        file="Examples/kernel/enum_modes.lp",
        k_values=[0, 1, 2, 3, 4],
        timeout_s=8.0,
    ),
    PerfCase(
        name="3nd_star_asp_convergence",
        solver_args=["--3nd-star", "--mode", "all", "-n", "0"],
        file="Examples/kernel/asp_convergence.lp",
        k_values=[0, 1, 2, 3, 4],
        timeout_s=8.0,
    ),
    PerfCase(
        name="3nd_totality",
        solver_args=["--3nd", "--mode", "all", "-n", "0"],
        file="Examples/kernel/bnm_totality.lp",
        k_values=[0, 1, 2, 3, 4],
        timeout_s=8.0,
    ),
    PerfCase(
        name="bnm_children_flip",
        solver_args=["--bnm", "--mode", "all", "-n", "1"],
        file="Examples/kernel/bnm_children_flip.lp",
        k_values=[0, 1, 2, 3, 4],
        timeout_s=8.0,
        collect_bnm_details=True,
    ),
    PerfCase(
        name="bnm_totality",
        solver_args=["--bnm", "--mode", "all", "-n", "0"],
        file="Examples/kernel/bnm_totality.lp",
        k_values=[0, 1, 2, 3, 4],
        timeout_s=8.0,
        collect_bnm_details=True,
    ),
]


PERF_FIELDNAMES = [
    "case",
    "k",
    "repeat",
    "status",
    "returncode",
    "timeout_s",
    "wall_s",
    "reported_time_s",
    "cpu_time_s",
    "calls",
    "restarts",
    "models",
    "bnm_shown_true_atoms",
    "nonmon_assumptions",
    "bnm_tagged_assignments",
    "bnm_tagged_unique_atoms",
    "bnm_tagged_true",
    "bnm_tagged_false",
    "bnm_tagged_undef",
    "valuations_detail",
    "undefined_assignments",
    "cmd",
    "detail_cmd",
    "stderr_tail",
    "detail_status",
    "detail_stderr_tail",
]


def run_command(cmd: list[str], cwd: Path) -> tuple[int, str, str]:
    proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    return proc.returncode, proc.stdout, proc.stderr


def run_command_timed(cmd: list[str], cwd: Path, timeout_s: float) -> dict:
    start = time.perf_counter()
    try:
        proc = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
    except subprocess.TimeoutExpired as exc:
        wall_s = time.perf_counter() - start
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""
        return {
            "timeout": True,
            "returncode": None,
            "stdout": stdout,
            "stderr": stderr,
            "wall_s": wall_s,
        }

    wall_s = time.perf_counter() - start
    return {
        "timeout": False,
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "wall_s": wall_s,
    }


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def snapshot_core_hashes() -> dict[str, str]:
    snapshot: dict[str, str] = {}
    for path in CORE_GUARD_PATHS:
        if path.exists():
            snapshot[str(path.relative_to(ROOT))] = _file_sha256(path)
    return snapshot


def diff_core_hashes(before: dict[str, str], after: dict[str, str]) -> list[str]:
    changed: list[str] = []
    keys = sorted(set(before.keys()) | set(after.keys()))
    for key in keys:
        if before.get(key) != after.get(key):
            changed.append(key)
    return changed


def normalize_output(text: str) -> str:
    out_lines = []
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        if line.startswith("klingo version "):
            line = "klingo version <VERSION>"
        line = re.sub(r"^Answer: \(Time: [0-9.]+s\)$", "Answer: (Time: <TIME>)", line)
        line = re.sub(r"^Time\s*:\s*[0-9.]+s$", "Time         : <TIME>", line)
        line = re.sub(r"^CPU Time\s*:\s*[0-9.]+s$", "CPU Time     : <TIME>", line)
        out_lines.append(line)
    normalized = "\n".join(out_lines).strip()
    return normalized + "\n"


def format_diff(expected: str, actual: str, fromfile: str, tofile: str) -> str:
    diff = difflib.unified_diff(
        expected.splitlines(keepends=True),
        actual.splitlines(keepends=True),
        fromfile=fromfile,
        tofile=tofile,
    )
    return "".join(diff)


def extract_final_answer_atoms(output: str) -> set[str]:
    lines = [line.strip() for line in output.splitlines()]
    answer_indices = [idx for idx, line in enumerate(lines) if line.startswith("Answer:")]
    if not answer_indices:
        return set()
    idx = answer_indices[-1] + 1
    while idx < len(lines) and lines[idx] == "":
        idx += 1
    if idx >= len(lines):
        return set()
    payload = lines[idx]
    if (
        not payload
        or payload.startswith("Consequences")
        or payload.startswith("Models")
        or payload.startswith("Calls")
        or payload.startswith("Time")
        or payload.startswith("CPU Time")
        or payload.startswith("SATISFIABLE")
        or payload.startswith("UNSATISFIABLE")
    ):
        return set()
    return set(payload.split())


def extract_summary_consequences(output: str) -> int | None:
    matches = re.findall(r"^Consequences\s*:\s*(\d+)$", output, flags=re.M)
    if not matches:
        return None
    return int(matches[-1])


def ensure_fixtures() -> None:
    GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
    if not TOTALITY_FIXTURE.exists():
        TOTALITY_FIXTURE.write_text(
            "1 { p(a); -p(a) } 1.\n1 { p(b); -p(b) } 1.\n",
            encoding="utf-8",
        )
    if not TOTALITY_FORMAL_3ND_FIXTURE.exists():
        TOTALITY_FORMAL_3ND_FIXTURE.write_text(
            "1 { a; -a } 1.\n1 { b; -b } 1.\n",
            encoding="utf-8",
        )


def parse_last_int(pattern: re.Pattern, text: str) -> int | None:
    matches = pattern.findall(text)
    if not matches:
        return None
    return int(matches[-1])


def parse_last_float(pattern: re.Pattern, text: str) -> float | None:
    matches = pattern.findall(text)
    if not matches:
        return None
    return float(matches[-1])


def parse_primary_perf_metrics(output: str) -> dict:
    calls = parse_last_int(CALLS_RE, output)
    restarts = max(calls - 1, 0) if calls is not None else None
    models = parse_last_int(MODELS_RE, output)
    # The Legend footer contains a literal "[b]atom" token that must not be
    # counted as a shown BNM atom.
    answer_text = "\n".join(line for line in output.splitlines() if not line.startswith("Legend:"))
    return {
        "reported_time_s": parse_last_float(TIME_RE, output),
        "cpu_time_s": parse_last_float(CPU_TIME_RE, output),
        "calls": calls,
        "restarts": restarts,
        "models": models,
        "bnm_shown_true_atoms": len(BNM_SHOWN_RE.findall(answer_text)),
    }


def parse_detail_perf_metrics(output: str) -> dict:
    tagged = BNM_DETAIL_RE.findall(output)
    unique_atoms = {atom for atom, _value in tagged}
    tagged_true = sum(1 for _atom, value in tagged if value == "1")
    tagged_false = sum(1 for _atom, value in tagged if value == "0")
    tagged_undef = sum(1 for _atom, value in tagged if value == "?")
    return {
        "bnm_tagged_assignments": len(tagged),
        "bnm_tagged_unique_atoms": len(unique_atoms),
        "bnm_tagged_true": tagged_true,
        "bnm_tagged_false": tagged_false,
        "bnm_tagged_undef": tagged_undef,
        "valuations_detail": len(VALUATION_RE.findall(output)),
        "undefined_assignments": len(UNDEF_RE.findall(output)),
    }


def init_perf_row(case: PerfCase, k: int, repeat: int, timeout_s: float, cmd: list[str]) -> dict:
    return {
        "case": case.name,
        "k": k,
        "repeat": repeat,
        "status": "ok",
        "returncode": 0,
        "timeout_s": timeout_s,
        "wall_s": None,
        "reported_time_s": None,
        "cpu_time_s": None,
        "calls": None,
        "restarts": None,
        "models": None,
        "bnm_shown_true_atoms": 0,
        "nonmon_assumptions": 0,
        "bnm_tagged_assignments": 0,
        "bnm_tagged_unique_atoms": 0,
        "bnm_tagged_true": 0,
        "bnm_tagged_false": 0,
        "bnm_tagged_undef": 0,
        "valuations_detail": 0,
        "undefined_assignments": 0,
        "cmd": " ".join(cmd),
        "detail_cmd": "",
        "stderr_tail": "",
        "detail_status": "n/a",
        "detail_stderr_tail": "",
    }


def write_perf_csv(rows: list[dict], out_csv: Path) -> None:
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=PERF_FIELDNAMES)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def avg_of(rows: list[dict], key: str) -> float:
    vals = [float(row[key]) for row in rows if row.get(key) is not None]
    if not vals:
        return 0.0
    return sum(vals) / len(vals)


def max_of(rows: list[dict], key: str) -> float:
    vals = [float(row[key]) for row in rows if row.get(key) is not None]
    if not vals:
        return 0.0
    return max(vals)


def write_perf_summary(rows: list[dict], out_dir: Path) -> None:
    by_case = {}
    for row in rows:
        by_case.setdefault(row["case"], []).append(row)

    lines = []
    lines.append("# Regression Performance Report")
    lines.append("")
    lines.append("Generated by `scripts/regress_semantics.py --perf`.")
    lines.append("")
    lines.append("| case | points | avg wall (s) | max wall (s) | avg calls | avg restarts | avg nonmon assumptions |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|")
    for case_name in sorted(by_case):
        ok_rows = [row for row in by_case[case_name] if row["status"] == "ok"]
        lines.append(
            "| `{}` | {} | {:.4f} | {:.4f} | {:.2f} | {:.2f} | {:.2f} |".format(
                case_name,
                len(by_case[case_name]),
                avg_of(ok_rows, "wall_s"),
                max_of(ok_rows, "wall_s"),
                avg_of(ok_rows, "calls"),
                avg_of(ok_rows, "restarts"),
                avg_of(ok_rows, "nonmon_assumptions"),
            )
        )
    lines.append("")
    for case_name in sorted(by_case):
        lines.append(f"## {case_name}")
        lines.append("")
        lines.append(f"![{case_name}]({case_name}.png)")
        lines.append("")
    (out_dir / "README.md").write_text("\n".join(lines), encoding="utf-8")


def _mean_per_k(case_rows: list[dict], key: str) -> tuple[list[int], list[float]]:
    grouped = {}
    for row in case_rows:
        if row["status"] != "ok":
            continue
        value = row.get(key)
        if value is None:
            continue
        grouped.setdefault(int(row["k"]), []).append(float(value))
    ks = sorted(grouped)
    ys = [sum(grouped[k]) / len(grouped[k]) for k in ks]
    return ks, ys


def plot_perf(rows: list[dict], out_dir: Path) -> None:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception as exc:
        raise RuntimeError(
            "matplotlib is required for --perf plots; install with "
            "`./.venv/bin/python -m pip install matplotlib`"
        ) from exc

    by_case = {}
    for row in rows:
        by_case.setdefault(row["case"], []).append(row)

    for case_name, case_rows in sorted(by_case.items()):
        fig, axes = plt.subplots(2, 2, figsize=(11, 7))
        fig.suptitle(f"{case_name}: performance metrics")

        k_wall, y_wall = _mean_per_k(case_rows, "wall_s")
        k_rep, y_rep = _mean_per_k(case_rows, "reported_time_s")
        if k_wall:
            axes[0, 0].plot(k_wall, y_wall, marker="o", label="wall_s")
        if k_rep:
            axes[0, 0].plot(k_rep, y_rep, marker="s", label="reported_time_s")
        axes[0, 0].set_title("Computation Time")
        axes[0, 0].set_xlabel("k")
        axes[0, 0].set_ylabel("seconds")
        axes[0, 0].grid(True, alpha=0.3)
        if k_wall or k_rep:
            axes[0, 0].legend()

        k_calls, y_calls = _mean_per_k(case_rows, "calls")
        k_restarts, y_restarts = _mean_per_k(case_rows, "restarts")
        if k_calls:
            axes[0, 1].plot(k_calls, y_calls, marker="o", label="calls")
        if k_restarts:
            axes[0, 1].plot(k_restarts, y_restarts, marker="s", label="restarts")
        axes[0, 1].set_title("Solver Iterations")
        axes[0, 1].set_xlabel("k")
        axes[0, 1].set_ylabel("count")
        axes[0, 1].grid(True, alpha=0.3)
        if k_calls or k_restarts:
            axes[0, 1].legend()

        k_nonmon, y_nonmon = _mean_per_k(case_rows, "nonmon_assumptions")
        k_unique, y_unique = _mean_per_k(case_rows, "bnm_tagged_unique_atoms")
        if k_nonmon:
            axes[1, 0].plot(k_nonmon, y_nonmon, marker="o", label="nonmon_assumptions")
        if k_unique:
            axes[1, 0].plot(k_unique, y_unique, marker="s", label="bnm_unique_atoms")
        axes[1, 0].set_title("Non-monotonic Assumptions")
        axes[1, 0].set_xlabel("k")
        axes[1, 0].set_ylabel("count")
        axes[1, 0].grid(True, alpha=0.3)
        if k_nonmon or k_unique:
            axes[1, 0].legend()

        k_models, y_models = _mean_per_k(case_rows, "models")
        k_undef, y_undef = _mean_per_k(case_rows, "undefined_assignments")
        if k_models:
            axes[1, 1].plot(k_models, y_models, marker="o", label="models")
        if k_undef:
            axes[1, 1].plot(k_undef, y_undef, marker="s", label="undefined_assignments")
        axes[1, 1].set_title("Model/Uncertainty")
        axes[1, 1].set_xlabel("k")
        axes[1, 1].set_ylabel("count")
        axes[1, 1].grid(True, alpha=0.3)
        if k_models or k_undef:
            axes[1, 1].legend()

        fig.tight_layout()
        fig.savefig(out_dir / f"{case_name}.png", dpi=160)
        plt.close(fig)


def run_golden_cases(python_bin: str, update: bool) -> tuple[int, int]:
    passed = 0
    failed = 0
    for case in GOLDEN_CASES:
        cmd = [python_bin, str(KLINGO_ENTRYPOINT)] + case.args
        return_code, stdout, stderr = run_command(cmd, ROOT)
        if return_code != 0:
            print(f"[FAIL] {case.name}: klingo returned {return_code}")
            if stderr.strip():
                print(stderr.strip())
            failed += 1
            continue

        actual = normalize_output(stdout)
        if update:
            case.golden_path.parent.mkdir(parents=True, exist_ok=True)
            case.golden_path.write_text(actual, encoding="utf-8")
            print(f"[UPDATED] {case.name} -> {case.golden_path}")
            passed += 1
            continue

        if not case.golden_path.exists():
            print(f"[FAIL] {case.name}: missing golden file {case.golden_path}")
            failed += 1
            continue

        expected = case.golden_path.read_text(encoding="utf-8")
        if expected != actual:
            print(f"[FAIL] {case.name}: output mismatch")
            print(
                format_diff(
                    expected,
                    actual,
                    fromfile=f"{case.golden_path}",
                    tofile=f"{case.name}.actual",
                )
            )
            failed += 1
            continue

        print(f"[PASS] {case.name}")
        passed += 1

    return passed, failed


def run_oracle_cases(python_bin: str, clingo_bin: str) -> tuple[int, int]:
    passed = 0
    failed = 0
    for case in ORACLE_CASES:
        klingo_cmd = [python_bin, str(KLINGO_ENTRYPOINT)] + case.klingo_args
        clingo_cmd = [clingo_bin] + case.clingo_args

        k_rc, k_out, k_err = run_command(klingo_cmd, ROOT)
        c_rc, c_out, c_err = run_command(clingo_cmd, ROOT)

        if k_rc != 0:
            print(f"[FAIL] {case.name}: klingo returned {k_rc}")
            if k_err.strip():
                print(k_err.strip())
            failed += 1
            continue
        if c_rc != 30:
            print(f"[FAIL] {case.name}: clingo returned {c_rc} (expected 30 on SAT)")
            if c_err.strip():
                print(c_err.strip())
            failed += 1
            continue

        k_atoms = extract_final_answer_atoms(k_out)
        c_atoms = extract_final_answer_atoms(c_out)
        k_cons = extract_summary_consequences(k_out)
        c_cons = extract_summary_consequences(c_out)

        if k_cons != c_cons or k_atoms != c_atoms:
            print(f"[FAIL] {case.name}: oracle mismatch")
            print(f"  klingo consequences={k_cons}, atoms={sorted(k_atoms)}")
            print(f"  clingo consequences={c_cons}, atoms={sorted(c_atoms)}")
            failed += 1
            continue

        print(f"[PASS] {case.name}")
        passed += 1

    return passed, failed


def run_custom_checks(python_bin: str) -> tuple[int, int]:
    passed = 0
    failed = 0

    with tempfile.TemporaryDirectory(prefix="klingo_regress_") as tmpdir:
        tmp = Path(tmpdir)

        # 1) Conditional #show filtering and signature extraction.
        show_conditional = tmp / "show_conditional.lp"
        show_conditional.write_text(
            "a(1).\n"
            "b(1).\n"
            "b(2).\n"
            "#show b(X) : a(X).\n",
            encoding="utf-8",
        )
        try:
            if str(ROOT) not in sys.path:
                sys.path.insert(0, str(ROOT))
            from klingo_semantics import parse_show_signatures

            sigs = parse_show_signatures((str(show_conditional),))
        except Exception as exc:
            print(f"[FAIL] show_conditional_signature: {exc}")
            failed += 1
        else:
            if ("b", 1) not in sigs:
                print(f"[FAIL] show_conditional_signature: expected ('b', 1), got {sorted(sigs)}")
                failed += 1
            else:
                print("[PASS] show_conditional_signature")
                passed += 1

        cmd = [python_bin, str(KLINGO_ENTRYPOINT), "--3nd-star", "-k", "0", "-n", "1", str(show_conditional)]
        rc, out, err = run_command(cmd, ROOT)
        atoms = extract_final_answer_atoms(out)
        if rc != 0:
            print(f"[FAIL] show_conditional_output: klingo returned {rc}")
            if err.strip():
                print(err.strip())
            failed += 1
        elif "b(1)" not in atoms or "b(2)" in atoms:
            print(f"[FAIL] show_conditional_output: expected b(1) only, got {sorted(atoms)}")
            failed += 1
        else:
            print("[PASS] show_conditional_output")
            passed += 1

        for summary_mode in ("brave", "cautious"):
            cmd = [
                python_bin,
                str(KLINGO_ENTRYPOINT),
                "--3nd-star",
                "-k",
                "0",
                "--mode",
                summary_mode,
                "-n",
                "0",
                str(show_conditional),
            ]
            rc, out, err = run_command(cmd, ROOT)
            atoms = extract_final_answer_atoms(out)
            label = f"show_conditional_{summary_mode}_summary"
            if rc != 0:
                print(f"[FAIL] {label}: klingo returned {rc}")
                if err.strip():
                    print(err.strip())
                failed += 1
            elif atoms != {"b(1)"}:
                print(f"[FAIL] {label}: expected only b(1), got {sorted(atoms)}")
                failed += 1
            else:
                print(f"[PASS] {label}")
                passed += 1

        # 2) Nested-term #show term filtering.
        show_nested = tmp / "show_nested.lp"
        show_nested.write_text(
            "q.\n"
            "p(f(a,b),c).\n"
            "p(f(a,b),d).\n"
            "#show p(f(a,b),c) : q.\n",
            encoding="utf-8",
        )
        cmd = [python_bin, str(KLINGO_ENTRYPOINT), "--3nd-star", "-k", "0", "-n", "1", str(show_nested)]
        rc, out, err = run_command(cmd, ROOT)
        atoms = extract_final_answer_atoms(out)
        if rc != 0:
            print(f"[FAIL] show_nested_output: klingo returned {rc}")
            if err.strip():
                print(err.strip())
            failed += 1
        elif "p(f(a,b),c)" not in atoms or "p(f(a,b),d)" in atoms:
            print(f"[FAIL] show_nested_output: expected only p(f(a,b),c), got {sorted(atoms)}")
            failed += 1
        else:
            print("[PASS] show_nested_output")
            passed += 1

        # 3) Mode gating for totality preprocessing.
        totality_fixture = tmp / "totality_gate.lp"
        totality_fixture.write_text("p(1).", encoding="utf-8")
        dump_star = tmp / "dump_star.lp"
        dump_3nd = tmp / "dump_3nd.lp"
        cmd_star = [
            python_bin,
            str(KLINGO_ENTRYPOINT),
            "--3nd-star",
            "-k",
            "0",
            "-n",
            "1",
            "--dump-preprocessed",
            str(dump_star),
            str(totality_fixture),
        ]
        cmd_3nd = [
            python_bin,
            str(KLINGO_ENTRYPOINT),
            "--3nd",
            "-k",
            "0",
            "-n",
            "1",
            "--dump-preprocessed",
            str(dump_3nd),
            str(totality_fixture),
        ]
        rc_star, out_star, err_star = run_command(cmd_star, ROOT)
        rc_3nd, out_3nd, err_3nd = run_command(cmd_3nd, ROOT)
        if rc_star != 0 or rc_3nd != 0:
            print("[FAIL] totality_mode_gating: preprocessing command failed")
            if err_star.strip():
                print(err_star.strip())
            if err_3nd.strip():
                print(err_3nd.strip())
            failed += 1
        else:
            txt_star = dump_star.read_text(encoding="utf-8")
            txt_3nd = dump_3nd.read_text(encoding="utf-8")
            match_star = re.search(r"totality_injected_count\s*=\s*(\d+)", txt_star)
            match_3nd = re.search(r"totality_injected_count\s*=\s*(\d+)", txt_3nd)
            count_star = int(match_star.group(1)) if match_star else -1
            count_3nd = int(match_3nd.group(1)) if match_3nd else -1
            if count_star != 0 or count_3nd <= 0:
                print(
                    f"[FAIL] totality_mode_gating: expected star=0 and 3nd>0, got star={count_star}, 3nd={count_3nd}"
                )
                failed += 1
            else:
                print("[PASS] totality_mode_gating")
                passed += 1

        # 4) Totality universe should follow grounded atoms only.
        totality_grounded = tmp / "totality_grounded.lp"
        totality_grounded.write_text(
            "p(1).\n"
            "q(2).\n"
            "s(X) :- p(X).\n",
            encoding="utf-8",
        )
        dump_grounded = tmp / "dump_grounded.lp"
        cmd_grounded = [
            python_bin,
            str(KLINGO_ENTRYPOINT),
            "--3nd",
            "-k",
            "0",
            "-n",
            "1",
            "--dump-preprocessed",
            str(dump_grounded),
            str(totality_grounded),
        ]
        rc, out, err = run_command(cmd_grounded, ROOT)
        if rc != 0:
            print("[FAIL] totality_grounded_universe: preprocessing command failed")
            if err.strip():
                print(err.strip())
            failed += 1
        else:
            txt = dump_grounded.read_text(encoding="utf-8")
            match = re.search(r"totality_injected_count\s*=\s*(\d+)", txt)
            count = int(match.group(1)) if match else -1
            forbidden = ["p(2)", "q(1)", "s(2)"]
            if count != 3 or any(sym in txt for sym in forbidden):
                print(
                    "[FAIL] totality_grounded_universe: expected grounded-only totality "
                    f"(count=3; forbidden={forbidden}), got count={count}"
                )
                failed += 1
            else:
                print("[PASS] totality_grounded_universe")
                passed += 1

        # 4b) Supervaluational BNM: nothing may be presumed when compatible
        # stable models disagree (guards against first-model-only completion).
        bnm_multi = tmp / "bnm_sv_multi.lp"
        bnm_multi.write_text(
            "a :- not b.\n"
            "b :- not a.\n"
            "c :- a.\n",
            encoding="utf-8",
        )
        cmd = [python_bin, str(KLINGO_ENTRYPOINT), "--bnm", "-k", "0", "--color", "never", str(bnm_multi)]
        rc, out, err = run_command(cmd, ROOT)
        atoms = extract_final_answer_atoms(out)
        if rc != 0:
            print(f"[FAIL] bnm_sv_no_unsound_promotion: klingo returned {rc}")
            if err.strip():
                print(err.strip())
            failed += 1
        elif any(not atom.startswith("?") for atom in atoms):
            print(f"[FAIL] bnm_sv_no_unsound_promotion: expected all-undecided, got {sorted(atoms)}")
            failed += 1
        else:
            print("[PASS] bnm_sv_no_unsound_promotion")
            passed += 1

        # 4c) Supervaluational BNM: unanimous stable models are presumed at k=0
        # (symmetrically: q presumed true, p presumed false via [b]-p) and the
        # presumption is inhibited at k=1 (cautious consequences vanish).
        bnm_naf = tmp / "bnm_sv_naf.lp"
        bnm_naf.write_text("q :- not p.\n", encoding="utf-8")
        cmd = [python_bin, str(KLINGO_ENTRYPOINT), "--bnm", "-k", "0", "--color", "never", str(bnm_naf)]
        rc, out, err = run_command(cmd, ROOT)
        atoms = extract_final_answer_atoms(out)
        if rc != 0 or atoms != {"[b]q", "[b]-p"}:
            print(f"[FAIL] bnm_sv_presumption_k0: expected {{[b]q, [b]-p}}, got {sorted(atoms)} (rc={rc})")
            failed += 1
        else:
            print("[PASS] bnm_sv_presumption_k0")
            passed += 1

        cmd = [
            python_bin,
            str(KLINGO_ENTRYPOINT),
            "--bnm",
            "-k",
            "1",
            "--mode",
            "cautious",
            "--color",
            "never",
            str(bnm_naf),
        ]
        rc, out, err = run_command(cmd, ROOT)
        cons = extract_summary_consequences(out)
        if rc != 0 or cons != 0:
            print(f"[FAIL] bnm_sv_flip_k1_cautious: expected 0 cautious consequences, got {cons} (rc={rc})")
            failed += 1
        else:
            print("[PASS] bnm_sv_flip_k1_cautious")
            passed += 1

        # 4d) Supervaluational BNM classical limit: at totality depth the
        # enumerated models are exactly the classical models of P + totality.
        cmd = [python_bin, str(KLINGO_ENTRYPOINT), "--bnm", "-k", "1", "-n", "0", "--color", "never", str(bnm_naf)]
        rc, out, err = run_command(cmd, ROOT)
        lines = out.splitlines()
        models = set()
        for idx, line in enumerate(lines):
            if line.startswith("Answer:") and idx + 1 < len(lines):
                models.add(frozenset(lines[idx + 1].split()))
        expected_models = {
            frozenset({"-p", "q"}),
            frozenset({"p", "-q"}),
            frozenset({"p", "q"}),
        }
        if rc != 0 or models != expected_models:
            print(f"[FAIL] bnm_sv_classical_limit: expected classical models of P+Tot, got {sorted(sorted(m) for m in models)}")
            failed += 1
        else:
            print("[PASS] bnm_sv_classical_limit")
            passed += 1

        # 4e) Atoms occurring only in #show bodies must not enter the totality
        # universe (display directives are semantics-neutral).
        show_leak = tmp / "show_leak.lp"
        show_leak.write_text(
            "visible.\n"
            "#show hidden : marker.\n"
            "#show visible/0.\n",
            encoding="utf-8",
        )
        dump_leak = tmp / "dump_leak.lp"
        cmd = [
            python_bin,
            str(KLINGO_ENTRYPOINT),
            "--3nd",
            "-k",
            "0",
            "-n",
            "1",
            "--dump-preprocessed",
            str(dump_leak),
            str(show_leak),
        ]
        rc, out, err = run_command(cmd, ROOT)
        if rc != 0:
            print("[FAIL] show_body_totality_gate: command failed")
            if err.strip():
                print(err.strip())
            failed += 1
        else:
            txt = dump_leak.read_text(encoding="utf-8")
            match = re.search(r"totality_injected_count\s*=\s*(\d+)", txt)
            count = int(match.group(1)) if match else -1
            if count != 1 or "marker" in txt.split("% --- begin injected totality rules ---")[-1]:
                print(f"[FAIL] show_body_totality_gate: expected only 'visible' injected, count={count}")
                failed += 1
            else:
                print("[PASS] show_body_totality_gate")
                passed += 1

        # 4f) Flip-trajectory gadgets: pin the single-crossing trajectory
        # grammar ([ST-verdict] -> UNDEC* -> [classical verdict]).
        def cautious_atoms(lp_path, k):
            cmd_flip = [
                python_bin,
                str(KLINGO_ENTRYPOINT),
                "--bnm",
                "-k",
                str(k),
                "--mode",
                "cautious",
                "--color",
                "never",
                str(lp_path),
            ]
            rc_flip, out_flip, _err_flip = run_command(cmd_flip, ROOT)
            if rc_flip != 0:
                return None
            return {atom.replace("[b]", "") for atom in extract_final_answer_atoms(out_flip)}

        flip_tf = ROOT / "Examples" / "kernel" / "flip_tf.lp"
        tf_k0 = cautious_atoms(flip_tf, 0)
        tf_k1 = cautious_atoms(flip_tf, 1)
        if tf_k0 == {"a", "-b", "-c"} and tf_k1 == {"-a", "b", "c"}:
            print("[PASS] flip_tf_polarity_swap")
            passed += 1
        else:
            print(f"[FAIL] flip_tf_polarity_swap: k0={sorted(tf_k0 or [])}, k1={sorted(tf_k1 or [])}")
            failed += 1

        flip_fut = ROOT / "Examples" / "kernel" / "flip_fut.lp"
        fut_k0 = cautious_atoms(flip_fut, 0)
        fut_k1 = cautious_atoms(flip_fut, 1)
        fut_k2 = cautious_atoms(flip_fut, 2)
        if (
            fut_k0 == {"-yes", "bait1", "bait2", "-x1", "-x2"}
            and fut_k1 == set()
            and fut_k2 == {"yes"}
        ):
            print("[PASS] flip_fut_three_status")
            passed += 1
        else:
            print(
                f"[FAIL] flip_fut_three_status: k0={sorted(fut_k0 or [])}, "
                f"k1={sorted(fut_k1 or [])}, k2={sorted(fut_k2 or [])}"
            )
            failed += 1

        flip_w4 = ROOT / "Examples" / "kernel" / "flip_width4.lp"
        w4_k0 = cautious_atoms(flip_w4, 0)
        w4_k1 = cautious_atoms(flip_w4, 1)
        w4_k4 = cautious_atoms(flip_w4, 4)
        if (
            w4_k0 is not None
            and "yes" in w4_k0
            and w4_k1 is not None
            and "yes" not in w4_k1
            and w4_k4 is not None
            and "yes" in w4_k4
        ):
            print("[PASS] flip_width_suspension")
            passed += 1
        else:
            print(
                f"[FAIL] flip_width_suspension: k0={sorted(w4_k0 or [])}, "
                f"k1={sorted(w4_k1 or [])}, k4={sorted(w4_k4 or [])}"
            )
            failed += 1

        # 4g) --learn / --use-lemmas: certified-schema learning round-trip.
        children_lp = ROOT / "Examples" / "kernel" / "bnm_children_open.lp"
        lemma_out = tmp / "children_learned.lp"
        cmd = [python_bin, str(KLINGO_ENTRYPOINT), "--bnm", "--learn", str(lemma_out), str(children_lp)]
        rc, out, err = run_command(cmd, ROOT)
        lemma_text = lemma_out.read_text(encoding="utf-8") if lemma_out.exists() else ""
        if rc != 0 or "answer_yes :-" not in lemma_text or "__ab_l" not in lemma_text:
            print(f"[FAIL] learn_children_schema: rc={rc}, lemma file:\n{lemma_text[:400]}")
            failed += 1
        else:
            print("[PASS] learn_children_schema")
            passed += 1

        def _cautious_set(extra_args):
            cmd_c = [python_bin, str(KLINGO_ENTRYPOINT), "--bnm", "--mode", "cautious",
                     "--color", "never"] + extra_args + [str(children_lp)]
            rc_c, out_c, _err_c = run_command(cmd_c, ROOT)
            if rc_c != 0:
                return None
            return {a.replace("[b]", "") for a in extract_final_answer_atoms(out_c)}

        trained_k0 = _cautious_set(["-k", "0", "--use-lemmas", str(lemma_out)])
        if (trained_k0 and "answer_yes" in trained_k0 and "answer_no" not in trained_k0
                and not any("__ab" in a for a in trained_k0)):
            print("[PASS] use_lemmas_depth0_presumption")
            passed += 1
        else:
            print(f"[FAIL] use_lemmas_depth0_presumption: got {sorted(trained_k0 or [])}")
            failed += 1

        untrained_k1 = _cautious_set(["-k", "1"])
        trained_k1 = _cautious_set(["-k", "1", "--use-lemmas", str(lemma_out)])
        if untrained_k1 is not None and untrained_k1 == trained_k1:
            print("[PASS] use_lemmas_classical_limit_unchanged")
            passed += 1
        else:
            print(
                f"[FAIL] use_lemmas_classical_limit_unchanged: untrained={sorted(untrained_k1 or [])}, "
                f"trained={sorted(trained_k1 or [])}"
            )
            failed += 1

        cmd = [python_bin, str(KLINGO_ENTRYPOINT), "--learn", str(tmp / "x.lp"), str(children_lp)]
        rc, out, err = run_command(cmd, ROOT)
        if rc != 0 and "--learn requires --bnm" in (out + err):
            print("[PASS] learn_requires_bnm")
            passed += 1
        else:
            print(f"[FAIL] learn_requires_bnm: rc={rc}")
            failed += 1

        # 5) Missing-file preflight should fail cleanly.
        missing = tmp / "does_not_exist.lp"
        cmd_missing = [python_bin, str(KLINGO_ENTRYPOINT), "--3nd-star", "-k", "1", str(missing)]
        rc, out, err = run_command(cmd_missing, ROOT)
        combined = (out + "\n" + err).strip()
        if rc == 0:
            print("[FAIL] missing_file_preflight: expected non-zero exit")
            failed += 1
        elif "Input file not found:" not in combined or "Traceback" in combined:
            print(f"[FAIL] missing_file_preflight: unexpected message\n{combined}")
            failed += 1
        else:
            print("[PASS] missing_file_preflight")
            passed += 1

        # 6) Max-depth detector should be mode-aware and print only an integer.
        max_depth_fixture = ROOT / "Examples" / "kernel" / "bnm_totality.lp"
        cmd_star = [python_bin, str(KLINGO_ENTRYPOINT), "--3nd-star", "--detect-max-depth", str(max_depth_fixture)]
        cmd_3nd = [python_bin, str(KLINGO_ENTRYPOINT), "--3nd", "--detect-max-depth", str(max_depth_fixture)]
        cmd_bnm = [python_bin, str(KLINGO_ENTRYPOINT), "--bnm", "--detect-max-depth", str(max_depth_fixture)]
        rc_star, out_star, err_star = run_command(cmd_star, ROOT)
        rc_3nd, out_3nd, err_3nd = run_command(cmd_3nd, ROOT)
        rc_bnm, out_bnm, err_bnm = run_command(cmd_bnm, ROOT)
        if rc_star != 0 or rc_3nd != 0 or rc_bnm != 0:
            print("[FAIL] detect_max_depth_mode_gating: detector command failed")
            if err_star.strip():
                print(err_star.strip())
            if err_3nd.strip():
                print(err_3nd.strip())
            if err_bnm.strip():
                print(err_bnm.strip())
            failed += 1
        else:
            txt_star = out_star.strip()
            txt_3nd = out_3nd.strip()
            txt_bnm = out_bnm.strip()
            if not (txt_star.isdigit() and txt_3nd.isdigit() and txt_bnm.isdigit()):
                print(
                    "[FAIL] detect_max_depth_mode_gating: expected integer-only output, got "
                    f"star={txt_star!r}, 3nd={txt_3nd!r}, bnm={txt_bnm!r}"
                )
                failed += 1
            else:
                depth_star = int(txt_star)
                depth_3nd = int(txt_3nd)
                depth_bnm = int(txt_bnm)
                if depth_star != 0 or depth_3nd != 1 or depth_bnm != depth_3nd:
                    print(
                        "[FAIL] detect_max_depth_mode_gating: expected star=0, 3nd=1, bnm=3nd; got "
                        f"star={depth_star}, 3nd={depth_3nd}, bnm={depth_bnm}"
                    )
                    failed += 1
                else:
                    print("[PASS] detect_max_depth_mode_gating")
                    passed += 1

    return passed, failed


def run_perf_cases(
    python_bin: str,
    perf_output_dir: Path,
    perf_repeats: int,
    skip_perf_plots: bool,
) -> tuple[int, int]:
    perf_output_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    passed = 0
    failed = 0

    for case in PERF_CASES:
        for k in case.k_values:
            for repeat in range(1, perf_repeats + 1):
                cmd = [python_bin, str(KLINGO_ENTRYPOINT)] + case.solver_args + ["-k", str(k), case.file]
                row = init_perf_row(case, k, repeat, case.timeout_s, cmd)
                result = run_command_timed(cmd, ROOT, timeout_s=case.timeout_s)
                row["wall_s"] = round(result["wall_s"], 6)
                row["returncode"] = result["returncode"]

                if result["timeout"]:
                    row["status"] = "timeout"
                    row["stderr_tail"] = (result["stderr"] or "")[-400:]
                    rows.append(row)
                    failed += 1
                    print(f"[PERF][FAIL] {case.name} k={k} rep={repeat}: timeout")
                    continue

                if result["returncode"] != 0:
                    row["status"] = "error"
                    row["stderr_tail"] = (result["stderr"] or "")[-400:]
                    rows.append(row)
                    failed += 1
                    print(f"[PERF][FAIL] {case.name} k={k} rep={repeat}: returncode={result['returncode']}")
                    continue

                row.update(parse_primary_perf_metrics(result["stdout"]))
                row["stderr_tail"] = (result["stderr"] or "")[-400:]

                if case.collect_bnm_details:
                    detail_cmd = [python_bin, str(KLINGO_ENTRYPOINT)] + case.solver_args + [
                        "--no-clingo-output",
                        "-k",
                        str(k),
                        case.file,
                    ]
                    row["detail_cmd"] = " ".join(detail_cmd)
                    detail = run_command_timed(detail_cmd, ROOT, timeout_s=case.timeout_s)
                    if detail["timeout"]:
                        row["detail_status"] = "timeout"
                        row["detail_stderr_tail"] = (detail["stderr"] or "")[-400:]
                    elif detail["returncode"] != 0:
                        row["detail_status"] = "error"
                        row["detail_stderr_tail"] = (detail["stderr"] or "")[-400:]
                    else:
                        row["detail_status"] = "ok"
                        row["detail_stderr_tail"] = (detail["stderr"] or "")[-400:]
                        row.update(parse_detail_perf_metrics(detail["stdout"]))

                row["nonmon_assumptions"] = (
                    row["bnm_tagged_assignments"] if row["bnm_tagged_assignments"] else row["bnm_shown_true_atoms"]
                )
                rows.append(row)
                passed += 1
                print(
                    "[PERF][PASS] {} k={} rep={} wall_s={:.4f} calls={} restarts={} nonmon={}".format(
                        case.name,
                        k,
                        repeat,
                        float(row["wall_s"]),
                        row["calls"],
                        row["restarts"],
                        row["nonmon_assumptions"],
                    )
                )

    write_perf_csv(rows, perf_output_dir / "metrics.csv")
    write_perf_summary(rows, perf_output_dir)
    if not skip_perf_plots:
        plot_perf(rows, perf_output_dir)

    print(f"[PERF] wrote: {perf_output_dir / 'metrics.csv'}")
    print(f"[PERF] wrote: {perf_output_dir / 'README.md'}")
    if not skip_perf_plots:
        print(f"[PERF] wrote plots: {perf_output_dir}/*.png")
    return passed, failed


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run semantic regressions with golden-output/oracle checks and optional performance reporting."
    )
    parser.add_argument(
        "--python",
        default=sys.executable,
        help="Python interpreter used to run klingo (default: current interpreter).",
    )
    parser.add_argument(
        "--clingo-bin",
        default=shutil.which("clingo") or "clingo",
        help="clingo executable path used for oracle checks (default: discovered from PATH).",
    )
    parser.add_argument(
        "--update-golden",
        action="store_true",
        help="regenerate golden output files from the current implementation.",
    )
    parser.add_argument(
        "--skip-oracle",
        action="store_true",
        help="skip clingo oracle parity checks.",
    )
    parser.add_argument(
        "--perf",
        action="store_true",
        help="collect performance metrics and generate plots/CSV report.",
    )
    parser.add_argument(
        "--perf-only",
        action="store_true",
        help="run only performance reporting (skip semantic golden/oracle checks).",
    )
    parser.add_argument(
        "--perf-output",
        default=str(DEFAULT_PERF_DIR),
        help="directory for performance CSV/plots (default: tests/perf).",
    )
    parser.add_argument(
        "--perf-repeats",
        type=int,
        default=1,
        help="number of repetitions for each (case, k) performance run (default: 1).",
    )
    parser.add_argument(
        "--skip-perf-plots",
        action="store_true",
        help="collect performance metrics without generating matplotlib plots.",
    )
    args = parser.parse_args()

    if args.perf_only:
        args.perf = True
    if args.perf_repeats < 1:
        raise SystemExit("--perf-repeats must be >= 1")

    ensure_fixtures()
    core_before = snapshot_core_hashes()

    g_passed = 0
    g_failed = 0
    o_passed = 0
    o_failed = 0
    c_passed = 0
    c_failed = 0
    p_passed = 0
    p_failed = 0

    if not args.perf_only:
        g_passed, g_failed = run_golden_cases(args.python, update=args.update_golden)
        if not args.skip_oracle:
            o_passed, o_failed = run_oracle_cases(args.python, args.clingo_bin)
        c_passed, c_failed = run_custom_checks(args.python)

    if args.perf:
        perf_output_dir = Path(args.perf_output)
        p_passed, p_failed = run_perf_cases(
            python_bin=args.python,
            perf_output_dir=perf_output_dir,
            perf_repeats=args.perf_repeats,
            skip_perf_plots=args.skip_perf_plots,
        )

    total_passed = g_passed + o_passed + c_passed + p_passed
    total_failed = g_failed + o_failed + c_failed + p_failed

    core_after = snapshot_core_hashes()
    changed_core = diff_core_hashes(core_before, core_after)
    if changed_core:
        print("[FAIL] Core files changed during regression run:")
        for rel in changed_core:
            print(f"  - {rel}")
        total_failed += 1
    else:
        print("[PASS] Core-file immutability guard")

    print("")
    print(f"Summary: {total_passed} passed, {total_failed} failed")
    return 1 if total_failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
