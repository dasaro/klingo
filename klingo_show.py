from dataclasses import dataclass, field
from functools import lru_cache

import clingo
from clingo import ast as clingo_ast


@dataclass
class ShowTermRule:
    term_template: tuple
    body_patterns: list[tuple[str, tuple]] = field(default_factory=list)


@dataclass
class ShowFilter:
    has_directives: bool = False
    signatures: set[tuple[str, int, bool]] = field(default_factory=set)
    term_rules: list[ShowTermRule] = field(default_factory=list)
    unsupported_terms: int = 0

    @property
    def disabled(self):
        return self.unsupported_terms > 0


def _template_from_term(term):
    if term.ast_type == clingo_ast.ASTType.Variable:
        return ("var", term.name)
    if term.ast_type == clingo_ast.ASTType.SymbolicTerm:
        return ("sym", term.symbol)
    if term.ast_type == clingo_ast.ASTType.Function:
        return ("func", term.name, tuple(_template_from_term(arg) for arg in term.arguments), True)
    if term.ast_type == clingo_ast.ASTType.UnaryOperation:
        if term.operator_type == clingo_ast.UnaryOperator.Minus and term.argument.ast_type == clingo_ast.ASTType.Function:
            arg = term.argument
            return ("func", arg.name, tuple(_template_from_term(t) for t in arg.arguments), False)
    raise ValueError(f"Unsupported show-term component: {term.ast_type}")


def _pattern_from_literal(literal):
    if literal.ast_type != clingo_ast.ASTType.Literal:
        raise ValueError("ShowTerm body contains non-literal entry.")
    sign = literal.sign
    if sign == clingo_ast.Sign.NoSign:
        sign_label = "pos"
    elif sign == clingo_ast.Sign.Negation:
        sign_label = "not"
    elif sign == clingo_ast.Sign.DoubleNegation:
        sign_label = "pos"
    else:
        raise ValueError("Unsupported literal sign in show-term body.")

    atom = literal.atom
    if atom.ast_type != clingo_ast.ASTType.SymbolicAtom:
        raise ValueError("ShowTerm body contains non-symbolic atom.")
    return sign_label, _template_from_term(atom.symbol)


def extract_show_filter(paths):
    show_filter = ShowFilter()

    def visit(node):
        if node.ast_type == clingo_ast.ASTType.ShowSignature:
            show_filter.has_directives = True
            show_filter.signatures.add((node.name, int(node.arity), bool(node.positive)))
            return
        if node.ast_type != clingo_ast.ASTType.ShowTerm:
            return
        show_filter.has_directives = True
        try:
            term_template = _template_from_term(node.term)
            body_patterns = [_pattern_from_literal(lit) for lit in node.body]
            show_filter.term_rules.append(ShowTermRule(term_template=term_template, body_patterns=body_patterns))
        except ValueError:
            # Disable custom filtering when directives are unsupported, so output
            # is not silently wrong.
            show_filter.unsupported_terms += 1

    clingo_ast.parse_files(paths, visit)
    return show_filter


def parse_show_signatures(paths):
    # Backward-compatible helper for callers expecting signature pairs.
    show_filter = extract_show_filter(paths)
    signatures = {(name, arity) for name, arity, _positive in show_filter.signatures}
    for rule in show_filter.term_rules:
        template = rule.term_template
        if template[0] == "func":
            _, name, args, _positive = template
            signatures.add((name, len(args)))
    return signatures


@lru_cache(maxsize=16384)
def _parse_atom_symbol(atom_str):
    return clingo.parse_term(atom_str)


def _unify_template_with_symbol(template, symbol, subst):
    kind = template[0]
    if kind == "var":
        var_name = template[1]
        bound = subst.get(var_name)
        if bound is None:
            subst[var_name] = symbol
            return subst
        return subst if bound == symbol else None
    if kind == "sym":
        return subst if template[1] == symbol else None
    if kind == "func":
        if symbol.type != clingo.SymbolType.Function:
            return None
        _, name, arg_templates, positive = template
        if symbol.name != name or bool(symbol.positive) != bool(positive):
            return None
        if len(symbol.arguments) != len(arg_templates):
            return None
        for sub_template, sub_symbol in zip(arg_templates, symbol.arguments):
            subst = _unify_template_with_symbol(sub_template, sub_symbol, subst)
            if subst is None:
                return None
        return subst
    return None


def _instantiate_template(template, subst):
    kind = template[0]
    if kind == "var":
        return subst.get(template[1])
    if kind == "sym":
        return template[1]
    if kind == "func":
        _, name, arg_templates, positive = template
        args = []
        for arg_template in arg_templates:
            arg_symbol = _instantiate_template(arg_template, subst)
            if arg_symbol is None:
                return None
            args.append(arg_symbol)
        return clingo.Function(name, args, positive)
    return None


def _eval_show_rule(rule, true_symbols):
    substitutions = [dict()]
    for sign, pattern_template in rule.body_patterns:
        if sign == "pos":
            next_subst = []
            for subst in substitutions:
                for true_symbol in true_symbols:
                    candidate = _unify_template_with_symbol(pattern_template, true_symbol, dict(subst))
                    if candidate is not None:
                        next_subst.append(candidate)
            substitutions = next_subst
            if not substitutions:
                break
            continue

        # "not": keep substitutions for which no true atom matches.
        kept = []
        for subst in substitutions:
            matched = False
            for true_symbol in true_symbols:
                candidate = _unify_template_with_symbol(pattern_template, true_symbol, dict(subst))
                if candidate is not None:
                    matched = True
                    break
            if not matched:
                kept.append(subst)
        substitutions = kept
        if not substitutions:
            break

    shown = set()
    for subst in substitutions:
        symbol = _instantiate_template(rule.term_template, subst)
        if symbol is not None and symbol.type == clingo.SymbolType.Function:
            shown.add(str(symbol))
    return shown


def filter_valuation_by_show(valuation, show_filter):
    if not show_filter or not show_filter.has_directives or show_filter.disabled:
        return list(valuation)

    shown_atoms = set()
    true_symbols = []
    for atom, value in valuation:
        try:
            symbol = _parse_atom_symbol(atom)
        except RuntimeError:
            continue
        if symbol.type != clingo.SymbolType.Function:
            continue
        if (symbol.name, len(symbol.arguments), bool(symbol.positive)) in show_filter.signatures:
            shown_atoms.add(atom)
        if value == "1":
            true_symbols.append(symbol)

    for rule in show_filter.term_rules:
        shown_atoms |= _eval_show_rule(rule, true_symbols)

    return [(atom, value) for atom, value in valuation if atom in shown_atoms]


def atom_signature(atom_str):
    try:
        symbol = _parse_atom_symbol(atom_str)
    except RuntimeError:
        if "(" not in atom_str:
            return atom_str, 0
        name, rest = atom_str.split("(", 1)
        args = rest.rsplit(")", 1)[0]
        if not args.strip():
            return name, 0
        # Count only top-level commas so nested terms keep their real arity.
        depth = 0
        arity = 1
        for char in args:
            if char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
            elif char == "," and depth == 0:
                arity += 1
        return name, arity
    if symbol.type != clingo.SymbolType.Function:
        return str(symbol), 0
    return symbol.name, len(symbol.arguments)


__all__ = [
    "ShowFilter",
    "ShowTermRule",
    "atom_signature",
    "extract_show_filter",
    "filter_valuation_by_show",
    "parse_show_signatures",
]
