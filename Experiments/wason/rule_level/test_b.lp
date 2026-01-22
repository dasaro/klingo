% Test B: colors inverted for relevance (flip blue)
card(e1). card(e2). card(e3). card(e4).
red(e1). red(e4).
blue(e2). blue(e3).

% ground truth: flip blue
flip(C) :- blue(C).

#show flip/1.
#show red/1.
#show blue/1.
#show card/1.
