import clingo
from clingo import ast as clingo_ast


def build_totality_universe_from_control(control):
    seen = {}
    for atom in control.symbolic_atoms:
        symbol = atom.symbol
        if symbol.type != clingo.SymbolType.Function:
            continue
        if symbol.name.startswith("#"):
            continue
        key = (symbol.name, tuple(symbol.arguments))
        if key not in seen:
            seen[key] = clingo.Function(symbol.name, list(symbol.arguments), True)
    return sorted(seen.values(), key=str)


def _ground_symbol_from_ast_symbol(node):
    if node.ast_type == clingo_ast.ASTType.Function:
        args = []
        for arg in node.arguments:
            sym = _ground_symbol_from_ast_term(arg)
            if sym is None:
                return None
            args.append(sym)
        return clingo.Function(node.name, args, True)
    if node.ast_type == clingo_ast.ASTType.UnaryOperation:
        if node.operator_type == clingo_ast.UnaryOperator.Minus and node.argument.ast_type == clingo_ast.ASTType.Function:
            base = node.argument
            args = []
            for arg in base.arguments:
                sym = _ground_symbol_from_ast_term(arg)
                if sym is None:
                    return None
                args.append(sym)
            return clingo.Function(base.name, args, False)
    return None


def _ground_symbol_from_ast_term(term):
    if term.ast_type == clingo_ast.ASTType.SymbolicTerm:
        return term.symbol
    if term.ast_type == clingo_ast.ASTType.Function:
        args = []
        for arg in term.arguments:
            sym = _ground_symbol_from_ast_term(arg)
            if sym is None:
                return None
            args.append(sym)
        return clingo.Function(term.name, args, True)
    return None


def _collect_ground_source_atoms(paths):
    symbols = set()

    def walk(node):
        yield node
        for key in node.keys():
            val = getattr(node, key)
            if isinstance(val, clingo_ast.AST):
                yield from walk(val)
            elif isinstance(val, (list, clingo_ast.ASTSequence)):
                for item in val:
                    if isinstance(item, clingo_ast.AST):
                        yield from walk(item)

    def visit(node):
        # Only harvest atoms from rules: display and meta directives (#show,
        # #external, ...) must never enlarge the totality universe.
        if node.ast_type != clingo_ast.ASTType.Rule:
            return
        for sub in walk(node):
            if sub.ast_type != clingo_ast.ASTType.SymbolicAtom:
                continue
            symbol = _ground_symbol_from_ast_symbol(sub.symbol)
            if symbol is None:
                continue
            if symbol.name.startswith("#"):
                continue
            symbols.add(clingo.Function(symbol.name, list(symbol.arguments), True))

    clingo_ast.parse_files(paths, visit)
    return symbols


def build_totality_universe(paths):
    control = clingo.Control(["-Wno-atom-undefined"])
    for path in paths:
        control.load(path)
    control.ground([("base", [])])
    from_grounding = set(build_totality_universe_from_control(control))
    from_source_ground = _collect_ground_source_atoms(paths)
    return sorted(from_grounding | from_source_ground, key=str)


def render_totality_rules(totality_symbols):
    lines = []
    for symbol in totality_symbols:
        pos = str(clingo.Function(symbol.name, list(symbol.arguments), True))
        neg = str(clingo.Function(symbol.name, list(symbol.arguments), False))
        lines.append(f"{{{pos}; {neg}}}.")
        lines.append(f":- {pos}, {neg}.")
        lines.append(f":- not {pos}, not {neg}.")
    return lines


def add_classical_totality_backend(control, totality_symbols):
    """
    Enforce classical totality without textual totality axioms.
    For each symbol a in the precomputed totality universe, inject:
      - support choice: {a; -a}.
      - at most one:   :- a, -a.
      - at least one:  :- not a, not -a.
    """
    if not totality_symbols:
        return

    with control.backend() as backend:
        for symbol in totality_symbols:
            pos = backend.add_atom(clingo.Function(symbol.name, list(symbol.arguments), True))
            neg = backend.add_atom(clingo.Function(symbol.name, list(symbol.arguments), False))
            # Local support for both truth values.
            backend.add_rule([pos, neg], [], choice=True)
            # Exactly one of a / -a must hold.
            backend.add_rule([], [pos, neg])
            backend.add_rule([], [-pos, -neg])


__all__ = [
    "add_classical_totality_backend",
    "build_totality_universe",
    "build_totality_universe_from_control",
    "render_totality_rules",
]
