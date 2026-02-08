% Property: --3nd-star approaches plain clingo stable semantics as depth increases.
a :- not b.
b :- not a.

#show a/0.
#show b/0.
