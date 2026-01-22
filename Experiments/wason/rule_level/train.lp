% Train: learn rule "flip red cards"
card(c1). card(c2). card(c3). card(c4).
red(c1). red(c3).
blue(c2). blue(c4).

% rule generating flips (train-side)
flip(C) :- red(C).

#show flip/1.
#show red/1.
#show blue/1.
#show card/1.
