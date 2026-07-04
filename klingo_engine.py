import argparse
import hashlib
import json
import os
import sys
import time
from dataclasses import dataclass, field
from itertools import cycle
from pathlib import Path
from typing import Optional

import clingo
from clingo import ast as clingo_ast

from klingo_completion import apply_default_completion
from klingo_output import format_atom, print_valuation, truth_value_to_string
from klingo_show import extract_show_filter, filter_valuation_by_show
from klingo_totality import (
    add_classical_totality_backend,
    build_totality_universe,
    render_totality_rules,
)

__version__ = "2.5.0"

RESTART_STRATEGIES = {
    "luby": "L,60",
    "geometric": "x,100,1.5",
    "dynamic": "D,100,0.7",
    "fixed": "F,100",
    "none": "0",
}

TOTALITY_WARNING_THRESHOLD = 50000


@dataclass
class RunState:
    seen: set = field(default_factory=set)
    blocking_constraints: list = field(default_factory=list)
    valuation_index: int = 0
    brave_union: set = field(default_factory=set)
    cautious_intersection: Optional[set] = None
    all_atoms: Optional[set] = None
    tag_map_for_summary: dict = field(default_factory=dict)
    legend_flags: set = field(default_factory=set)
    exhausted: bool = False
    hit_limit: bool = False
    solve_calls: int = 0


class Propagator:
    def __init__(self, depth, control, debug=False, dictionary=False):
        self.depth = depth
        self.control = control
        self.debug = debug
        self.dictionary = dictionary
        self.solver_literals = []
        self.symbols = []
        self.fixed_false_symbols = []
        self.symbol_by_abs_lit = {}
        self.found = False
        self.valuation = None
        self.decision_level = None
        self.decision_literals = []
        self.exceeded_depth = False

    def init(self, init):
        init.check_mode = clingo.PropagatorCheckMode.Fixpoint

        for atom in init.symbolic_atoms:
            # Program literal 0 means the atom has been simplified away as false.
            # Do not map/watch it through solver literals to avoid spurious truth values.
            if atom.literal <= 0:
                self.fixed_false_symbols.append(atom.symbol)
                if self.dictionary:
                    print(atom.symbol, "has fixed value 0 (program literal", atom.literal, ")")
                continue
            lit = init.solver_literal(atom.literal)
            init.add_watch(lit)
            self.solver_literals.append(lit)
            self.symbols.append(atom.symbol)
            self.symbol_by_abs_lit[abs(lit)] = str(atom.symbol)
            if self.dictionary:
                print(atom.symbol, "has solver literal", lit)

    def check(self, ctl):
        if self.debug:
            print("Current depth = ", ctl.assignment.decision_level - 1)

        if ctl.assignment.decision_level > self.depth + 1:
            self.exceeded_depth = True
            if self.control:
                self.control.interrupt()
            return

        if (ctl.assignment.decision_level == self.depth + 1) or ctl.assignment.is_total:
            self.valuation = []
            decision_literals = []
            for level in range(1, ctl.assignment.decision_level + 1):
                try:
                    decision_lit = ctl.assignment.decision(level)
                except RuntimeError:
                    continue
                if decision_lit == 0:
                    continue
                atom_name = self.symbol_by_abs_lit.get(abs(decision_lit))
                if atom_name is None:
                    continue
                value = "1" if decision_lit > 0 else "0"
                decision_literals.append(
                    {
                        "level": level,
                        "lit": decision_lit,
                        "atom": atom_name,
                        "value": value,
                        "literal": atom_name if value == "1" else f"not {atom_name}",
                    }
                )
            self.decision_literals = decision_literals
            for idx in range(len(self.solver_literals)):
                truth_value = truth_value_to_string(ctl.assignment.value(self.solver_literals[idx]))
                self.valuation.append((str(self.symbols[idx]), truth_value))
            for symbol in self.fixed_false_symbols:
                self.valuation.append((str(symbol), "0"))
            self.found = True
            self.decision_level = ctl.assignment.decision_level
            if self.control:
                self.control.interrupt()


def configure_solver(control, restart_key):
    if restart_key not in RESTART_STRATEGIES:
        raise ValueError(f"Unknown restart strategy: {restart_key}")
    control.configuration.solver[0].restarts = RESTART_STRATEGIES[restart_key]


def valuation_signature(valuation):
    return tuple(valuation)


def branch_profile_hash(valuation):
    pos = sorted([atom for atom, value in valuation if value == "1"])
    neg = sorted([atom for atom, value in valuation if value == "0"])
    payload = json.dumps({"pos": pos, "neg": neg}, sort_keys=True, separators=(",", ":"))
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:16]


def valuation_block_constraint(valuation):
    literals = []
    for atom, value in valuation:
        if value == "1":
            literals.append(atom)
        elif value == "0":
            literals.append(f"not {atom}")
    if not literals:
        return None
    return ":- " + ", ".join(literals) + "."


def models_flag_was_explicit(argv):
    for arg in argv:
        if arg in {"-n", "--models"}:
            return True
        if arg.startswith("--models="):
            return True
        # Combined short form, e.g. "-n5" (argparse also accepts "-n-1").
        if arg.startswith("-n") and arg[2:].lstrip("-").isdigit():
            return True
    return False


def non_negative_depth(value):
    depth = int(value)
    if depth < 0:
        raise argparse.ArgumentTypeError(f"depth must be >= 0 (got {depth})")
    return depth


def build_arg_parser():
    parser = argparse.ArgumentParser(
        description="Depth-bounded reasoning over ASP programs.",
        epilog=(
            "Common use: choose a mode (--3nd-star/--3nd/--bnm), set -k, and optionally "
            "select --mode brave or --mode cautious. Inspection/debug flags are optional."
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"klingo version {__version__}",
    )
    parser.add_argument("files", nargs="+", type=str, help="path(s) to base lp file(s)")
    mode_section = parser.add_argument_group("reasoning mode")
    mode_group = mode_section.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--3nd-star",
        dest="solver_mode",
        action="store_const",
        const="3nd-star",
        help="3ND* mode: original ASP approximation (default)",
    )
    mode_group.add_argument(
        "--3nd",
        dest="solver_mode",
        action="store_const",
        const="3nd",
        help="3ND mode: totality axioms only (no completion)",
    )
    mode_group.add_argument(
        "--bnm",
        dest="solver_mode",
        action="store_const",
        const="bnm",
        help="BNM mode: totality axioms + bounded non-monotonic completion",
    )
    parser.set_defaults(solver_mode="3nd-star")

    core_group = parser.add_argument_group("core options")
    core_group.add_argument(
        "-k", "--depth", type=non_negative_depth, help="depth bound (default=0)", default=0
    )
    core_group.add_argument(
        "-n",
        "--models",
        type=int,
        default=0,
        help="stop after N valuations (0 = no limit)",
    )

    learn_group = parser.add_argument_group("learning")
    learn_group.add_argument(
        "--learn",
        type=str,
        default=None,
        metavar="PATH",
        help=(
            "learn certified schemas from the depth flip gain, write them to PATH "
            "as ab-guarded default lemmas, then exit (requires --bnm)"
        ),
    )
    learn_group.add_argument(
        "--ilasp",
        type=str,
        default=None,
        metavar="PATH",
        help=(
            "learn lemmas inductively with ILASP from the flip gains of the input files "
            "(each positional file is a separate training instance), refine by "
            "property-based CEGIS, write certified lemmas to PATH, then exit "
            "(requires --bnm and the ILASP binary)"
        ),
    )
    learn_group.add_argument(
        "--use-lemmas",
        type=str,
        default=None,
        metavar="PATH",
        help="load a lemma file produced by --learn or --ilasp alongside the input files",
    )

    output_group = parser.add_argument_group("output")
    output_group.add_argument(
        "-o",
        "--clingo-output",
        help="enable clingo-style output (default)",
        action="store_true",
        default=True,
    )
    output_group.add_argument(
        "--no-clingo-output",
        dest="clingo_output",
        action="store_false",
        help="use legacy k-lingo output",
    )
    output_group.add_argument(
        "--mode",
        type=str,
        default="all",
        choices=["all", "brave", "cautious"],
        help="output mode: all valuations, brave (true in some), cautious (true in all).",
    )
    output_group.add_argument(
        "--color",
        choices=["auto", "always", "never"],
        default="auto",
        help="colorize ?atoms in clingo-style output (default: auto)",
    )

    inspect_group = parser.add_argument_group("inspection / debugging (optional)")
    inspect_group.add_argument(
        "--restart-strategy",
        type=str,
        default="luby",
        help="restart strategy (luby, geometric, dynamic, fixed, none); comma-separated values cycle.",
    )
    inspect_group.add_argument(
        "--detect-max-depth",
        action="store_true",
        help=(
            "print only the maximum reachable decision depth for the selected mode and input, "
            "then exit"
        ),
    )
    inspect_group.add_argument("--dictionary", help="print the literal dictionary", action="store_true")
    inspect_group.add_argument("--debug", help="print debug information", action="store_true")
    inspect_group.add_argument(
        "--emit-bnm-trace",
        type=str,
        default=None,
        help="optional output directory for per-depth BNM engine traces (JSON, debug only)",
    )
    inspect_group.add_argument(
        "--dump-preprocessed",
        type=str,
        default=None,
        help="write the preprocessed static program (mode injections only, no dynamic blockers) to this path",
    )
    inspect_group.add_argument(
        "--print-config",
        action="store_true",
        help="print resolved run configuration and preprocessing settings before solving",
    )
    return parser


def prepare_models_setting(args, raw_args):
    models_explicit = models_flag_was_explicit(raw_args)
    forced_models_default = False
    show_models_warning = False
    if args.mode in {"brave", "cautious"}:
        if models_explicit:
            if args.models != 0:
                show_models_warning = True
        else:
            # brave/cautious consequences require full model exploration by default
            args.models = 0
            forced_models_default = True
    return forced_models_default, show_models_warning


def select_color_mode(color_arg):
    if color_arg == "always":
        return True
    if color_arg == "never":
        return False
    return sys.stdout.isatty()


def _write_trace_payload(output_dir, depth, payload):
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"trace_k{depth}.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return str(path)


def validate_input_files(paths):
    for raw in paths:
        path = Path(raw)
        if not path.exists() or not path.is_file():
            raise SystemExit(f"Input file not found: {raw}")
        if not os.access(path, os.R_OK):
            raise SystemExit(f"Input file is not readable: {raw}")


def validate_program_syntax(paths):
    messages = []

    def _log(_code, message):
        messages.append(message)

    try:
        clingo_ast.parse_files(list(paths), lambda _stm: None, logger=_log)
    except RuntimeError as exc:
        detail = next(
            (msg.strip() for msg in messages if "error" in msg),
            messages[-1].strip() if messages else str(exc),
        )
        raise SystemExit(f"Parse error: {detail}") from exc


def dump_preprocessed_program(output_path, mode, paths, totality_symbols):
    lines = []
    lines.append(f"% klingo preprocessed program")
    lines.append(f"% mode = {mode}")
    lines.append(f"% source_files = {', '.join(paths)}")
    lines.append(f"% totality_injected_count = {len(totality_symbols)}")
    lines.append("")
    for raw in paths:
        path = Path(raw)
        lines.append(f"% --- begin source: {path} ---")
        lines.extend(path.read_text(encoding="utf-8", errors="ignore").splitlines())
        lines.append(f"% --- end source: {path} ---")
        lines.append("")
    if totality_symbols:
        lines.append("% --- begin injected totality rules ---")
        lines.extend(render_totality_rules(totality_symbols))
        lines.append("% --- end injected totality rules ---")
    out_path = Path(output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(out_path)


def print_run_config(args, totality_symbols, show_filter):
    print("*** Run configuration")
    print(f"  mode                 : {args.solver_mode}")
    print(f"  output mode          : {args.mode}")
    print(f"  depth                : {args.depth}")
    print(f"  models               : {args.models}")
    print(f"  restart strategy     : {args.restart_strategy}")
    print(f"  files                : {', '.join(args.files)}")
    print(f"  heuristics           : off")
    print(f"  emit_bnm_trace       : {'on' if args.emit_bnm_trace else 'off'}")
    print(f"  completion_debug_env : {'on' if os.environ.get('KLINGO_COMPLETION_DEBUG') else 'off'}")
    print(f"  dump_preprocessed    : {args.dump_preprocessed if args.dump_preprocessed else 'off'}")
    print(f"  totality_enabled     : {'yes' if args.solver_mode in {'3nd', 'bnm'} else 'no'}")
    print(f"  totality_sigma_size  : {len(totality_symbols)}")
    if show_filter and show_filter.has_directives:
        print(
            "  show filter          : directives={} signatures={} terms={} unsupported_terms={}".format(
                "yes",
                len(show_filter.signatures),
                len(show_filter.term_rules),
                show_filter.unsupported_terms,
            )
        )
    else:
        print("  show filter          : none")


def filter_summary_atoms(summary_atoms, atom_universe, show_filter):
    summary_atoms = {atom for atom in summary_atoms if not _is_internal_atom(atom)}
    if not show_filter or not show_filter.has_directives or show_filter.disabled:
        return sorted(summary_atoms)
    valuation = []
    for atom in sorted((atom_universe or set()) | set(summary_atoms)):
        valuation.append((atom, "1" if atom in summary_atoms else "0"))
    filtered = filter_valuation_by_show(valuation, show_filter)
    return sorted(atom for atom, value in filtered if value == "1")


def detect_max_decision_depth(paths, solver_mode, restart_keys, totality_symbols):
    """
    Enumerate unique base valuations with the standard blocker loop and return
    the maximum encountered decision depth (decision_level - 1).

    Mode behavior:
      - 3nd-star: original program (no totality injection)
      - 3nd / bnm: totality-backed core search (same core as 3nd)
    """
    seen = set()
    blockers = []
    restart_cycle = cycle(restart_keys)
    max_depth = 0

    # Disable the depth cutoff by giving the propagator a very large bound.
    unbounded_depth = sys.maxsize // 4

    while True:
        strategy = next(restart_cycle)
        propagator, solve_result = solve_core_iteration(
            paths,
            strategy,
            unbounded_depth,
            blockers,
            solver_mode,
            totality_symbols,
        )
        if propagator.exceeded_depth:
            raise RuntimeError("Unexpected depth overflow while detecting max depth.")

        if not propagator.found:
            break

        signature = valuation_signature(propagator.valuation)
        if signature in seen:
            block = valuation_block_constraint(propagator.valuation)
            if not block or block in blockers:
                break
            blockers.append(block)
            continue

        seen.add(signature)
        decision_level = propagator.decision_level or 1
        current_depth = max(0, decision_level - 1)
        if current_depth > max_depth:
            max_depth = current_depth

        block = valuation_block_constraint(propagator.valuation)
        if not block:
            break
        if block not in blockers:
            blockers.append(block)

        if solve_result.unsatisfiable:
            break

    return max_depth


def _is_internal_atom(atom):
    """Atoms named with a double-underscore prefix (e.g. lemma guards) are
    internal bookkeeping: they take part in solving but are never displayed."""
    return atom.startswith("__") or atom.startswith("-__")


def _cautious_atoms_for_learning(paths, depth, restart_keys, totality_symbols):
    """In-process cautious --bnm consequences at the given depth (true atoms
    shared by every completed branch). Used by --learn."""
    seen = set()
    blockers = []
    restart_cycle = cycle(restart_keys)
    intersection = None
    while True:
        strategy = next(restart_cycle)
        propagator, _solve_result = solve_core_iteration(
            paths, strategy, depth, blockers, "bnm", totality_symbols
        )
        if propagator.exceeded_depth:
            raise SystemExit("Search exceeded k-depth; aborting.")
        if not propagator.found:
            break
        signature = valuation_signature(propagator.valuation)
        if signature in seen:
            block = valuation_block_constraint(propagator.valuation)
            if not block or block in blockers:
                break
            blockers.append(block)
            continue
        seen.add(signature)
        completed, _bnm_atoms = apply_default_completion(
            propagator.valuation,
            paths,
            depth=depth,
            program_id=",".join(paths),
            totality_symbols=totality_symbols,
        )
        true_atoms = {atom for atom, value in completed if value == "1"}
        intersection = set(true_atoms) if intersection is None else (intersection & true_atoms)
        block = valuation_block_constraint(propagator.valuation)
        if not block:
            break
        if block not in blockers:
            blockers.append(block)
    return intersection or set()


def solve_core_iteration(
    paths,
    restart_key,
    depth,
    blockers,
    solver_mode,
    totality_symbols,
    *,
    debug=False,
    dictionary=False,
):
    control = clingo.Control(["-Wno-atom-undefined"])
    configure_solver(control, restart_key)
    propagator = Propagator(depth, control, debug=debug, dictionary=dictionary)
    control.register_propagator(propagator)

    for path in paths:
        control.load(path)

    if blockers:
        control.add("blocks", [], "\n".join(blockers))

    if solver_mode in {"3nd", "bnm"}:
        add_classical_totality_backend(control, totality_symbols)

    control.ground([("base", [])])
    if blockers:
        control.ground([("blocks", [])])

    solve_result = control.solve(on_model=lambda _m: None)
    return propagator, solve_result


def run(argv=None):
    start_wall = time.perf_counter()
    start_cpu = time.process_time()
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    raw_args = sys.argv[1:] if argv is None else list(argv)
    all_paths = list(args.files)
    if args.use_lemmas:
        all_paths.append(args.use_lemmas)
    validate_input_files(all_paths)
    validate_program_syntax(all_paths)

    restart_keys = [key.strip() for key in args.restart_strategy.split(",") if key.strip()]
    for key in restart_keys:
        if key not in RESTART_STRATEGIES:
            raise SystemExit(f"Unknown restart strategy: {key}")

    totality_symbols = []
    if args.solver_mode in {"3nd", "bnm"}:
        totality_symbols = build_totality_universe(all_paths)
        if (not args.detect_max_depth) and len(totality_symbols) > TOTALITY_WARNING_THRESHOLD:
            print(
                f"*** Warn : (klingo): injecting totality over {len(totality_symbols)} atoms "
                f"(threshold={TOTALITY_WARNING_THRESHOLD})."
            )

    if args.detect_max_depth:
        max_depth = detect_max_decision_depth(all_paths, args.solver_mode, restart_keys, totality_symbols)
        print(max_depth)
        return 0

    if args.ilasp:
        if args.solver_mode != "bnm":
            raise SystemExit("--ilasp requires --bnm (completion semantics defines the flip gain).")
        if args.learn:
            raise SystemExit("choose one of --learn / --ilasp")
        from klingo_learn import ilasp_learn

        instances = [
            [path] + ([args.use_lemmas] if args.use_lemmas else [])
            for path in args.files
        ]

        def instance_cautious_fn(paths, depth):
            instance_totality = build_totality_universe(paths)
            return _cautious_atoms_for_learning(paths, depth, restart_keys, instance_totality)

        print("klingo version", __version__)
        print("ILASP learning from", ", ".join(args.files))
        ilasp_learn(instances, instance_cautious_fn, args.ilasp)
        return 0

    if args.learn:
        if args.solver_mode != "bnm":
            raise SystemExit("--learn requires --bnm (completion semantics defines the flip gain).")
        from klingo_learn import learn_lemmas

        def cautious_fn(depth):
            return _cautious_atoms_for_learning(all_paths, depth, restart_keys, totality_symbols)

        print("klingo version", __version__)
        print("Learning from", ", ".join(all_paths))
        probe_upper = max(2, args.depth)
        learn_lemmas(
            all_paths,
            cautious_fn,
            args.learn,
            probe_depths=tuple(range(1, probe_upper + 1)),
        )
        return 0

    forced_models_default, show_models_warning = prepare_models_setting(args, raw_args)
    clingo_output = args.clingo_output

    if show_models_warning:
        # Keep clingo warning text verbatim for compatibility.
        print("*** Warn : (clingo): #models not 0: last model may not cover consequences.")
    elif forced_models_default:
        print(f"*** Info : (klingo): --mode={args.mode} defaults to --models=0 (all models).")

    if clingo_output:
        print("klingo version", __version__)
        print("Reading from", ", ".join(all_paths))
        print("Solving...")
    else:
        print("k-lingo version", __version__)
        print("Reading from", ", ".join(all_paths))
        print("Solving with k =", args.depth, "...\n")

    colorize = select_color_mode(args.color)
    state = RunState()
    restart_cycle = cycle(restart_keys)
    show_filter = extract_show_filter(all_paths) if clingo_output else None
    if args.dump_preprocessed:
        dump_path = dump_preprocessed_program(args.dump_preprocessed, args.solver_mode, all_paths, totality_symbols)
        if args.print_config or args.debug:
            print(f"*** Info : (klingo): wrote preprocessed program to {dump_path}")
    if args.print_config:
        print_run_config(args, totality_symbols, show_filter)
    trace_payload = None
    if args.emit_bnm_trace:
        trace_payload = {
            "version": __version__,
            "solver_mode": args.solver_mode,
            "mode": args.mode,
            "depth": args.depth,
            "models": args.models,
            "restart_strategy": args.restart_strategy,
            "program_files": all_paths,
            "totality_universe": sorted(str(sym) for sym in totality_symbols),
            "created_unix": time.time(),
            "iterations": [],
            "branches": [],
            "repeat_blocks": [],
            "final": {},
        }
    iteration_index = 0

    while True:
        iteration_index += 1
        strategy = next(restart_cycle)
        active_blockers = list(state.blocking_constraints)
        iter_record = None
        if trace_payload is not None:
            iter_record = {
                "iteration": iteration_index,
                "restart_strategy": strategy,
                "active_blockers_before": active_blockers,
                "found": False,
                "unsat": False,
                "exceeded_depth": False,
            }
            trace_payload["iterations"].append(iter_record)
        state.solve_calls += 1
        propagator, solve_result = solve_core_iteration(
            all_paths,
            strategy,
            args.depth,
            state.blocking_constraints,
            args.solver_mode,
            totality_symbols,
            debug=bool(args.debug),
            dictionary=bool(args.dictionary),
        )
        if iter_record is not None:
            iter_record["found"] = bool(propagator.found)
            iter_record["unsat"] = bool(solve_result.unsatisfiable)
            iter_record["exceeded_depth"] = bool(propagator.exceeded_depth)

        if propagator.exceeded_depth:
            raise SystemExit("Search exceeded k-depth; aborting.")

        if not propagator.found:
            # clingo-style output reports the status once in the footer.
            if solve_result.unsatisfiable and state.valuation_index == 0 and not clingo_output:
                print("\nUNSATISFIABLE")
            state.exhausted = True
            break

        signature = valuation_signature(propagator.valuation)
        if signature in state.seen:
            block = valuation_block_constraint(propagator.valuation)
            if not block or block in state.blocking_constraints:
                if not clingo_output:
                    print("\nNo new blocking constraint for a repeated valuation; stopping to avoid loops.")
                break
            state.blocking_constraints.append(block)
            if trace_payload is not None:
                trace_payload["repeat_blocks"].append(
                    {
                        "iteration": iteration_index,
                        "blocker": block,
                        "valuation": list(propagator.valuation),
                    }
                )
            continue

        state.valuation_index += 1
        state.seen.add(signature)
        base_valuation = propagator.valuation
        completed_valuation = base_valuation
        bnm_atoms = set()
        completion_record = None
        if args.solver_mode == "bnm":
            if trace_payload is not None:
                completed_valuation, bnm_atoms, completion_record = apply_default_completion(
                    base_valuation,
                    all_paths,
                    depth=args.depth,
                    program_id=",".join(all_paths),
                    return_record=True,
                    totality_symbols=totality_symbols,
                )
            else:
                completed_valuation, bnm_atoms = apply_default_completion(
                    base_valuation,
                    all_paths,
                    depth=args.depth,
                    program_id=",".join(all_paths),
                    totality_symbols=totality_symbols,
                )

        tag_map = {}
        for atom in bnm_atoms:
            tag_map[atom] = "bnm"

        if clingo_output:
            filtered = filter_valuation_by_show(completed_valuation, show_filter)
        else:
            filtered = list(completed_valuation)
        filtered = [(atom, value) for atom, value in filtered if not _is_internal_atom(atom)]

        true_atoms = {atom for atom, value in completed_valuation if value == "1"}
        if args.mode == "all":
            # Legend markers must reflect displayed output: brave/cautious runs
            # never print per-model valuations, and clingo-style output only
            # tags atoms rendered as true.
            for atom, value in filtered:
                if value == "?":
                    state.legend_flags.add("?")
                if atom in tag_map and (not clingo_output or value == "1"):
                    state.legend_flags.add(tag_map[atom])
        if tag_map:
            for atom, value in completed_valuation:
                if value == "1" and atom in tag_map:
                    state.tag_map_for_summary[atom] = tag_map[atom]

        state.brave_union |= true_atoms
        if state.cautious_intersection is None:
            state.cautious_intersection = set(true_atoms)
        else:
            state.cautious_intersection &= true_atoms
        current_atoms = {atom for atom, _value in completed_valuation}
        if state.all_atoms is None:
            state.all_atoms = set(current_atoms)
        else:
            state.all_atoms |= current_atoms
        if trace_payload is not None and state.all_atoms is not None:
            trace_payload["atom_universe"] = sorted(state.all_atoms)

        block = valuation_block_constraint(base_valuation)
        if trace_payload is not None:
            branch_id = None
            assump_literals = []
            if completion_record is not None:
                branch_id = completion_record.get("branch_id")
                assump_literals = list(completion_record.get("assumption_literals", []))
            if not branch_id:
                branch_id = branch_profile_hash(base_valuation)
            trace_payload["branches"].append(
                {
                    "index": state.valuation_index,
                    "iteration": iteration_index,
                    "restart_strategy": strategy,
                    "branch_id": branch_id,
                    "decision_level": propagator.decision_level,
                    "decision_literals": list(propagator.decision_literals),
                    "dec_prefix_literals": [entry["literal"] for entry in propagator.decision_literals],
                    "base_valuation": list(base_valuation),
                    "assump_literals": assump_literals,
                    "completed_valuation": list(completed_valuation),
                    "model_count": None if completion_record is None else completion_record.get("model_count"),
                    "identity_completion": None
                    if completion_record is None
                    else completion_record.get("identity_completion"),
                    "completion_unsat_core_literals": []
                    if completion_record is None
                    else list(completion_record.get("unsat_core_literals", [])),
                    "completion_debug": completion_record,
                    "active_blockers_before": active_blockers,
                    "new_blocker": block,
                }
            )

        if clingo_output:
            if args.mode == "all":
                print(f"Answer: {state.valuation_index}")
                atoms = []
                for atom, value in filtered:
                    if value == "1":
                        if atom in tag_map:
                            atoms.append(format_atom(atom, tag_map, colorize))
                        else:
                            atoms.append(atom)
                    elif value == "?":
                        if colorize:
                            atoms.append("\033[90m?" + atom + "\033[0m")
                        else:
                            atoms.append("?" + atom)
                print(" ".join(atoms))
            elif args.mode in {"brave", "cautious"}:
                pass
        else:
            if args.mode == "all":
                print_valuation(
                    completed_valuation,
                    state.valuation_index,
                    args.depth,
                    strategy,
                    clingo_output,
                    tag_map,
                    colorize,
                )

        if block:
            if block not in state.blocking_constraints:
                state.blocking_constraints.append(block)
        else:
            if not clingo_output:
                print("\nNo defined literals to block this valuation; stopping.")
            break

        if args.models > 0 and state.valuation_index >= args.models:
            state.hit_limit = True
            break

    elapsed = time.perf_counter() - start_wall
    cpu_elapsed = time.process_time() - start_cpu
    if not state.exhausted:
        state.exhausted = not state.hit_limit
    if trace_payload is not None:
        trace_payload["final"] = {
            "solve_calls": state.solve_calls,
            "valuation_count": state.valuation_index,
            "exhausted": state.exhausted,
            "hit_limit": state.hit_limit,
            "elapsed_sec": elapsed,
            "blocking_constraints": list(state.blocking_constraints),
        }
        trace_path = _write_trace_payload(args.emit_bnm_trace, args.depth, trace_payload)
        if args.debug:
            print(f"[debug] wrote BNM trace: {trace_path}")

    if clingo_output:
        status = "SATISFIABLE" if state.valuation_index > 0 else "UNSATISFIABLE"
        print(status)
        models_suffix = "" if state.exhausted else "+"
        if args.mode in {"brave", "cautious"} and state.valuation_index > 0:
            # Bounds, displayed atoms, and the final count all use the
            # #show-filtered view so the summary is internally consistent.
            if args.mode == "brave":
                atoms = filter_summary_atoms(state.brave_union, state.all_atoms or set(), show_filter)
                shown_universe = filter_summary_atoms(
                    state.all_atoms or set(), state.all_atoms or set(), show_filter
                )
                low = len(atoms)
                high = len(shown_universe)
            else:
                atoms = filter_summary_atoms(
                    state.cautious_intersection or set(), state.all_atoms or set(), show_filter
                )
                low = 0
                high = len(atoms)
            print(f"Consequences [{low};{high}]")
            print(f"Answer: (Time: {elapsed:.3f}s)")
            if atoms:
                if state.tag_map_for_summary:
                    colored = []
                    for atom in atoms:
                        if atom in state.tag_map_for_summary:
                            state.legend_flags.add(state.tag_map_for_summary[atom])
                            colored.append(format_atom(atom, state.tag_map_for_summary, colorize))
                        else:
                            colored.append(atom)
                    print(" ".join(colored))
                else:
                    print(" ".join(atoms))
            print(f"\nModels       : {state.valuation_index}{models_suffix}")
            flag = "yes" if state.exhausted else "unknown"
            cons_suffix = "" if state.exhausted else "+"
            if args.mode == "brave":
                cons = len(atoms)
                print(f"  Brave      : {flag}")
            else:
                cons = len(atoms) if state.exhausted else 0
                print(f"  Cautious   : {flag}")
            print(f"Consequences : {cons}{cons_suffix}")
        else:
            print(f"Models       : {state.valuation_index}{models_suffix}")
        print(f"Calls        : {state.solve_calls}")
        print("Time         : {:.2f}s".format(elapsed))
        print("CPU Time     : {:.2f}s".format(cpu_elapsed))
    else:
        print("\nTime         : {:.2f}".format(elapsed) + "s")

    if not clingo_output and args.mode in {"brave", "cautious"} and (
        state.brave_union or state.cautious_intersection is not None
    ):
        if args.mode == "brave":
            atoms = state.brave_union
            label = "Brave consequences"
        else:
            atoms = state.cautious_intersection or set()
            label = "Cautious consequences"
        print(f"\n{label} (k={args.depth}):")
        if atoms:
            if state.tag_map_for_summary:
                colored = []
                for atom in sorted(atoms):
                    if atom in state.tag_map_for_summary:
                        state.legend_flags.add(state.tag_map_for_summary[atom])
                        colored.append(format_atom(atom, state.tag_map_for_summary, colorize))
                    else:
                        colored.append(atom)
                print(" ".join(colored))
            else:
                print(" ".join(sorted(atoms)))
        else:
            print("(none)")

    if state.legend_flags:
        parts = []
        if colorize:
            if "?" in state.legend_flags:
                parts.append("\033[90m?atom\033[0m = undefined")
            if "bnm" in state.legend_flags:
                parts.append("\033[34matom\033[0m = BNM-completed")
        else:
            if "?" in state.legend_flags:
                parts.append("?atom = undefined")
            if "bnm" in state.legend_flags:
                parts.append("[b]atom = BNM-completed")
        if parts:
            print("Legend: " + ", ".join(parts))

    return 0


def main(argv=None):
    return run(argv)
