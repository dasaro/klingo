# ABA example: assumptions, rules, and contraries.
#
# Assumptions: a, b, c
# Contraries: contrary(a, na), contrary(b, nb), contrary(c, nc)
# Rules:
#   na :- b.        (b attacks a)
#   nb :- c.        (c attacks b)
#   nc :- a.        (a attacks c)
#   p  :- a.        (claim p supported by a)
#   q  :- b.        (claim q supported by b)
#   r  :- c.        (claim r supported by c)
#
# With k-bounded reasoning, acceptance of p/q/r can be brave or cautious
# depending on which assumptions remain undefeated at depth k.

assump(a; b; c).
contrary(a, na).
contrary(b, nb).
contrary(c, nc).

na :- b.
nb :- c.
nc :- a.

p :- a.
q :- b.
r :- c.

# Show only claims and assumptions.
#show a/0.
#show b/0.
#show c/0.
#show p/0.
#show q/0.
#show r/0.
