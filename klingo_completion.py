import hashlib
import json
import os
import time
from functools import lru_cache
from pathlib import Path

import clingo
from clingo import ast as clingo_ast


def _is_strong_negation(atom_str):
    # Predicate names may start with a letter or an underscore.
    return atom_str.startswith("-") and len(atom_str) > 1 and (atom_str[1].isalpha() or atom_str[1] == "_")


def _complement_atom(atom_str):
    if _is_strong_negation(atom_str):
        return atom_str[1:]
    return "-" + atom_str


def _runtime_symbol_head_key(symbol):
    if symbol.type != clingo.SymbolType.Function:
        return None
    return (symbol.name, len(symbol.arguments), bool(symbol.positive))


def _literal_head_key(node):
    if node is None:
        return None

    literal = node
    if node.ast_type == clingo_ast.ASTType.ConditionalLiteral:
        literal = node.literal
    if literal.ast_type == clingo_ast.ASTType.Literal:
        if literal.sign != clingo_ast.Sign.NoSign:
            return None
        atom = literal.atom
    else:
        atom = literal

    if atom.ast_type != clingo_ast.ASTType.SymbolicAtom:
        return None
    sym = atom.symbol
    if sym.ast_type == clingo_ast.ASTType.Function:
        return (sym.name, len(sym.arguments), True)
    if sym.ast_type == clingo_ast.ASTType.UnaryOperation:
        if sym.operator_type == clingo_ast.UnaryOperator.Minus and sym.argument.ast_type == clingo_ast.ASTType.Function:
            fn = sym.argument
            return (fn.name, len(fn.arguments), False)
    return None


def _collect_head_literal_keys(paths):
    keys = set()

    def visit(node):
        if node.ast_type != clingo_ast.ASTType.Rule:
            return
        head = node.head
        if head.ast_type == clingo_ast.ASTType.Literal:
            key = _literal_head_key(head)
            if key is not None:
                keys.add(key)
            return
        if head.ast_type in {clingo_ast.ASTType.Disjunction, clingo_ast.ASTType.Aggregate}:
            for element in head.elements:
                key = _literal_head_key(element)
                if key is not None:
                    keys.add(key)
            return
        if head.ast_type == clingo_ast.ASTType.HeadAggregate:
            for element in head.elements:
                key = _literal_head_key(element.condition)
                if key is not None:
                    keys.add(key)

    clingo_ast.parse_files(paths, visit)
    return keys


class ClingoCompletionEngine:
    """
    Branch completion engine implementing supervaluational stable completion.
    For each depth-k branch valuation V over P + totality:
      - read V's decided literals as classical content over base atoms
        (the totality dictionary maps -u=1 to u=0 and -u=0 to u=1);
      - condition the stable models of the ORIGINAL program P on that content
        via clingo assumptions (the program itself is never modified);
      - presume, for each undecided atom, the value every compatible stable
        model agrees on (true in all -> 1, true in none -> 0, mixed -> ?);
      - no compatible model, or an impossible supposition -> identity.
    """

    def __init__(self, paths, debug_outdir=None, program_id=None):
        self._paths = list(paths)
        self._program_id = program_id or ",".join(self._paths)
        self._head_literal_keys = _collect_head_literal_keys(self._paths)
        self._debug_outdir = debug_outdir or os.environ.get("KLINGO_COMPLETION_DEBUG")
        self._debug_path = None
        if self._debug_outdir:
            out = Path(self._debug_outdir)
            out.mkdir(parents=True, exist_ok=True)
            self._debug_path = out / "completion_records.jsonl"
        self.last_debug_record = None

    def _profile_hash(self, valuation):
        pos = sorted([atom for atom, value in valuation if value == "1"])
        neg = sorted([atom for atom, value in valuation if value == "0"])
        payload = json.dumps({"pos": pos, "neg": neg}, sort_keys=True, separators=(",", ":"))
        return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:16], pos, neg

    def _emit_debug_record(self, record):
        self.last_debug_record = record
        if self._debug_path is None:
            return
        with self._debug_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True) + "\n")

    def _completion_control(self):
        control = clingo.Control(["0", "-Wno-atom-undefined"])
        for path in self._paths:
            control.load(path)
        control.ground([("base", [])])
        control.configuration.solve.models = 0
        symbol_by_atom = {str(atom.symbol): atom.symbol for atom in control.symbolic_atoms}
        return control, symbol_by_atom

    def complete_branch(self, valuation, *, depth=None, program_id=None, totality_symbols=None):
        branch_id, pos_profile, neg_profile = self._profile_hash(valuation)
        record = {
            "program_id": program_id or self._program_id,
            "depth": depth,
            "branch_id": branch_id,
            "semantics": "supervaluational",
            "profile_pos": pos_profile,
            "profile_neg": neg_profile,
            "fix_literals": [],
            "assumption_literals": [],
            "model_count": None,
            "unsat_core_literals": [],
            "unsupported_literals": [],
            "bad_assumptions": [],
            "elapsed_ms": 0.0,
            "identity_completion": False,
            "skipped_reason": None,
        }

        control, symbol_by_atom = self._completion_control()
        unsupported_literals = []
        for atom_name, symbol in symbol_by_atom.items():
            key = _runtime_symbol_head_key(symbol)
            if key not in self._head_literal_keys:
                unsupported_literals.append(atom_name)
        unsupported_set = set(unsupported_literals)
        record["unsupported_literals"] = sorted(unsupported_literals)

        bivalent = {str(symbol) for symbol in (totality_symbols or [])}

        # Classical content of the branch: for bivalent pairs the totality
        # dictionary folds -u onto its base atom (-u=1 <=> u=0); atoms outside
        # the totality universe carry no bivalence and condition on their own
        # stable-model membership.
        delta = {}
        incoherent = False
        for atom, value in valuation:
            if value not in {"1", "0"}:
                continue
            truth = value == "1"
            if _is_strong_negation(atom) and atom[1:] in bivalent:
                key, val = atom[1:], not truth
            else:
                key, val = atom, truth
            if key in delta and delta[key] != val:
                incoherent = True
                break
            delta[key] = val
        record["fix_literals"] = sorted(key if val else f"not {key}" for key, val in delta.items())
        record["bad_assumptions"] = sorted(
            (key if val else f"not {key}") for key, val in delta.items() if key in unsupported_set
        )

        if incoherent:
            record["identity_completion"] = True
            record["skipped_reason"] = "incoherent_branch_content"
            self._emit_debug_record(record)
            return valuation, set()

        undecided = [atom for atom, value in valuation if value == "?" and not _is_strong_negation(atom)]
        undecided_negs = [atom for atom, value in valuation if value == "?" and _is_strong_negation(atom)]
        if not undecided and not undecided_negs:
            record["identity_completion"] = True
            record["skipped_reason"] = "no_undecided_atoms"
            self._emit_debug_record(record)
            return valuation, set()

        assumptions = []
        assumption_lit_map = {}
        empty_reason = None
        for key, val in sorted(delta.items()):
            symbol = symbol_by_atom.get(key)
            if symbol is None:
                if val:
                    # The branch supposes true an atom no stable model of P can
                    # contain: the compatible-model family is empty.
                    empty_reason = f"incompatible_supposition:{key}"
                    break
                continue
            assumptions.append((symbol, val))
            record["assumption_literals"].append(key if val else f"not {key}")
            program_lit = control.symbolic_atoms[symbol].literal
            signed = program_lit if val else -program_lit
            assumption_lit_map[signed] = record["assumption_literals"][-1]

        if empty_reason:
            record["identity_completion"] = True
            record["skipped_reason"] = empty_reason
            self._emit_debug_record(record)
            return valuation, set()

        in_all = None
        in_some = set()
        model_count = 0
        solve_start = time.perf_counter()
        core_literals = []
        with control.solve(assumptions=assumptions, yield_=True) as handle:
            for model in handle:
                atoms = {str(symbol) for symbol in model.symbols(atoms=True)}
                in_all = set(atoms) if in_all is None else (in_all & atoms)
                in_some |= atoms
                model_count += 1
            solve_result = handle.get()
            if model_count == 0 and solve_result.unsatisfiable:
                core_literals = list(handle.core())
        record["elapsed_ms"] = round((time.perf_counter() - solve_start) * 1000.0, 4)
        record["model_count"] = model_count
        if core_literals:
            record["unsat_core_literals"] = [assumption_lit_map.get(lit, f"lit({lit})") for lit in core_literals]
        if model_count == 0:
            record["identity_completion"] = True
            record["skipped_reason"] = "no_compatible_stable_model"
            self._emit_debug_record(record)
            return valuation, set()

        index = {atom: idx for idx, (atom, _value) in enumerate(valuation)}
        updated = list(valuation)
        bnm_atoms = set()
        in_all = in_all or set()

        def presume(name, value):
            idx = index.get(name)
            if idx is not None and updated[idx][1] == "?":
                updated[idx] = (name, value)
                bnm_atoms.add(name)

        for atom in undecided:
            if atom in in_all:
                presume(atom, "1")
                # coherence: a true atom's strong complement holds in no model
                presume(_complement_atom(atom), "0")
            elif atom not in in_some:
                presume(atom, "0")
                if atom in bivalent:
                    presume(_complement_atom(atom), "1")
        # Strong-negated leftovers without a bivalent pair complete on their
        # own stable-model membership.
        for atom in undecided_negs:
            if atom[1:] in bivalent:
                continue
            if atom in in_all:
                presume(atom, "1")
            elif atom not in in_some:
                presume(atom, "0")

        record["identity_completion"] = (updated == list(valuation))
        self._emit_debug_record(record)
        return updated, bnm_atoms


@lru_cache(maxsize=32)
def _completion_engine_for_paths(paths_key):
    return ClingoCompletionEngine(list(paths_key))


def apply_default_completion(
    valuation, paths, *, depth=None, program_id=None, return_record=False, totality_symbols=None
):
    """
    Backward-compatible completion entrypoint used by klingo_engine.
    Delegates to ClingoCompletionEngine while reusing cached engines by path tuple.
    """
    paths_key = tuple(paths)
    engine = _completion_engine_for_paths(paths_key)
    completed, bnm_atoms = engine.complete_branch(
        valuation, depth=depth, program_id=program_id, totality_symbols=totality_symbols
    )
    if return_record:
        return completed, bnm_atoms, engine.last_debug_record
    return completed, bnm_atoms


__all__ = [
    "ClingoCompletionEngine",
    "apply_default_completion",
]
