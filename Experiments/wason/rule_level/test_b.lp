% Test B: flips blue (heuristic red rule misleads)
card(e1). card(e2). card(e3). card(e4).
red(e1). red(e4).
blue(e2). blue(e3).

flip(C) :- blue(C).

#show flip/1.
#show red/1.
#show blue/1.
#show card/1.
