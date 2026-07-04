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
    lines.append(provenance_line([list(paths)]))
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    report(f"wrote {len(lemmas)} lemma(s) to {out}")
    return lemmas


# ====================================================================
# ILASP bridge (--ilasp): inductive generation with certification-routed
# CEGIS refinement over sampled contexts.
# ====================================================================

import random
import re
import shutil
import subprocess
import tempfile

ILASP_BINARY = "ILASP"
CEGIS_ROUNDS = 5
CEGIS_SAMPLES = 60
CEGIS_INDIVIDUALS = ("i1", "i2", "i3")

_STRONG_NEG_RE = re.compile(r"(?<![\w\)])-(?=[a-z_])")


def _bridge_text(text):
    """Rewrite strong negation -p(...) to the bridge predicate np(...) so the
    ILASP task stays classical-negation-free. Arithmetic minus (preceded by a
    word character or ')') is left alone."""
    return _STRONG_NEG_RE.sub("n", text)


def _unbridge_lit(lit, bridged_preds):
    positive, name, args = lit
    if positive and name in bridged_preds:
        return (False, name[1:], args)
    return lit


def _expand_ground_terms(node):
    """Ground term -> list of ("const", text) alternatives (pools expand);
    None if the term is non-ground or unsupported."""
    if node.ast_type == clingo_ast.ASTType.SymbolicTerm:
        return [("const", str(node.symbol))]
    if node.ast_type == clingo_ast.ASTType.Pool:
        out = []
        for arg in node.arguments:
            sub = _expand_ground_terms(arg)
            if sub is None:
                return None
            out.extend(sub)
        return out
    return None


def dissect_instance(path):
    """Split an instance into (bridged rule texts, bridged ground fact
    literals). Pooled facts (p(a;b;c).) are expanded; #show/#external
    directives are skipped -- externals model open questions, which contexts
    express by omission."""
    import itertools

    rules, facts = [], []

    def fact_atoms(sym):
        positive = True
        if (sym.ast_type == clingo_ast.ASTType.UnaryOperation
                and sym.operator_type == clingo_ast.UnaryOperator.Minus):
            positive = False
            sym = sym.argument
        if sym.ast_type == clingo_ast.ASTType.Pool:
            # symbol-level pool: child(anne;martha;jane) == Pool of atoms
            expanded = []
            for alternative in sym.arguments:
                sub = fact_atoms(alternative)
                if sub is None:
                    return None
                if not positive:
                    sub = [(True, "n" + n if not n.startswith("n") else n, a)
                           for _p, n, a in sub]
                expanded.extend(sub)
            return expanded
        if sym.ast_type != clingo_ast.ASTType.Function:
            return None
        expansions = []
        for arg in sym.arguments:
            alt = _expand_ground_terms(arg)
            if alt is None:
                return None
            expansions.append(alt)
        name = sym.name if positive else "n" + sym.name
        return [(True, name, combo) for combo in itertools.product(*expansions)] if expansions \
            else [(True, name, ())]

    def visit(stm):
        if stm.ast_type != clingo_ast.ASTType.Rule:
            return
        head = stm.head
        if (not stm.body
                and head.ast_type == clingo_ast.ASTType.Literal
                and head.atom.ast_type == clingo_ast.ASTType.SymbolicAtom):
            expanded = fact_atoms(head.atom.symbol)
            if expanded is not None:
                facts.extend(expanded)
                return
        rules.append(_bridge_text(str(stm)))

    clingo_ast.parse_files([path], visit)
    return rules, facts


def _collect_body_atoms(paths):
    """Head predicate -> set of (bridged body predicate, arity), tolerant of
    NAF bodies (used for dependency-cone bias generation)."""
    cone = {}

    def visit(stm):
        if stm.ast_type != clingo_ast.ASTType.Rule or not stm.body:
            return
        head = stm.head
        if (head.ast_type != clingo_ast.ASTType.Literal
                or head.atom.ast_type != clingo_ast.ASTType.SymbolicAtom):
            return
        try:
            h = _atom(head.atom.symbol)
        except ValueError:
            return
        hname = h[1] if h[0] else "n" + h[1]
        bucket = cone.setdefault(hname, set())
        for lit in stm.body:
            if (lit.ast_type != clingo_ast.ASTType.Literal
                    or lit.atom.ast_type != clingo_ast.ASTType.SymbolicAtom):
                continue
            try:
                b = _atom(lit.atom.symbol)
            except ValueError:
                continue
            bucket.add((b[1] if b[0] else "n" + b[1], len(b[2])))

    clingo_ast.parse_files(paths, visit)
    return cone


def _cone_bias(cone, target, max_def_body):
    preds, frontier = set(), {target}
    while frontier:
        pred = frontier.pop()
        for body_pred, arity in cone.get(pred, ()):
            if body_pred != target and (body_pred, arity) not in preds:
                preds.add((body_pred, arity))
                frontier.add(body_pred)
    lines = [f"#modeh({target})."]
    for name, arity in sorted(preds):
        vars_ = ", ".join("var(p)" for _ in range(arity)) if arity else ""
        atom = f"{name}({vars_})" if arity else name
        lines.append(f"#modeb(2, {atom}, (positive)).")
    lines.append("#maxv(3).")
    return lines, preds, max_def_body + 1


def _ctx_text(facts):
    return " ".join(lit_str(lit) + "." for lit in sorted(facts))


def _parse_learned_rules(output, bridged_preds):
    rules = []
    for line in output.splitlines():
        line = line.strip()
        if not line or line.startswith("%") or line == "UNSATISFIABLE":
            continue
        if line.startswith(":-"):
            continue  # learned constraints are not lemma material
        body_txt = ""
        head_txt = line.rstrip(".")
        if ":-" in line:
            head_txt, body_txt = line.rstrip(".").split(":-", 1)

        def parse_atom(text):
            text = text.strip()
            if "(" in text:
                name, rest = text.split("(", 1)
                args = tuple(
                    ("var", a.strip()) if a.strip()[0].isupper() else ("const", a.strip())
                    for a in rest.rsplit(")", 1)[0].split(",")
                )
            else:
                name, args = text, ()
            return _unbridge_lit((True, name.strip(), args), bridged_preds)

        head = parse_atom(head_txt)
        # ILASP separates body literals with ';' (commas only inside argument lists)
        body = tuple(parse_atom(b) for b in body_txt.split(";") if b.strip())
        rules.append((head, body))
    return rules


def _entailed_in_context(atom_lit, rule_texts_orig, ctx_facts, bridged_preds):
    """Classical oracle: does P_ctx + Tot entail the atom? Returns None for a
    classically inconsistent context (which would entail everything
    vacuously and must not become an example)."""
    orig_facts = [_unbridge_lit(f, bridged_preds) for f in ctx_facts]
    program = "\n".join(rule_texts_orig + [lit_str(f) + "." for f in orig_facts])
    with tempfile.NamedTemporaryFile("w", suffix=".lp", delete=False) as handle:
        handle.write(program)
        tmp_path = handle.name
    try:
        tot = build_totality_universe([tmp_path])
        sat_probe = clingo.Control(["1", "-Wno-atom-undefined"])
        sat_probe.add("base", [], program + "\n" + "\n".join(render_totality_rules(tot)))
        sat_probe.ground([("base", [])])
        if str(sat_probe.solve()) == "UNSAT":
            return None
        return certify((atom_lit, ()), [tmp_path], tot)
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def _predicted_in_context(atom_name, background_bridged, hypothesis_texts, ctx_facts):
    """Does the learned program cautiously conclude the atom in this context?"""
    program = "\n".join(background_bridged + hypothesis_texts) + "\n" + _ctx_text(ctx_facts)
    control = clingo.Control(["0", "-Wno-atom-undefined"])
    control.add("base", [], program)
    control.ground([("base", [])])
    seen = {"any": False, "cautious": True}

    def on_model(model):
        seen["any"] = True
        if not any(str(sym) == atom_name for sym in model.symbols(atoms=True)):
            seen["cautious"] = False

    control.solve(on_model=on_model)
    return seen["any"] and seen["cautious"]


def _sample_context(rng, unary_preds, binary_preds):
    facts = []
    for name, _arity in binary_preds:
        for a in CEGIS_INDIVIDUALS:
            for b in CEGIS_INDIVIDUALS:
                if a != b and rng.random() < 0.35:
                    facts.append((True, name, (("const", a), ("const", b))))
    # Complementary unary pairs (p / np, i.e. p / -p in the original
    # vocabulary) are sampled coherently: each individual gets the positive
    # phase, the negative phase, or stays unknown -- never both.
    names = {n for n, _a in unary_preds}
    paired = {n for n in names if "n" + n in names}
    handled = paired | {"n" + n for n in paired}
    for base in sorted(paired):
        for a in CEGIS_INDIVIDUALS:
            roll = rng.random()
            if roll < 0.35:
                facts.append((True, base, (("const", a),)))
            elif roll < 0.70:
                facts.append((True, "n" + base, (("const", a),)))
    for name, _arity in unary_preds:
        if name in handled:
            continue
        for a in CEGIS_INDIVIDUALS:
            if rng.random() < 0.4:
                facts.append((True, name, (("const", a),)))
    return facts


def ilasp_learn(instances, cautious_fn, out_path, probe_depths=(1, 2),
                report=print, seed=0):
    """ILASP-backed learning. `instances` is a list of path-lists (one list
    per training instance); `cautious_fn(paths, k)` is the engine's cautious
    oracle. Gains become context-dependent examples, ILASP proposes, a
    property-based CEGIS loop against the classical oracle refines, and
    certified survivors are compiled as ab-guarded defaults."""
    if shutil.which(ILASP_BINARY) is None:
        raise SystemExit(f"--ilasp requires the {ILASP_BINARY} binary on PATH (see ilasp.com).")

    # -- per-instance flip gains -------------------------------------------
    gains, contexts = [], []
    background_bridged, rule_texts_orig = None, None
    for paths in instances:
        rules_b, facts_b = dissect_instance(paths[0])
        for extra in paths[1:]:
            extra_rules, extra_facts = dissect_instance(extra)
            rules_b += extra_rules
            facts_b += extra_facts
        if background_bridged is None:
            background_bridged = rules_b
            rule_texts_orig = []

            def collect_orig(stm):
                if stm.ast_type == clingo_ast.ASTType.Rule and stm.body:
                    rule_texts_orig.append(str(stm))

            clingo_ast.parse_files([paths[0]], collect_orig)
        contexts.append(facts_b)
        baseline = cautious_fn(paths, 0)
        gain = set()
        for k in probe_depths:
            gain = {a for a in cautious_fn(paths, k) - baseline if not a.startswith("-")}
            if gain:
                break
        gains.append(gain)
        report(f"instance {Path(paths[0]).name}: gain = {' '.join(sorted(gain)) or '(none)'}")

    target_atoms = sorted({a for g in gains for a in g})
    if not target_atoms:
        report("no flip gain across instances; nothing to learn")
        return []
    target = target_atoms[0].split("(")[0]
    if len({a.split("(")[0] for a in target_atoms}) > 1:
        report(f"multiple gained predicates; learning the first: {target}")

    # Bridge predicates are those _bridge_text introduced: predicates that
    # occur strong-negated anywhere in the original instance sources.
    source_text = "\n".join(
        Path(p).read_text(encoding="utf-8", errors="ignore")
        for paths in instances for p in paths
    )
    strong = set(re.findall(r"(?<![\w\)])-([a-z_]\w*)", source_text))
    bridged_preds = {"n" + s for s in strong}

    cone = _collect_body_atoms([instances[0][0]])
    defs_len = [len(r[1]) for r in collect_definite_rules([instances[0][0]])
                if r[0][1] == target] or [3]
    bias_lines, cone_preds, max_len = _cone_bias(cone, target, max(defs_len))
    unary = [(n, a) for n, a in cone_preds if a == 1]
    binary = [(n, a) for n, a in cone_preds if a == 2]

    # -- assemble base examples --------------------------------------------
    example_lines = []
    for idx, (gain, ctx) in enumerate(zip(gains, contexts)):
        ctx_txt = _ctx_text(ctx)
        if target_atoms[0] in {a for a in gain} or any(a.split("(")[0] == target for a in gain):
            example_lines.append(f"#neg(g{idx}, {{}}, {{{target}}}, {{ {ctx_txt} }}).")
            example_lines.append(f"#pos(s{idx}, {{}}, {{}}, {{ {ctx_txt} }}).")
        else:
            example_lines.append(f"#pos(o{idx}, {{}}, {{{target}}}, {{ {ctx_txt} }}).")

    rng = random.Random(seed)
    lemmas = []
    for rnd in range(1, CEGIS_ROUNDS + 1):
        task = "\n".join(background_bridged + bias_lines + example_lines)
        output = None
        for attempt_len in (max_len, max_len + 1):
            with tempfile.NamedTemporaryFile("w", suffix=".las", delete=False) as handle:
                handle.write(task)
                task_path = handle.name
            try:
                proc = subprocess.run(
                    [ILASP_BINARY, "--version=4", f"-ml={attempt_len}", task_path],
                    capture_output=True, text=True, timeout=300)
            finally:
                Path(task_path).unlink(missing_ok=True)
            output = proc.stdout
            if proc.returncode != 0 or (not output.strip() and proc.stderr.strip()):
                detail = (proc.stderr or proc.stdout).strip().splitlines()
                raise SystemExit(f"ILASP failed: {detail[0] if detail else 'no output'}")
            if "UNSATISFIABLE" not in output:
                break
            report(f"[round {rnd}] unsatisfiable at -ml={attempt_len}; "
                   + ("retrying with a longer rule budget" if attempt_len == max_len else "giving up"))
        if "UNSATISFIABLE" in output:
            debug_path = Path(out_path).with_suffix(".failed.las")
            debug_path.write_text(task, encoding="utf-8")
            report(f"final task preserved at {debug_path}")
            return []
        hypothesis = _parse_learned_rules(output, bridged_preds)
        if not hypothesis:
            raise SystemExit(
                "ILASP returned no parsable hypothesis; raw output head: "
                + " / ".join(output.strip().splitlines()[:3])
            )
        hyp_bridged = [_bridge_text(rule_str(r)) for r in hypothesis]
        report(f"[round {rnd}] hypothesis: " + " | ".join(rule_str(r) for r in hypothesis))

        # property-based CEGIS: compare prediction vs classical oracle
        discrepancies = 0
        for _ in range(CEGIS_SAMPLES):
            ctx = _sample_context(rng, unary, binary)
            predicted = _predicted_in_context(target, background_bridged, hyp_bridged, ctx)
            entailed = _entailed_in_context((True, target, ()), rule_texts_orig, ctx, bridged_preds)
            if entailed is None:
                continue  # classically inconsistent context: no example value
            if predicted and not entailed:
                example_lines.append(f"#pos(c{rnd}_{discrepancies}, {{}}, {{{target}}}, {{ {_ctx_text(ctx)} }}).")
                discrepancies += 1
            elif entailed and not predicted:
                example_lines.append(f"#neg(d{rnd}_{discrepancies}, {{}}, {{{target}}}, {{ {_ctx_text(ctx)} }}).")
                example_lines.append(f"#pos(e{rnd}_{discrepancies}, {{}}, {{}}, {{ {_ctx_text(ctx)} }}).")
                discrepancies += 1
            if discrepancies >= 3:
                break
        if discrepancies:
            report(f"[round {rnd}] {discrepancies} counterexample context(s) found; refining")
            continue
        report(f"[round {rnd}] no counterexamples in {CEGIS_SAMPLES} sampled contexts")
        lemmas = hypothesis
        break

    if not lemmas:
        report("CEGIS budget exhausted without a stable hypothesis")
        return []

    # -- emit (same ab-guarded register as --learn) -------------------------
    out = Path(out_path)
    lines = ["% Certified-schema lemma file (generated by klingo --ilasp)."]
    lines.append(f"% Training instances: {', '.join(Path(p[0]).name for p in instances)}")
    lines.append(f"% Hypothesis stable after property-based CEGIS ({CEGIS_SAMPLES} contexts/round, seed {seed}).")
    lines.append("% Register: ab-guarded default (depth-0 [b] presumption, overridable")
    lines.append("% by deeper derivation, retractable via the guard atom).")
    for idx, lemma in enumerate(lemmas, 1):
        lines.append(rule_str(lemma, guard=f"not __ab_i{idx}"))
    # Provenance for --gate-lemmas: the instances whose gain licensed the
    # hypothesis define its syntactic trust region.
    gain_instances = [paths for paths, g in zip(instances, gains) if g]
    lines.append(provenance_line(gain_instances or instances))
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    report(f"wrote {len(lemmas)} lemma(s) to {out}")
    return lemmas


# ====================================================================
# Familiarity gate (--gate-lemmas): a syntactic trust region for compiled
# lemmas, measured by Weisfeiler-Leman label histograms (name-blind
# "Hamming distance up to constant renaming") against the lemma file's
# provenance instances.
# ====================================================================

import json

WL_ROUNDS = 2
GATE_SLACK = 1.5
GATE_FALLBACK_TAU = 0.25
PROVENANCE_PREFIX = "%__gate_provenance: "


def wl_histogram_paths(paths):
    """Name-blind structural signature of an instance (facts of all files):
    2-round WL refinement over the constant graph, plus edge-label counts."""
    facts = []
    for path in paths:
        _rules, instance_facts = dissect_instance(str(path))
        facts.extend(instance_facts)
    nodes, unary, edges = set(), {}, []
    for _pos, name, args in facts:
        consts = [a[1] for a in args]
        nodes.update(consts)
        if len(consts) == 1:
            unary.setdefault(consts[0], []).append(name)
        elif len(consts) == 2:
            edges.append((name, consts[0], consts[1]))
    label = {n: "|".join(sorted(unary.get(n, ["_"]))) for n in nodes}
    for _ in range(WL_ROUNDS):
        label = {
            n: label[n]
            + "(" + ",".join(sorted(f"{e}>{label[b]}" for e, a, b in edges if a == n))
            + ";" + ",".join(sorted(f"{e}<{label[a]}" for e, a, b in edges if b == n))
            + ")"
            for n in nodes
        }
    hist = {}
    for value in label.values():
        hist[value] = hist.get(value, 0) + 1
    for e, _a, _b in edges:
        key = f"edge:{e}"
        hist[key] = hist.get(key, 0) + 1
    return hist


def wl_distance(h1, h2):
    total = sum(h1.values()) + sum(h2.values())
    if total == 0:
        return 0.0
    keys = set(h1) | set(h2)
    diff = sum(abs(h1.get(k, 0) - h2.get(k, 0)) for k in keys)
    return diff / total


def gate_threshold(hists):
    """Corpus spread: largest nearest-neighbour distance inside the
    provenance set, widened by a slack factor; a fixed fallback for
    single-instance provenance."""
    if len(hists) < 2:
        return GATE_FALLBACK_TAU
    spread = max(
        min(wl_distance(h, other) for j, other in enumerate(hists) if j != i)
        for i, h in enumerate(hists)
    )
    return min(1.0, spread * GATE_SLACK) or GATE_FALLBACK_TAU


def provenance_line(instance_path_lists):
    hists = [wl_histogram_paths(paths) for paths in instance_path_lists]
    payload = {"tau": gate_threshold(hists), "histograms": hists}
    return PROVENANCE_PREFIX + json.dumps(payload, sort_keys=True)


def gate_guard_file(lemma_path, instance_paths):
    """Decide whether the compiled bias applies to this instance. Returns
    (info message, guard-file path or None). When the instance is
    unfamiliar, the guard file asserts every __ab guard atom of the lemma
    file, disabling the lemmas for this run."""
    text = Path(lemma_path).read_text(encoding="utf-8", errors="ignore")
    payload = None
    for line in text.splitlines():
        if line.startswith(PROVENANCE_PREFIX):
            payload = json.loads(line[len(PROVENANCE_PREFIX):])
            break
    if payload is None:
        return ("lemma file has no gate provenance; lemmas applied ungated", None)
    instance_hist = wl_histogram_paths(instance_paths)
    dist = min(wl_distance(instance_hist, h) for h in payload["histograms"])
    tau = payload["tau"]
    if dist <= tau:
        return (f"familiarity d={dist:.3f} <= tau={tau:.3f}; compiled bias applied", None)
    guards = sorted(set(re.findall(r"__ab_\w+", text)))
    if not guards:
        return (f"familiarity d={dist:.3f} > tau={tau:.3f}, but lemmas carry no guards", None)
    with tempfile.NamedTemporaryFile(
            "w", suffix=".lp", prefix="klingo_gate_", delete=False) as handle:
        handle.write(f"% familiarity gate: d={dist:.3f} > tau={tau:.3f}\n")
        handle.writelines(f"{g}.\n" for g in guards)
        guard_path = handle.name
    return (f"familiarity d={dist:.3f} > tau={tau:.3f}; compiled bias disabled", guard_path)


__all__ = [
    "certify",
    "collect_definite_rules",
    "gate_guard_file",
    "ilasp_learn",
    "learn_lemmas",
    "resolve",
    "wl_distance",
    "wl_histogram_paths",
]
