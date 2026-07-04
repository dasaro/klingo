def truth_value_to_string(val):
    if val is True:
        return "1"
    if val is False:
        return "0"
    return "?"


def format_atom(atom, tag_map, colorize):
    if atom not in tag_map:
        return atom
    tag = tag_map[atom]
    if colorize:
        color = {
            "bnm": "\033[34m",
        }[tag]
        return f"{color}{atom}\033[0m"
    prefix = {
        "bnm": "[b]",
    }[tag]
    return f"{prefix}{atom}"


def print_valuation(valuation, idx, depth, strategy, clingo_output, tag_map=None, colorize=False):
    bot_atoms = 0
    tot_atoms = 0
    tag_map = tag_map or {}
    print(f"\nValuation {idx} (k={depth}, restart={strategy}):")
    if not clingo_output:
        for atom, value in valuation:
            if value == "?":
                bot_atoms += 1
            tot_atoms += 1
            if atom in tag_map:
                print(f"V({format_atom(atom, tag_map, colorize)}) = {value}")
            else:
                print(f"V({atom}) = {value}")
    else:
        for atom, value in valuation:
            if value == "1":
                if atom in tag_map:
                    print(format_atom(atom, tag_map, colorize), end=" ")
                else:
                    print(atom, end=" ")
            elif value == "?":
                print("?" + atom, end=" ")
            if value == "?":
                bot_atoms += 1
            tot_atoms += 1
        print()

    print("\n" + str(depth) + "-DEPTH SATISFIABLE")
    print("\nAtoms        : " + str(tot_atoms))
    print("Bottoms      : " + str(bot_atoms))
