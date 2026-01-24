% Test A: same rule as training but gated by h (k=0 undecided)
card(d1). card(d2). card(d3). card(d4).
red(d1). red(d4).
blue(d2). blue(d3).

1 { h; -h } 1.

flip(C) :- red(C), h.

#show flip/1.
#show red/1.
#show blue/1.
#show card/1.
