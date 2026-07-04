"""
Certified-schema learning for --bnm.

Pipeline (see --learn):
  1. flip gain: cautious consequences at a probe depth that depth 0 lacks;
  2. candidates: resolve the gained atom's defining rules pairwise on
     complementary bivalent body literals (p(t) vs -p(s)); the unifier
     eliminates the case-split atom and the remaining variables generalize
     the instance;
  3. certification: a candidate H :- B is kept iff P + Tot classically
     entails it (P + Tot + B + -H is unsatisfiable over all groundings);
  4. compilation: certified schemas are emitted as ab-guarded defaults
     (H :- B, not __ab_lN.). The fresh guard atom joins the totality
     universe, so the lemma never fires by mere propagation: its conclusion
     arrives as a depth-0 presumption of the completion, overridable by
     deeper derivation, and retractable by asserting the guard atom.
     Because the schema is certified, the classical limit is unchanged.
"""
from pathlib import Path

import clingo
from clingo import ast as clingo_ast

from klingo_totality import build_totality_universe, render_totality_rules

MAX_RESOLUTION_ROUNDS = 4


# ---------- rule extraction ----------
# literal = (positive: bool, name: str, args: tuple)
# term    = ("var", name) | ("const", symbol-string)

def _term(node):
    if node.ast_type == clingo_ast.ASTType.Variable:
        return ("var", node.name)
    if node.ast_type == clingo_ast.ASTType.SymbolicTerm:
        return ("const", str(node.symbol))
    raise ValueError("unsupported term")


def _atom(sym):
    if sym.ast_type == clingo_ast.ASTType.Function:
        return (True, sym.name, tuple(_term(a) for a in sym.arguments))
    if (sym.ast_type == clingo_ast.ASTType.UnaryOperation
            and sym.operator_type == clingo_ast.UnaryOperator.Minus
            and sym.argument.ast_type == clingo_ast.ASTType.Function):
        fn = sym.argument
        return (False, fn.name, tuple(_term(a) for a in fn.arguments))
    raise ValueError("unsupported atom")


def collect_definite_rules(paths):
    """Rules with a symbolic-literal head and a purely positive symbolic body
    (resolution inputs; NAF-bodied rules are skipped)."""
    rules = []

    def visit(stm):
        if stm.ast_type != clingo_ast.ASTType.Rule:
            return
        head = stm.head
        if (head.ast_type != clingo_ast.ASTType.Literal
                or head.atom.ast_type != clingo_ast.ASTType.SymbolicAtom):
            return
        try:
            h = _atom(head.atom.symbol)
            body = []
            for lit in stm.body:
                if (lit.ast_type != clingo_ast.ASTType.Literal
                        or lit.sign != clingo_ast.Sign.NoSign
                        or lit.atom.ast_type != clingo_ast.ASTType.SymbolicAtom):
                    return
                body.append(_atom(lit.atom.symbol))
            rules.append((h, tuple(body)))
        except ValueError:
            return

    clingo_ast.parse_files(paths, visit)
    return rules


# ---------- resolution ----------

def _rename(rule, suffix):
    def rn(term):
        return ("var", term[1] + suffix) if term[0] == "var" else term

    head, body = rule
    return ((head[0], head[1], tuple(rn(a) for a in head[2])),
            tuple((s, n, tuple(rn(a) for a in args)) for s, n, args in body))


def _unify(args1, args2):
    subst = {}

    def walk(term):
        while term[0] == "var" and term[1] in subst:
            term = subst[term[1]]
        return term

    for a, b in zip(args1, args2):
        a, b = walk(a), walk(b)
        if a == b:
            continue
        if a[0] == "var":
            subst[a[1]] = b
        elif b[0] == "var":
            subst[b[1]] = a
        else:
            return None
    return walk


def resolve(rule1, rule2):
    """All resolvents of rule1 and rule2 on complementary body literals."""
    out = []
    head1, body1 = rule1
    head2, body2 = _rename(rule2, "_R")
    for i, lit1 in enumerate(body1):
        for j, lit2 in enumerate(body2):
            if lit1[1] != lit2[1] or lit1[0] == lit2[0]:
                continue
            walk = _unify(lit1[2] + head1[2], lit2[2] + head2[2])
            if walk is None:
                continue
            body = [(s, n, tuple(walk(a) for a in args))
                    for k, (s, n, args) in enumerate(body1) if k != i]
            body += [(s, n, tuple(walk(a) for a in args))
                     for k, (s, n, args) in enumerate(body2) if k != j]
            head = (head1[0], head1[1], tuple(walk(a) for a in head1[2]))
            seen, dedup = set(), []
            for lit in body:
                if lit not in seen:
                    seen.add(lit)
                    dedup.append(lit)
            out.append((head, tuple(dedup)))
    return out


def body_unsatisfiable(rule):
    """Syntactic precheck: a body containing p(t) and -p(t) is classically
    unsatisfiable under coherence, so the certificate would be vacuous."""
    _, body = rule
    atoms = {(s, n, args) for s, n, args in body}
    return any((not s, n, args) in atoms for s, n, args in atoms)


def canonical(rule):
    """Alpha-variant canonical string: sort body, rename vars by traversal."""
    head, body = rule
    ordered = sorted(body, key=lambda lit: (lit[1], not lit[0], len(lit[2])))
    mapping = {}

    def rn(term):
        if term[0] != "var":
            return term
        if term[1] not in mapping:
            mapping[term[1]] = f"V{len(mapping)}"
        return ("var", mapping[term[1]])

    canon_head = (head[0], head[1], tuple(rn(a) for a in head[2]))
    canon_body = tuple((s, n, tuple(rn(a) for a in args)) for s, n, args in ordered)
    return str((canon_head, canon_body))


# ---------- rendering ----------

def lit_str(lit):
    sign, name, args = lit
    inner = f"{name}({', '.join(a[1] for a in args)})" if args else name
    return inner if sign else "-" + inner


def rule_str(rule, guard=None):
    head, body = rule
    parts = [lit_str(b) for b in body]
    if guard:
        parts.append(guard)
    return f"{lit_str(head)} :- {', '.join(parts)}." if parts else f"{lit_str(head)}."


# ---------- certification ----------

def _program_text(paths):
    lines = []
    for p in paths:
        for line in Path(p).read_text(encoding="utf-8", errors="ignore").splitlines():
            if line.strip().startswith(("#external", "#show")):
                continue
            lines.append(line)
    return "\n".join(lines)


def certify(rule, paths, totality_symbols):
    """P + Tot |= (B -> H) classically iff P + Tot + probe is UNSAT, where
    the probe demands a violated instance."""
    head, body = rule
    tot = "\n".join(render_totality_rules(totality_symbols))
    neg_head = lit_str((not head[0], head[1], head[2]))
    probe_body = ", ".join([lit_str(b) for b in body] + [neg_head])
    probe = f"__viol :- {probe_body}.\n:- not __viol.\n"
    control = clingo.Control(["1", "-Wno-atom-undefined"])
    control.add("base", [], _program_text(paths) + "\n" + tot + "\n" + probe)
    control.ground([("base", [])])
    return str(control.solve()) == "UNSAT"


# ---------- driver ----------

def learn_lemmas(paths, cautious_fn, out_path, probe_depths=(1, 2), report=print):
    """Run the full pipeline. `cautious_fn(k)` must return the cautious atom
    set (strings, [b]-tags stripped) of the --bnm run at depth k."""
    baseline = cautious_fn(0)
    report(f"cautious k=0 : {' '.join(sorted(baseline)) or '(none)'}")
    gain, gain_depth = set(), None
    for k in probe_depths:
        ck = cautious_fn(k)
        report(f"cautious k={k} : {' '.join(sorted(ck)) or '(none)'}")
        gain = {a for a in ck - baseline if not a.startswith("-")}
        if gain:
            gain_depth = k
            break
    report(f"flip gain    : {' '.join(sorted(gain)) or '(none)'}")
    if not gain:
        report("nothing to learn")
        return []

    rules = collect_definite_rules(paths)
    totality_symbols = build_totality_universe(paths)
    lemmas, seen_canon = [], set()
    for atom in sorted(gain):
        pred = atom.split("(")[0]
        defs = [r for r in rules if r[0][0] and r[0][1] == pred]
        if not defs:
            report(f"'{atom}': no definite rules to resolve, skipped")
            continue
        # Growth control: candidate bodies may exceed the defining rules by at
        # most one literal, and only lemmas STRICTLY SHORTER than every
        # defining rule are fed back into the resolution pool (the shrinking
        # direction is compilation; the growing direction is unrolling and
        # never terminates usefully).
        min_def_body = min(len(r[1]) for r in defs)
        max_body = max(len(r[1]) for r in defs) + 1
        pool = list(defs)
        certified = []
        for _round in range(MAX_RESOLUTION_ROUNDS):
            fresh = []
            for r1 in pool:
                for r2 in pool:
                    for cand in resolve(r1, r2):
                        if len(cand[1]) > max_body or body_unsatisfiable(cand):
                            continue
                        key = canonical(cand)
                        if key in seen_canon or cand in pool:
                            continue
                        seen_canon.add(key)
                        if certify(cand, paths, totality_symbols):
                            report(f"certified    : {rule_str(cand)}")
                            fresh.append(cand)
            if not fresh:
                break
            certified.extend(fresh)
            feed = [lem for lem in fresh if len(lem[1]) < min_def_body]
            if not feed:
                break
            feed.sort(key=lambda r: len(r[1]))
            pool.extend(feed)
        # keep only body-minimal certified lemmas
        for lemma in sorted(certified, key=lambda r: len(r[1])):
            if not any(k[0] == lemma[0] and set(k[1]) <= set(lemma[1]) for k in lemmas):
                lemmas.append(lemma)

    out = Path(out_path)
    lines = ["% Certified-schema lemma file (generated by klingo --learn)."]
    lines.append(f"% Source program: {', '.join(str(p) for p in paths)}")
    lines.append(f"% Flip gain at depth {gain_depth}: {', '.join(sorted(gain))}")
    lines.append("% Register: ab-guarded default. The guard atom joins the totality")
    lines.append("% universe, so each lemma's conclusion arrives as a depth-0 [b]")
    lines.append("% presumption (never by mere propagation), remains overridable by")
    lines.append("% deeper derivation, and is retractable by asserting the guard.")
    lines.append("% The schemas are classically certified, so the classical limit")
    lines.append("% of the source program is unchanged.")
    for idx, lemma in enumerate(lemmas, 1):
        lines.append(rule_str(lemma, guard=f"not __ab_l{idx}"))
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    report(f"wrote {len(lemmas)} lemma(s) to {out}")
    return lemmas


__all__ = [
    "certify",
    "collect_definite_rules",
    "learn_lemmas",
    "resolve",
]
