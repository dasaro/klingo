#!/usr/bin/env python3
"""
Generate a width-m flip gadget for --bnm depth sweeps.

The atom `yes` is a case-enumeration tautology over m exclusive pairs
(x_i / nx_i), so it is classically entailed with refutation width m+1:
refuting `not yes` requires deciding all m pairs. Under --bnm its cautious
status follows the single-crossing trajectory

    T (k=0, presumed: yes holds in every stable model)
    UNDEC (1 <= k < ~m, while spurious not-yes branches survive)
    T (k >= ~m, once every branch derives or presumes yes)

The bait rules (`bait_j :- not yes.`) raise the solver activity of `yes`
so the decision heuristic actually opens the not-yes branches; without
them the suspension interval may not be observable in the enumerated
frontier.

Usage: gen_flip_gadget.py M [BAITS]
"""
import itertools
import sys


def generate(m, baits=5):
    lines = [f"% width-{m} flip gadget: yes is T at k=0, UNDEC while spurious"]
    lines.append(f"% not-yes branches survive, and T again from about k={m}.")
    for i in range(1, m + 1):
        lines.append(f"x{i} :- not nx{i}.  nx{i} :- not x{i}.  :- x{i}, nx{i}.")
    for bits in itertools.product([0, 1], repeat=m):
        body = ", ".join((f"x{i+1}" if b else f"nx{i+1}") for i, b in enumerate(bits))
        lines.append(f"yes :- {body}.")
    for j in range(1, baits + 1):
        lines.append(f"bait{j} :- not yes.")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit(__doc__.strip())
    m = int(sys.argv[1])
    baits = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    print(generate(m, baits), end="")
